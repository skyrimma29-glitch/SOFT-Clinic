# REFERENCIA RÁPIDA: Estructura de datos de cada Endpoint

## 1️⃣ `/api/kpi-dashboard/` - KPIs Principales

**Propósito**: Traer todos los indicadores clave de una sola consulta

**Parámetros opcionales**:
```
?ano=2026&mes=5&nit_erp=800123456&tipo_erp=Régimen Contributivo
```

**Estructura de Respuesta**:
```json
{
  "timestamp": "2026-05-28T14:30:00.123456Z",
  "filtros": {
    "ano": "2026",
    "mes": "5",
    "nit_erp": null,
    "tipo_erp": null
  },
  "kpi_cartera": {
    "total_facturas": 450,
    "total_cartera_bruta": 15000000.00,
    "total_cartera_neta": 12000000.00,
    "diferencia_saldo": 3000000.00
  },
  "kpi_glosas": {
    "total_glosas_iniciales": 2000000.00,
    "total_glosas_aceptadas": 800000.00,
    "total_glosas_levantadas": 600000.00,
    "pct_glosa_inicial": 13.33,
    "pct_glosa_definitiva": 5.33,
    "tasa_recuperacion_glosa": 75.0
  },
  "kpi_recaudo": {
    "total_abonos": 8000000.00,
    "total_retenciones": 1200000.00,
    "pct_recaudo": 53.33
  },
  "kpi_operativo": {
    "pct_radicacion_efectiva": 95.5,
    "dso_dias": 45.2
  }
}
```

---

## 2️⃣ `/api/cartera-por-edades/` - Cartera por Rangos de Edad

**Propósito**: Visualizar en gráfico de barras la distribución de cartera por antigüedad

**Parámetros opcionales**:
```
?ano=2026&mes=5
```

**Estructura de Respuesta**:
```json
{
  "rango_0_30": {
    "etiqueta": "0-30 días",
    "saldo": 3000000.00,
    "cantidad_facturas": 120
  },
  "rango_31_60": {
    "etiqueta": "31-60 días",
    "saldo": 2500000.00,
    "cantidad_facturas": 95
  },
  "rango_61_90": {
    "etiqueta": "61-90 días",
    "saldo": 2000000.00,
    "cantidad_facturas": 78
  },
  "rango_91_180": {
    "etiqueta": "91-180 días",
    "saldo": 2000000.00,
    "cantidad_facturas": 85
  },
  "rango_181_360": {
    "etiqueta": "181-360 días",
    "saldo": 1500000.00,
    "cantidad_facturas": 55
  },
  "rango_mayor_360": {
    "etiqueta": "+360 días (CRÍTICO)",
    "saldo": 1000000.00,
    "cantidad_facturas": 17
  }
}
```

---

## 3️⃣ `/api/top-erps/` - Top ERPs por Cartera

**Propósito**: Ver ranking de qué ERPs deben más dinero

**Parámetros opcionales**:
```
?ano=2026&mes=5&limite=10
```

**Estructura de Respuesta**:
```json
{
  "cantidad": 10,
  "erps": [
    {
      "erp__nit": "800123456",
      "erp__nombre": "SANITAS SA EPS-C",
      "erp__tipo_erp__nombre": "Régimen Contributivo",
      "total_cartera": 4500000.00,
      "cantidad_facturas": 125,
      "total_glosas": 600000.00
    },
    {
      "erp__nit": "800234567",
      "erp__nombre": "NUEVA EPS SA",
      "erp__tipo_erp__nombre": "Régimen Contributivo",
      "total_cartera": 3200000.00,
      "cantidad_facturas": 98,
      "total_glosas": 400000.00
    }
  ]
}
```

---

## 4️⃣ `/api/embudo-glosas/` - Embudo de Glosas

**Propósito**: Analizar cómo progresa una glosa desde objeción hasta acuerdo

**Parámetros opcionales**:
```
?ano=2026&mes=5
```

**Estructura de Respuesta**:
```json
{
  "embudo": {
    "radicadas": {
      "cantidad": 450,
      "valor": 15000000.00
    },
    "glosadas_inicialmente": {
      "cantidad": 120,
      "valor": 2000000.00
    },
    "aceptadas_ips": {
      "valor": 800000.00
    },
    "levantadas_erp": {
      "valor": 600000.00
    },
    "en_discusion": {
      "valor": 600000.00
    }
  }
}
```

**Interpretación**:
- 450 facturas radicadas por $15M
- 120 de esas facturas fueron glosadas por $2M
- IPS aceptó perder $800k (glosa definitiva)
- ERP levantó (pagará) $600k adicionales
- Quedan $600k en discusión (ni aceptados ni levantados)

---

## 5️⃣ `/api/trazabilidad-abonos/` - Detalle de Abonos

**Propósito**: Ver cada factura y cómo ha sido pagada (1, 2, 3, 4 abonos)

**Parámetros opcionales**:
```
?ano=2026&mes=5&limite=100
```

**Estructura de Respuesta**:
```json
{
  "abonos": [
    {
      "num_factura": "FE00012345",
      "erp_nombre": "SANITAS SA EPS-C",
      "fecha_radicacion": "2026-03-15",
      "valor_neto": 5000000.00,
      "abonos": [
        2000000.00,
        2000000.00,
        800000.00
      ],
      "rtf_total": 200000.00,
      "saldo_actual": 0.00
    },
    {
      "num_factura": "FE00012346",
      "erp_nombre": "NUEVA EPS SA",
      "fecha_radicacion": "2026-03-20",
      "valor_neto": 3000000.00,
      "abonos": [
        1500000.00,
        1000000.00
      ],
      "rtf_total": 150000.00,
      "saldo_actual": 350000.00
    }
  ]
}
```

**Interpretación**:
- Factura 1: Pagada completamente en 3 abonos (2M + 2M + 800k)
- Factura 2: Pagada parcialmente en 2 abonos (1.5M + 1M = 2.5M de 3M)
- Saldo_actual = Valor_neto - (Abono1 + Abono2 + ... + RTF)

---

## 6️⃣ `/api/facturas-devueltas/` - Facturas Devueltas (ALERTA)

**Propósito**: Identificar facturas rechazadas que requieren refacturación urgente

**Parámetros opcionales**:
```
?ano=2026&mes=5
```

**Estructura de Respuesta**:
```json
{
  "devueltas": [
    {
      "num_factura": "FE00010234",
      "erp_nombre": "SANITAS SA EPS-C",
      "fecha_devolucion": "2026-05-15",
      "dias_desde_devolucion": 13,
      "valor_factura": 2500000.00
    },
    {
      "num_factura": "FE00010456",
      "erp_nombre": "NUEVA EPS SA",
      "fecha_devolucion": "2026-05-10",
      "dias_desde_devolucion": 18,
      "valor_factura": 1800000.00
    }
  ]
}
```

**Interpretación**:
- Factura devuelta hace 13 días → Urgente refacturar
- Factura devuelta hace 18 días → MUY urgente (riesgo de vencer términos)

---

## 🔍 USO EN POWER BI

### Ejemplo 1: Crear tarjeta de "Total Cartera Neta"
```
1. Get Data → Web
2. URL: http://localhost:8000/api/kpi-dashboard/
3. Convertir JSON a tabla
4. Crear tarjeta con: kpi_cartera[total_cartera_neta]
```

### Ejemplo 2: Gráfico de barras "Cartera por Edades"
```
1. Get Data → Web
2. URL: http://localhost:8000/api/cartera-por-edades/
3. Gráfico de barras con X = rango, Y = saldo
```

### Ejemplo 3: Top 10 ERPs
```
1. Get Data → Web
2. URL: http://localhost:8000/api/top-erps/?limite=10
3. Tabla con sorteo por total_cartera DESC
```

---

## ⚡ FILTROS COMUNES

Todos los endpoints aceptan estos parámetros:

```
?ano=2026              # Filtrar por año
?mes=5                 # Filtrar por mes (1-12)
?nit_erp=800123456     # Filtrar por NIT de ERP
?tipo_erp=Régimen Contributivo  # Filtrar por tipo de régimen
?limite=10             # Limitar cantidad de resultados (top-erps, trazabilidad)
```

**Ejemplo combinado**:
```
/api/kpi-dashboard/?ano=2026&mes=5&tipo_erp=Régimen+Subsidiado
/api/cartera-por-edades/?ano=2026
/api/top-erps/?ano=2026&mes=5&limite=15
```

---

## 📋 RESUMEN DE USO

| Endpoint | Gráfico | Filtros |
|----------|---------|---------|
| `/api/kpi-dashboard/` | Tarjetas KPI | Año, Mes, NIT, Tipo |
| `/api/cartera-por-edades/` | Barras | Año, Mes |
| `/api/top-erps/` | Tabla | Año, Mes, Límite |
| `/api/embudo-glosas/` | Waterfall | Año, Mes |
| `/api/trazabilidad-abonos/` | Tabla Detalle | Año, Mes, Límite |
| `/api/facturas-devueltas/` | Tabla Alerta | Año, Mes |

---

## 🚀 PRÓXIMO: Ejecutar estos pasos

1. Instalar dependencias: `pip install -r requirements.txt`
2. Actualizar settings.py (agregar REST_FRAMEWORK)
3. Ejecutar: `python manage.py runserver`
4. Probar cada endpoint en el navegador
5. Conectar Power BI usando estas URLs
