# core/urls.py o urls.py raíz
from pathlib import Path

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from facturacion import api
from facturacion import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='home'),
    path('subir/', views.subir_cartera, name='subir_cartera'),
    path('actualizar-pae/', views.actualizar_eventos_pae, name='actualizar_pae'),
    path('facturas/', views.lista_facturas, name='lista_facturas'),
    path('exportar-eas/', views.exportar_eas, name='exportar_eas'),
    path('exportar-eas-seleccionadas/', views.exportar_eas_seleccionadas, name='exportar_eas_seleccionadas'),
    path('logs/', views.import_logs, name='import_logs'),
    path('logs/<int:log_id>/', views.import_log_detail, name='import_log_detail'),
    path('limpiar-cartera/', views.limpiar_cartera, name='limpiar_cartera'),
    path('environments/', views.environments, name='environments'),
    path('resolver-duplicados-dif/', views.resolver_duplicados_dif, name='resolver_duplicados_dif'),
    path('facturas/<int:factura_id>/actualizar-campo/', views.actualizar_campo_factura, name='actualizar_campo_factura'),
    path('limpiar-import-logs/', views.limpiar_import_logs, name='limpiar_import_logs'),

    # ===== API REST PARA POWER BI =====
    path('api/kpi-dashboard/', api.kpi_dashboard, name='api_kpi_dashboard'),
    path('api/cartera-por-edades/', api.cartera_por_edades, name='api_cartera_edades'),
    path('api/top-erps/', api.top_erps_cartera, name='api_top_erps'),
    path('api/embudo-glosas/', api.embudo_glosas, name='api_embudo_glosas'),
    path('api/trazabilidad-abonos/', api.trazabilidad_abonos, name='api_trazabilidad_abonos'),
    path('api/facturas-devueltas/', api.facturas_devueltas, name='api_devueltas'),
    path('api/dashboard-data/', api.dashboard_data, name='api_dashboard_data'),
    path('api/dashboard-factura/', api.dashboard_factura, name='api_dashboard_factura'),
    path('api/dashboard-pulse/', api.dashboard_pulse, name='api_dashboard_pulse'),
]

base_dir = Path(__file__).resolve().parent.parent
urlpatterns += static(settings.STATIC_URL, document_root=str(base_dir / 'facturacion' / 'static'))
urlpatterns += static(settings.STATIC_URL, document_root=str(base_dir / 'static'))
