# ClinicSoft-IPS™ - Módulo de Facturación y Cartera
import json
from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.hashers import check_password, make_password
from .environment import get_current_environment_id


class EnvironmentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(environment_id=get_current_environment_id())


class Environment(models.Model):
    numero = models.PositiveSmallIntegerField(unique=True)
    nickname = models.CharField(max_length=100, blank=True, default='')
    password = models.CharField(max_length=128, blank=True, default='')
    comentario = models.CharField(max_length=255, blank=True, default='')

    def set_password(self, raw_password):
        self.password = make_password(raw_password) if raw_password else ''

    def check_password(self, raw_password):
        return not self.password or check_password(raw_password or '', self.password)

    def __str__(self):
        return self.nickname or f'Environment {self.numero}'

# 1. TABLA PARAMÉTRICA (Flexibilidad total de Regímenes)
class TipoERP(models.Model):
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, default=get_current_environment_id)
    nombre = models.CharField(max_length=100)
    objects = EnvironmentManager()

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Tipo de ERP"
        verbose_name_plural = "Tipos de ERP"
        constraints = [models.UniqueConstraint(fields=['environment', 'nombre'], name='tipoerp_environment_nombre')]

# 2. ENTIDADES RESPONSABLES (ERP)
class EntidadResponsable(models.Model):
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, default=get_current_environment_id)
    nit = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=255)
    tipo_erp = models.ForeignKey(TipoERP, on_delete=models.PROTECT, related_name='entidades')
    objects = models.Manager()

    def __str__(self):
        return f"{self.nombre} ({self.nit})"

    class Meta:
        constraints = [models.UniqueConstraint(fields=['environment', 'nit'], name='entidad_environment_nit')]

# 3. MAESTRO DE FACTURACIÓN (DIF EXTENDIDO)
class Factura(models.Model):
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, default=get_current_environment_id)
    erp = models.ForeignKey(EntidadResponsable, on_delete=models.PROTECT)
    num_factura = models.CharField(max_length=50) # Mapea con NFact
    objects = EnvironmentManager()
    
    # Nuevos campos de identificación clínica y paciente
    historia_clinica = models.CharField(max_length=50, null=True, blank=True)
    nombre_paciente = models.CharField(max_length=255, null=True, blank=True)
    nivel_sisben = models.CharField(max_length=50, null=True, blank=True)
    tipo_usuario = models.CharField(max_length=100, null=True, blank=True)
    tipo_afiliado = models.CharField(max_length=100, null=True, blank=True)
    tel_celular = models.CharField(max_length=50, null=True, blank=True)
    telefono = models.CharField(max_length=50, null=True, blank=True)
    
    # Contexto Operativo de la IPS
    id_contrato = models.CharField(max_length=50, null=True, blank=True) # ContratoId
    id_atencion = models.CharField(max_length=50, null=True, blank=True) # Id Atencion
    fecha_admision = models.DateField(null=True, blank=True)
    id_cajero = models.CharField(max_length=50, null=True, blank=True)
    nom_canal = models.CharField(max_length=100, null=True, blank=True)
    nombre_ips = models.CharField(max_length=255, null=True, blank=True)
    
    # Banderas de auditoría interna
    cerrada = models.CharField(max_length=10, null=True, blank=True)
    liquidada = models.CharField(max_length=10, null=True, blank=True)
    facturada_status = models.CharField(max_length=10, null=True, blank=True)

    # Fechas Clave (Permitiendo vacíos reales según la guía)
    fecha_factura = models.DateField(null=True, blank=True) # Fecha Factura
    fecha_radicacion_inicial = models.DateField(null=True, blank=True) # Fecha Radicacion
    fecha_glosa_inicial = models.DateField(null=True, blank=True)
    fecha_limite_respuesta_glosa = models.DateField(null=True, blank=True)
    causal_glosa = models.CharField(max_length=10, null=True, blank=True)
    fecha_devolucion = models.DateField(null=True, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    numero_recaudo = models.CharField(max_length=80, null=True, blank=True)
    fecha_importacion = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    fecha_actualizacion = models.DateField(null=True, blank=True)  # Fecha de actualización de la factura desde un archivo PAE
    pae_cambios = models.JSONField(null=True, blank=True, default=list)
    datos_origen = models.JSONField(null=True, blank=True, default=dict)
    pae_datos_origen = models.JSONField(null=True, blank=True, default=dict)

    # Valores Monetarios del nuevo formato
    total_factura = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_pagado_caja = models.DecimalField(max_digits=18, decimal_places=2, default=0) # Valor Pagado
    copago = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    copago_per_desc = models.DecimalField(max_digits=18, decimal_places=2, default=0) # Copago PerDesc
    total_final = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    # Auditoría de Cartera
    valor_glosa_inicial = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    saldo_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0.00)

    def __str__(self):
        return self.num_factura

    def calcular_saldo(self):
        """Saldo real: valor bruto menos los pagos reales del PAE/DIF."""
        self.saldo_actual = max(Decimal('0.00'), self.total_factura - self.pagos_total)
        self.save()

    # --- NUEVA LÓGICA DE CLASIFICACIÓN TRIPLE ---
    @property
    def esta_facturada(self):
        """Determina si la factura está facturada usando el estado real de la carga DIF/PAE."""
        status = (self.facturada_status or '').strip().upper()
        if status in ('FACTURADA', 'FACTURADO', '1', 'TRUE', 'SI', 'YES'):
            return True
        if status in ('NOFACT', 'NO_FACTURADA', 'NO FACTURADA', '0', 'FALSE', 'NO'):
            return False
        return not str(self.num_factura or '').upper().startswith('NOFACT-')

    @property
    def estado_gestion(self):
        """Categorización estricta basada en la ausencia de fechas"""
        if not self.fecha_factura:
            return "No Facturado"
        if not self.fecha_radicacion_inicial:
            return "No Radicado"
        return "Radicado"

    @property
    def dias_vencimiento(self):
        if not self.fecha_radicacion_inicial:
            return 0
        hoy = timezone.now().date()
        base_fecha = self.fecha_devolucion if self.fecha_devolucion else hoy
        diferencia = base_fecha - self.fecha_radicacion_inicial
        return max(0, diferencia.days)

    @property
    def valor_neto(self):
        """Valor neto de la factura: bruto menos pagos reales del PAE/DIF."""
        bruto = Decimal(str(self.total_factura or 0))
        if self.pk is None:
            return max(Decimal('0.00'), bruto)
        pagos = self.pagos_total
        return max(Decimal('0.00'), bruto - pagos)

    @property
    def campos_actualizados(self):
        """Resumen breve de las actualizaciones aplicadas por PAE."""
        if self.pae_cambios:
            campos = []
            for cambio in self.pae_cambios:
                campo = cambio.get('campo') if isinstance(cambio, dict) else None
                if campo and campo not in campos:
                    campos.append(campo)
            if campos:
                if len(campos) > 3:
                    return ', '.join(campos[:3]) + ' y más'
                return ', '.join(campos)

        campos = []
        if self.eventos.filter(tipo='GLO_INI').exists():
            campos.append('Glosa inicial')
        if self.eventos.filter(tipo='GLO_ACEP').exists():
            campos.append('Glosa aceptada')
        if self.eventos.filter(tipo='GLO_LEV').exists():
            campos.append('Glosa levantada')
        if self.eventos.filter(tipo='ABONO').exists():
            campos.append('Abonos')
        if self.eventos.filter(tipo='RTF').exists():
            campos.append('Retención (RTF)')
        if self.eventos.filter(tipo='DEV').exists():
            campos.append('Devolución')
        if not campos:
            return 'Sin actualizaciones PAE'
        if len(campos) > 3:
            return ', '.join(campos[:3]) + ' y más'
        return ', '.join(campos)

    @property
    def pae_cambios_preview(self):
        if not self.pae_cambios:
            return 'Sin cambios aplicados'
        partes = []
        for cambio in self.pae_cambios:
            if not isinstance(cambio, dict):
                continue
            campo = cambio.get('campo') or 'Campo'
            anterior = cambio.get('anterior') or '—'
            nuevo = cambio.get('nuevo') or '—'
            partes.append(f'{campo}: {anterior} → {nuevo}')
        return '; '.join(partes[:4]) if partes else 'Sin cambios aplicados'

    @property
    def pae_cambios_json(self):
        return json.dumps(self.pae_cambios or [], ensure_ascii=False)

    @property
    def edad_cartera(self):
        """Edad de cartera en días desde la radicación hasta hoy."""
        return self.dias_vencimiento

    @property
    def fuente_datos(self):
        """Indica si la factura viene de DIF únicamente o ya fue enriquecida por PAE."""
        if self.pk is None:
            return 'PAE + DIF' if self.pae_datos_origen else 'DIF'
        if self.pae_datos_origen or self.eventos.exists():
            return 'PAE + DIF'
        return 'DIF'

    @property
    def abonos_pae(self):
        if self.pk is None:
            return []
        return list(
            self.eventos.filter(tipo='ABONO').order_by('fecha').values('fecha', 'valor', 'observacion')
        )

    @property
    def abonos_pae_resumen(self):
        resumen = []
        for abono in self.abonos_pae:
            resumen.append({
                'fecha': abono['fecha'].strftime('%d/%m/%Y') if abono['fecha'] else '—',
                'valor': float(abono['valor'] or 0),
                'observacion': abono['observacion'] or 'Abono PAE',
            })
        return resumen

    @property
    def abonos_pae_json(self):
        return json.dumps(self.abonos_pae_resumen, ensure_ascii=False)

    @property
    def rtf_pae(self):
        if self.pk is None:
            return Decimal('0.00')
        total = self.eventos.filter(tipo='RTF').aggregate(total=Sum('valor'))['total']
        if total is None:
            return Decimal('0.00')
        try:
            if total.is_nan():
                return Decimal('0.00')
        except AttributeError:
            pass
        return total if total == total else Decimal('0.00')

    @property
    def pagos_total(self):
        """Pagos reales: vlr_aceptado_ips + abonos + RTF. Copago no es un pago en esta lógica."""
        if self.pk is None:
            return Decimal('0.00')
        total_abonos = self.eventos.filter(tipo='ABONO').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        total_rtf = self.eventos.filter(tipo='RTF').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        total_aceptado = self.eventos.filter(tipo='GLO_ACEP').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        return max(Decimal('0.00'), total_aceptado + total_abonos + total_rtf)

    @property
    def estado_glosa(self):
        glosa = Decimal(str(self.valor_glosa_inicial or 0))
        if glosa > 0:
            return 'Glosa inicial registrada'
        if self.pk is None:
            return 'Available soon'
        if self.eventos.filter(tipo='GLO_INI').exists():
            return 'Glosa inicial registrada'
        if self.eventos.filter(tipo='GLO_ACEP').exists():
            return 'Glosa aceptada IPS'
        if self.eventos.filter(tipo='GLO_LEV').exists():
            return 'Glosa levantada ERP'
        return 'Available soon'


class ImportLog(models.Model):
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, default=get_current_environment_id)
    TIPO_LOG = [
        ('DIF', 'DIF'),
        ('PAE', 'PAE'),
    ]

    codigo = models.CharField(max_length=50, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPO_LOG)
    descripcion = models.TextField(null=True, blank=True)
    resumen = models.JSONField(null=True, blank=True, default=dict)
    detalles = models.JSONField(null=True, blank=True, default=list)
    creado_en = models.DateTimeField(auto_now_add=True)
    objects = EnvironmentManager()

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.codigo} - {self.tipo} - {self.creado_en:%Y-%m-%d %H:%M}"

    @property
    def abonos_pae(self):
        return list(self.eventos.filter(tipo='ABONO').order_by('fecha').values('fecha', 'valor', 'observacion'))

    @property
    def abonos_pae_resumen(self):
        return [
            {
                'fecha': abono['fecha'].strftime('%d/%m/%Y') if abono['fecha'] else '—',
                'valor': f"{abono['valor']:.2f}",
                'observacion': abono['observacion'] or 'Abono PAE',
            }
            for abono in self.abonos_pae
        ]

    @property
    def abonos_pae_json(self):
        return json.dumps(self.abonos_pae_resumen, ensure_ascii=False)

    @property
    def rtf_pae(self):
        return self.eventos.filter(tipo='RTF').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    @property
    def estado_glosa(self):
        """Estado de glosa para la vista de detalle. Se mantiene como 'Available soon' hasta que el flujo PAE tenga campos de objeción/glosa completos."""
        glosa = Decimal(str(self.valor_glosa_inicial or 0))
        if glosa > 0:
            return 'Glosa inicial registrada'
        return 'Available soon'

    @property
    def rango_mora(self):
        if not self.fecha_factura:
            return "No Facturado"
        if not self.fecha_radicacion_inicial:
            return "Pendiente de Radicación"
        if self.fecha_devolucion:
            return "Devuelta / En Trámite"
            
        dias = self.dias_vencimiento
        if dias <= 30: return "0-30 días (Corriente)"
        if dias <= 60: return "31-60 días"
        if dias <= 90: return "61-90 días"
        return "+90 días (Crítico)"
    
# 4. ACTUALIZACIÓN DE EVENTOS (PAE)
class EventoCartera(models.Model):
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, default=get_current_environment_id)
    TIPO_EVENTO = [
        ('RAD', 'Radicación Real'),
        ('DEV', 'Devolución'),
        ('GLO_INI', 'Glosa Inicial (Informativa)'),
        ('GLO_ACEP', 'Glosa Aceptada IPS (Afecta Saldo)'),
        ('GLO_LEV', 'Glosa Levantada ERP'),
        ('ABONO', 'Abono/Pago (Afecta Saldo)'),
        ('RTF', 'Retención en la Fuente (Afecta Saldo)'),
    ]
    
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='eventos')
    tipo = models.CharField(max_length=10, choices=TIPO_EVENTO)
    fecha = models.DateField()
    valor = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    observacion = models.TextField(null=True, blank=True)
    objects = EnvironmentManager()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.factura.calcular_saldo()

    class Meta:
        ordering = ['fecha']

# 5. TABLA DE DIMENSIÓN TEMPORAL (Para Power BI y Filtros)
class CalendarioDimension(models.Model):
    """
    Tabla de calendario parametrizada para soportar filtros de fecha 
    sin depender de fórmulas complejas en Power BI o Dashboard.
    Se regenera automáticamente al inicio de cada año.
    """
    fecha = models.DateField(primary_key=True)
    ano = models.IntegerField()
    mes = models.IntegerField()
    dia = models.IntegerField()
    nombre_mes = models.CharField(max_length=20)  # Enero, Febrero, etc.
    nombre_dia = models.CharField(max_length=20)  # Lunes, Martes, etc.
    trimestre = models.CharField(max_length=10)  # Q1, Q2, Q3, Q4
    semana = models.IntegerField()  # Número de semana (1-52)
    es_fin_semana = models.BooleanField(default=False)
    es_festivo = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.fecha} ({self.nombre_mes} {self.ano})"
    
    class Meta:
        ordering = ['fecha']
        verbose_name = "Calendario"
        verbose_name_plural = "Calendarios"
        indexes = [
            models.Index(fields=['ano', 'mes']),
            models.Index(fields=['ano']),
            models.Index(fields=['trimestre']),
        ]