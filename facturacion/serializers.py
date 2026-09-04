# facturacion/serializers.py
"""
Serializers para convertir modelos Django a JSON para la API REST.
"""
from rest_framework import serializers
from .models import Factura, EventoCartera, EntidadResponsable, TipoERP


class TipoERPSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoERP
        fields = ['id', 'nombre']


class EntidadResponsableSerializer(serializers.ModelSerializer):
    tipo_erp = TipoERPSerializer(read_only=True)
    
    class Meta:
        model = EntidadResponsable
        fields = ['nit', 'nombre', 'tipo_erp']


class EventoCarteraSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoCartera
        fields = ['id', 'tipo', 'fecha', 'valor', 'observacion']


class FacturaSerializer(serializers.ModelSerializer):
    erp = EntidadResponsableSerializer(read_only=True)
    eventos = EventoCarteraSerializer(many=True, read_only=True)
    
    class Meta:
        model = Factura
        fields = [
            'id',
            'num_factura',
            'erp',
            'fecha_factura',
            'fecha_radicacion_inicial',
            'fecha_devolucion',
            'total_final',
            'saldo_actual',
            'valor_glosa_inicial',
            'estado_gestion',
            'rango_mora',
            'dias_vencimiento',
            'eventos',
            'datos_origen',
            'pae_datos_origen',
        ]
