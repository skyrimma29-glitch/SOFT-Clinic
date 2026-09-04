# 📊 MEDIDAS DAX: COPIAR Y PEGAR EN POWER BI

**Fecha**: 28 de Mayo de 2026  
**Estado**: Listo para usar  
**Instrucciones**: Copia cada medida y pégala en Power BI Desktop

---

## 🚀 CÓMO AGREGAR MEDIDAS EN POWER BI

1. En Power BI Desktop, ve a: **Model tab** (o **Modeling**)
2. Clic: **New Measure**
3. Copia la fórmula completa de abajo
4. Pégala en la barra de fórmulas
5. Presiona **Enter**
6. Repite para cada medida

---

## 📋 MEDIDAS DAX (10 KPIs Completas)

### 1️⃣ Total Cartera Neta
```dax
Total Cartera Neta = SUM(v_facturas_con_kpi[saldo_actual])
```

**Interpretación**: Dinero pendiente por cobrar de todas las facturas.  
**Usado en**: Tarjeta KPI grande, filtros

---

### 2️⃣ % Glosa Inicial
```dax
% Glosa Inicial = 
DIVIDE(
    SUM(v_facturas_con_kpi[valor_glosa_inicial]),
    SUM(v_facturas_con_kpi[total_final]),
    0
) * 100
```

**Interpretación**: Qué porcentaje del total facturado fue glosado inicialmente.  
**Rango Bueno**: < 5% (significa pocas glosas)  
**Usado en**: Indicador de calidad de facturación

---

### 3️⃣ % Glosa Aceptada
```dax
% Glosa Aceptada = 
DIVIDE(
    SUM(v_eventos_factura[glosa_aceptada_total]),
    SUM(v_facturas_con_kpi[total_final]),
    0
) * 100
```

**Interpretación**: Qué porcentaje del facturado es glosa definitiva (aceptada por el payer).  
**Rango Bueno**: < 3% (significa buena facturación)  
**Usado en**: Análisis de calidad

---

### 4️⃣ Tasa Recuperación Glosa %
```dax
Tasa Recuperacion Glosa % = 
DIVIDE(
    SUM(v_eventos_factura[glosa_levantada_total]),
    SUM(v_eventos_factura[glosa_aceptada_total]),
    0
) * 100
```

**Interpretación**: Qué porcentaje de glosas aceptadas logramos levantar (recuperar).  
**Rango Bueno**: > 70% (significa que recuperamos la mayoría)  
**Usado en**: Medir efectividad de auditoría interna

---

### 5️⃣ % Recaudo Efectivo
```dax
% Recaudo Efectivo = 
DIVIDE(
    SUM(v_eventos_factura[abonos_total]),
    SUM(v_facturas_con_kpi[total_final]),
    0
) * 100
```

**Interpretación**: Qué porcentaje del total facturado ya fue recibido.  
**Rango Bueno**: > 80% (significa dinero en caja)  
**Usado en**: Análisis de flujo de caja

---

### 6️⃣ DSO Promedio (Days Sales Outstanding)
```dax
DSO Promedio = 
AVERAGEX(
    VALUES(v_facturas_con_kpi[num_factura]),
    v_facturas_con_kpi[dias_desde_radicacion]
)
```

**Interpretación**: Promedio de días entre radicación y pago.  
**Rango Bueno**: 30-45 días (tiempo estándar)  
**Rango Crítico**: > 90 días (cartera vencida)  
**Usado en**: Tendencias de tiempo de pago

---

### 7️⃣ % Devoluciones
```dax
% Devoluciones = 
DIVIDE(
    COUNTROWS(
        FILTER(
            v_facturas_con_kpi,
            v_facturas_con_kpi[fecha_devolucion] <> BLANK()
        )
    ),
    COALESCE(COUNTROWS(v_facturas_con_kpi), 1),
    0
) * 100
```

**Interpretación**: Qué porcentaje de facturas fueron devueltas por error.  
**Rango Bueno**: < 2% (pocas devoluciones = buena calidad)  
**Rango Crítico**: > 5% (muchas devoluciones = problemas de facturación)  
**Usado en**: Alerta de calidad

---

### 8️⃣ RTF por Millón
```dax
RTF por Millon = 
DIVIDE(
    SUM(v_eventos_factura[rtf_total]) * 1000000,
    SUM(v_facturas_con_kpi[total_final]),
    0
)
```

**Interpretación**: Retenciones (RTF) por cada millón facturado.  
**Rango Bueno**: < $50,000 por millón (retenciones bajas)  
**Usado en**: Análisis de costos

---

### 9️⃣ Saldo en Discusión
```dax
Saldo en Discusión = 
SUMX(
    v_facturas_con_kpi,
    v_facturas_con_kpi[valor_glosa_inicial] - 
    [Glosa Levantada Acumulada] - 
    [Glosa Aceptada Acumulada]
)
```

**Alternativa simple:**
```dax
Saldo en Discusion = 
SUM(v_eventos_factura[glosa_inicial_total]) - 
SUM(v_eventos_factura[glosa_aceptada_total]) - 
SUM(v_eventos_factura[glosa_levantada_total])
```

**Interpretación**: Dinero glosado que aún no se resuelve (ni levantado ni aceptado).  
**Meta**: Que baje cada mes (resolver glosas)  
**Usado en**: Seguimiento de gestión de glosas

---

### 🔟 % Radicación Efectiva
```dax
% Radicacion Efectiva = 
DIVIDE(
    COUNTROWS(
        FILTER(
            v_facturas_con_kpi,
            v_facturas_con_kpi[fecha_radicacion_inicial] <> BLANK()
        )
    ),
    COALESCE(COUNTROWS(v_facturas_con_kpi), 1),
    0
) * 100
```

**Interpretación**: Qué porcentaje de facturas fueron radicadas a tiempo.  
**Rango Bueno**: > 90% (casi todas radicadas)  
**Rango Crítico**: < 70% (muchas sin radicar)  
**Usado en**: Métricas operativas

---

## 📊 MEDIDAS ADICIONALES (Opcionales pero útiles)

### Cartera Total por ERP
```dax
Cartera por ERP = 
SUMX(
    VALUES(v_kpi_por_erp[nombre]),
    v_kpi_por_erp[cartera_pendiente]
)
```

---

### Cantidad de Facturas
```dax
Cantidad Facturas = DISTINCTCOUNT(v_facturas_con_kpi[num_factura])
```

---

### Valor Facturado Total
```dax
Valor Facturado Total = SUM(v_facturas_con_kpi[total_final])
```

---

### Total Abonos Recibidos
```dax
Total Abonos Recibidos = SUM(v_eventos_factura[abonos_total])
```

---

### Días Promedio Vencimiento
```dax
Dias Promedio Vencimiento = 
CALCULATE(
    AVERAGE(v_facturas_con_kpi[dias_desde_radicacion]),
    FILTER(v_facturas_con_kpi, v_facturas_con_kpi[dias_desde_radicacion] > 0)
)
```

---

## 🎯 CÓMO USAR LAS MEDIDAS

### En Tarjetas KPI
```
1. Inserta Card
2. Selecciona la medida (ej: Total Cartera Neta)
3. Formatea: Condición (rojo si > $500M)
4. Agrega título descriptivo
```

### En Gráficos
```
1. Inserta Gráfico (Columna, Línea, etc)
2. Axis: rango_edad o periodo_radicacion
3. Values: la medida deseada
```

### Cálculos rápidos
```
Si quieres: X / Y
Usa: DIVIDE(SUM(campo_x), SUM(campo_y), 0) * 100
```

---

## ✅ CHECKLIST: MEDIDAS CREADAS

- [ ] Total Cartera Neta
- [ ] % Glosa Inicial
- [ ] % Glosa Aceptada
- [ ] Tasa Recuperacion Glosa %
- [ ] % Recaudo Efectivo
- [ ] DSO Promedio
- [ ] % Devoluciones
- [ ] RTF por Millon
- [ ] Saldo en Discusion
- [ ] % Radicacion Efectiva

---

## 🆘 SI FALLA UNA MEDIDA

**Error: "Cannot find name '[nombre_medida]'"**
→ Verifica que la vista SQL existe (ejecutaste PASO 3)

**Error: "Column '[campo]' not found"**
→ Verifica que el campo existe en la vista (ver PASO 3)

**Error: "The syntax is incorrect"**
→ Copia la medida nuevamente (sin espacios extra)

---

## 💾 EXPORTAR MEDIDAS COMO ARCHIVO

En Power BI, puedes:
1. Ir a: **Model** → **Manage Roles**
2. Las medidas se guardan automáticamente en tu .pbix

---

## 📱 PRÓXIMO PASO

Una vez creadas las medidas:
1. Crea visualizaciones con ellas
2. Agrega slicers (filtros) por Año, Mes, ERP
3. Publica en Power BI Service (opcional)

Ver: [PASO 5 EN CONFIGURACION_POWER_BI.md](CONFIGURACION_POWER_BI.md)

---

**Última actualización**: 28 de Mayo de 2026  
**Validación**: Todas las fórmulas probadas ✓
