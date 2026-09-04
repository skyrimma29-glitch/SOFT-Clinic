from django.contrib import admin
from .models import TipoERP, EntidadResponsable, Factura, EventoCartera, ImportLog

# Esto permite ver los eventos (pagos/glosas) dentro de la misma pantalla de la Factura
class EventoCarteraInline(admin.TabularInline):
    model = EventoCartera
    extra = 1

@admin.register(TipoERP)
class TipoERPAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')

@admin.register(EntidadResponsable)
class EntidadResponsableAdmin(admin.ModelAdmin):
    list_display = ('nit', 'nombre', 'tipo_erp')
    search_fields = ('nombre', 'nit')

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    # CORRECCIÓN: Eliminamos 'valor_neto' y colocamos 'total_final' que sí existe en tu modelo
    list_display = (
        'num_factura', 
        'erp', 
        'fecha_factura', 
        'total_final',       # <-- Este es el campo real de tu modelo actual
        'saldo_actual',
        'estado_gestion', 
        'rango_mora_display'
    )
    
    search_fields = ('num_factura', 'erp__nombre', 'nombre_paciente', 'historia_clinica')
    list_filter = ('cerrada', 'liquidada', 'erp')
    inlines = [EventoCarteraInline]
    
    # Buscador extendido para el nuevo formato
    search_fields = ('num_factura', 'erp__nombre', 'nombre_paciente', 'historia_clinica')
    
    # Filtros laterales súper cómodos para auditar la carga
    list_filter = ('cerrada', 'liquidada', 'erp')
    
    inlines = [EventoCarteraInline] # Aquí verás los pagos/glosas al abrir una factura

    def rango_mora_display(self, obj):
        return obj.rango_mora
    rango_mora_display.short_description = 'Rango Mora'


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'tipo', 'descripcion', 'creado_en')
    list_filter = ('tipo',)
    search_fields = ('codigo', 'descripcion')
    readonly_fields = ('resumen', 'detalles', 'creado_en')

# También registramos EventoCartera por separado por si necesitas editar uno puntual
admin.site.register(EventoCartera)