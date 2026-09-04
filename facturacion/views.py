# facturacion/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q, F, Case, When, DecimalField, Subquery, OuterRef, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from .models import Environment, Factura, EntidadResponsable, TipoERP, EventoCartera, ImportLog
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import io
from .services import importar_excel_cartera, importar_eventos_pae, construir_dataframe_exportacion_eas
import base64
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
# precheque function no usado en vista principal (la lógica ahora se hace dentro del importador)

def generar_codigo_log(tipo):
    hoy = timezone.localdate()
    contador = ImportLog.objects.filter(tipo=tipo, creado_en__date=hoy).count() + 1
    fecha = hoy.strftime('%Y%m%d')
    return f"{tipo}-LOG-{contador:03d}-{fecha}"


def registrar_import_log(tipo, resumen, descripcion='', detalles=None):
    codigo = generar_codigo_log(tipo)
    log = ImportLog.objects.create(
        codigo=codigo,
        tipo=tipo,
        descripcion=descripcion,
        resumen=resumen,
        detalles=detalles or [],
    )
    return log


@ensure_csrf_cookie
def subir_cartera(request):
    """Importa la Plantilla DIF (Datos Iniciales de Facturación)"""
    context = {'active_tab': 'dif'}
    if request.method == 'POST':
        print("\n==============================================")
        print("📥 [DIF] ¡CARGA DE PLANTILLA INICIAL RECIBIDA!")
        print("==============================================")
        
        try:
            archivo = request.FILES['archivo_dif']
            tipo_erp = 'Por Clasificar'
            print(f"📦 [DIF] Archivo: {archivo.name}, Tipo ERP: {tipo_erp}")
        except KeyError:
            messages.error(request, "Error: No se envió el archivo DIF.")
            return redirect('/subir/')

        try:
            # Leer el archivo en memoria para poder pasarlo al importador y guardarlo en sesión si es necesario
            from types import SimpleNamespace
            contenido_bytes = archivo.read()
            file_like = SimpleNamespace(read=lambda: contenido_bytes, name=archivo.name)
            resumen = importar_excel_cartera(file_like, tipo_erp_predefinido=tipo_erp)
            mensaje = f"✅ Proceso exitoso: {resumen['creadas']} creadas, {resumen['actualizadas']} actualizadas."
            if resumen.get('filas_duplicadas', 0) > 0:
                mensaje += f" ⚠️ {resumen['filas_duplicadas']} filas duplicadas detectadas." 
            if resumen['alertas_aritmeticas']:
                mensaje += f" ⚠️ {len(resumen['alertas_aritmeticas'])} alertas aritméticas detectadas."

            detalles_log = [
                f"Filas en Excel: {resumen.get('filas_en_excel', 0)}",
                f"Filas procesadas: {resumen.get('filas_procesadas', 0)}",
                f"Creadas: {resumen.get('creadas', 0)}",
                f"Actualizadas: {resumen.get('actualizadas', 0)}",
                f"Duplicadas: {resumen.get('filas_duplicadas', 0)}",
                f"Errores: {len(resumen.get('errores', []))}",
            ]
            if resumen.get('duplicados'):
                detalles_log.append('Duplicados: ' + '; '.join(resumen['duplicados'][:5]))
            if resumen.get('alertas_aritmeticas'):
                detalles_log.append('Alertas: ' + '; '.join(resumen['alertas_aritmeticas'][:5]))

            log = registrar_import_log(
                'DIF',
                resumen,
                descripcion='Subida de documento DIF',
                detalles=detalles_log,
            )

            resumen['log_codigo'] = log.codigo
            mensaje += f" 📘 Código de log: {log.codigo}"
            messages.success(request, mensaje)
            context['resumen_importacion'] = resumen
            context['tipo_erp_seleccionado'] = tipo_erp
        except Exception as e:
            print(f"❌ [ERROR DIF] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error al procesar DIF: {type(e).__name__}: {e}")
            return redirect('/subir/')
            
    return render(request, 'facturacion/subir.html', context)


@require_POST
def actualizar_campo_factura(request, factura_id):
    """Actualiza un campo editable de la factura desde el modal de detalle."""
    factura = get_object_or_404(Factura, pk=factura_id)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    field = (body.get('field') or '').strip()
    value = body.get('value')

    if not field:
        return JsonResponse({'ok': False, 'error': 'Campo requerido'}, status=400)

    allowed_fields = {'nombre_paciente', 'historia_clinica', 'tel_celular', 'nom_canal', 'erp', 'estado_gestion'}
    if field not in allowed_fields:
        return JsonResponse({'ok': False, 'error': 'Campo no permitido'}, status=400)

    if field == 'nombre_paciente':
        factura.nombre_paciente = str(value or '').strip() or ''
    elif field == 'historia_clinica':
        factura.historia_clinica = str(value or '').strip() or ''
    elif field == 'tel_celular':
        factura.tel_celular = str(value or '').strip() or ''
    elif field == 'nom_canal':
        factura.nom_canal = str(value or '').strip() or ''
    elif field == 'erp':
        nombre_erp = str(value or '').strip()
        if nombre_erp:
            entidad = EntidadResponsable.objects.filter(nombre__iexact=nombre_erp).first()
            if entidad is None:
                return JsonResponse({'ok': False, 'error': 'Entidad ERP no encontrada'}, status=404)
            factura.erp = entidad
    elif field == 'estado_gestion':
        opcion = str(value or '').strip()
        if opcion == 'No Facturado':
            factura.fecha_factura = None
            factura.fecha_radicacion_inicial = None
        elif opcion == 'No Radicado':
            factura.fecha_factura = timezone.localdate()
            factura.fecha_radicacion_inicial = None
        elif opcion == 'Radicado':
            factura.fecha_factura = factura.fecha_factura or timezone.localdate()
            factura.fecha_radicacion_inicial = factura.fecha_radicacion_inicial or timezone.localdate()
        else:
            return JsonResponse({'ok': False, 'error': 'Opción de gestión no válida'}, status=400)

    factura.save()
    return JsonResponse({'ok': True, 'value': getattr(factura, field) if field not in {'erp', 'estado_gestion'} else (factura.erp.nombre if field == 'erp' else factura.estado_gestion)})


@require_POST
def resolver_duplicados_dif(request):
    """Endpoint para resolver duplicados encontrados en la pre-chequeo.
    Espera JSON con un mapa 'resoluciones': {fila_idx: 'existing'|'incoming'}
    """
    import json
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    resoluciones = body.get('resoluciones') or {}
    # Recuperar archivo guardado en sesión
    if not request.session.get('last_upload_dif_bytes'):
        return JsonResponse({'error': 'No hay archivo en sesión para resolver.'}, status=400)

    archivo_bytes = base64.b64decode(request.session.get('last_upload_dif_bytes'))
    nombre = request.session.get('last_upload_dif_name', 'upload.xlsx')

    from types import SimpleNamespace
    file_like = SimpleNamespace(read=lambda: archivo_bytes, name=nombre)

    # Convertir claves a enteros si vienen como strings
    dup_map = {}
    for k, v in resoluciones.items():
        try:
            ik = int(k)
        except Exception:
            continue
        if v not in ('existing', 'incoming'):
            continue
        dup_map[ik] = 'incoming' if v == 'incoming' else 'existing'

    resumen = importar_excel_cartera(file_like, tipo_erp_predefinido='Por Clasificar', duplicate_resolutions=dup_map)
    # Limpiar sesión
    try:
        del request.session['last_upload_dif_bytes']
        del request.session['last_upload_dif_name']
        request.session.modified = True
    except Exception:
        pass

    return JsonResponse({'resumen': resumen})


def actualizar_eventos_pae(request):
    """Importa la Plantilla PAE (Actualización de Eventos: Glosas, Abonos, etc)"""
    context = {'active_tab': 'pae'}
    if request.method == 'POST':
        print("\n==============================================")
        print("📥 [PAE] ¡CARGA DE EVENTOS RECIBIDA!")
        print("==============================================")
        
        try:
            archivo = request.FILES['archivo_pae']
            print(f"📦 [PAE] Archivo: {archivo.name}")
        except KeyError:
            messages.error(request, "Error: No se envió el archivo PAE.")
            return redirect('/subir/')

        try:
            audit_log = []
            resumen = importar_eventos_pae(archivo, audit_log=audit_log)
            procesados = resumen.get('procesados', 0)
            errores = resumen.get('errores', [])

            request.session['pae_audit_log'] = audit_log
            request.session['pae_audit_log_resumen'] = {
                'procesados': procesados,
                'errores': len(errores),
                'advertencias': len(resumen.get('advertencias', [])),
            }
            request.session.modified = True

            mensaje = f"✅ Procesados {procesados} eventos. "
            if errores:
                mensaje += f"⚠️ {len(errores)} errores detectados."
                for error in errores[:5]:  # Mostrar primeros 5
                    messages.warning(request, f"  • {error}")

            print(f"✅ [PAE] {mensaje}")
            log = registrar_import_log(
                'PAE',
                resumen,
                descripcion='Subida de documento PAE',
                detalles=[
                    f"Procesados: {procesados}",
                    f"Errores: {len(errores)}",
                    f"Advertencias: {len(resumen.get('advertencias', []))}",
                ] + [f"{item.get('factura')}: {item.get('detalle')}" for item in audit_log[:5]],
            )
            resumen['log_codigo'] = log.codigo

            messages.success(request, mensaje)
            context['resumen_importacion'] = resumen
            context['pae_audit_log'] = audit_log
            return render(request, 'facturacion/subir.html', context)
        except Exception as e:
            print(f"❌ [ERROR PAE] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            audit_log = [{
                'fila': 'N/A',
                'factura': 'N/A',
                'estado': 'error',
                'detalle': f'{type(e).__name__}: {e}',
            }]
            request.session['pae_audit_log'] = audit_log
            request.session['pae_audit_log_resumen'] = {'procesados': 0, 'errores': 1, 'advertencias': 0}
            request.session.modified = True
            context['pae_audit_log'] = audit_log
            messages.error(request, f"Error al procesar PAE: {type(e).__name__}: {e}")
            return render(request, 'facturacion/subir.html', context)
    
    return redirect('/subir/')

@ensure_csrf_cookie
def import_logs(request):
    per_page = request.GET.get('per_page', '200')
    try:
        per_page = int(per_page)
    except (TypeError, ValueError):
        per_page = 200
    per_page = 200 if per_page not in (200, 500) else per_page

    dif_page_num = request.GET.get('dif_page', '1')
    pae_page_num = request.GET.get('pae_page', '1')

    logs_dif = ImportLog.objects.filter(tipo='DIF').order_by('-creado_en')
    logs_pae = ImportLog.objects.filter(tipo='PAE').order_by('-creado_en')

    dif_paginator = Paginator(logs_dif, per_page)
    pae_paginator = Paginator(logs_pae, per_page)

    dif_page_obj = dif_paginator.get_page(dif_page_num)
    pae_page_obj = pae_paginator.get_page(pae_page_num)

    context = {
        'logs_dif': dif_page_obj.object_list,
        'logs_pae': pae_page_obj.object_list,
        'dif_page_obj': dif_page_obj,
        'pae_page_obj': pae_page_obj,
        'per_page': per_page,
        'dif_page': dif_page_num,
        'pae_page': pae_page_num,
    }
    return render(request, 'facturacion/logs.html', context)


@require_POST
@csrf_exempt
def limpiar_import_logs(request):
    """Elimina los ImportLog (todos o solo los seleccionados)."""
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        payload = {}

    try:
        if payload.get('modo') == 'all':
            ImportLog.objects.all().delete()
            return JsonResponse({'ok': True, 'mensaje': 'Todos los logs fueron eliminados.'})

        ids = payload.get('ids') or []
        if ids:
            ids = [int(item) for item in ids if str(item).strip()]
            if ids:
                deleted_count, _ = ImportLog.objects.filter(id__in=ids).delete()
                return JsonResponse({'ok': True, 'mensaje': f'{deleted_count} log(s) eliminados.'})

        return JsonResponse({'ok': False, 'error': 'No se seleccionaron registros para eliminar.'}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def import_log_detail(request, log_id):
    log = get_object_or_404(ImportLog, pk=log_id)
    return render(request, 'facturacion/log_detail.html', {
        'log': log,
    })


def dashboard(request):
    """Dashboard mejorado con filtros por Año/Mes y KPIs calculados"""
    from .models import CalendarioDimension
    
    # 1. OBTENER FILTROS DEL REQUEST
    ano_filtro = request.GET.get('ano')
    mes_filtro = request.GET.get('mes')
    tipo_erp = request.GET.get('tipo_erp')
    nit_erp = request.GET.get('nit_erp')
    fecha_admision_desde = request.GET.get('fecha_admision_desde')
    fecha_admision_hasta = request.GET.get('fecha_admision_hasta')
    
    # Obtener años disponibles para el selector
    anos_disponibles = CalendarioDimension.objects.values_list('ano', flat=True).distinct().order_by('-ano')
    tipos_erp = TipoERP.objects.order_by('nombre').values_list('nombre', flat=True).distinct()
    erps_disponibles = EntidadResponsable.objects.order_by('nombre').values_list('nombre', flat=True).distinct()
    
    # Si no se selecciona año, usar el año actual
    if not ano_filtro and anos_disponibles:
        ano_filtro = str(anos_disponibles[0])
    
    # 2. APLICAR FILTROS A LAS FACTURAS
    filtro_facturadas = (
        Q(facturada_status__iexact='TRUE') |
        Q(facturada_status__iexact='FACTURADA') |
        Q(facturada_status__iexact='FACTURADO') |
        Q(facturada_status__iexact='1') |
        Q(facturada_status__iexact='SI') |
        Q(facturada_status__iexact='YES')
    )

    queryset_radicadas = Factura.objects.filter(
        fecha_radicacion_inicial__isnull=False
    )
    queryset_facturadas = Factura.objects.filter(
        fecha_factura__isnull=False
    ).filter(filtro_facturadas)

    if ano_filtro:
        queryset_radicadas = queryset_radicadas.filter(fecha_radicacion_inicial__year=int(ano_filtro))
        queryset_facturadas = queryset_facturadas.filter(fecha_factura__year=int(ano_filtro))

    if mes_filtro:
        queryset_radicadas = queryset_radicadas.filter(fecha_radicacion_inicial__month=int(mes_filtro))
        queryset_facturadas = queryset_facturadas.filter(fecha_factura__month=int(mes_filtro))

    if tipo_erp:
        queryset_radicadas = queryset_radicadas.filter(erp__tipo_erp__nombre=tipo_erp)
        queryset_facturadas = queryset_facturadas.filter(erp__tipo_erp__nombre=tipo_erp)
    if nit_erp:
        filtro_erp = Q(erp__nit__iexact=nit_erp) | Q(erp__nombre__icontains=nit_erp)
        queryset_radicadas = queryset_radicadas.filter(filtro_erp)
        queryset_facturadas = queryset_facturadas.filter(filtro_erp)

    if fecha_admision_desde:
        try:
            desde = datetime.strptime(fecha_admision_desde, '%Y-%m-%d').date()
            queryset_radicadas = queryset_radicadas.filter(fecha_admision__gte=desde)
            queryset_facturadas = queryset_facturadas.filter(fecha_admision__gte=desde)
        except ValueError:
            pass

    if fecha_admision_hasta:
        try:
            hasta = datetime.strptime(fecha_admision_hasta, '%Y-%m-%d').date()
            queryset_radicadas = queryset_radicadas.filter(fecha_admision__lte=hasta)
            queryset_facturadas = queryset_facturadas.filter(fecha_admision__lte=hasta)
        except ValueError:
            pass

    # 3. CALCULAR KPIs
    total_facturas = queryset_radicadas.count()
    total_radicados = queryset_radicadas.aggregate(total=Sum('total_factura'))['total'] or 0
    total_facturas_facturadas = queryset_facturadas.count()
    total_facturados = queryset_facturadas.aggregate(total=Sum('total_factura'))['total'] or 0
    pct_radicacion = (total_radicados / total_facturados * 100) if total_facturados > 0 else 0

    # Glosas iniciales vs valor total de factura
    total_glosas_iniciales = queryset_radicadas.aggregate(total=Sum('valor_glosa_inicial'))['total'] or 0
    total_neto = queryset_radicadas.aggregate(total=Sum('total_factura'))['total'] or 0
    pct_glosa_inicial = (total_glosas_iniciales / total_neto * 100) if total_neto > 0 else 0
    
    # Edad media de cartera (DSO - Days Sales Outstanding)
    dso = 0
    if total_facturas > 0:
        hoy = timezone.now().date()
        suma_dias = sum(
            (hoy - f.fecha_radicacion_inicial).days 
            for f in queryset_radicadas 
            if f.fecha_radicacion_inicial
        )
        dso = suma_dias / total_facturas if total_facturas > 0 else 0
    
    # 4. CLASIFICACIÓN POR EDADES
    hoy = timezone.now().date()
    facturas_activas = queryset_radicadas.filter(fecha_devolucion__isnull=True)
    
    valor_0_30 = 0
    valor_31_60 = 0
    valor_61_90 = 0
    valor_mas_90 = 0
    
    for factura in facturas_activas:
        dias = (hoy - factura.fecha_radicacion_inicial).days if factura.fecha_radicacion_inicial else 0
        if dias <= 30:
            valor_0_30 += factura.total_factura
        elif dias <= 60:
            valor_31_60 += factura.total_factura
        elif dias <= 90:
            valor_61_90 += factura.total_factura
        else:
            valor_mas_90 += factura.total_factura
    
    # 5. TOP 5 ERPS POR CARTERA
    top_erps = queryset_radicadas.values(
        nombre_erp=F('erp__nombre')
    ).annotate(
        total=Sum('total_factura')
    ).order_by('-total')[:5]
    
    # 6. ARMAR CONTEXTO
    context = {
        'valor_radicados': f"{total_radicados:,.2f}",
        'total_facturas_radicadas': total_facturas,
        'valor_facturados': f"{total_facturados:,.2f}",
        'total_facturas_facturadas': total_facturas_facturadas,
        'pct_radicacion': f"{pct_radicacion:.1f}",
        'pct_glosa_inicial': f"{pct_glosa_inicial:.1f}",
        'dso': f"{dso:.0f}",
        'datos_grafico': [float(valor_0_30), float(valor_31_60), float(valor_61_90), float(valor_mas_90)],
        'etiquetas_grafico': ['0-30 días', '31-60 días', '61-90 días', '+90 días'],
        'fecha_actual': timezone.now().strftime("%d/%m/%y"),
        'anos_disponibles': list(anos_disponibles),
        'tipos_erp': list(tipos_erp),
        'erps_disponibles': list(erps_disponibles),
        'ano_filtro': ano_filtro,
        'mes_filtro': mes_filtro,
        'tipo_erp': tipo_erp,
        'nit_erp': nit_erp,
        'fecha_admision_desde': fecha_admision_desde,
        'fecha_admision_hasta': fecha_admision_hasta,
        'top_erps': list(top_erps),
        'total_glosas': f"{total_glosas_iniciales:,.2f}",
    }
    
    return render(request, 'facturacion/dashboard.html', context)

def limpiar_cartera(request):
    """Borrado seguro en bloque para desarrollo y pruebas."""
    cantidad = Factura.objects.count()

    with transaction.atomic():
        # Eliminar primero los hijos para evitar problemas de integridad en datasets reales.
        EventoCartera.objects.all().delete()
        Factura.objects.all().delete()
        EntidadResponsable.objects.filter(factura__isnull=True).delete()
        TipoERP.objects.filter(entidades__factura__isnull=True).delete()

    messages.success(request, f"Base de datos limpia de raíz. Se eliminaron {cantidad} facturas operativas.")
    return redirect('home')


def environments(request):
    environments_list = Environment.objects.order_by('numero')
    selected_id = request.session.get('environment_id', 1)
    if request.method == 'POST':
        if request.POST.get('cancelar'):
            return redirect('environments')

        try:
            selected = environments_list.get(pk=int(request.POST.get('environment') or 1))
        except (TypeError, ValueError, Environment.DoesNotExist):
            messages.error(request, 'Seleccione un environment válido.')
            return redirect('environments')

        password = request.POST.get('password', '')
        if selected.pk != selected_id and not selected.check_password(password):
            messages.error(request, 'La contraseña del environment no es correcta.')
            return render(request, 'facturacion/environments.html', {
                'environments': environments_list,
                'selected_environment': selected,
            })

        selected.nickname = request.POST.get('nickname', '').strip()
        selected.comentario = request.POST.get('comentario', '').strip()
        if password:
            selected.set_password(password)
        selected.save(update_fields=['nickname', 'comentario', 'password'])
        request.session['environment_id'] = selected.pk
        request.session.modified = True
        messages.success(request, f'Environment {selected.numero} aplicado correctamente.')
        return redirect('environments')

    selected = Environment.objects.filter(pk=selected_id).first() or Environment.objects.get(numero=1)
    return render(request, 'facturacion/environments.html', {
        'environments': environments_list,
        'selected_environment': selected,
    })


def _respuesta_exportacion_eas(queryset):
    df = construir_dataframe_exportacion_eas(queryset)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)

    nombre_archivo = f"EAS_{timezone.localtime().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


def exportar_eas(request):
    """Exporta todas las facturas del entorno activo a un archivo EAS."""
    queryset = Factura.objects.select_related('erp').order_by('id')
    return _respuesta_exportacion_eas(queryset)


def exportar_eas_seleccionadas(request):
    """Exporta únicamente las facturas seleccionadas del entorno activo."""
    factura_ids = request.GET.getlist('factura_ids')
    queryset = Factura.objects.select_related('erp').filter(id__in=factura_ids).order_by('id')
    return _respuesta_exportacion_eas(queryset)


def lista_facturas(request):
    if request.method == 'POST':
        factura_ids = request.POST.getlist('factura_ids')
        query_params = request.POST.copy()
        query_params.pop('factura_ids', None)
        query_params.pop('csrfmiddlewaretoken', None)
        query_string = query_params.urlencode()

        if factura_ids:
            deleted_count, _ = Factura.objects.filter(id__in=factura_ids).delete()
            messages.success(request, f'Se eliminaron {deleted_count} factura(s) correctamente.')
        else:
            messages.warning(request, 'Seleccione al menos una factura antes de eliminar.')

        if query_string:
            return redirect(f"{reverse('lista_facturas')}?{query_string}")
        return redirect('lista_facturas')

    query = request.GET.get('q', '').strip()
    fecha_admision_desde = request.GET.get('fecha_admision_desde')
    fecha_admision_hasta = request.GET.get('fecha_admision_hasta')
    fecha_radicacion_desde = request.GET.get('fecha_radicacion_desde')
    fecha_radicacion_hasta = request.GET.get('fecha_radicacion_hasta')
    solo_radicadas = request.GET.get('solo_radicadas') == '1'
    sin_radicacion = request.GET.get('sin_radicacion') == '1'
    solo_facturadas = request.GET.get('solo_facturadas') == '1'
    sin_factura = request.GET.get('sin_factura') == '1'
    solo_valor_neto_cero = request.GET.get('solo_valor_neto_cero') == '1'
    valor_neto_min = request.GET.get('valor_neto_min')
    valor_neto_max = request.GET.get('valor_neto_max')
    entidad = request.GET.get('entidad', '').strip()
    canal = request.GET.get('canal', '').strip()
    pagos_subquery = Subquery(
        EventoCartera.objects.filter(
            factura_id=OuterRef('pk'),
            tipo__in=['GLO_ACEP', 'ABONO', 'RTF']
        )
        .values('factura_id')
        .annotate(total=Sum('valor'))
        .values('total')[:1],
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )

    facturas_list = (
        Factura.objects.select_related('erp')
        .annotate(
            pagos_calculado=Coalesce(pagos_subquery, Value(Decimal('0.00')), output_field=DecimalField(max_digits=18, decimal_places=2)),
            valor_neto_calculado=F('total_factura') - F('pagos_calculado'),
        )
        .order_by('-id')
    )

    if query:
        facturas_list = facturas_list.filter(
            Q(num_factura__icontains=query) |
            Q(id_atencion__icontains=query) |
            Q(erp__nombre__icontains=query) |
            Q(nombre_paciente__icontains=query) |
            Q(nom_canal__icontains=query)
        )

    if fecha_admision_desde:
        try:
            desde = datetime.strptime(fecha_admision_desde, '%Y-%m-%d').date()
            facturas_list = facturas_list.filter(fecha_admision__gte=desde)
        except ValueError:
            pass

    if fecha_admision_hasta:
        try:
            hasta = datetime.strptime(fecha_admision_hasta, '%Y-%m-%d').date()
            facturas_list = facturas_list.filter(fecha_admision__lte=hasta)
        except ValueError:
            pass

    if fecha_radicacion_desde:
        try:
            desde = datetime.strptime(fecha_radicacion_desde, '%Y-%m-%d').date()
            facturas_list = facturas_list.filter(fecha_radicacion_inicial__gte=desde)
        except ValueError:
            pass

    if fecha_radicacion_hasta:
        try:
            hasta = datetime.strptime(fecha_radicacion_hasta, '%Y-%m-%d').date()
            facturas_list = facturas_list.filter(fecha_radicacion_inicial__lte=hasta)
        except ValueError:
            pass

    if solo_radicadas:
        facturas_list = facturas_list.filter(fecha_radicacion_inicial__isnull=False)
    if sin_radicacion:
        facturas_list = facturas_list.filter(fecha_radicacion_inicial__isnull=True)
    if solo_facturadas:
        facturas_list = facturas_list.filter(
            Q(facturada_status__iexact='FACTURADA') |
            (~Q(num_factura__istartswith='NOFACT-'))
        )
    if sin_factura:
        facturas_list = facturas_list.filter(
            Q(facturada_status__iexact='NOFACT') |
            Q(num_factura__istartswith='NOFACT-')
        )
    if solo_valor_neto_cero:
        facturas_list = facturas_list.filter(valor_neto_calculado=Decimal('0.00'))

    if valor_neto_min:
        try:
            minimo = Decimal(str(valor_neto_min))
            facturas_list = facturas_list.filter(valor_neto_calculado__gte=minimo)
        except (InvalidOperation, ValueError):
            pass
    if valor_neto_max:
        try:
            maximo = Decimal(str(valor_neto_max))
            facturas_list = facturas_list.filter(valor_neto_calculado__lte=maximo)
        except (InvalidOperation, ValueError):
            pass

    if entidad:
        facturas_list = facturas_list.filter(erp__nombre__icontains=entidad)
    if canal:
        facturas_list = facturas_list.filter(nom_canal__icontains=canal)

    paginator = Paginator(facturas_list, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    query_string = query_params.urlencode()

    entidades_disponibles = list(EntidadResponsable.objects.order_by('nombre').values_list('nombre', flat=True).distinct())

    return render(request, 'facturacion/lista_facturas.html', {
        'page_obj': page_obj,
        'query_string': query_string,
        'query': query,
        'fecha_admision_desde': fecha_admision_desde,
        'fecha_admision_hasta': fecha_admision_hasta,
        'fecha_radicacion_desde': fecha_radicacion_desde,
        'fecha_radicacion_hasta': fecha_radicacion_hasta,
        'solo_radicadas': solo_radicadas,
        'sin_radicacion': sin_radicacion,
        'solo_facturadas': solo_facturadas,
        'sin_factura': sin_factura,
        'solo_valor_neto_cero': solo_valor_neto_cero,
        'valor_neto_min': valor_neto_min,
        'valor_neto_max': valor_neto_max,
        'entidad': entidad,
        'entidades_disponibles': entidades_disponibles,
    })