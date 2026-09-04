# facturacion/api.py
"""
API REST para alimentar Power BI con datos limpios y optimizados.
Endpoints exponen datos de Facturas, Eventos y Indicadores KPI en formato JSON.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum, Count, Q, F, Max, DecimalField, Case, When
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import Factura, EventoCartera, EntidadResponsable, TipoERP, CalendarioDimension
from .serializers import FacturaSerializer, EventoCarteraSerializer


def _dashboard_queryset(request):
    """Construye el queryset común del dashboard sin duplicar filtros."""
    qs = Factura.objects.filter(fecha_factura__isnull=False)
    ano = request.GET.get('ano')
    mes = request.GET.get('mes')
    tipo_erp = request.GET.get('tipo_erp')
    nit_erp = request.GET.get('nit_erp')
    desde = request.GET.get('fecha_admision_desde')
    hasta = request.GET.get('fecha_admision_hasta')
    if ano:
        qs = qs.filter(fecha_factura__year=int(ano))
    if mes:
        qs = qs.filter(fecha_factura__month=int(mes))
    if tipo_erp:
        qs = qs.filter(erp__tipo_erp__nombre=tipo_erp)
    if nit_erp:
        qs = qs.filter(Q(erp__nit__iexact=nit_erp) | Q(erp__nombre__icontains=nit_erp))
    if desde:
        qs = qs.filter(fecha_admision__gte=desde)
    if hasta:
        qs = qs.filter(fecha_admision__lte=hasta)
    return qs.select_related('erp', 'erp__tipo_erp')


def _dashboard_money(value):
    return float(value or Decimal('0'))


# ===== ENDPOINTS PARA PODER BI =====

@api_view(['GET'])
def kpi_dashboard(request):
    """
    Endpoint principal: Todos los KPIs en una sola llamada.
    Filtros opcionales: ano, mes, nit_erp, tipo_erp
    """
    # Parámetros de filtro
    ano = request.GET.get('ano')
    mes = request.GET.get('mes')
    nit_erp = request.GET.get('nit_erp')
    tipo_erp = request.GET.get('tipo_erp')
    fecha_admision_desde = request.GET.get('fecha_admision_desde')
    fecha_admision_hasta = request.GET.get('fecha_admision_hasta')
    
    # Aplicar filtros
    filtro_facturadas = (
        Q(facturada_status__iexact='TRUE') |
        Q(facturada_status__iexact='FACTURADA') |
        Q(facturada_status__iexact='FACTURADO') |
        Q(facturada_status__iexact='1') |
        Q(facturada_status__iexact='SI') |
        Q(facturada_status__iexact='YES')
    )

    queryset_radicadas = Factura.objects.filter(fecha_radicacion_inicial__isnull=False)
    queryset_facturadas = Factura.objects.filter(fecha_factura__isnull=False).filter(filtro_facturadas)

    if ano:
        queryset_radicadas = queryset_radicadas.filter(fecha_radicacion_inicial__year=int(ano))
        queryset_facturadas = queryset_facturadas.filter(fecha_factura__year=int(ano))
    if mes:
        queryset_radicadas = queryset_radicadas.filter(fecha_radicacion_inicial__month=int(mes))
        queryset_facturadas = queryset_facturadas.filter(fecha_factura__month=int(mes))
    if nit_erp:
        filtro_erp = Q(erp__nit__iexact=nit_erp) | Q(erp__nombre__icontains=nit_erp)
        queryset_radicadas = queryset_radicadas.filter(filtro_erp)
        queryset_facturadas = queryset_facturadas.filter(filtro_erp)
    if tipo_erp:
        queryset_radicadas = queryset_radicadas.filter(erp__tipo_erp__nombre=tipo_erp)
        queryset_facturadas = queryset_facturadas.filter(erp__tipo_erp__nombre=tipo_erp)

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
    
    # Cálculos base
    total_facturas = queryset_radicadas.count()
    total_facturas_facturadas = queryset_facturadas.count()
    total_cartera_bruta = queryset_radicadas.aggregate(total=Sum('total_factura'))['total'] or Decimal('0')
    total_cartera_neta = queryset_facturadas.aggregate(total=Sum('total_factura'))['total'] or Decimal('0')
    
    # Glosas
    total_glosas_iniciales = queryset_radicadas.aggregate(total=Sum('valor_glosa_inicial'))['total'] or Decimal('0')
    
    # Eventos: Glosa Aceptada (real), Abonos, RTF
    eventos_glosa_acep = EventoCartera.objects.filter(factura__in=queryset_radicadas, tipo='GLO_ACEP').aggregate(total=Sum('valor'))['total'] or Decimal('0')
    eventos_abonos = EventoCartera.objects.filter(factura__in=queryset_radicadas, tipo='ABONO').aggregate(total=Sum('valor'))['total'] or Decimal('0')
    eventos_rtf = EventoCartera.objects.filter(factura__in=queryset_radicadas, tipo='RTF').aggregate(total=Sum('valor'))['total'] or Decimal('0')
    
    # KPIs calculados
    pct_radicacion = (float(total_cartera_bruta) / float(total_cartera_neta) * 100) if total_cartera_neta > 0 else 0
    pct_glosa_inicial = (float(total_glosas_iniciales) / float(total_cartera_bruta) * 100) if total_cartera_bruta > 0 else 0
    pct_glosa_definitiva = (float(eventos_glosa_acep) / float(total_cartera_bruta) * 100) if total_cartera_bruta > 0 else 0
    pct_recaudo = (float(eventos_abonos) / float(total_cartera_bruta) * 100) if total_cartera_bruta > 0 else 0
    
    # DSO (Days Sales Outstanding)
    dso = 0
    if total_facturas > 0:
        hoy = timezone.now().date()
        suma_dias = sum(
            (hoy - f.fecha_radicacion_inicial).days 
            for f in queryset_radicadas 
            if f.fecha_radicacion_inicial
        )
        dso = suma_dias / total_facturas
    
    # Tasa de Recuperación de Glosas
    tasa_recuperacion_glosa = 0
    if total_glosas_iniciales > 0:
        eventos_glosa_lev = EventoCartera.objects.filter(factura__in=queryset_radicadas, tipo='GLO_LEV').aggregate(total=Sum('valor'))['total'] or Decimal('0')
        tasa_recuperacion_glosa = (float(eventos_glosa_lev) / float(total_glosas_iniciales) * 100)
    
    return Response({
        'timestamp': timezone.now().isoformat(),
        'filtros': {
            'ano': ano,
            'mes': mes,
            'nit_erp': nit_erp,
            'tipo_erp': tipo_erp,
            'fecha_admision_desde': fecha_admision_desde,
            'fecha_admision_hasta': fecha_admision_hasta,
        },
        'kpi_cartera': {
            'total_facturas': total_facturas,
            'total_facturas_facturadas': total_facturas_facturadas,
            'total_cartera_bruta': float(total_cartera_bruta),
            'total_cartera_neta': float(total_cartera_neta),
            'diferencia_saldo': float(total_cartera_bruta - total_cartera_neta),
        },
        'kpi_glosas': {
            'total_glosas_iniciales': float(total_glosas_iniciales),
            'total_glosas_aceptadas': float(eventos_glosa_acep),
            'total_glosas_levantadas': float(EventoCartera.objects.filter(factura__in=queryset_radicadas, tipo='GLO_LEV').aggregate(total=Sum('valor'))['total'] or 0),
            'pct_glosa_inicial': round(pct_glosa_inicial, 2),
            'pct_glosa_definitiva': round(pct_glosa_definitiva, 2),
            'tasa_recuperacion_glosa': round(tasa_recuperacion_glosa, 2),
        },
        'kpi_recaudo': {
            'total_abonos': float(eventos_abonos),
            'total_retenciones': float(eventos_rtf),
            'pct_recaudo': round(pct_recaudo, 2),
        },
        'kpi_operativo': {
            'pct_radicacion_efectiva': round(pct_radicacion, 2),
            'dso_dias': round(dso, 1),
        }
    })


@api_view(['GET'])
def cartera_por_edades(request):
    """
    Endpoint: Cartera clasificada por rangos de días de mora.
    Retorna: [0-30, 31-60, 61-90, 91-180, 181-360, +360 días]
    """
    ano = request.GET.get('ano')
    mes = request.GET.get('mes')
    nit_erp = request.GET.get('nit_erp')
    tipo_erp = request.GET.get('tipo_erp')
    fecha_admision_desde = request.GET.get('fecha_admision_desde')
    fecha_admision_hasta = request.GET.get('fecha_admision_hasta')
    hoy = timezone.now().date()
    
    queryset = Factura.objects.filter(
        fecha_radicacion_inicial__isnull=False,
        fecha_devolucion__isnull=True  # Solo activas
    )
    
    if ano:
        queryset = queryset.filter(fecha_radicacion_inicial__year=int(ano))
    if mes:
        queryset = queryset.filter(fecha_radicacion_inicial__month=int(mes))
    if nit_erp:
        queryset = queryset.filter(
            Q(erp__nit__iexact=nit_erp) | Q(erp__nombre__icontains=nit_erp)
        )
    if tipo_erp:
        queryset = queryset.filter(erp__tipo_erp__nombre=tipo_erp)

    if fecha_admision_desde:
        try:
            desde = datetime.strptime(fecha_admision_desde, '%Y-%m-%d').date()
            queryset = queryset.filter(fecha_admision__gte=desde)
        except ValueError:
            pass

    if fecha_admision_hasta:
        try:
            hasta = datetime.strptime(fecha_admision_hasta, '%Y-%m-%d').date()
            queryset = queryset.filter(fecha_admision__lte=hasta)
        except ValueError:
            pass
    rango_0_30 = queryset.filter(
        fecha_radicacion_inicial__gte=hoy - timedelta(days=30)
    ).aggregate(total=Sum('total_factura'), count=Count('id'))
    
    rango_31_60 = queryset.filter(
        fecha_radicacion_inicial__gte=hoy - timedelta(days=60),
        fecha_radicacion_inicial__lt=hoy - timedelta(days=30)
    ).aggregate(total=Sum('total_factura'), count=Count('id'))
    
    rango_61_90 = queryset.filter(
        fecha_radicacion_inicial__gte=hoy - timedelta(days=90),
        fecha_radicacion_inicial__lt=hoy - timedelta(days=60)
    ).aggregate(total=Sum('total_factura'), count=Count('id'))
    
    rango_91_180 = queryset.filter(
        fecha_radicacion_inicial__gte=hoy - timedelta(days=180),
        fecha_radicacion_inicial__lt=hoy - timedelta(days=90)
    ).aggregate(total=Sum('total_factura'), count=Count('id'))
    
    rango_181_360 = queryset.filter(
        fecha_radicacion_inicial__gte=hoy - timedelta(days=360),
        fecha_radicacion_inicial__lt=hoy - timedelta(days=180)
    ).aggregate(total=Sum('total_factura'), count=Count('id'))
    
    rango_mayor_360 = queryset.filter(
        fecha_radicacion_inicial__lt=hoy - timedelta(days=360)
    ).aggregate(total=Sum('total_factura'), count=Count('id'))
    
    return Response({
        'rango_0_30': {
            'etiqueta': '0-30 días',
            'saldo': float(rango_0_30['total'] or 0),
            'cantidad_facturas': rango_0_30['count'] or 0,
        },
        'rango_31_60': {
            'etiqueta': '31-60 días',
            'saldo': float(rango_31_60['total'] or 0),
            'cantidad_facturas': rango_31_60['count'] or 0,
        },
        'rango_61_90': {
            'etiqueta': '61-90 días',
            'saldo': float(rango_61_90['total'] or 0),
            'cantidad_facturas': rango_61_90['count'] or 0,
        },
        'rango_91_180': {
            'etiqueta': '91-180 días',
            'saldo': float(rango_91_180['total'] or 0),
            'cantidad_facturas': rango_91_180['count'] or 0,
        },
        'rango_181_360': {
            'etiqueta': '181-360 días',
            'saldo': float(rango_181_360['total'] or 0),
            'cantidad_facturas': rango_181_360['count'] or 0,
        },
        'rango_mayor_360': {
            'etiqueta': '+360 días (CRÍTICO)',
            'saldo': float(rango_mayor_360['total'] or 0),
            'cantidad_facturas': rango_mayor_360['count'] or 0,
        },
    })


@api_view(['GET'])
def top_erps_cartera(request):
    """
    Endpoint: Top 10 ERPs por cartera pendiente.
    """
    ano = request.GET.get('ano')
    mes = request.GET.get('mes')
    nit_erp = request.GET.get('nit_erp')
    tipo_erp = request.GET.get('tipo_erp')
    fecha_admision_desde = request.GET.get('fecha_admision_desde')
    fecha_admision_hasta = request.GET.get('fecha_admision_hasta')
    limite = int(request.GET.get('limite', 10))
    
    queryset = Factura.objects.filter(fecha_radicacion_inicial__isnull=False)
    
    if ano:
        queryset = queryset.filter(fecha_radicacion_inicial__year=int(ano))
    if mes:
        queryset = queryset.filter(fecha_radicacion_inicial__month=int(mes))
    if nit_erp:
        queryset = queryset.filter(
            Q(erp__nit__iexact=nit_erp) | Q(erp__nombre__icontains=nit_erp)
        )
    if tipo_erp:
        queryset = queryset.filter(erp__tipo_erp__nombre=tipo_erp)

    if fecha_admision_desde:
        try:
            desde = datetime.strptime(fecha_admision_desde, '%Y-%m-%d').date()
            queryset = queryset.filter(fecha_admision__gte=desde)
        except ValueError:
            pass

    if fecha_admision_hasta:
        try:
            hasta = datetime.strptime(fecha_admision_hasta, '%Y-%m-%d').date()
            queryset = queryset.filter(fecha_admision__lte=hasta)
        except ValueError:
            pass
    
    top_erps = queryset.values(
        'erp__nit',
        'erp__nombre',
        'erp__tipo_erp__nombre'
    ).annotate(
        total_cartera=Sum('total_factura'),
        cantidad_facturas=Count('id'),
        total_glosas=Sum('valor_glosa_inicial')
    ).order_by('-total_cartera')[:limite]
    
    return Response({
        'cantidad': len(list(top_erps)),
        'erps': list(top_erps),
    })


@api_view(['GET'])
def embudo_glosas(request):
    """
    Endpoint: Visualización del embudo de glosas.
    Muestra: Radicadas -> Glosadas Inicialmente -> Aceptadas -> Levantadas
    """
    ano = request.GET.get('ano')
    mes = request.GET.get('mes')
    
    queryset = Factura.objects.filter(fecha_radicacion_inicial__isnull=False)
    
    if ano:
        queryset = queryset.filter(fecha_radicacion_inicial__year=int(ano))
    if mes:
        queryset = queryset.filter(fecha_radicacion_inicial__month=int(mes))
    
    # Cantidad de facturas en cada etapa
    total_radicadas = queryset.count()
    total_glosadas_ini = queryset.filter(valor_glosa_inicial__gt=0).count()
    
    # Valores monetarios
    valor_radicado = queryset.aggregate(total=Sum('total_factura'))['total'] or Decimal('0')
    valor_glosado_ini = queryset.aggregate(total=Sum('valor_glosa_inicial'))['total'] or Decimal('0')
    
    # Eventos de glosa aceptada y levantada
    glosas_aceptadas = EventoCartera.objects.filter(factura__in=queryset, tipo='GLO_ACEP').aggregate(total=Sum('valor'))['total'] or Decimal('0')
    glosas_levantadas = EventoCartera.objects.filter(factura__in=queryset, tipo='GLO_LEV').aggregate(total=Sum('valor'))['total'] or Decimal('0')
    
    return Response({
        'embudo': {
            'radicadas': {
                'cantidad': total_radicadas,
                'valor': float(valor_radicado),
            },
            'glosadas_inicialmente': {
                'cantidad': total_glosadas_ini,
                'valor': float(valor_glosado_ini),
            },
            'aceptadas_ips': {
                'valor': float(glosas_aceptadas),
            },
            'levantadas_erp': {
                'valor': float(glosas_levantadas),
            },
            'en_discusion': {
                'valor': float(valor_glosado_ini - glosas_aceptadas - glosas_levantadas) if (valor_glosado_ini - glosas_aceptadas - glosas_levantadas) > 0 else 0,
            },
        }
    })


@api_view(['GET'])
def trazabilidad_abonos(request):
    """
    Endpoint: Detalle de abonos por factura.
    Muestra: Factura, Radicación, Abono 1, Abono 2, Abono 3, Abono 4, RTF, Saldo Final
    """
    ano = request.GET.get('ano')
    mes = request.GET.get('mes')
    limite = int(request.GET.get('limite', 100))
    
    queryset = Factura.objects.filter(fecha_radicacion_inicial__isnull=False).order_by('-fecha_radicacion_inicial')[:limite]
    
    if ano:
        queryset = queryset.filter(fecha_radicacion_inicial__year=int(ano))
    if mes:
        queryset = queryset.filter(fecha_radicacion_inicial__month=int(mes))
    
    resultado = []
    for factura in queryset:
        abonos = factura.eventos.filter(tipo='ABONO').order_by('fecha')
        rtf = factura.eventos.filter(tipo='RTF').aggregate(total=Sum('valor'))['total'] or Decimal('0')
        
        dict_factura = {
            'num_factura': factura.num_factura,
            'erp_nombre': factura.erp.nombre,
            'fecha_radicacion': factura.fecha_radicacion_inicial,
            'valor_neto': float(factura.valor_neto),
            'abonos': [float(abono.valor) for abono in abonos],
            'rtf_total': float(rtf),
            'saldo_actual': float(factura.saldo_actual),
        }
        resultado.append(dict_factura)
    
    return Response({'abonos': resultado})


@api_view(['GET'])
def facturas_devueltas(request):
    """
    Endpoint: Facturas devueltas que requieren refacturación urgente.
    """
    ano = request.GET.get('ano')
    mes = request.GET.get('mes')
    
    queryset = Factura.objects.filter(fecha_devolucion__isnull=False).order_by('-fecha_devolucion')
    
    if ano:
        queryset = queryset.filter(fecha_devolucion__year=int(ano))
    if mes:
        queryset = queryset.filter(fecha_devolucion__month=int(mes))
    
    devueltas = []
    for factura in queryset[:50]:
        devueltas.append({
            'num_factura': factura.num_factura,
            'erp_nombre': factura.erp.nombre,
            'fecha_devolucion': factura.fecha_devolucion,
            'valor_factura': float(factura.total_factura),
            'dias_desde_devolucion': (timezone.now().date() - factura.fecha_devolucion).days,
        })
    
    return Response({'devueltas': devueltas})


@api_view(['GET'])
def dashboard_data(request):
    """Contrato único para la vista interactiva del dashboard."""
    hoy = timezone.now().date()
    qs = _dashboard_queryset(request)
    radicadas = qs.filter(fecha_radicacion_inicial__isnull=False)
    eventos = EventoCartera.objects.filter(factura__in=radicadas)
    total_facturado = qs.aggregate(v=Sum('total_factura'))['v'] or Decimal('0')
    total_radicado = radicadas.aggregate(v=Sum('total_factura'))['v'] or Decimal('0')
    total_glosa = radicadas.aggregate(v=Sum('valor_glosa_inicial'))['v'] or Decimal('0')
    total_abonos = eventos.filter(tipo='ABONO').aggregate(v=Sum('valor'))['v'] or Decimal('0')
    total_aceptado = eventos.filter(tipo='GLO_ACEP').aggregate(v=Sum('valor'))['v'] or Decimal('0')
    total_levantado = eventos.filter(tipo='GLO_LEV').aggregate(v=Sum('valor'))['v'] or Decimal('0')
    total_rtf = eventos.filter(tipo='RTF').aggregate(v=Sum('valor'))['v'] or Decimal('0')
    saldo = max(Decimal('0'), total_radicado - total_glosa - total_aceptado - total_abonos - total_rtf)
    dias = [(hoy - f.fecha_radicacion_inicial).days for f in radicadas if f.fecha_radicacion_inicial]
    dso = round(sum(dias) / len(dias), 1) if dias else 0
    rangos = [(0, 30), (31, 60), (61, 90), (91, 180), (181, 360), (361, 10 ** 9)]
    edades = []
    for minimo, maximo in rangos:
        grupo = [f for f in radicadas if f.fecha_radicacion_inicial and minimo <= (hoy - f.fecha_radicacion_inicial).days <= maximo]
        edades.append({'min': minimo, 'max': maximo, 'saldo': _dashboard_money(sum((f.saldo_actual or 0) for f in grupo)), 'cantidad': len(grupo)})
    erp_map = {}
    for factura in radicadas:
        key = factura.erp.nit
        item = erp_map.setdefault(key, {'nit': key, 'nombre': factura.erp.nombre, 'tipo': factura.erp.tipo_erp.nombre, 'facturado': Decimal('0'), 'saldo': Decimal('0'), 'glosa': Decimal('0'), 'dias_ponderados': Decimal('0'), 'cantidad': 0})
        item['facturado'] += factura.total_factura or 0
        item['saldo'] += factura.saldo_actual or 0
        item['glosa'] += factura.valor_glosa_inicial or 0
        item['dias_ponderados'] += (factura.saldo_actual or 0) * max(0, (hoy - factura.fecha_radicacion_inicial).days)
        item['cantidad'] += 1
    erps = []
    for item in erp_map.values():
        item['pct_glosa'] = _dashboard_money(item['glosa'] / item['facturado'] * 100) if item['facturado'] else 0
        item['dso'] = round(float(item['dias_ponderados'] / item['saldo']), 1) if item['saldo'] else 0
        item['riesgo'] = round(min(item['dso'] / 420, 1) * .45 + min(item['pct_glosa'] / 12, 1) * .30 + min(item['dso'] / 360, 1) * .25, 3)
        item['facturado'] = _dashboard_money(item['facturado'])
        item['saldo'] = _dashboard_money(item['saldo'])
        item['glosa'] = _dashboard_money(item['glosa'])
        item.pop('dias_ponderados', None)
        erps.append(item)
    erps.sort(key=lambda item: item['saldo'], reverse=True)
    serie = []
    for fecha in sorted({f.fecha_factura.replace(day=1) for f in qs if f.fecha_factura})[-12:]:
        mes_qs = qs.filter(fecha_factura__year=fecha.year, fecha_factura__month=fecha.month)
        serie.append({'periodo': fecha.strftime('%Y-%m'), 'facturado': _dashboard_money(mes_qs.aggregate(v=Sum('total_factura'))['v']), 'recaudado': _dashboard_money(EventoCartera.objects.filter(factura__in=mes_qs, tipo='ABONO').aggregate(v=Sum('valor'))['v'])})
    pct_rad = _dashboard_money(total_radicado / total_facturado * 100) if total_facturado else 0
    pct_glosa = _dashboard_money(total_glosa / total_radicado * 100) if total_radicado else 0
    alertas = []
    if pct_rad < 90:
        alertas.append({'nivel': 'atencion', 'titulo': 'Radicación pendiente', 'detalle': f'{100 - pct_rad:.1f}% del valor facturado aún no está radicado.'})
    if pct_glosa > 5:
        alertas.append({'nivel': 'riesgo', 'titulo': 'Glosa por encima del umbral', 'detalle': f'La glosa inicial representa {pct_glosa:.1f}% de lo radicado.'})
    if edades[-1]['saldo'] > 0:
        alertas.append({'nivel': 'critico', 'titulo': 'Cartera mayor a 360 días', 'detalle': f"{_dashboard_money(edades[-1]['saldo']):,.0f} COP requieren conciliación prioritaria."})
    glosas_por_vencer = radicadas.filter(
        fecha_glosa_inicial__isnull=False,
        fecha_limite_respuesta_glosa__gte=hoy,
        fecha_limite_respuesta_glosa__lte=hoy + timedelta(days=7),
        valor_glosa_inicial__gt=0,
    )
    if glosas_por_vencer.exists():
        valor_por_vencer = glosas_por_vencer.aggregate(v=Sum('valor_glosa_inicial'))['v'] or Decimal('0')
        alertas.append({'nivel': 'urgente', 'titulo': 'Glosas próximas a vencer', 'detalle': f'{glosas_por_vencer.count()} facturas por {_dashboard_money(valor_por_vencer):,.0f} COP vencen en los próximos 7 días.'})
    return Response({
        'actualizado': timezone.now().isoformat(),
        'kpis': {'facturado': _dashboard_money(total_facturado), 'radicado': _dashboard_money(total_radicado), 'glosa': _dashboard_money(total_glosa), 'abonos': _dashboard_money(total_abonos), 'saldo': _dashboard_money(saldo), 'pct_radicacion': pct_rad, 'pct_glosa': pct_glosa, 'dso': dso, 'facturas': qs.count(), 'radicadas': radicadas.count()},
        'edades': edades,
        'erps': erps[:10],
        'embudo': {'facturado': _dashboard_money(total_facturado), 'radicado': _dashboard_money(total_radicado), 'aceptado': _dashboard_money(total_radicado - total_glosa), 'recaudado': _dashboard_money(total_abonos), 'glosa_aceptada': _dashboard_money(total_aceptado), 'glosa_levantada': _dashboard_money(total_levantado)},
        'pagos': {'total': _dashboard_money(total_abonos), 'fecha_ultimo': eventos.filter(tipo='ABONO').aggregate(fecha=Max('fecha'))['fecha']},
        'serie': serie,
        'alertas': alertas,
    })


@api_view(['GET'])
def dashboard_factura(request):
    """Detalle de una factura para el drill-down del dashboard."""
    numero = (request.GET.get('numero') or '').strip()
    if not numero:
        return Response({'error': 'Debe indicar el número de factura.'}, status=400)
    factura = Factura.objects.select_related('erp', 'erp__tipo_erp').filter(num_factura=numero).first()
    if factura is None:
        return Response({'error': 'Factura no encontrada.'}, status=404)
    eventos = factura.eventos.order_by('fecha', 'id').values('tipo', 'fecha', 'valor', 'observacion')
    return Response({
        'factura': {
            'numero': factura.num_factura,
            'atencion': factura.id_atencion,
            'erp': factura.erp.nombre if factura.erp else None,
            'nit': factura.erp.nit if factura.erp else None,
            'tipo_erp': factura.erp.tipo_erp.nombre if factura.erp and factura.erp.tipo_erp else None,
            'fecha_factura': factura.fecha_factura,
            'fecha_radicacion': factura.fecha_radicacion_inicial,
            'fecha_glosa': factura.fecha_glosa_inicial,
            'fecha_limite_glosa': factura.fecha_limite_respuesta_glosa,
            'fecha_pago': factura.fecha_pago,
            'facturado': _dashboard_money(factura.total_factura),
            'glosa': _dashboard_money(factura.valor_glosa_inicial),
            'saldo': _dashboard_money(factura.saldo_actual),
            'estado': factura.estado_gestion,
            'eventos': list(eventos),
        }
    })


@api_view(['GET'])
def dashboard_pulse(request):
    """Latido liviano para refrescar tras una importación PAE/DIF."""
    ultimo_evento = EventoCartera.objects.aggregate(fecha=Max('fecha'))['fecha']
    ultima_factura = Factura.objects.aggregate(fecha=Max('fecha_importacion'))['fecha']
    return Response({
        'ultimo_evento': ultimo_evento.isoformat() if ultimo_evento else None,
        'ultima_importacion': ultima_factura.isoformat() if ultima_factura else None,
        'facturas': Factura.objects.count(),
    })
