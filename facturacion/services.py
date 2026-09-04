# facturacion/services.py
import pandas as pd
import io
import re
import hashlib
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from django.db import transaction       # Importación para el bloque atomic
from django.db.models import Q, Sum
from django.utils import timezone      # Importación para las fechas por defecto
from .models import Factura, EntidadResponsable, TipoERP, EventoCartera

# Función auxiliar para eliminar acentos y normalizar texto
def remover_acentos(texto):
    if texto is None:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    )

# Función auxiliar para normalizar nombres de columnas y alias
def normalizar_columna(texto):
    if texto is None:
        return ''
    texto = remover_acentos(str(texto)).strip().lower()
    texto = re.sub(r'[_\-\s]+', ' ', texto)
    texto = re.sub(r'[^a-z0-9 ]+', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def normalizar_telefono(valor):
    if valor is None or (isinstance(valor, str) and valor.strip().lower() in ['nan', 'none', 'nat', '']):
        return ''
    texto = str(valor).strip()
    numeros = re.sub(r'\D+', '', texto)
    if len(numeros) >= 7:
        return numeros
    return ''


def convertir_a_json_compatible(valor):
    """Convierte valores de pandas/NumPy/Decimal a tipos serializables en JSON."""
    if valor is None:
        return None

    try:
        if pd.isna(valor):
            return None
    except Exception:
        pass

    if isinstance(valor, str):
        texto = valor.strip()
        if texto.lower() in ['nan', 'none', 'null', '']:
            return None
        return valor

    if isinstance(valor, (int, bool)):
        return valor

    if isinstance(valor, float):
        if pd.isna(valor):
            return None
        return valor

    if isinstance(valor, Decimal):
        return str(valor)

    if isinstance(valor, (datetime, date)):
        return valor.isoformat()

    if isinstance(valor, (list, tuple)):
        return [convertir_a_json_compatible(item) for item in valor]

    if isinstance(valor, dict):
        return {str(k): convertir_a_json_compatible(v) for k, v in valor.items()}

    try:
        return convertir_a_json_compatible(valor.item())
    except Exception:
        pass

    return str(valor)


def convertir_a_decimal_excel(valor):
    """Convierte un valor de Excel a Decimal usando la lógica de importación y limita a 2 decimales."""
    try:
        if valor is None or pd.isna(valor):
            return None, 'vacío'
    except Exception:
        pass

    texto = str(valor).strip()
    if texto.lower() in ['nan', 'none', 'nat', '']:
        return None, 'vacío'

    negativo = False
    if texto.startswith('(') and texto.endswith(')'):
        negativo = True
        texto = texto[1:-1]

    texto = texto.replace('$', '').replace('€', '').replace('£', '').strip()
    texto = texto.replace(' ', '')
    texto = texto.replace('%', '')

    if texto.count(',') > 0 and texto.count('.') > 0:
        if texto.rfind(',') > texto.rfind('.'):
            texto = texto.replace('.', '').replace(',', '.')
        else:
            texto = texto.replace(',', '')
    elif texto.count(',') > 0 and texto.count('.') == 0:
        partes = texto.split(',')
        ultimo = partes[-1]
        if len(ultimo) in (1, 2):
            texto = texto.replace(',', '.')
        else:
            texto = texto.replace(',', '')

    texto = re.sub(r'[^0-9.\-+]', '', texto)
    if texto in ['', '.', '-', '-.', '+', '+.']:
        return None, 'vacío'

    if negativo and not texto.startswith('-'):
        texto = '-' + texto

    try:
        decimal_valor = Decimal(texto)
        return decimal_valor.quantize(Decimal('0.01')), None
    except (InvalidOperation, ValueError, TypeError):
        return None, f"El valor '{valor}' no es numérico"


def decimal_excel_seguro(valor, valor_por_defecto=Decimal('0.00')):
    """Convierte un valor de Excel a Decimal y devuelve un fallback seguro."""
    decimal_valor, _ = convertir_a_decimal_excel(valor)
    return decimal_valor if decimal_valor is not None else valor_por_defecto


def es_valor_excel_vacio(valor):
    if valor is None:
        return True
    try:
        if pd.isna(valor):
            return True
    except Exception:
        pass
    texto = str(valor).strip().lower()
    return texto in ['', 'nan', 'none', 'nat']


def validar_consistencia_aritmetica_dif(total_factura, copago, total_final=None, tolerancia=Decimal('0.01')):
    """Valida que los montos base de la factura sean numéricos y que total_final coincida si está presente."""
    bruto, error_bruto = convertir_a_decimal_excel(total_factura)
    descuento, error_descuento = convertir_a_decimal_excel(copago)
    final, error_final = convertir_a_decimal_excel(total_final)

    if error_bruto == 'vacío' and error_descuento == 'vacío' and error_final == 'vacío':
        return True, None

    if error_bruto and error_bruto != 'vacío':
        return False, error_bruto
    if error_descuento and error_descuento != 'vacío':
        return False, error_descuento
    if error_final and error_final != 'vacío':
        return False, error_final

    if bruto is None or descuento is None:
        return True, None

    if final is not None:
        esperado = max(Decimal('0.00'), bruto - descuento)
        if abs(final - esperado) > tolerancia:
            return False, (
                f"total_final {final} no coincide con total_factura {bruto} - copago {descuento} = {esperado}."
            )

    return True, None


def normalizar_texto_factura(valor):
    """Normaliza identificadores de factura para el cruce DIF/PAE."""
    if valor is None:
        return ''

    texto = str(valor).strip().lower()
    texto = texto.replace(' ', '')
    if texto.endswith('.0'):
        texto = texto[:-2]
    return texto


def buscar_factura_para_pae(num_factura, id_atencion=None):
    """Busca la factura DIF asociada a una fila PAE usando num_factura o id_atencion."""
    candidatos = []

    # Construir variantes razonables a partir de los valores recibidos
    for valor in (num_factura, id_atencion):
        if valor is None:
            continue
        raw = str(valor).strip()
        if raw == '' or raw.lower() in ['nan', 'none']:
            continue
        candidatos.append(raw)

    # Normalizaciones adicionales: quitar espacios, eliminar sufijo .0, y mantener solo alfanuméricos
    variantes = []
    for c in candidatos:
        variantes.append(c)
        variantes.append(normalizar_texto_factura(c))
        variantes.append(re.sub(r"[^0-9A-Za-z]", "", c))
        if c.endswith('.0'):
            variantes.append(c[:-2])

    vistos = set()
    for texto in variantes:
        if not texto:
            continue
        if texto in vistos:
            continue
        vistos.add(texto)

        # Intentos de búsqueda progresivos: exacto primero, luego contains
        factura = Factura.objects.filter(
            Q(num_factura__iexact=texto) |
            Q(id_atencion__iexact=texto)
        ).first()
        if factura:
            return factura

        factura = Factura.objects.filter(
            Q(num_factura__icontains=texto) |
            Q(id_atencion__icontains=texto)
        ).first()
        if factura:
            return factura

    return None


def validar_integridad_datos_excel(total_factura, total_final=None, fecha_factura=None, num_factura=None):
    """
    Valida que los campos clave del Excel tengan el tipo y formato correctos.
    La verificación se centra en total_factura y en la consistencia básica del
    archivo, sin alertar por un valor opcional de total_final.
    """
    errores = []

    decimal_valor, error = convertir_a_decimal_excel(total_factura)
    if error:
        errores.append('total_factura debe ser un valor numérico válido.')

    if fecha_factura not in (None, '', 'nan', 'None', 'NaN'):
        try:
            if isinstance(fecha_factura, pd.Timestamp):
                fecha_factura = fecha_factura.date()
            elif isinstance(fecha_factura, datetime):
                fecha_factura = fecha_factura.date()
            else:
                texto_fecha = str(fecha_factura).strip()
                try:
                    fecha_factura = datetime.strptime(texto_fecha, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        fecha_factura = datetime.strptime(texto_fecha, '%d/%m/%Y').date()
                    except ValueError:
                        fecha_factura = pd.to_datetime(texto_fecha, errors='raise').date()
        except Exception:
            errores.append('fecha_factura debe tener un formato de fecha válido.')

    if num_factura is not None and str(num_factura).strip().lower() in ['', 'nan', 'none']:
        errores.append('num_factura no puede estar vacío.')

    if errores:
        return False, ' '.join(errores)

    return True, None


def _obtener_valor_pae(factura, claves):
    """Obtiene un valor del bloque PAE guardado en la factura, tolerando varios nombres de clave."""
    if not factura.pae_datos_origen:
        return None

    raw_row = factura.pae_datos_origen.get('raw_row') or {}
    if not isinstance(raw_row, dict):
        return None

    for clave in claves:
        if clave in raw_row:
            return raw_row.get(clave)

    normalized_aliases = {normalizar_columna(k): k for k in raw_row.keys()}
    for clave in claves:
        alias_norm = normalizar_columna(clave)
        if alias_norm in normalized_aliases:
            return raw_row.get(normalized_aliases[alias_norm])

    return None


def _formatear_valor_export(valor):
    if valor is None:
        return ''
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (datetime, date)):
        return valor.date() if isinstance(valor, datetime) else valor
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime().date() if hasattr(valor, 'to_pydatetime') else valor
    if isinstance(valor, (int, float)):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        if texto == '':
            return ''
        try:
            return Decimal(texto)
        except Exception:
            pass
    return str(valor)


def _resolver_valor_a_exportar(valor, fallback):
    if valor is None:
        return fallback
    if isinstance(valor, str) and valor.strip() == '':
        return fallback
    return valor


def _sumar_eventos_por_tipo(factura, tipo_evento):
    return factura.eventos.filter(tipo=tipo_evento).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')


def _base_neto_factura(factura):
    """Valor neto real: bruto menos pagos (aceptado IPS + abonos + RTF)."""
    bruto = factura.total_factura or Decimal('0.00')
    pagos = factura.pagos_total
    return max(Decimal('0.00'), bruto - pagos)


def construir_dataframe_exportacion_eas(queryset):
    """Construye un DataFrame consolidado con columnas DIF y columnas PAE para exportar a EAS."""
    registros = []

    for factura in queryset.select_related('erp'):
        raw_pae = factura.pae_datos_origen.get('raw_row', {}) if factura.pae_datos_origen else {}

        valor_glosa_pae = _obtener_valor_pae(factura, ['vlr_glosa_inicial', 'vlr glosa inicial', 'vlr_glosa', 'valor glosa inicial'])
        valor_aceptado_pae = _obtener_valor_pae(factura, ['vlr_aceptado_ips', 'vlr aceptado ips', 'vlr aceptado', 'valor aceptado ips'])
        valor_levantado_pae = _obtener_valor_pae(factura, ['vlr_levantado_erp', 'vlr levantado erp', 'vlr levantado', 'valor levantado erp'])
        abono_1_pae = _obtener_valor_pae(factura, ['vlr_abono_1', 'vlr abono 1'])
        abono_2_pae = _obtener_valor_pae(factura, ['vlr_abono_2', 'vlr abono 2'])
        abono_3_pae = _obtener_valor_pae(factura, ['vlr_abono_3', 'vlr abono 3'])
        abono_4_pae = _obtener_valor_pae(factura, ['vlr_abono_4', 'vlr abono 4'])
        total_abonos_pae = _obtener_valor_pae(factura, ['vlr_total_abonos', 'vlr total abonos', 'total abonos'])
        rtf_pae = _obtener_valor_pae(factura, ['vlr_rtf', 'vlr rtf', 'rtf', 'valor rtf'])
        saldo_pae = _obtener_valor_pae(factura, ['saldo_factura', 'saldo factura', 'saldo', 'saldo_final'])

        fecha_radicacion_pae = _obtener_valor_pae(factura, ['fecha_radicacion', 'fecha radicacion', 'fecha_radicacion_inicial', 'fecha de radicacion'])
        fecha_devolucion_pae = _obtener_valor_pae(factura, ['fecha_devolucion', 'fecha devolucion'])
        fecha_glosa_pae = _obtener_valor_pae(factura, ['fecha_glosa_inicial', 'fecha glosa inicial', 'fecha_glosa', 'fecha glosa'])

        valor_glosa_export = _resolver_valor_a_exportar(valor_glosa_pae, factura.valor_glosa_inicial or _sumar_eventos_por_tipo(factura, 'GLO_INI'))
        valor_aceptado_export = _resolver_valor_a_exportar(valor_aceptado_pae, _sumar_eventos_por_tipo(factura, 'GLO_ACEP'))
        valor_levantado_export = _resolver_valor_a_exportar(valor_levantado_pae, _sumar_eventos_por_tipo(factura, 'GLO_LEV'))
        total_abonos_export = _resolver_valor_a_exportar(total_abonos_pae, _sumar_eventos_por_tipo(factura, 'ABONO'))
        rtf_export = _resolver_valor_a_exportar(rtf_pae, _sumar_eventos_por_tipo(factura, 'RTF'))

        total_final_export = _base_neto_factura(factura)

        base_saldo = _base_neto_factura(factura)
        saldo_export = _resolver_valor_a_exportar(
            saldo_pae,
            factura.saldo_actual if factura.saldo_actual not in (None, Decimal('0.00')) else base_saldo
        )

        registro = {
            'Id Tercero': factura.erp.nit if factura.erp else '',
            'Nombre Tercero': factura.erp.nombre if factura.erp else '',
            'Nombre Contrato': factura.id_contrato or '',
            'Id Atencion': factura.id_atencion or '',
            'Fecha Admision': factura.fecha_admision,
            'Hist Clinica': factura.historia_clinica or '',
            'Nombre de Paciente': factura.nombre_paciente or '',
            'Nivel Sisben': factura.nivel_sisben or '',
            'Tipo Usuario': factura.tipo_usuario or '',
            'Tipo Afiliado': factura.tipo_afiliado or '',
            'Tel Celular': factura.tel_celular or '',
            'Telefono': factura.telefono or '',
            'Valor Pagado': factura.valor_pagado_caja or Decimal('0.00'),
            'Copago': factura.copago or Decimal('0.00'),
            'Copago Per': factura.copago_per_desc or Decimal('0.00'),
            'Desc Copago': '',
            'Cerrada': factura.cerrada or '',
            'Liquidada': factura.liquidada or '',
            'Facturada': factura.facturada_status or '',
            'NFact': factura.num_factura or '',
            'Total Factura': factura.total_factura or Decimal('0.00'),
            'Fecha Factura': factura.fecha_factura,
            'Fecha Radicacion': factura.fecha_radicacion_inicial,
            'Total Final': total_final_export,
            'Id Cajero': factura.id_cajero or '',
            'Nom Canal': factura.nom_canal or '',
            'Nombre IPS': factura.nombre_ips or '',
            'Nombre_Tercero': _formatear_valor_export(raw_pae.get('Nombre_Tercero') or raw_pae.get('nombre_tercero') or raw_pae.get('nombre tercero') or factura.erp.nombre if factura.erp else ''),
            'Nombre_Contrato': _formatear_valor_export(raw_pae.get('Nombre_Contrato') or raw_pae.get('nombre_contrato') or raw_pae.get('nombre contrato') or factura.id_contrato or ''),
            'num_factura': factura.num_factura or '',
            'Total_Factura': _formatear_valor_export(raw_pae.get('Total_Factura') or raw_pae.get('total_factura') or factura.total_factura or Decimal('0.00')),
            'fecha_radicacion': _formatear_valor_export(fecha_radicacion_pae or factura.fecha_radicacion_inicial),
            'fecha_devolucion': _formatear_valor_export(fecha_devolucion_pae or factura.fecha_devolucion),
            'Fecha_glosa_inicial': _formatear_valor_export(fecha_glosa_pae or next((evento.fecha for evento in factura.eventos.filter(tipo='GLO_INI').order_by('fecha')[:1]), None)),
            'vlr_glosa_inicial': _formatear_valor_export(valor_glosa_export),
            'vlr_aceptado_ips': _formatear_valor_export(valor_aceptado_export),
            'vlr_levantado_erp': _formatear_valor_export(valor_levantado_export),
            'vlr_Abono_1': _formatear_valor_export(abono_1_pae if abono_1_pae is not None else Decimal('0.00')),
            'vlr_Abono_2': _formatear_valor_export(abono_2_pae if abono_2_pae is not None else Decimal('0.00')),
            'vlr_Abono_3': _formatear_valor_export(abono_3_pae if abono_3_pae is not None else Decimal('0.00')),
            'vlr_Abono_4': _formatear_valor_export(abono_4_pae if abono_4_pae is not None else Decimal('0.00')),
            'fecha_abono_1': '',
            'fecha_abono_2': '',
            'fecha_abono_3': '',
            'fecha_abono_4': '',
            'vlr_Total_Abonos': _formatear_valor_export(total_abonos_export),
            'vlr_rtf': _formatear_valor_export(rtf_export),
            'saldo_factura': _formatear_valor_export(saldo_export),
        }
        registros.append(registro)

    columnas_orden = [
        'Id Tercero', 'Nombre Tercero', 'Nombre Contrato', 'Id Atencion', 'Fecha Admision', 'Hist Clinica',
        'Nombre de Paciente', 'Nivel Sisben', 'Tipo Usuario', 'Tipo Afiliado', 'Tel Celular', 'Telefono',
        'Valor Pagado', 'Copago', 'Copago Per', 'Desc Copago', 'Cerrada', 'Liquidada', 'Facturada', 'NFact',
        'Total Factura', 'Fecha Factura', 'Fecha Radicacion', 'Total Final', 'Id Cajero', 'Nom Canal', 'Nombre IPS',
        'Nombre_Tercero', 'Nombre_Contrato', 'num_factura', 'Total_Factura', 'fecha_radicacion', 'fecha_devolucion',
        'Fecha_glosa_inicial', 'vlr_glosa_inicial', 'vlr_aceptado_ips', 'vlr_levantado_erp', 'vlr_Abono_1',
        'fecha_abono_1', 'vlr_Abono_2', 'fecha_abono_2', 'vlr_Abono_3', 'fecha_abono_3', 'vlr_Abono_4',
        'fecha_abono_4', 'vlr_Total_Abonos', 'vlr_rtf', 'saldo_factura'
    ]

    return pd.DataFrame(registros, columns=columnas_orden)


# Función auxiliar mantenida por compatibilidad; ya no se usa para la alerta aritmética.
def validar_consistencia_dinero(valor_bruto, copago, valor_neto, tolerancia=Decimal('0.01')):
    """
    Se mantiene por compatibilidad, pero la validación real del DIF ahora se hace
    a través de validar_integridad_datos_excel.
    """
    return True, None

def prechequear_excel_cartera(archivo_django):
    """
    Escanea el Excel en busca de facturas que ya existen en la base (posibles duplicados).
    Devuelve una lista de duplicados con datos resumidos para que la UI pueda mostrar opciones.
    """
    contenido_bytes = archivo_django.read()
    nombre_archivo = archivo_django.name.lower()

    def cargar_hoja_excel(bytes_data):
        buffer = io.BytesIO(bytes_data)
        if nombre_archivo.endswith('.xls') and not nombre_archivo.endswith('.xlsx'):
            xls = pd.ExcelFile(buffer, engine='xlrd')
        else:
            xls = pd.ExcelFile(buffer)

        for hoja in xls.sheet_names:
            try:
                df_hoja = pd.read_excel(xls, sheet_name=hoja, dtype=str)
            except Exception:
                continue
            if not df_hoja.empty and df_hoja.shape[1] > 1:
                return df_hoja, hoja

        if nombre_archivo.endswith('.xls') and not nombre_archivo.endswith('.xlsx'):
            return pd.read_excel(io.BytesIO(bytes_data), engine='xlrd', dtype=str), xls.sheet_names[0]
        return pd.read_excel(io.BytesIO(bytes_data), dtype=str), xls.sheet_names[0]

    df, hoja_usada = cargar_hoja_excel(contenido_bytes)
    if df.empty:
        return []

    df.columns = [normalizar_columna(c) for c in df.columns]

    # Reutilizar alias mapping mínimo para detectar num_factura y fecha
    posibles_nfact = ['nfact', 'nfactura', 'num_factura', 'numero factura', 'factura']
    posibles_fecha = ['fecha_factura', 'fecha factura', 'fecha_facturacion']
    normalized_columns = {normalizar_columna(col): col for col in df.columns}
    col_nfact = None
    col_fecha = None
    for alias in posibles_nfact:
        a = normalizar_columna(alias)
        if a in normalized_columns:
            col_nfact = normalized_columns[a]
            break
    for alias in posibles_fecha:
        a = normalizar_columna(alias)
        if a in normalized_columns:
            col_fecha = normalized_columns[a]
            break

    duplicados = []
    for idx, fila in df.iterrows():
        nfact_raw = str(fila.get(col_nfact) or '').strip() if col_nfact else ''
        if nfact_raw.endswith('.0'):
            nfact_raw = nfact_raw[:-2]
        if not nfact_raw:
            continue
        id_atencion_valor = fila.get('id_atencion') if 'id_atencion' in df.columns else None
        factura_existente = buscar_factura_para_pae(nfact_raw, id_atencion_valor)
        if factura_existente:
            total_raw = fila.get('total_factura') or ''
            fecha_raw = fila.get(col_fecha) if col_fecha else None
            fecha_parsed = None
            # Parser local de fecha para el prechequeo (evita dependencia de la función interna)
            def _parse_date_local(valor):
                if not valor or pd.isna(valor) or str(valor).strip() in ['nan', '', 'nat', 'n', 'c', 'none']:
                    return None
                text = str(valor).strip().split()[0]
                try:
                    return datetime.strptime(text, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        return datetime.strptime(text, "%d/%m/%Y").date()
                    except ValueError:
                        return None

            try:
                fecha_parsed = _parse_date_local(fecha_raw)
            except Exception:
                fecha_parsed = None
            duplicados.append({
                'fila_excel': idx + 2,
                'fila_idx': idx,
                'num_factura': nfact_raw,
                'total_importado_raw': convertir_a_json_compatible(total_raw),
                'fecha_importada': convertir_a_json_compatible(fecha_parsed),
                'factura_existente_id': factura_existente.id,
                'factura_existente_num': factura_existente.num_factura,
                'factura_existente_total': convertir_a_json_compatible(factura_existente.total_factura),
                'factura_existente_fecha': convertir_a_json_compatible(factura_existente.fecha_factura),
            })

    return duplicados


def importar_excel_cartera(archivo_django, tipo_erp_predefinido='Por Clasificar', duplicate_resolutions=None):
    # Leer el contenido en bytes del archivo cargado
    contenido_bytes = archivo_django.read()
    nombre_archivo = archivo_django.name.lower()

    def cargar_hoja_excel(bytes_data):
        buffer = io.BytesIO(bytes_data)
        if nombre_archivo.endswith('.xls') and not nombre_archivo.endswith('.xlsx'):
            xls = pd.ExcelFile(buffer, engine='xlrd')
        else:
            xls = pd.ExcelFile(buffer)

        for hoja in xls.sheet_names:
            try:
                df_hoja = pd.read_excel(xls, sheet_name=hoja, dtype=str)
            except Exception:
                continue
            if not df_hoja.empty and df_hoja.shape[1] > 1:
                return df_hoja, hoja

        # Fallback al primer sheet si ninguna hoja tuvo datos válidos
        if nombre_archivo.endswith('.xls') and not nombre_archivo.endswith('.xlsx'):
            return pd.read_excel(io.BytesIO(bytes_data), engine='xlrd', dtype=str), xls.sheet_names[0]
        return pd.read_excel(io.BytesIO(bytes_data), dtype=str), xls.sheet_names[0]

    def cargar_hoja_excel_con_headers(bytes_data):
        sheet, hoja = cargar_hoja_excel(bytes_data)
        return sheet, hoja

    df, hoja_usada = cargar_hoja_excel(contenido_bytes)
    if df.empty:
        raise ValueError("El Excel no contiene datos en ninguna hoja válida.")

    df.columns = [normalizar_columna(c) for c in df.columns]
    print(f"🔎 [DEBUG] Hoja seleccionada: {hoja_usada}, columnas normalizadas: {list(df.columns)}")

    alias_columnas = {
        'nit_tercero': ['id tercero', 'nit tercero', 'id_tercero', 'nit_tercero', 'tercero'],
        'nombre_tercero': ['nombre tercero', 'nombre_tercero', 'entidad responsable', 'eps', 'entidad'],
        'id_contrato': ['nombre contrato', 'nombre_contrato', 'contrato', 'id contrato'],
        'id_atencion': ['id atencion', 'id_atencion', 'atencion'],
        'fecha_admision': ['fecha admision', 'fecha_admision', 'admision'],
        'hist_clinica': ['hist clinica', 'historia clinica', 'historia_clinica', 'hist_clinica', 'hc', 'historia'],
        'nombre_paciente': ['nombre de paciente', 'nombre paciente', 'nombre_paciente', 'paciente', 'paciente nombre'],
        'nivel_sisben': ['nivel sisben', 'nivel_sisben', 'sisben'],
        'tipo_usuario': ['tipo usuario', 'tipo_usuario'],
        'tipo_afiliado': ['tipo afiliado', 'tipo_afiliado'],
        'tipo_erp': ['tipo erp', 'tipo_erp', 'regimen', 'regimen afiliacion', 'tipo regimen', 'regimen de importacion', 'tipo de regimen', 'regimen de afiliacion'],
        'tel_celular': ['tel celular', 'tel_celular', 'celular', 'telefono movil'],
        'telefono': ['telefono', 'teléfono', 'tel', 'telefono fijo'],
        'valor_pagado': ['valor pagado', 'valor_pagado', 'valorpagado'],
        'copago': ['copago'],
        'copago_per': ['copago per', 'copago_per', 'copagoper'],
        'desc_copago': ['desc copago', 'desc_copago', 'descopago'],
        'cerrada': ['cerrada'],
        'liquidada': ['liquidada'],
        'facturada': ['facturada'],
        'nfact': ['nfact', 'nfactura', 'n factura', 'num factura', 'num_factura', 'numfactura', 'numero factura', 'numero de factura', 'numero_factura', 'número factura', 'número de factura', 'factura'],
        'total_factura': ['total factura', 'total_factura', 'valor factura', 'valor_factura', 'total'],
        'fecha_factura': ['fecha factura', 'fecha_factura', 'fecha_facturacion', 'fecha de factura'],
        'fecha_radicacion': ['fecha radicacion', 'fecha_radicacion', 'fecha_radicacion_inicial', 'fecha radicacion inicial'],
        'total_final': ['total final', 'total_final', 'total_neto', 'valor final', 'total cartera', 'total_cartera'],
        'id_cajero': ['id cajero', 'id_cajero'],
        'nom_canal': ['nom canal', 'nom_canal', 'canal'],
        'nombre_ips': ['nombre ips', 'nombre_ips', 'ips', 'nombre clinica', 'nombre_clinica', 'nombre de la clinica', 'clinica', 'nombre_clinica', 'ips nombre'],
    }

    def encontrar_columna_real(dataframe, aliases):
        normalized_columns = {normalizar_columna(col): col for col in dataframe.columns}
        for alias in aliases:
            alias_norm = normalizar_columna(alias)
            if alias_norm in normalized_columns:
                return normalized_columns[alias_norm]
        return None

    columnas = {clave: encontrar_columna_real(df, aliases) for clave, aliases in alias_columnas.items()}
    columnas_faltantes = [clave for clave, valor in columnas.items() if not valor and clave in ['nfact', 'hist_clinica', 'nombre_paciente']]
    if columnas_faltantes:
        print(f"⚠️ [ADVERTENCIA] No se encontraron las columnas requeridas: {columnas_faltantes}")
        print(f"    Columnas normalizadas detectadas: {list(df.columns)}")
        # Intentamos leer usando una fila de header superior si las columnas no aparecen en la primera fila.
        for header_row in [1, 2, 3]:
            try:
                if nombre_archivo.endswith('.xls') and not nombre_archivo.endswith('.xlsx'):
                    df_alt = pd.read_excel(io.BytesIO(contenido_bytes), engine='xlrd', header=header_row, dtype=str)
                else:
                    df_alt = pd.read_excel(io.BytesIO(contenido_bytes), header=header_row, dtype=str)
            except Exception:
                continue
            if df_alt.empty:
                continue
            df_alt.columns = [normalizar_columna(c) for c in df_alt.columns]
            nuevas_columnas = {clave: encontrar_columna_real(df_alt, aliases) for clave, aliases in alias_columnas.items()}
            if all(nuevas_columnas[k] for k in ['nfact', 'hist_clinica', 'nombre_paciente']):
                df = df_alt
                columnas = nuevas_columnas
                print(f"✅ [INFO] Releyendo Excel con header={header_row} en la hoja '{hoja_usada}'. Columnas encontradas: {columnas}")
                break
        else:
            # Antes de fallar, intentamos detectar si el archivo corresponde
            # a una plantilla PAE (abonos/rtf) y reenviarlo al importador PAE.
            normalized_cols = set(df.columns)
            posible_pae_aliases = ['vlr_abono_1', 'vlr_total_abonos', 'vlr_rtf', 'fecha_abono_1']
            is_pae_like = any(normalizar_columna(a) in normalized_cols for a in posible_pae_aliases)
            if is_pae_like:
                print("⚠️ [INFO] Archivo parece PAE, reenviando al importador PAE automáticamente.")
                from types import SimpleNamespace
                file_like = SimpleNamespace(read=lambda: contenido_bytes, name=nombre_archivo)
                return importar_eventos_pae(file_like)

            raise ValueError(
                f"No se encontraron las columnas claves en el Excel tras intentarlo con headers alternativos: {columnas_faltantes}. "
                f"Columnas detectadas: {list(df.columns)}"
            )
    
    creadas = 0
    actualizadas = 0
    alertas_aritmeticas = []
    resumen = {
        'tipo': 'DIF',
        'filas_en_excel': 0,
        'filas_procesadas': 0,
        'creadas': 0,
        'actualizadas': 0,
        'filas_omitidas': 0,
        'filas_duplicadas': 0,
        'duplicados': [],
        'alertas_aritmeticas': [],
        'errores': [],
    }
    # Añadir información sobre columnas detectadas y mapeadas para auditoría
    resumen['columnas_detectadas'] = list(df.columns)
    resumen['columnas_mapeadas'] = {k: (v if v else None) for k, v in columnas.items()}
    
    # Función auxiliar para convertir las fechas colombianas del Excel
    def limpiar_fecha(valor):
        if not valor or pd.isna(valor) or str(valor).strip() in ['nan', '', 'nat', 'n', 'c', 'none']:
            return None
        text = str(valor).strip().split()[0]
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            try:
                return datetime.strptime(text, "%d/%m/%Y").date()
            except ValueError:
                return None

    def normalizar_texto(valor):
        if valor is None or pd.isna(valor):
            return ''
        texto = remover_acentos(str(valor).strip())
        texto = texto.replace('_', ' ')
        texto = re.sub(r'\s+', ' ', texto)
        return texto.upper()

    def comparar_regimen(regimen_fila, tipo_erp_seleccionado):
        if not regimen_fila:
            return False
        regimen_normal = limpiar_regimen_registrado(regimen_fila)
        seleccion_normal = limpiar_regimen_registrado(tipo_erp_seleccionado)
        if not regimen_normal or not seleccion_normal:
            return False
        return regimen_normal == seleccion_normal

    def inferir_regimen_por_contrato(nombre_contrato):
        if not nombre_contrato:
            return ''
        texto = normalizar_texto(nombre_contrato)
        # Solo consideramos los regímenes que tenemos claros para importar.
        if re.search(r'\bCONT\b|\bCONTRIBUTIVO\b|\bCONTRIB\b', texto):
            return 'Régimen Contributivo'
        if re.search(r'\bSUB\b|\bSUBSIDIADO\b|\bSISBEN\b', texto):
            return 'Régimen Subsidiado'
        return ''

    def limpiar_regimen_registrado(regimen):
        if not regimen:
            return ''
        texto = normalizar_texto(regimen)
        if re.search(r'\bCONT\b|\bCONTRIBUTIVO\b|\bCONTRIB\b', texto):
            return 'Régimen Contributivo'
        if re.search(r'\bSUB\b|\bSUBSIDIADO\b|\bSISBEN\b', texto):
            return 'Régimen Subsidiado'
        return ''

    # Función auxiliar para limpiar números y dinero (devuelve Decimal para precisión)
    def limpiar_dinero(valor, campo=None, fila_idx=None):
        if valor is None or pd.isna(valor) or str(valor).strip().lower() in ['nan', '']:
            return Decimal('0.00')
        s_raw = str(valor).strip()
        s = s_raw
        # Manejar negativos con paréntesis
        negativo = False
        if s.startswith('(') and s.endswith(')'):
            negativo = True
            s = s[1:-1]

        # Eliminar símbolos de moneda y espacios
        s = s.replace('$', '').replace('€', '').replace('£', '').strip()
        s = s.replace(' ', '')

        # Quitar porcentaje si existe
        s = s.replace('%', '')

        # Detectar formatos tipo europeo: '1.234.567,89' -> quitar puntos de miles y convertir coma decimal
        if s.count(',') > 0 and s.count('.') > 0:
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        else:
            # Si solo hay comas, decidir si son separador decimal o de miles
            if s.count(',') > 0 and s.count('.') == 0:
                last = s.split(',')[-1]
                if len(last) in (1, 2):
                    s = s.replace(',', '.')
                else:
                    s = s.replace(',', '')

        # Eliminar cualquier caracter no numérico excepto punto y signo
        s = re.sub(r'[^0-9.\-]', '', s)
        if negativo and not s.startswith('-'):
            s = '-' + s

        if s in ['', '.', '-', '-.']:
            return Decimal('0.00')

        try:
            return Decimal(s).quantize(Decimal('0.01'))
        except Exception as e:
            print(f"❌ [ERROR_DECIMAL] fila={fila_idx} campo={campo} valor_raw={s_raw!r} valor_limpio={s!r} error={type(e).__name__}:{e}")
            return Decimal('0.00')

    def obtener_valor(fila, claves):
        for clave in claves:
            valor = fila.get(clave)
            if valor is not None:
                return valor
        return None

    def limpiar_campo_vacio(val):
        text = str(val or '').strip()
        return '' if text.lower() in ['nan', '0', '0.0', 'none', 'nat'] else text

    duplicados_en_archivo = set()
    if columnas.get('nfact'):
        facturas_archivo = df[columnas['nfact']].map(limpiar_campo_vacio)
        duplicados_en_archivo = set(facturas_archivo[facturas_archivo.duplicated(keep=False)]) - {''}

    def es_misma_fecha_factura(fecha_a, fecha_b):
        if fecha_a is None and fecha_b is None:
            return True
        return fecha_a == fecha_b

    def registrar_duplicado(factura, fila_idx, mensaje, fecha_importada=None, fecha_existente=None):
        resumen['filas_duplicadas'] += 1
        resumen['duplicados'].append(mensaje)
        datos_origen = dict(factura.datos_origen or {})
        duplicados = datos_origen.get('duplicados', [])
        duplicados.append({
            'fila_excel': fila_idx + 2,
            'mensaje': mensaje,
            'num_factura': factura.num_factura,
            'fecha_factura_existente': convertir_a_json_compatible(fecha_existente),
            'fecha_factura_importada': convertir_a_json_compatible(fecha_importada),
        })
        datos_origen['duplicados'] = duplicados
        factura.datos_origen = datos_origen
        try:
            factura.save(update_fields=['datos_origen'])
        except Exception:
            # No bloquear la importación por fallos de logging
            pass

    # Usamos transacciones atómicas para optimizar el insert masivo de tus +7,000 datos en PostgreSQL
    with transaction.atomic():
        for idx, fila in df.iterrows():
            try:
                with transaction.atomic():
                    # Extracción y estandarización limpia de identificadores primarios
                    nfact_original = limpiar_campo_vacio(fila.get(columnas.get('nfact')))
                    hist_clinica = limpiar_campo_vacio(fila.get(columnas.get('hist_clinica')))
                    nombre_paciente = limpiar_campo_vacio(fila.get(columnas.get('nombre_paciente')))

                    nit_tercero = limpiar_campo_vacio(fila.get(columnas.get('nit_tercero')))
                    if not nit_tercero:
                        nit_tercero = '0'
                    if nit_tercero.endswith('.0'):
                        nit_tercero = nit_tercero[:-2]

                    nombre_tercero = limpiar_campo_vacio(fila.get(columnas.get('nombre_tercero')))
                    if not nombre_tercero:
                        nombre_tercero = 'ENTIDAD NO ESPECIFICADA'

                    # REGLA DE SEGURIDAD FLEXIBLE: 
                    # Únicamente nos saltamos la línea si carece por completo de Factura, HC Y Nombre.
                    if not nfact_original and not hist_clinica and not nombre_paciente:
                        continue

                    # Quitar el .0 flotante residual de conversión si existe
                    if nfact_original.endswith('.0'):
                        nfact_original = nfact_original[:-2]
                    if hist_clinica.endswith('.0'):
                        hist_clinica = hist_clinica[:-2]

                    if nfact_original in duplicados_en_archivo:
                        factura_existente = Factura.objects.filter(num_factura=nfact_original).first()
                        referencia = 'la factura existente y las filas repetidas' if factura_existente else 'la fila original y la fila repetida'
                        mensaje_dup = f'Factura {nfact_original}: {referencia} se omitieron por duplicada.'
                        resumen['filas_duplicadas'] += 1
                        resumen['filas_omitidas'] += 1
                        resumen['duplicados'].append(mensaje_dup)
                        resumen['errores'].append(mensaje_dup)
                        continue

                    # Extracción de Fechas Reales del entorno clínico
                    f_factura = limpiar_fecha(fila.get(columnas.get('fecha_factura')))
                    f_radicacion = limpiar_fecha(fila.get(columnas.get('fecha_radicacion')))
                    f_admision = limpiar_fecha(fila.get(columnas.get('fecha_admision')))

                    tipo_erp_fila = limpiar_regimen_registrado(fila.get(columnas.get('tipo_erp'))) if columnas.get('tipo_erp') else ''
                    tipo_erp_por_contrato = inferir_regimen_por_contrato(fila.get(columnas.get('id_contrato')))
                    if not tipo_erp_fila and tipo_erp_por_contrato:
                        tipo_erp_fila = tipo_erp_por_contrato

                    if tipo_erp_fila:
                        tipo_erp_asignado = tipo_erp_fila
                    else:
                        tipo_erp_asignado = 'Por Clasificar'

                    if tipo_erp_fila and tipo_erp_predefinido != 'Por Clasificar' and not comparar_regimen(tipo_erp_fila, tipo_erp_predefinido):
                        resumen['filas_omitidas'] += 1
                        continue

                    if not nfact_original:
                        id_atencion_valor = limpiar_campo_vacio(fila.get(columnas.get('id_atencion')))
                        if id_atencion_valor.endswith('.0'):
                            id_atencion_valor = id_atencion_valor[:-2]
                        if id_atencion_valor:
                            num_fac = f"NOFACT-{id_atencion_valor}"
                        else:
                            datos_clave = f"{nit_tercero}_{hist_clinica}_{nombre_paciente}_{str(f_admision or '')}"
                            hash_id = hashlib.md5(datos_clave.encode()).hexdigest()[:8].upper()
                            num_fac = f"NOFACT-{hash_id}"
                    else:
                        num_fac = nfact_original
                        id_atencion_valor = limpiar_campo_vacio(fila.get(columnas.get('id_atencion')))
                        if id_atencion_valor.endswith('.0'):
                            id_atencion_valor = id_atencion_valor[:-2]

                    tipo_base, _ = TipoERP.objects.get_or_create(nombre=tipo_erp_asignado)
                    eps, _ = EntidadResponsable.objects.get_or_create(
                        nit=nit_tercero,
                        defaults={'nombre': nombre_tercero, 'tipo_erp': tipo_base}
                    )

                    # Validación de integridad de datos del Excel (tipo, formato y campos clave).
                    raw_total_factura = fila.get(columnas.get('total_factura'))
                    raw_total_final = fila.get(columnas.get('total_final'))
                    raw_copago = fila.get(columnas.get('copago'))
                    raw_fecha_factura = fila.get(columnas.get('fecha_factura'))

                    es_valido, msg_error = validar_integridad_datos_excel(
                        raw_total_factura,
                        raw_total_final,
                        raw_fecha_factura,
                        nfact_original or num_fac,
                    )
                    if not es_valido:
                        alertas_aritmeticas.append(f"Factura {num_fac}: {msg_error}")
                        print(f"⚠️ [VALIDACIÓN DIF] Factura {num_fac}: {msg_error}")

                    es_aritmetico_valido, msg_aritmetico = validar_consistencia_aritmetica_dif(
                        raw_total_factura,
                        raw_copago,
                        raw_total_final,
                    )
                    if not es_aritmetico_valido:
                        alertas_aritmeticas.append(f"Factura {num_fac}: {msg_aritmetico}")
                        print(f"⚠️ [ARITMÉTICA DIF] Factura {num_fac}: {msg_aritmetico}")

                    # Extracción de Dinero, Cartera y Copagos
                    total_factura = limpiar_dinero(raw_total_factura, 'total_factura', idx)
                    total_final = limpiar_dinero(raw_total_final, 'total_final', idx)
                    copago = limpiar_dinero(raw_copago, 'copago', idx)
                    valor_pagado_caja = limpiar_dinero(fila.get(columnas.get('valor_pagado')), 'valor_pagado', idx)

                    # Si no viene total_final en el Excel, inferirlo como total_factura - copago
                    # y generar una alerta para trazabilidad.
                    if es_valor_excel_vacio(raw_total_final) and total_factura is not None:
                        inferido = (total_factura - copago) if copago is not None else total_factura
                        alertas_aritmeticas.append(
                            f"Fila {idx+2} (Factura {num_fac}): total_final ausente; inferido {inferido} desde total_factura({total_factura}) - copago({copago})."
                        )
                        total_final = inferido

                    # Banderas de auditoría e IPS
                    es_cerrada = str(fila.get(columnas.get('cerrada')) or '').strip().upper() in ['TRUE', 'SI', '1', 'VERDADERO']
                    es_liquidada = str(fila.get(columnas.get('liquidada')) or '').strip().upper() in ['TRUE', 'SI', '1', 'VERDADERO']

                    factura_obj = None
                    if id_atencion_valor:
                        factura_obj = Factura.objects.filter(id_atencion=id_atencion_valor).first()
                    if not factura_obj and nfact_original:
                        factura_obj = Factura.objects.filter(num_factura=nfact_original).first()

                    if factura_obj:
                        created = False
                        if nfact_original and factura_obj.num_factura != nfact_original:
                            if not Factura.objects.exclude(pk=factura_obj.pk).filter(num_factura=nfact_original).exists():
                                factura_obj.num_factura = nfact_original
                        if id_atencion_valor and factura_obj.id_atencion != id_atencion_valor:
                            factura_obj.id_atencion = id_atencion_valor

                        fecha_existente = factura_obj.fecha_factura
                        fecha_importada = f_factura or f_admision
                        # Si hay una resolución proporcionada para esta fila, aplicarla.
                        if duplicate_resolutions and isinstance(duplicate_resolutions, dict) and idx in duplicate_resolutions:
                            decision = duplicate_resolutions.get(idx)
                            if decision == 'incoming':
                                # Reemplazar datos existentes por la fila importada (sin sumar)
                                factura_obj.total_factura = total_factura
                                factura_obj.copago = copago
                                factura_obj.total_final = total_final
                                factura_obj.valor_pagado_caja = valor_pagado_caja
                                factura_obj.fecha_factura = fecha_importada or factura_obj.fecha_factura
                                factura_obj.fecha_radicacion_inicial = f_radicacion or factura_obj.fecha_radicacion_inicial
                                base_para_saldo = factura_obj.total_final if factura_obj.total_final is not None else factura_obj.total_factura
                                factura_obj.saldo_actual = max(Decimal('0.00'), base_para_saldo - factura_obj.valor_pagado_caja)
                                mensaje_dup = (
                                    f"Factura {num_fac}: fila duplicada reemplazó la existente por selección del usuario."
                                )
                                registrar_duplicado(
                                    factura_obj,
                                    idx,
                                    mensaje_dup,
                                    fecha_importada=fecha_importada,
                                    fecha_existente=fecha_existente,
                                )
                                resumen['filas_procesadas'] += 1
                            else:
                                # decision == 'existing' -> omitir la fila importada
                                mensaje_dup = (
                                    f"Factura {num_fac}: fila duplicada omitida por selección del usuario (se conserva existente)."
                                )
                                registrar_duplicado(
                                    factura_obj,
                                    idx,
                                    mensaje_dup,
                                    fecha_importada=fecha_importada,
                                    fecha_existente=fecha_existente,
                                )
                                resumen['filas_omitidas'] += 1
                                resumen['errores'].append(mensaje_dup)
                                # continuar sin modificar factura_obj
                                # marcar como no created y seguir
                                pass
                        else:
                            # Sin resolución: comportamiento por defecto ahora es omitir la fila entrante,
                            # registrar el duplicado en el log y continuar con la importación normal.
                            mensaje_dup = (
                                f"Factura {num_fac}: la factura original y la fila repetida se omitieron por duplicada."
                            )
                            registrar_duplicado(
                                factura_obj,
                                idx,
                                mensaje_dup,
                                fecha_importada=fecha_importada,
                                fecha_existente=fecha_existente,
                            )
                            resumen['filas_omitidas'] += 1
                            resumen['errores'].append(mensaje_dup)
                            # Omitir la fila importada y continuar con las siguientes filas
                            continue
                    else:
                        created = True
                        factura_obj = Factura(num_factura=num_fac, id_atencion=id_atencion_valor)

                    factura_obj.erp = eps
                    factura_obj.fecha_factura = factura_obj.fecha_factura or f_factura or f_admision
                    factura_obj.fecha_radicacion_inicial = factura_obj.fecha_radicacion_inicial if factura_obj.fecha_radicacion_inicial else f_radicacion
                    factura_obj.fecha_admision = factura_obj.fecha_admision or f_admision
                    factura_obj.total_factura = factura_obj.total_factura if not created else total_factura
                    factura_obj.total_final = factura_obj.total_final if not created else total_final
                    factura_obj.datos_origen = factura_obj.datos_origen if not created else {
                        'total_factura_raw': convertir_a_json_compatible(raw_total_factura),
                        'total_final_raw': convertir_a_json_compatible(raw_total_final),
                        'copago_raw': convertir_a_json_compatible(raw_copago),
                        'valor_pagado_raw': convertir_a_json_compatible(fila.get(columnas.get('valor_pagado'))),
                        'mapped_columns': {
                            k: convertir_a_json_compatible(v)
                            for k, v in columnas.items()
                            if v
                        },
                    }
                    # Para evitar inconsistencias entre vistas y sumatorias, usar `total_final` (valor neto)
                    # como base para el saldo inicial si está disponible.
                    base_para_saldo = factura_obj.total_final if factura_obj.total_final is not None else factura_obj.total_factura
                    factura_obj.saldo_actual = factura_obj.saldo_actual if not created else max(Decimal('0.00'), base_para_saldo - valor_pagado_caja)
                    factura_obj.copago = factura_obj.copago if not created else copago
                    factura_obj.valor_pagado_caja = factura_obj.valor_pagado_caja if not created else valor_pagado_caja
                    factura_obj.copago_per_desc = limpiar_dinero(fila.get(columnas.get('copago_per')), 'copago_per', idx) or limpiar_dinero(fila.get(columnas.get('desc_copago')), 'desc_copago', idx)
                    factura_obj.historia_clinica = factura_obj.historia_clinica or hist_clinica
                    factura_obj.nombre_paciente = factura_obj.nombre_paciente or nombre_paciente if nombre_paciente else 'SIN NOMBRE'
                    factura_obj.nivel_sisben = factura_obj.nivel_sisben or str(fila.get(columnas.get('nivel_sisben')) or '').strip()
                    factura_obj.tipo_usuario = factura_obj.tipo_usuario or str(fila.get(columnas.get('tipo_usuario')) or '').strip()
                    factura_obj.tipo_afiliado = factura_obj.tipo_afiliado or str(fila.get(columnas.get('tipo_afiliado')) or '').strip()
                    tel_cel = normalizar_telefono(fila.get(columnas.get('tel_celular')))
                    tel_fijo = normalizar_telefono(fila.get(columnas.get('telefono')))
                    factura_obj.tel_celular = factura_obj.tel_celular or (tel_cel or tel_fijo)
                    factura_obj.telefono = factura_obj.telefono or str(fila.get(columnas.get('telefono')) or '').strip()
                    factura_obj.cerrada = factura_obj.cerrada if not created else es_cerrada
                    factura_obj.liquidada = factura_obj.liquidada if not created else es_liquidada
                    factura_obj.facturada_status = factura_obj.facturada_status if not created else ('FACTURADA' if nfact_original else 'NOFACT')
                    factura_obj.id_contrato = factura_obj.id_contrato or str(fila.get(columnas.get('id_contrato')) or '').strip()
                    factura_obj.nom_canal = factura_obj.nom_canal or str(fila.get(columnas.get('nom_canal')) or '').strip()
                    factura_obj.nombre_ips = factura_obj.nombre_ips or str(fila.get(columnas.get('nombre_ips')) or '').strip()
                    factura_obj.id_cajero = factura_obj.id_cajero or str(fila.get(columnas.get('id_cajero')) or '').strip()
                    factura_obj.save()

                    if created:
                        creadas += 1
                    else:
                        # Incrementar actualización cuando el registro existía y la fila no fue ignorada.
                        if not es_misma_fecha_factura(fecha_existente, fecha_importada) and fecha_importada and fecha_importada > fecha_existente:
                            actualizadas += 1
                        elif es_misma_fecha_factura(fecha_existente, fecha_importada):
                            actualizadas += 1
                    resumen['filas_procesadas'] += 1
            except Exception as e:
                resumen['errores'].append(f"Fila {idx + 2}: {type(e).__name__} - {e}")
                continue

    resumen['creadas'] = creadas
    resumen['actualizadas'] = actualizadas
    resumen['alertas_aritmeticas'] = alertas_aritmeticas
    resumen['filas_en_excel'] = len(df)
    return resumen


def importar_eventos_pae(archivo_django, audit_log=None):
    """
    Procesa la Plantilla de Actualización de Eventos (PAE).
    Maneja glosas, devoluciones, abonos y RTF, usando la estructura estándar del Excel PAE.
    Si se pasa audit_log, registra por fila la factura afectada, el estado y detalles de la importación.
    """
    contenido_bytes = archivo_django.read()
    nombre_archivo = archivo_django.name.lower()

    def cargar_hoja_excel(bytes_data):
        buffer = io.BytesIO(bytes_data)
        if nombre_archivo.endswith('.xls') and not nombre_archivo.endswith('.xlsx'):
            xls = pd.ExcelFile(buffer, engine='xlrd')
        else:
            xls = pd.ExcelFile(buffer)

        for hoja in xls.sheet_names:
            try:
                df_hoja = pd.read_excel(xls, sheet_name=hoja, dtype=str)
            except Exception:
                continue
            if not df_hoja.empty and df_hoja.shape[1] > 1:
                return df_hoja, hoja

        if nombre_archivo.endswith('.xls') and not nombre_archivo.endswith('.xlsx'):
            return pd.read_excel(io.BytesIO(bytes_data), engine='xlrd', dtype=str), xls.sheet_names[0]
        return pd.read_excel(io.BytesIO(bytes_data), dtype=str), xls.sheet_names[0]

    df, hoja_usada = cargar_hoja_excel(contenido_bytes)
    if df.empty:
        raise ValueError("El archivo PAE está vacío.")

    df.columns = [normalizar_columna(c) for c in df.columns]
    print(f"🔎 [PAE] Hoja seleccionada: {hoja_usada}, columnas normalizadas: {list(df.columns)}")

    alias_columnas_pae = {
        'nombre_tercero': ['nombre tercero', 'nombre_tercero', 'entidad responsable', 'eps', 'entidad'],
        'nombre_contrato': ['nombre contrato', 'nombre_contrato', 'contrato', 'id contrato'],
        'num_factura': ['num factura', 'num_factura', 'numero factura', 'numero_factura', 'n factura', 'nfact', 'nfactura', 'factura'],
        'total_factura': ['total factura', 'total_factura', 'valor factura', 'valor_factura'],
        'copago': ['copago', 'valor copago', 'copago total', 'total copago'],
        'fecha_radicacion': ['fecha radicacion', 'fecha_radicacion', 'fecha_radicacion_inicial', 'fecha de radicacion'],
        'fecha_devolucion': ['fecha devolucion', 'fecha_devolucion', 'fecha_devolucion'],
        'fecha_glosa_inicial': ['fecha glosa inicial', 'fecha_glosa_inicial', 'fecha_glosa', 'fecha glosa'],
        'causal_glosa': ['causal glosa', 'causal_glosa', 'codigo causal glosa', 'causal'],
        'vlr_glosa_inicial': ['vlr glosa inicial', 'vlr_glosa_inicial', 'vlr glosa', 'valor glosa inicial'],
        'vlr_aceptado_ips': ['vlr aceptado ips', 'vlr_aceptado_ips', 'vlr aceptado', 'valor aceptado ips'],
        'vlr_levantado_erp': ['vlr levantado erp', 'vlr_levantado_erp', 'vlr levantado', 'valor levantado erp'],
        'vlr_abono_1': ['vlr abono 1', 'vlr_abono_1', 'vlr abono_1', 'vlr_abono1', 'vlr_abono_1'],
        'vlr_abono_2': ['vlr abono 2', 'vlr_abono_2', 'vlr abono_2', 'vlr_abono2', 'vlr_abono_2'],
        'vlr_abono_3': ['vlr abono 3', 'vlr_abono_3', 'vlr abono_3', 'vlr_abono3', 'vlr_abono_3'],
        'vlr_abono_4': ['vlr abono 4', 'vlr_abono_4', 'vlr abono_4', 'vlr_abono4', 'vlr_abono_4'],
        'fecha_abono_1': ['fecha abono 1', 'fecha_abono_1', 'fecha abono_1', 'fecha_abono1', 'fecha_abono_1'],
        'fecha_abono_2': ['fecha abono 2', 'fecha_abono_2', 'fecha abono_2', 'fecha_abono2', 'fecha_abono_2'],
        'fecha_abono_3': ['fecha abono 3', 'fecha_abono_3', 'fecha abono_3', 'fecha_abono3', 'fecha_abono_3'],
        'fecha_abono_4': ['fecha abono 4', 'fecha_abono_4', 'fecha abono_4', 'fecha_abono4', 'fecha_abono_4'],
        'numero_recaudo': ['numero recaudo', 'numero_recaudo', 'número recaudo', 'comprobante pago'],
        'vlr_total_abonos': ['vlr total abonos', 'vlr_total_abonos', 'valor total abonos', 'total abonos'],
        'vlr_rtf': ['vlr rtf', 'vlr_rtf', 'vlr rtf total', 'vlr_rtf_total', 'rtf', 'valor rtf', 'valor rtf total'],
        'saldo_factura': ['saldo factura', 'saldo_factura', 'saldo', 'saldo_final'],
        'id_atencion': ['id atencion', 'id_atencion', 'atencion'],
    }

    def encontrar_columna_real(dataframe, aliases):
        normalized_columns = {normalizar_columna(col): col for col in dataframe.columns}
        for alias in aliases:
            alias_norm = normalizar_columna(alias)
            if alias_norm in normalized_columns:
                return normalized_columns[alias_norm]
        return None

    columnas = {clave: encontrar_columna_real(df, aliases) for clave, aliases in alias_columnas_pae.items()}
    for col_name in df.columns:
        nombre_normal = normalizar_columna(col_name)
        match_valor = re.search(r'vlr\s*abono\s*_(\d+)|vlr\s*abono\s*(\d+)', nombre_normal)
        if match_valor:
            indice = match_valor.group(1) or match_valor.group(2)
            columnas[f'vlr_abono_{indice}'] = col_name
        match_fecha = re.search(r'fecha\s*abono\s*_(\d+)|fecha\s*abono\s*(\d+)', nombre_normal)
        if match_fecha:
            indice = match_fecha.group(1) or match_fecha.group(2)
            columnas[f'fecha_abono_{indice}'] = col_name

    if not columnas.get('num_factura'):
        raise ValueError('No se encontró la columna num_factura en el archivo PAE.')

    if audit_log is None:
        audit_log = []

    resumen = {'procesados': 0, 'errores': [], 'advertencias': []}
    contador_actualizadas = 0
    def normalizar_numero_factura(valor):
        texto = str(valor or '').strip()
        if texto.lower() in ['nan', 'none', 'nat']:
            return ''
        return texto[:-2] if texto.endswith('.0') else texto

    facturas_archivo = df[columnas['num_factura']].map(normalizar_numero_factura)
    duplicados_en_archivo = set(facturas_archivo[facturas_archivo.duplicated(keep=False)]) - {''}

    def convertir_timestamp_a_date(ts):
        if ts is None or pd.isnull(ts) or str(ts).strip().lower() in ['nan', '', 'none', 'nat']:
            return None

        def intentar_parsear(texto):
            texto = texto.strip()
            if not texto:
                return None

            if re.fullmatch(r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}', texto):
                delimitador = '-' if '-' in texto else ('/' if '/' in texto else '.')
                patron = f'%Y{delimitador}%m{delimitador}%d'
                try:
                    return datetime.strptime(texto, patron).date()
                except ValueError:
                    pass

            if re.fullmatch(r'\d{1,2}[-/.]\d{1,2}[-/.]\d{4}', texto):
                partes = re.split(r'[-/.]', texto)
                primer_num = int(partes[0])
                segundo_num = int(partes[1])
                delimitador = '-' if '-' in texto else ('/' if '/' in texto else '.')

                if primer_num > 12 and segundo_num <= 12:
                    patron = f'%d{delimitador}%m{delimitador}%Y'
                    try:
                        return datetime.strptime(texto, patron).date()
                    except ValueError:
                        pass
                if segundo_num > 12 and primer_num <= 12:
                    patron = f'%m{delimitador}%d{delimitador}%Y'
                    try:
                        return datetime.strptime(texto, patron).date()
                    except ValueError:
                        pass

                for patron in (f'%d{delimitador}%m{delimitador}%Y', f'%m{delimitador}%d{delimitador}%Y'):
                    try:
                        return datetime.strptime(texto, patron).date()
                    except ValueError:
                        continue

            if re.fullmatch(r'\d{1,2}[-/.]\d{1,2}[-/.]\d{2}', texto):
                delimitador = '-' if '-' in texto else ('/' if '/' in texto else '.')
                for patron in (
                    f'%d{delimitador}%m{delimitador}%y',
                    f'%m{delimitador}%d{delimitador}%y',
                ):
                    try:
                        return datetime.strptime(texto, patron).date()
                    except ValueError:
                        continue

            # Fallback final para cualquier otro formato textual, pero solo tras detectar la estructura.
            for patron in (
                '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
                '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y',
                '%m/%d/%Y', '%m-%d-%Y', '%m.%d.%Y',
                '%d/%m/%y', '%d-%m-%y', '%d.%m.%y',
                '%m/%d/%y', '%m-%d-%y', '%m.%d.%y',
            ):
                try:
                    return datetime.strptime(texto, patron).date()
                except ValueError:
                    continue

            return None

        if isinstance(ts, str):
            texto = ts.strip()
            if texto.lower() in ['nan', '', 'none', 'nat']:
                return None
            return intentar_parsear(texto)

        if isinstance(ts, pd.Timestamp):
            return ts.date()
        if hasattr(ts, 'date'):
            return ts.date()
        return None

    def validar_fecha_no_menor(fecha_actual, fecha_base, mensaje_error):
        if fecha_actual and fecha_base and fecha_actual < fecha_base:
            raise ValueError(mensaje_error)

    def es_diferencia_aproximada(valor_calculado, valor_reportado, absoluto=Decimal('0.05'), relativo=Decimal('0.005')):
        if valor_calculado is None or valor_reportado is None:
            return False
        diferencia = abs(valor_calculado - valor_reportado)
        if diferencia <= absoluto:
            return True
        if valor_calculado == 0:
            return False
        return diferencia <= abs(valor_calculado) * relativo

    with transaction.atomic():
        for idx, fila in df.iterrows():
            num_fac = str(fila.get(columnas.get('num_factura')) or '').strip()
            if num_fac.endswith('.0'):
                num_fac = num_fac[:-2]

            if not num_fac or num_fac.lower() in ['nan', 'none']:
                mensaje_error = f'Fila {idx + 2}: num_factura vacío o inválido.'
                resumen['errores'].append(mensaje_error)
                audit_log.append({
                    'fila': idx + 2,
                    'factura': num_fac or 'SIN_FACTURA',
                    'estado': 'omitida',
                    'detalle': mensaje_error,
                })
                continue

            if num_fac in duplicados_en_archivo:
                mensaje_dup = f'Factura {num_fac}: la fila original y la fila repetida se omitieron por duplicada.'
                resumen['errores'].append(mensaje_dup)
                audit_log.append({
                    'fila': idx + 2,
                    'factura': num_fac,
                    'estado': 'omitida',
                    'detalle': mensaje_dup,
                })
                continue

            try:
                with transaction.atomic():
                    factura = buscar_factura_para_pae(num_fac, fila.get(columnas.get('id_atencion')))
                    if factura is None:
                        mensaje_error = f'Factura {num_fac} no existe en base de datos DIF.'
                        resumen['errores'].append(mensaje_error)
                        audit_log.append({
                            'fila': idx + 2,
                            'factura': num_fac,
                            'estado': 'omitida',
                            'detalle': mensaje_error,
                        })
                        continue

                    # Valores previos para construir el historial de cambios PAE
                    old_total_factura = factura.total_factura
                    old_fecha_radicacion_inicial = factura.fecha_radicacion_inicial
                    old_fecha_devolucion = factura.fecha_devolucion
                    old_valor_glosa_inicial = factura.valor_glosa_inicial
                    old_saldo_actual = factura.saldo_actual
                    old_abonos_total = factura.eventos.filter(tipo='ABONO').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
                    old_abonos_count = factura.eventos.filter(tipo='ABONO').count()
                    old_rtf_total = factura.eventos.filter(tipo='RTF').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
                    old_rtf_count = factura.eventos.filter(tipo='RTF').count()
                    old_dev_count = factura.eventos.filter(tipo='DEV').count()
                    old_glo_acep_count = factura.eventos.filter(tipo='GLO_ACEP').count()
                    old_glo_lev_count = factura.eventos.filter(tipo='GLO_LEV').count()
                    cambios = []

                    def registrar_cambio(campo, anterior, nuevo):
                        if anterior != nuevo:
                            cambios.append({
                                'campo': campo,
                                'anterior': str(anterior) if anterior is not None else '—',
                                'nuevo': str(nuevo) if nuevo is not None else '—'
                            })

                    # Eliminar eventos PAE previos para evitar duplicados en reimportaciones.
                    EventoCartera.objects.filter(
                        factura=factura,
                        tipo__in=['GLO_INI', 'GLO_ACEP', 'GLO_LEV', 'ABONO', 'RTF', 'DEV']
                    ).delete()

                    f_radicacion = convertir_timestamp_a_date(fila.get(columnas.get('fecha_radicacion')))
                    f_devolucion = convertir_timestamp_a_date(fila.get(columnas.get('fecha_devolucion')))
                    f_glosa_ini = convertir_timestamp_a_date(fila.get(columnas.get('fecha_glosa_inicial')))
                    causal_glosa = str(fila.get(columnas.get('causal_glosa')) or '').strip()
                    if causal_glosa.lower() in ['nan', 'none']:
                        causal_glosa = ''

                    total_factura = decimal_excel_seguro(fila.get(columnas.get('total_factura')))
                    copago_pae = decimal_excel_seguro(fila.get(columnas.get('copago')))
                    v_glosa_ini = decimal_excel_seguro(fila.get(columnas.get('vlr_glosa_inicial')))
                    v_acep = decimal_excel_seguro(fila.get(columnas.get('vlr_aceptado_ips')))
                    v_levantado_erp = decimal_excel_seguro(fila.get(columnas.get('vlr_levantado_erp')))
                    v_rtf_total = decimal_excel_seguro(fila.get(columnas.get('vlr_rtf')))
                    saldo_factura_raw = fila.get(columnas.get('saldo_factura'))
                    v_saldo_factura = decimal_excel_seguro(saldo_factura_raw)

                    validar_fecha_no_menor(f_radicacion, factura.fecha_factura, f'Factura {num_fac}: fecha de radicación {f_radicacion} no puede ser menor que la fecha de factura {factura.fecha_factura}.')
                    validar_fecha_no_menor(f_glosa_ini, f_radicacion, f'Factura {num_fac}: fecha de glosa inicial {f_glosa_ini} no puede ser menor que la fecha de radicación {f_radicacion}.')

                    fecha_abonos = []
                    for i in range(1, 5):
                        fecha_abono = convertir_timestamp_a_date(fila.get(columnas.get(f'fecha_abono_{i}')))
                        if fecha_abono:
                            fecha_abonos.append((i, fecha_abono))
                    for i, fecha_abono in fecha_abonos:
                        validar_fecha_no_menor(fecha_abono, f_radicacion, f'Factura {num_fac}: fecha de abono {i} ({fecha_abono}) no puede ser menor que la fecha de radicación {f_radicacion}.')

                    factura.fecha_radicacion_inicial = f_radicacion or factura.fecha_radicacion_inicial
                    factura.fecha_devolucion = f_devolucion or factura.fecha_devolucion
                    factura.fecha_glosa_inicial = f_glosa_ini
                    factura.fecha_limite_respuesta_glosa = f_glosa_ini + timedelta(days=22) if f_glosa_ini else None
                    factura.causal_glosa = causal_glosa or None
                    if total_factura > 0:
                        factura.total_factura = total_factura
                    if copago_pae > 0:
                        factura.copago = copago_pae
                    factura.save()

                    if v_glosa_ini > 0:
                        factura.valor_glosa_inicial = v_glosa_ini
                        factura.save()
                        if not f_glosa_ini:
                            f_glosa_ini = timezone.now().date()
                        EventoCartera.objects.create(
                            factura=factura,
                            tipo='GLO_INI',
                            fecha=f_glosa_ini,
                            valor=v_glosa_ini
                        )

                    if f_devolucion:
                        factura.fecha_devolucion = f_devolucion
                        factura.save()
                        EventoCartera.objects.create(
                            factura=factura,
                            tipo='DEV',
                            fecha=f_devolucion,
                            valor=Decimal('0.00'),
                            observacion='Factura Devuelta'
                        )

                    if v_acep > 0:
                        fecha_resp_ips = f_glosa_ini or f_radicacion or timezone.now().date()
                        EventoCartera.objects.create(
                            factura=factura,
                            tipo='GLO_ACEP',
                            fecha=fecha_resp_ips,
                            valor=v_acep
                        )

                    if v_levantado_erp > 0:
                        fecha_levantado = f_radicacion or timezone.now().date()
                        EventoCartera.objects.create(
                            factura=factura,
                            tipo='GLO_LEV',
                            fecha=fecha_levantado,
                            valor=v_levantado_erp
                        )

                    abonos_creados = []
                    total_abonos_calculado = Decimal('0.00')
                    abono_indices = sorted({
                        int(re.search(r'(\d+)$', clave).group(1))
                        for clave in columnas.keys()
                        if clave.startswith('vlr_abono_') and columnas.get(clave)
                    }, key=lambda x: x)

                    for i in abono_indices:
                        valor_abono = decimal_excel_seguro(fila.get(columnas.get(f'vlr_abono_{i}')))
                        fecha_abono = convertir_timestamp_a_date(fila.get(columnas.get(f'fecha_abono_{i}')))
                        if valor_abono > 0:
                            if fecha_abono:
                                EventoCartera.objects.create(
                                    factura=factura,
                                    tipo='ABONO',
                                    fecha=fecha_abono,
                                    valor=valor_abono,
                                    observacion=f'Abono {i} PAE'
                                )
                                abonos_creados.append((i, valor_abono, fecha_abono))
                                total_abonos_calculado += valor_abono

                                if not fecha_abonos:
                                    factura.fecha_pago = fecha_abono
                                elif fecha_abono < fecha_abonos[0][1]:
                                    factura.fecha_pago = fecha_abono
                                numero_recaudo = str(fila.get(columnas.get('numero_recaudo')) or '').strip()
                                factura.numero_recaudo = numero_recaudo if numero_recaudo.lower() not in ['nan', 'none'] else None
                                factura.save()

                    if abonos_creados:
                        fecha_abonos = [(i, fecha) for i, _, fecha in abonos_creados]
                        factura.fecha_pago = min(fecha for _, fecha in fecha_abonos) if fecha_abonos else None
                        factura.save()

                    vlr_total_abonos = decimal_excel_seguro(fila.get(columnas.get('vlr_total_abonos')))
                    if vlr_total_abonos > 0 and total_abonos_calculado < vlr_total_abonos:
                        faltante_abonos = vlr_total_abonos - total_abonos_calculado
                        if faltante_abonos > 0:
                            fecha_fallback = f_radicacion or f_glosa_ini or f_devolucion or timezone.now().date()
                            EventoCartera.objects.create(
                                factura=factura,
                                tipo='ABONO',
                                fecha=fecha_fallback,
                                valor=faltante_abonos,
                                observacion='Abono PAE (total del archivo sin fecha)'
                            )
                            total_abonos_calculado += faltante_abonos
                            factura.fecha_pago = factura.fecha_pago or fecha_fallback
                            factura.save()
                    if vlr_total_abonos > 0 and total_abonos_calculado != vlr_total_abonos:
                        resumen['advertencias'].append(
                            f'Factura {num_fac}: suma abonos {total_abonos_calculado} no coincide con vlr_Total_Abonos {vlr_total_abonos}.'
                        )

                    if v_rtf_total > 0:
                        fecha_rtf = f_devolucion or f_radicacion or timezone.now().date()
                        EventoCartera.objects.create(
                            factura=factura,
                            tipo='RTF',
                            fecha=fecha_rtf,
                            valor=v_rtf_total,
                            observacion='RTF PAE'
                        )

                    # Guardar origen PAE completo para exportación futura
                    factura.pae_datos_origen = {
                        'raw_row': {
                            k: convertir_a_json_compatible(fila.get(columnas.get(k)))
                            for k in columnas.keys()
                            if columnas.get(k)
                        },
                        'mapped_columns': {
                            k: convertir_a_json_compatible(columnas.get(k))
                            for k in columnas.keys()
                            if columnas.get(k)
                        },
                    }
                    factura.save(update_fields=['pae_datos_origen'])

                    factura.calcular_saldo()
                    factura.refresh_from_db()
                    registrar_cambio('Fecha de radicación', old_fecha_radicacion_inicial, factura.fecha_radicacion_inicial)
                    registrar_cambio('Fecha de devolución', old_fecha_devolucion, factura.fecha_devolucion)
                    registrar_cambio('Total factura', old_total_factura, factura.total_factura)
                    registrar_cambio('Valor glosa inicial', old_valor_glosa_inicial, factura.valor_glosa_inicial)
                    registrar_cambio('Saldo actual', old_saldo_actual, factura.saldo_actual)

                    nuevo_abonos_total = factura.eventos.filter(tipo='ABONO').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
                    nuevo_abonos_count = factura.eventos.filter(tipo='ABONO').count()
                    registrar_cambio('Abonos PAE (count)', old_abonos_count, nuevo_abonos_count)
                    registrar_cambio('Abonos PAE (total)', old_abonos_total, nuevo_abonos_total)

                    nuevo_rtf_total = factura.eventos.filter(tipo='RTF').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
                    nuevo_rtf_count = factura.eventos.filter(tipo='RTF').count()
                    registrar_cambio('RTF total', old_rtf_total, nuevo_rtf_total)
                    registrar_cambio('RTF (count)', old_rtf_count, nuevo_rtf_count)

                    nuevo_dev_count = factura.eventos.filter(tipo='DEV').count()
                    registrar_cambio('Devoluciones', old_dev_count, nuevo_dev_count)

                    nuevo_glo_acep_count = factura.eventos.filter(tipo='GLO_ACEP').count()
                    registrar_cambio('Glosa aceptada', old_glo_acep_count, nuevo_glo_acep_count)
                    nuevo_glo_lev_count = factura.eventos.filter(tipo='GLO_LEV').count()
                    registrar_cambio('Glosa levantada', old_glo_lev_count, nuevo_glo_lev_count)

                    factura.pae_cambios = cambios
                    factura.save(update_fields=['pae_cambios'])

                    if saldo_factura_raw not in (None, '', 'nan', 'NaN', 'None') and v_saldo_factura is not None:
                        if factura.saldo_actual != v_saldo_factura:
                            if es_diferencia_aproximada(factura.saldo_actual, v_saldo_factura):
                                resumen['advertencias'].append(
                                    f'Factura {num_fac}: saldo calculado {factura.saldo_actual} difiere ligeramente de saldo_factura {v_saldo_factura}; se conserva el saldo recalculado desde la factura y los eventos PAE.'
                                )
                            else:
                                resumen['advertencias'].append(
                                    f'Factura {num_fac}: saldo calculado {factura.saldo_actual} diferente de saldo_factura {v_saldo_factura}; se conserva el saldo recalculado desde la factura y los eventos PAE.'
                                )

                    # Contabilizar fila procesada como actualización exitosa
                    contador_actualizadas += 1
                    resumen['procesados'] += 1
                    audit_log.append({
                        'fila': idx + 2,
                        'factura': num_fac,
                        'estado': 'procesada',
                        'detalle': f'Eventos PAE aplicados a {num_fac}. Abonos: {nuevo_abonos_count}, RTF: {nuevo_rtf_total}, Cambios: {len(cambios)}',
                    })
            except Exception as e:
                mensaje_error = f'Error en {num_fac}: {str(e)}'
                resumen['errores'].append(mensaje_error)
                audit_log.append({
                    'fila': idx + 2,
                    'factura': num_fac,
                    'estado': 'error',
                    'detalle': mensaje_error,
                })

    # Construir un resumen compatible con la vista `subir.html`
    full_resumen = {
        'tipo': 'PAE',
        'filas_en_excel': len(df),
        'filas_procesadas': resumen.get('procesados', 0),
        'creadas': 0,
        'actualizadas': contador_actualizadas,
        'filas_omitidas': 0,
        'alertas_aritmeticas': resumen.get('advertencias', []),
        'errores': resumen.get('errores', []),
        # Mantener compatibilidad hacia atrás
        'procesados': resumen.get('procesados', 0),
        'advertencias': resumen.get('advertencias', []),
    }

    return full_resumen