# 🎨 GUÍA VISUAL: CREAR DASHBOARD EN POWER BI

**Objetivo**: Dashboard completo con KPIs, gráficos y filtros  
**Tiempo**: 1-2 horas  
**Nivel**: Principiante  

---

## 📋 CONTENIDO DEL DASHBOARD

```
┌─────────────────────────────────────────────────────────────┐
│                      DASHBOARD CARTERA 2026                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [Año: 2026 ▼]  [Mes: Mayo ▼]  [ERP: Todos ▼]             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │Total Cartera │  │% Recaudo     │  │DSO Promedio  │       │
│  │ $357.7 MM    │  │     78%      │  │  82.5 días   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  ┌──────────────────────────┐  ┌──────────────────────────┐ │
│  │  Cartera por Edades      │  │   Glosas (Embudo)        │ │
│  │  Barras                  │  │   Columna apilada        │ │
│  │  X: Rango (0-30, etc)    │  │   X: Etapa (GLO_INI...)  │ │
│  │  Y: Saldo                │  │   Y: Valor               │ │
│  └──────────────────────────┘  └──────────────────────────┘ │
│                                                              │
│  ┌──────────────────────────┐  ┌──────────────────────────┐ │
│  │  Top 10 ERPs             │  │   Facturas Devueltas     │ │
│  │  Tabla                   │  │   Tabla con alerta       │ │
│  └──────────────────────────┘  └──────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚙️ PASO 1: CONECTAR DATOS

### Opción A: PostgreSQL (RECOMENDADO)

**Paso a paso:**

1. Abre **Power BI Desktop**
2. Clic: **Get Data**
   ```
   Home → Get Data (o Ctrl+Alt+D)
   ```

3. Busca: **PostgreSQL**
   ```
   Search "PostgreSQL" → Clic en PostgreSQL database
   ```

4. Rellena conexión:
   ```
   Server: 127.0.0.1
   Database: soft_clinic_db
   ```

5. Clic: **OK**

6. Rellena credenciales:
   ```
   Username: postgres
   Password: Wnjr9367
   
   Connection: Create
   ```

7. Selecciona las vistas (marca con ✓):
   ```
   ✓ v_facturas_con_kpi
   ✓ v_eventos_factura
   ✓ v_kpi_por_erp
   ✓ v_cartera_por_edad
   ✓ v_embudo_glosas
   ✓ v_facturas_devueltas
   ```

8. Clic: **Load**

---

### Opción B: API REST (Alternativa)

1. Clic: **Get Data** → **Web**
2. URL: `http://localhost:8000/api/kpi-dashboard/`
3. Clic: **OK**
4. Power BI convierte JSON a tabla automáticamente

---

## 📐 PASO 2: CREAR MEDIDAS

Ver: [MEDIDAS_DAX_LISTAS.md](MEDIDAS_DAX_LISTAS.md)

**Resumen:**
- Abre: Model tab
- Clic: New Measure
- Copia medida DAX
- Presiona: Enter

Crear las 10 medidas principales (15 minutos)

---

## 🎨 PASO 3: CREAR VISUALIZACIONES

### Visualización 1: Tarjetas KPI (Fila Superior)

**Tarjeta 1: Total Cartera Neta**

```
1. Insert → Card
2. Fields:
   - Value: [Total Cartera Neta]
3. Format:
   - Title: "Total Cartera Neta"
   - Data label: $, 0 decimales
   - Conditional: 
     * Rojo si > $500,000,000
     * Verde si < $250,000,000
     * Amarillo si entre
```

**Tarjeta 2: % Recaudo Efectivo**

```
1. Insert → Card
2. Fields:
   - Value: [% Recaudo Efectivo]
3. Format:
   - Title: "% Recaudo"
   - Data label: 0.0%, 1 decimal
   - Conditional:
     * Verde si > 80%
     * Rojo si < 60%
```

**Tarjeta 3: DSO Promedio**

```
1. Insert → Card
2. Fields:
   - Value: [DSO Promedio]
3. Format:
   - Title: "DSO (Días)"
   - Data label: 0 decimales
   - Conditional:
     * Verde si < 45
     * Rojo si > 90
```

---

### Visualización 2: Cartera por Edades (Gráfico de Barras)

```
1. Insert → Stacked Bar Chart
2. Axis:
   - X: v_cartera_por_edad[rango_edad]
3. Legend:
   - Empty
4. Values:
   - Y: v_cartera_por_edad[valor_cartera]
5. Format:
   - Title: "Cartera por Edades"
   - Sort: rango_edad (Ascending)
   - Color: Gradiente Rojo (crítico si +360)
```

**Orden esperado:**
```
0-30 días:      Bajo (verde)
31-60 días:     Medio (amarillo)
61-90 días:     Alto (naranja)
91-180 días:    Muy alto (rojo)
181-360 días:   CRÍTICO (rojo intenso)
+360 días:      EMERGENCIA (rojo oscuro)
```

---

### Visualización 3: Embudo de Glosas (Waterfall)

```
1. Insert → Stacked Column Chart
2. Axis:
   - X: Crear columna manual o usar SWITCH
3. Values:
   - Glosa Inicial
   - Glosa Aceptada (resta)
   - Glosa Levantada (resta)
   - Saldo en Discusión
4. Format:
   - Title: "Flujo de Glosas"
```

**Lo que debería verse:**
```
Glosa Inicial: $5.2MM (total glosado)
-Glosa Acepta: $3.1MM (se acepta el 60%)
= En Discusión: $2.1MM (pendiente resolver)
```

---

### Visualización 4: Top 10 ERPs (Tabla)

```
1. Insert → Table
2. Columns:
   - v_kpi_por_erp[nombre]
   - v_kpi_por_erp[cartera_pendiente]
   - v_kpi_por_erp[cantidad_facturas]
   - [% Recaudo Efectivo]
3. Format:
   - Title: "Top 10 ERPs por Cartera"
   - Sort: cartera_pendiente DESC
   - Filtro Top: 10
4. Conditional formatting:
   - cartera_pendiente: Rojo si alto, Verde si bajo
```

---

### Visualización 5: Trazabilidad de Abonos (Tabla)

```
1. Insert → Table
2. Columns:
   - v_facturas_con_kpi[num_factura]
   - v_facturas_con_kpi[erp_nombre]
   - v_eventos_factura[abonos_total]
   - v_eventos_factura[cantidad_abonos]
   - v_eventos_factura[fecha_ultimo_abono]
3. Format:
   - Title: "Últimos Abonos Recibidos"
   - Sort: fecha_ultimo_abono DESC
   - Filtro: últimos 50 registros
```

---

### Visualización 6: Facturas Devueltas (Alerta)

```
1. Insert → Table
2. Columns:
   - v_facturas_devueltas[num_factura]
   - v_facturas_devueltas[erp_nombre]
   - v_facturas_devueltas[dias_desde_devolucion]
   - v_facturas_devueltas[valor_factura]
3. Format:
   - Title: "⚠️ FACTURAS DEVUELTAS"
   - Background: Rojo claro
   - Condicional: Si dias_desde_devolucion > 30 → Rojo intenso
   - Sort: dias_desde_devolucion DESC
```

---

## 🎚️ PASO 4: AGREGAR SLICERS (FILTROS)

### Slicer 1: Año

```
1. Insert → Slicer → Dropdown
2. Field: v_facturas_con_kpi[ano_radicacion]
3. Format:
   - Title: "Año"
   - Position: Top-left
4. Style: Light
```

### Slicer 2: Mes

```
1. Insert → Slicer → Dropdown
2. Field: v_facturas_con_kpi[mes_radicacion]
3. Format:
   - Title: "Mes"
   - Position: Top-center
4. Values: 1-12 (enero a diciembre)
```

### Slicer 3: ERP

```
1. Insert → Slicer → Dropdown
2. Field: v_facturas_con_kpi[erp_nombre]
3. Format:
   - Title: "ERP"
   - Position: Top-right
   - Multi-select: On
4. Allow blanks: Off
```

### Slicer 4: Rango Mora

```
1. Insert → Slicer → Dropdown
2. Field: v_facturas_con_kpi[rango_mora]
3. Format:
   - Title: "Estado"
   - Position: Second row
   - Order: Custom
     * 0-30 días
     * 31-60 días
     * 61-90 días
     * 91-180 días
     * 181-360 días
     * +360 días (CRÍTICO)
```

---

## 🔗 PASO 5: CONFIGURAR INTERACCIONES

### Qué hace qué

1. Slicer Año → Afecta TODOS los gráficos
2. Slicer Mes → Afecta TODOS los gráficos
3. Slicer ERP → Afecta tabla Top ERPs y Glosas
4. Slicer Rango → Afecta Cartera por Edades

**Power BI hace esto automáticamente** si relacionas bien los datos

---

## 🎨 PASO 6: PERSONALIZAR TEMA

### Colores recomendados

```
Primario (Cartera):     #1f77b4 (Azul)
Secundario (Glosas):    #ff7f0e (Naranja)
Crítico (Vencido):      #d62728 (Rojo)
Bueno (Recaudado):      #2ca02c (Verde)
Fondo:                  #ffffff (Blanco)
```

### Tipografía

```
Título principal:       Segoe UI, 28, Bold
Subtítulos:            Segoe UI, 14, Semi-bold
Datos:                 Segoe UI, 11, Regular
```

---

## ✅ CHECKLIST DE DASHBOARD

- [ ] 6 vistas cargadas
- [ ] 10 medidas DAX creadas
- [ ] 3 tarjetas KPI (Cartera, Recaudo, DSO)
- [ ] 1 gráfico Cartera por Edades
- [ ] 1 gráfico Embudo Glosas
- [ ] 1 tabla Top 10 ERPs
- [ ] 1 tabla Trazabilidad Abonos
- [ ] 1 tabla Facturas Devueltas
- [ ] 4 slicers (Año, Mes, ERP, Rango)
- [ ] Interacciones configuradas
- [ ] Tema personalizado
- [ ] Guardado: File → Save As

---

## 🚀 PASO 7: PUBLICAR (OPCIONAL)

Si tienes **Power BI Premium** o **Power BI Pro:**

```
1. File → Publish
2. Selecciona: Workspace
3. Clic: Select
4. Espera upload (2-3 minutos)
5. ¡Dashboard disponible online!
```

**Sin Pro?** Guarda como archivo local `.pbix`

---

## 📱 PASO 8: ACTUALIZAR DATOS

Power BI se actualiza:

**Automático:**
```
Settings → Refresh schedule
Cada: Diaria (08:00 AM)
```

**Manual:**
```
Refresh (Ctrl+Shift+R)
o Home → Refresh
```

---

## 🆘 PROBLEMAS COMUNES

### "No se ven datos en gráficos"
→ Verifica que el slicer está en el valor correcto

### "Error: Table not found"
→ Revisa que vistas SQL estén creadas (PASO 3)

### "Las medidas muestran 0"
→ Copia nuevamente la medida DAX (pueden tener espacios)

### "Conexión lenta"
→ Los índices en PostgreSQL aceleran consultas

---

## 📊 EJEMPLO: DASHBOARD COMPLETADO

```
┌─────────────────────────────────────────────────────────┐
│   2026 ▼  Mayo ▼  Todas ▼  Todos ▼                     │
├─────────────────────────────────────────────────────────┤
│  Cartera: $357.7MM | Recaudo: 78% | DSO: 82.5 días    │
├─────────────────────────────────────────────────────────┤
│          Cartera por Edades      │    Embudo Glosas     │
│  ████                            │  ░░░░░░░░░░          │
│  ███░                            │  ░░░░░░░░            │
│  ██░░                            │  ░░░░░░              │
├─────────────────────────────────────────────────────────┤
│  Top ERPs              │ Facturas Devueltas             │
│  ERP A: $45.2MM        │ ⚠️ Fac_001: 45 días           │
│  ERP B: $38.1MM        │ ⚠️ Fac_002: 32 días           │
└─────────────────────────────────────────────────────────┘
```

---

## 🎓 TIPS EXPERTO

1. **Usa bookmarks** para capas diferentes del dashboard
2. **Drill-down**: Haz gráficos interactivos (click en barra)
3. **DAX avanzado**: Crea medidas que calculen % vs mes anterior
4. **Performance**: Si es lento, agrega filtros para periodos recientes

---

## 📞 PRÓXIMO PASO

¿Necesitas ayuda con:
- Crear medidas más complejas?
- Configurar alertas automáticas?
- Publicar en Power BI Service?

---

**Última actualización**: 28 de Mayo de 2026  
**Validación**: Dashboard ejemplo creado y probado ✓
