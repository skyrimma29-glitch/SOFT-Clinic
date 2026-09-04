# ⚡ QUICK START: 5 Comandos para Empezar

**Duración total: 30 minutos**

---

## 📝 ANTES DE EMPEZAR

Verifica que tienes:
- ✅ PostgreSQL corriendo
- ✅ Python 3.8+
- ✅ Power BI Desktop (opcional para pruebas)
- ✅ Acceso a `c:\SoftClinicProject\`

---

## 🚀 5 PASOS EXACTOS

### PASO 1: Instalar dependencias (5 min)

```bash
cd c:\SoftClinicProject
pip install -r requirements.txt
```

Esto instala:
- `djangorestframework==3.14.0`
- `django-cors-headers==4.3.1`

---

### PASO 2: Actualizar settings.py (10 min)

Abre `core/settings.py` y busca:

#### A) INSTALLED_APPS
Encuentra la línea `'django.contrib.humanize',` y agrega debajo:
```python
INSTALLED_APPS = [
    ...
    'facturacion',
    'django.contrib.humanize',
    'rest_framework',          # ← AGREGAR
    'corsheaders',             # ← AGREGAR
]
```

#### B) MIDDLEWARE
Encuentra la primera línea de MIDDLEWARE y busca:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    ...
]
```

Agrega después de SecurityMiddleware:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # ← AGREGAR AQUÍ
    'django.contrib.sessions.middleware.SessionMiddleware',
    ...
]
```

#### C) Al final del archivo
```python
# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 1000,
}

# CORS configuration for Power BI
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
]
```

---

### PASO 3: Ejecutar Vistas SQL (5 min)

Abre PostgreSQL y ejecuta:

```bash
# Opción 1: Desde terminal
psql -U postgres -d soft_clinic_db -f facturacion/sql/vistas_power_bi.sql
psql -U postgres -d soft_clinic_db -f facturacion/sql/indices_optimizacion.sql

# Opción 2: Copiar-pegar en pgAdmin
# Abre el archivo facturacion/sql/vistas_power_bi.sql
# Copia TODO el contenido
# Pégalo en pgAdmin Query Tool
# Ejecuta (F5)
# Repite con indices_optimizacion.sql
```

**Verificar que funcionó:**
```sql
SELECT * FROM v_facturas_con_kpi LIMIT 5;
```

Si ves datos, ✅ está bien.

---

### PASO 4: Probar API (5 min)

```bash
cd c:\SoftClinicProject
python manage.py runserver
```

En el navegador, abre:
```
http://localhost:8000/api/kpi-dashboard/
```

Deberías ver JSON como:
```json
{
  "timestamp": "2026-05-28T14:30:00...",
  "kpi_cartera": {
    "total_facturas": 450,
    "total_cartera_bruta": 15000000.00,
    ...
  },
  ...
}
```

✅ Si ves esto, la API funciona.

---

### PASO 5: Conectar Power BI (15 min)

#### Opción A: PostgreSQL Directo (Recomendado)

1. Abre **Power BI Desktop**
2. Clic: **Get Data**
3. Busca: **PostgreSQL Database**
4. Rellena:
   - Server: `127.0.0.1`
   - Database: `soft_clinic_db`
   - Username: `postgres`
   - Password: `Wnjr9367`
5. Clic: **Connect**
6. Selecciona las vistas:
   - ✅ v_facturas_con_kpi
   - ✅ v_eventos_factura
   - ✅ v_kpi_por_erp
   - ✅ v_cartera_por_edad
   - ✅ v_embudo_glosas
   - ✅ v_facturas_devueltas
7. Clic: **Load**

#### Opción B: API REST

1. Clic: **Get Data**
2. Busca: **Web**
3. URL: `http://localhost:8000/api/kpi-dashboard/`
4. Clic: **OK**
5. Power BI convertirá JSON a tabla automáticamente

---

## ✅ VALIDACIÓN FINAL

Después de los 5 pasos, verifica:

```bash
# Test 1: PostgreSQL
psql -U postgres -d soft_clinic_db
SELECT COUNT(*) FROM v_facturas_con_kpi;
-- Debería retornar un número > 0

# Test 2: API REST
curl http://localhost:8000/api/kpi-dashboard/
# Debería retornar JSON

# Test 3: Power BI
# Crear tarjeta con KPI "Total Cartera Neta"
# Debería mostrar un número
```

---

## 🎯 Siguiente: Crear Visualizaciones

Ahora que tienes datos en Power BI, crea:

### Tarjeta KPI
1. Arrastra: `total_cartera_neta` (medida DAX)
2. Personaliza: Rojo si > 500M, Verde si < 250M

### Gráfico de Barras
1. Arrastra: `rango_edad` (categoría)
2. Arrastra: `saldo` (valor)
3. Título: "Cartera por Edades"

### Tabla Top ERPs
1. Tabla con: `erp_nombre`, `cartera_pendiente`, `cantidad_facturas`
2. Ordena por: `cartera_pendiente` DESC

Para medidas DAX completas, ver: **CONFIGURACION_POWER_BI.md**

---

## 📚 Documentación Completa

- **Visión General**: README_FASE1.md
- **Pasos Detallados**: CHECKLIST_FASE1.md
- **Troubleshooting**: CONFIGURACION_POWER_BI.md
- **Estructura API**: REFERENCIA_ENDPOINTS.md
- **Arquitectura**: ARQUITECTURA_DIAGRAMA.md
- **Todo Indexado**: INDICE_DOCUMENTACION.md

---

## ⏱️ TIMELINE

| Paso | Duracion | Subtotal |
|------|----------|---------|
| 1. pip install | 5 min | 5 min |
| 2. Editar settings.py | 10 min | 15 min |
| 3. Ejecutar SQL | 5 min | 20 min |
| 4. Probar API | 5 min | 25 min |
| 5. Conectar Power BI | 15 min | 40 min |

**Si todo sale bien: 30-40 minutos**
**Si tienes preguntas: +20 minutos (consulta docs)**

---

## 🆘 Si algo falla

### Error: "Could not connect to PostgreSQL"
```bash
# Verifica que PostgreSQL está corriendo:
psql -U postgres
\c soft_clinic_db
```

### Error: "Module not found: rest_framework"
```bash
pip install djangorestframework
```

### Error: "ModuleNotFoundError: No module named 'corsheaders'"
```bash
pip install django-cors-headers
```

### Power BI: "No connection to PostgreSQL"
- Verifica firewall (puerto 5432)
- Usa IP `127.0.0.1` en lugar de `localhost`
- Verifica usuario/contraseña

Ver más: **TROUBLESHOOTING** en CONFIGURACION_POWER_BI.md

---

## ✨ SUCCESS

Si viste todo funcionar:
- ✅ API retorna JSON
- ✅ Vistas SQL tienen datos
- ✅ Power BI conectado
- ✅ Visualizaciones creadas

**¡Felicidades! FASE 1 completada 🚀**

---

**Próximo**: Leer CONFIGURACION_POWER_BI.md para crear dashboard completo con 10 medidas DAX y 8 visualizaciones.
