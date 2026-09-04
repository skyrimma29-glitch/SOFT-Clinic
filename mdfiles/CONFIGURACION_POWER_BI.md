# Guía de Configuración: Power BI ↔ ClinicSoft-IPS

## FASE 1: CONECTAR POWER BI A POSTGRESQL

### Paso 1: Instalar dependencia (Django REST Framework)
```bash
pip install djangorestframework django-cors-headers
```

### Paso 2: Actualizar settings.py
```python
# En INSTALLED_APPS, agregar:
INSTALLED_APPS = [
    ...
    'rest_framework',
    'corsheaders',
    ...
]

# En MIDDLEWARE, agregar (después de SecurityMiddleware):
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # <-- AGREGAR AQUÍ
    ...
]

# Al final de settings.py, agregar:
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:5173",  # Vite dev server
]

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 1000,
    'DEFAULT_FILTER_BACKENDS': ['rest_framework.filters.SearchFilter'],
}
```

### Paso 3: Ejecutar las vistas SQL en PostgreSQL
Abrir pgAdmin o DBeaver y ejecutar el archivo:
```sql
-- En facturacion/sql/vistas_power_bi.sql
```

### Paso 4: Verificar que la API funciona
```bash
python manage.py runserver
# Visitar: http://localhost:8000/api/kpi-dashboard/
# Debería retornar JSON con todos los KPIs
```

---

## FASE 2: CONECTAR POWER BI A LA API

### Opción A: Conexión directa a PostgreSQL (RECOMENDADO - MÁS RÁPIDO)
1. En Power BI Desktop, clic en **"Get Data"** → **PostgreSQL Database**
2. Configurar conexión:
   - Server: `127.0.0.1`
   - Database: `soft_clinic_db`
   - Username: `postgres`
   - Password: `Wnjr9367`
3. En el Navigator, seleccionar las vistas:
   - `v_facturas_con_kpi`
   - `v_eventos_factura`
   - `v_kpi_por_erp`
   - `v_cartera_por_edad`
   - `v_embudo_glosas`
   - `v_facturas_devueltas`
4. Cargar datos

### Opción B: Conexión a API REST (MÁS FLEXIBLE)
1. En Power BI, clic en **"Get Data"** → **Web**
2. URLs de los endpoints:
   ```
   http://localhost:8000/api/kpi-dashboard/
   http://localhost:8000/api/cartera-por-edades/
   http://localhost:8000/api/top-erps/
   http://localhost:8000/api/embudo-glosas/
   http://localhost:8000/api/trazabilidad-abonos/
   http://localhost:8000/api/facturas-devueltas/
   ```
3. Convertir cada respuesta JSON a tabla

---

## FASE 3: MEDIDAS DAX EN POWER BI

### KPI 1: Total Cartera Neta
```dax
Total Cartera Neta = 
SUMX(
    v_facturas_con_kpi,
    [saldo_actual]
)
```

### KPI 2: % Glosa Inicial (Índice de Glosabilidad)
```dax
% Glosa Inicial = 
DIVIDE(
    SUMX(v_facturas_con_kpi, [valor_glosa_inicial]),
    SUMX(v_facturas_con_kpi, [valor_neto]),
    0
) * 100
```

### KPI 3: % Glosa Definitiva (Impacto Real)
```dax
% Glosa Aceptada = 
DIVIDE(
    SUMX(v_eventos_factura, [glosa_aceptada_total]),
    SUMX(v_facturas_con_kpi, [valor_neto]),
    0
) * 100
```

### KPI 4: Tasa de Recuperación de Glosas
```dax
Tasa Recuperación Glosa % = 
DIVIDE(
    SUMX(v_eventos_factura, [glosa_levantada_total]),
    SUMX(v_eventos_factura, [glosa_inicial_total]),
    0
) * 100
```

### KPI 5: % Recaudo Efectivo
```dax
% Recaudo = 
DIVIDE(
    SUMX(v_eventos_factura, [abonos_total]),
    SUMX(v_facturas_con_kpi, [valor_neto]),
    0
) * 100
```

### KPI 6: Days Sales Outstanding (DSO)
```dax
DSO Promedio = 
AVERAGEX(
    v_facturas_con_kpi,
    [dias_desde_radicacion]
)
```

### KPI 7: Tasa de Devoluciones
```dax
% Devoluciones = 
DIVIDE(
    COUNTA(v_facturas_devueltas[num_factura]),
    COUNTA(v_facturas_con_kpi[num_factura]),
    0
) * 100
```

### KPI 8: Costo Impositivo por ERP
```dax
RTF por Millón = 
DIVIDE(
    SUMX(v_eventos_factura, [rtf_total]),
    SUMX(v_facturas_con_kpi, [valor_neto]) / 1000000,
    0
)
```

### KPI 9: Saldo en Discusión (Glosa - Aceptada - Levantada)
```dax
Saldo en Discusión = 
SUMX(
    v_eventos_factura,
    [glosa_inicial_total] - [glosa_aceptada_total] - [glosa_levantada_total]
)
```

### KPI 10: % Radicación Efectiva
```dax
% Radicación Efectiva = 
DIVIDE(
    COUNTA(
        FILTER(v_facturas_con_kpi, NOT(ISBLANK([fecha_radicacion_inicial])))
    ),
    COUNTA(v_facturas_con_kpi[num_factura]),
    0
) * 100
```

---

## FASE 4: VISUALIZACIONES RECOMENDADAS

### 1. Termómetro: Total Cartera Neta
- **Medida**: Total Cartera Neta
- **Objetivo**: 0 (0 deuda ideal)
- **Rojo**: > 500.000.000
- **Amarillo**: 250.000.000 - 500.000.000
- **Verde**: < 250.000.000

### 2. Embudo (Waterfall Chart): Cascada de Glosas
- X: Etapas (Radicadas → Glosadas → Aceptadas → Levantadas → En Discusión)
- Y: Valor monetario
- Datos de: `v_embudo_glosas`

### 3. Barras: Cartera por Edades
- X: Rango de edad (0-30, 31-60, 61-90, 91-180, 181-360, +360)
- Y: Valor de cartera
- Datos de: `v_cartera_por_edad`

### 4. Tabla Dinámica: Top 10 ERPs por Cartera
- Columnas: Nombre ERP | Tipo ERP | Cartera Pendiente | % Recaudo | DSO
- Datos de: `v_kpi_por_erp`

### 5. Tarjeta: Facturas Devueltas (ALERTA CRÍTICA)
- Medida: COUNT(v_facturas_devueltas[num_factura])
- Formato: Grande, en Rojo si > 10

### 6. Línea de Tiempo: Velocidad de Pago (Trend)
- X: Periodo (Mes/Trimestre)
- Y: Días promedio entre radicación y primer abono
- Mostrar tendencia (creciente = MALO)

### 7. Scatter Plot: Glosa Inicial vs Recaudo por ERP
- X: % Glosa Inicial
- Y: % Recaudo
- Size: Valor facturado
- Category: ERP

### 8. Mapa: Clasificación 2x2 (Eficiencia vs Volumen)
- X: DSO Promedio (eje horizontal)
- Y: Cartera Pendiente (eje vertical)
- Cuadrantes:
  - **VERDE** (Arriba Izq): Alto volumen, rápido pago ✅
  - **AMARILLO** (Arriba Der): Alto volumen, lento pago ⚠️
  - **AZUL** (Abajo Izq): Bajo volumen, rápido pago
  - **ROJO** (Abajo Der): Bajo volumen, lento pago ❌

---

## FASE 5: CONFIGURAR FILTROS GLOBALES

### Slicers recomendados:
1. **Año**: Desde `v_facturas_con_kpi[ano_radicacion]`
2. **Mes**: Desde `v_facturas_con_kpi[mes_radicacion]`
3. **ERP**: Desde `v_kpi_por_erp[nombre]`
4. **Tipo ERP**: Desde `v_kpi_por_erp[tipo_erp]`
5. **Estado**: Desde `v_facturas_con_kpi[estado_gestion]`
6. **Rango de Mora**: Desde `v_facturas_con_kpi[rango_mora]`

---

## FASE 6: ACTUALIZACIÓN AUTOMÁTICA EN POWER BI

### Para que el Dashboard se actualice cada vez que cargas datos:

1. **En Power BI Desktop**:
   - Clic en **Transform Data** → **Settings** → **Power Query Editor**
   - Para cada fuente, clic derecho → **Edit Query**
   - En la ventana que aparece, clic en **"Invoke Function"** para cada query

2. **En Power BI Service (Cloud)**:
   - Publicar el archivo
   - Configurar **Refresh Schedule**:
     - Frecuencia: Diaria
     - Hora: 08:00 (cada mañana)
   - O usar **Incremental Refresh** para solo traer datos nuevos

---

## PRUEBAS Y VALIDACIÓN

### Test 1: Verificar conexión a PostgreSQL
```sql
SELECT * FROM v_facturas_con_kpi LIMIT 10;
```

### Test 2: Verificar API Rest
```bash
curl http://localhost:8000/api/kpi-dashboard/
# Debería retornar JSON con estructura similar a:
# {"timestamp": "...", "kpi_cartera": {...}, "kpi_glosas": {...}, ...}
```

### Test 3: En Power BI Desktop
- Cargar datos
- Crear tarjeta con medida "Total Cartera Neta"
- Debería mostrar un número

### Test 4: Publicar a Power BI Service
- Archivo > Publish
- Seleccionar workspace
- Configurar credenciales de PostgreSQL
- Probar filtros

---

## TROUBLESHOOTING

### Problema: "No se puede conectar a PostgreSQL desde Power BI"
**Solución**: 
- Verificar que PostgreSQL está corriendo: `psql -U postgres -d soft_clinic_db`
- Verificar firewall: Puerto 5432 abierto
- En Power BI, usar IP `127.0.0.1` en lugar de `localhost`

### Problema: "Las medidas DAX retornan valores incorrectos"
**Solución**:
- Verificar que las vistas SQL se ejecutaron correctamente
- Refreshear datos en Power BI (Ctrl+Shift+R)
- Verificar que los nombres de tablas coinciden (case-sensitive)

### Problema: "El Dashboard se demora mucho en cargar"
**Solución**:
- Agregar índices en PostgreSQL:
  ```sql
  CREATE INDEX idx_factura_radicacion ON facturacion_factura(fecha_radicacion_inicial);
  CREATE INDEX idx_evento_tipo ON facturacion_eventocartera(tipo);
  ```
- Reducir cantidad de datos en visualizaciones (Top N en lugar de All)
- Usar "Import" en lugar de "DirectQuery" en Power BI

---

## PRÓXIMOS PASOS

1. ✅ Instalar DRF y CORS
2. ✅ Ejecutar vistas SQL en PostgreSQL
3. ✅ Verificar que la API funciona (`/api/kpi-dashboard/`)
4. Conectar Power BI a PostgreSQL
5. Crear visualizaciones con medidas DAX
6. Configurar filtros globales
7. Publicar a Power BI Service
