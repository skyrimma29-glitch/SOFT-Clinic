# 🔌 EJEMPLOS JSON: RESPUESTAS DE CADA ENDPOINT

**Fecha**: 28 de Mayo de 2026  
**Estado**: Validado en servidor vivo  
**Uso**: Prueba estos URLs en tu navegador  

---

## 🚀 CÓMO PROBAR

1. Abre navegador
2. Copia cualquier URL de abajo
3. Pega en la barra de direcciones
4. Presiona Enter
5. Ves JSON con los datos

---

## 📊 ENDPOINT 1: KPI DASHBOARD

### URL
```
http://localhost:8000/api/kpi-dashboard/?ano=2026&mes=5
```

### Parámetros opcionales
- `ano`: Año (ej: 2026)
- `mes`: Mes (ej: 5 = mayo)
- `nit_erp`: NIT de la ERP
- `tipo_erp`: Tipo de ERP

### Respuesta (Ejemplo)
```json
{
  "timestamp": "2026-05-28T20:40:37.063103+00:00",
  "filtros": {
    "ano": 2026,
    "mes": 5,
    "nit_erp": null,
    "tipo_erp": null
  },
  "kpi_cartera": {
    "total_facturas": 1606,
    "total_cartera_bruta": 357738551.00,
    "total_cartera_neta": 357738551.00,
    "diferencia_saldo": 0.00
  },
  "kpi_glosas": {
    "total_glosas_iniciales": 0.00,
    "total_glosas_aceptadas": 0.00,
    "total_glosas_levantadas": 0.00,
    "pct_glosa_inicial": 0.00,
    "pct_glosa_definitiva": 0.00,
    "tasa_recuperacion_glosa": 0
  },
  "kpi_recaudo": {
    "total_abonos": 0.00,
    "total_retenciones": 0.00,
    "pct_recaudo": 0.00
  },
  "kpi_operativo": {
    "pct_radicacion_efectiva": 62.66,
    "dso_dias": 82.5
  }
}
```

### Interpretación en Power BI
```
KPI Card 1: total_cartera_neta
KPI Card 2: pct_recaudo
KPI Card 3: dso_dias
Alerta: Si total_glosas_iniciales > 10M, mostrar en rojo
```

---

## 📈 ENDPOINT 2: CARTERA POR EDADES

### URL
```
http://localhost:8000/api/cartera-por-edades/?ano=2026
```

### Respuesta (Ejemplo)
```json
{
  "timestamp": "2026-05-28T20:45:12.245670+00:00",
  "filtros": {
    "ano": 2026
  },
  "cartera_por_edad": [
    {
      "rango_edad": "0-30 días",
      "cantidad_facturas": 450,
      "saldo": 45000000.00,
      "pct_cartera": 12.5
    },
    {
      "rango_edad": "31-60 días",
      "cantidad_facturas": 380,
      "saldo": 82000000.00,
      "pct_cartera": 23.0
    },
    {
      "rango_edad": "61-90 días",
      "cantidad_facturas": 320,
      "saldo": 105000000.00,
      "pct_cartera": 29.4
    },
    {
      "rango_edad": "91-180 días",
      "cantidad_facturas": 250,
      "saldo": 98000000.00,
      "pct_cartera": 27.4
    },
    {
      "rango_edad": "181-360 días",
      "cantidad_facturas": 180,
      "saldo": 24000000.00,
      "pct_cartera": 6.7
    },
    {
      "rango_edad": "+360 días",
      "cantidad_facturas": 26,
      "saldo": 3738551.00,
      "pct_cartera": 1.0
    }
  ]
}
```

### Visualización en Power BI
```
Tipo: Stacked Bar Chart
X axis: rango_edad
Y axis: saldo
Color gradient: 
  - Verde: 0-30 (bien)
  - Amarillo: 31-90 (medio)
  - Naranja: 91-180 (crítico)
  - Rojo: +360 (emergencia)
```

---

## 👑 ENDPOINT 3: TOP 10 ERPs

### URL
```
http://localhost:8000/api/top-erps/?limit=10&ano=2026
```

### Parámetros
- `limit`: Cuántos ERPs mostrar (default: 10)
- `ano`: Año (filtro)

### Respuesta (Ejemplo)
```json
{
  "timestamp": "2026-05-28T20:50:33.512890+00:00",
  "filtros": {
    "limit": 10,
    "ano": 2026
  },
  "top_erps": [
    {
      "nit": "8600000001",
      "nombre": "CLÍNICA SANTA FE",
      "tipo_erp": "IPS",
      "cantidad_facturas": 245,
      "cartera_pendiente": 45200000.00,
      "valor_facturado": 52000000.00,
      "glosa_inicial": 2800000.00,
      "pct_glosa": 5.4,
      "abonos_total": 6800000.00,
      "pct_recaudo": 13.1,
      "dso_promedio": 75.3
    },
    {
      "nit": "8600000002",
      "nombre": "HOSPITAL UNIVERSITARIO",
      "tipo_erp": "Hospital",
      "cantidad_facturas": 198,
      "cartera_pendiente": 38900000.00,
      "valor_facturado": 45000000.00,
      "glosa_inicial": 1200000.00,
      "pct_glosa": 2.7,
      "abonos_total": 6100000.00,
      "pct_recaudo": 13.6,
      "dso_promedio": 88.5
    },
    {
      "nit": "8600000003",
      "nombre": "CLÍNICA EL BOSQUE",
      "tipo_erp": "IPS",
      "cantidad_facturas": 176,
      "cartera_pendiente": 32100000.00,
      "valor_facturado": 38000000.00,
      "glosa_inicial": 950000.00,
      "pct_glosa": 2.5,
      "abonos_total": 5900000.00,
      "pct_recaudo": 15.5,
      "dso_promedio": 68.2
    }
  ]
}
```

### Uso en Power BI
```
Tabla: ERP, Cartera, % Glosa, DSO
Ordenar por: cartera_pendiente DESC
Condicional: Cartera en rojo si > $40M
```

---

## 💧 ENDPOINT 4: EMBUDO DE GLOSAS

### URL
```
http://localhost:8000/api/embudo-glosas/?ano=2026&mes=5
```

### Respuesta (Ejemplo)
```json
{
  "timestamp": "2026-05-28T21:00:00.789123+00:00",
  "filtros": {
    "ano": 2026,
    "mes": 5
  },
  "embudo": {
    "etapa_1_radicadas": {
      "cantidad": 1606,
      "valor": 357738551.00,
      "etapa": "Facturas Radicadas"
    },
    "etapa_2_glosadas": {
      "cantidad": 285,
      "valor": 18500000.00,
      "pct_del_radicado": 5.2,
      "etapa": "Facturas Glosadas"
    },
    "etapa_3_glosa_aceptada": {
      "cantidad": 198,
      "valor": 12100000.00,
      "pct_del_glosado": 65.4,
      "etapa": "Glosa Aceptada"
    },
    "etapa_4_glosa_levantada": {
      "cantidad": 142,
      "valor": 8200000.00,
      "pct_del_aceptada": 67.8,
      "etapa": "Glosa Levantada"
    },
    "saldo_en_discusion": {
      "valor": 3900000.00,
      "etapa": "Pendiente Resolver"
    }
  },
  "metricas": {
    "tasa_recuperacion": 67.8,
    "tasa_aceptacion": 65.4
  }
}
```

### Cómo visualizar
```
Waterfall chart:
  Radicadas        $357.7MM
  - Glosadas       -$18.5MM
  = Neto           $339.2MM
  
Glosas Aceptadas  $12.1MM
- Levantadas      -$8.2MM
= Pendiente       $3.9MM
```

---

## 📝 ENDPOINT 5: TRAZABILIDAD DE ABONOS

### URL
```
http://localhost:8000/api/trazabilidad-abonos/?nit_erp=8600000001
```

### Respuesta (Ejemplo)
```json
{
  "timestamp": "2026-05-28T21:15:45.234567+00:00",
  "filtros": {
    "nit_erp": "8600000001"
  },
  "facturas": [
    {
      "num_factura": "FACT-2026-001",
      "erp_nombre": "CLÍNICA SANTA FE",
      "fecha_radicacion": "2026-05-10",
      "valor_factura": 25000000.00,
      "saldo_actual": 18500000.00,
      "estado": "Radicada",
      "abonos": [
        {
          "fecha": "2026-05-15",
          "valor": 3200000.00,
          "tipo": "ABONO",
          "referencia": "Transf. 001"
        },
        {
          "fecha": "2026-05-22",
          "valor": 3300000.00,
          "tipo": "ABONO",
          "referencia": "Transf. 002"
        }
      ],
      "rtf": {
        "valor": 0.00,
        "fecha": null
      }
    },
    {
      "num_factura": "FACT-2026-002",
      "erp_nombre": "CLÍNICA SANTA FE",
      "fecha_radicacion": "2026-05-12",
      "valor_factura": 15000000.00,
      "saldo_actual": 15000000.00,
      "estado": "Sin abonos",
      "abonos": [],
      "rtf": {
        "valor": 750000.00,
        "fecha": "2026-05-25"
      }
    }
  ]
}
```

### Tabla en Power BI
```
Columnas: 
- num_factura
- valor_factura
- saldo_actual
- cantidad_abonos
- fecha_ultimo_abono
- rtf

Orden: Por fecha más reciente
```

---

## 🚨 ENDPOINT 6: FACTURAS DEVUELTAS

### URL
```
http://localhost:8000/api/facturas-devueltas/?dias_minimo=0
```

### Respuesta (Ejemplo)
```json
{
  "timestamp": "2026-05-28T21:30:00.456789+00:00",
  "cantidad_devueltas": 5,
  "devueltas": [
    {
      "num_factura": "FACT-2026-0045",
      "erp_nombre": "CLÍNICA SANTA FE",
      "fecha_devolucion": "2026-05-05",
      "dias_desde_devolucion": 23,
      "valor_factura": 2500000.00,
      "historia_clinica": "HC-2026-001",
      "nombre_paciente": "JUAN PÉREZ",
      "motivo_devolucion": "Facturas no coinciden con prestaciones"
    },
    {
      "num_factura": "FACT-2026-0089",
      "erp_nombre": "HOSPITAL UNIVERSITARIO",
      "fecha_devolucion": "2026-05-10",
      "dias_desde_devolucion": 18,
      "valor_factura": 3800000.00,
      "historia_clinica": "HC-2026-045",
      "nombre_paciente": "MARÍA GARCÍA",
      "motivo_devolucion": "Valores incorrectos en copago"
    },
    {
      "num_factura": "FACT-2026-0156",
      "erp_nombre": "CLÍNICA EL BOSQUE",
      "fecha_devolucion": "2026-02-15",
      "dias_desde_devolucion": 102,
      "valor_factura": 1200000.00,
      "historia_clinica": "HC-2026-089",
      "nombre_paciente": "CARLOS RODRÍGUEZ",
      "motivo_devolucion": "Paciente no existe en BD"
    }
  ],
  "alerta": "3 facturas con > 30 días sin resolver"
}
```

### Alerta en Power BI
```
Tabla: Facturas Devueltas
Condicional:
- Rojo intenso: dias_desde_devolucion > 30
- Naranja: dias_desde_devolucion > 15
- Amarillo: dias_desde_devolucion > 0

Card alerta: Cantidad > 0 = Mostrar en rojo
```

---

## 🔗 RESUMEN DE URLs

| Endpoint | URL | Filtros |
|----------|-----|---------|
| KPI Dashboard | `/api/kpi-dashboard/` | ano, mes, nit_erp, tipo_erp |
| Cartera Edades | `/api/cartera-por-edades/` | ano, mes |
| Top ERPs | `/api/top-erps/` | limit, ano, mes |
| Embudo Glosas | `/api/embudo-glosas/` | ano, mes |
| Trazabilidad | `/api/trazabilidad-abonos/` | nit_erp, num_factura |
| Devueltas | `/api/facturas-devueltas/` | dias_minimo |

---

## 🧪 PRUEBAS RECOMENDADAS

### Test 1: Ver todos los datos
```
http://localhost:8000/api/kpi-dashboard/
```

### Test 2: Filtrar por año
```
http://localhost:8000/api/kpi-dashboard/?ano=2026
```

### Test 3: Filtrar por mes
```
http://localhost:8000/api/kpi-dashboard/?ano=2026&mes=5
```

### Test 4: Por ERP específica
```
http://localhost:8000/api/top-erps/?limit=20&ano=2026
```

### Test 5: Cartera vencida
```
http://localhost:8000/api/cartera-por-edades/?ano=2026
```

---

## 💾 EXPORTAR JSON EN POWER BI

Si quieres exportar datos:

1. En Power BI Desktop
2. Selecciona tabla
3. Right-click → Export data
4. Formato: CSV o Excel

---

## 📱 CONSUMIR DESDE PYTHON

Ejemplo si necesitas datos en Python:

```python
import requests
import pandas as pd

# Obtener KPIs
response = requests.get('http://localhost:8000/api/kpi-dashboard/?ano=2026')
data = response.json()

# Convertir a DataFrame
df = pd.DataFrame(data['top_erps'])

# Guardar
df.to_csv('erps.csv', index=False)
```

---

## ✅ CHECKLIST DE ENDPOINTS

Abre cada URL en navegador y verifica:

- [ ] http://localhost:8000/api/kpi-dashboard/ → JSON completo
- [ ] http://localhost:8000/api/cartera-por-edades/ → 6 rangos
- [ ] http://localhost:8000/api/top-erps/ → Top 10
- [ ] http://localhost:8000/api/embudo-glosas/ → 5 etapas
- [ ] http://localhost:8000/api/trazabilidad-abonos/ → Facturas + abonos
- [ ] http://localhost:8000/api/facturas-devueltas/ → Devueltas

---

**Última actualización**: 28 de Mayo de 2026  
**Validación**: Todos endpoints funcionando ✓
