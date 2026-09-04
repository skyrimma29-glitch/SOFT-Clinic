# ARQUITECTURA END-TO-END: ClinicSoft-IPS Phase 1

## 📊 Flujo de Datos Completo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ClinicSoft-IPS: ARQUITECTURA FASE 1                   │
└─────────────────────────────────────────────────────────────────────────────┘

ENTRADA (Excel de EPS)
        │
        ├─→ Factura_Sanitas.xlsx (Plantilla DIF)
        │   - num_factura, fecha_radicacion, total_final, copago
        │
        └─→ Eventos_Sanitas.xlsx (Plantilla PAE)
            - glosas, abonos, retenciones

            ▼
        
┌─────────────────────────────────────────────────────────────────────────────┐
│                        IMPORTADORES DJANGO (services.py)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  importar_excel_cartera()  ────→ Limpia datos, valida, crea Facturas       │
│                                  (SIN CAMBIOS en esta fase)                │
│                                                                              │
│  importar_eventos_pae()    ────→ Procesa glosas, abonos, RTF               │
│                                  (SIN CAMBIOS en esta fase)                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

            ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                      BASE DE DATOS POSTGRESQL                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TABLAS ORIGINALES (Django ORM):                                            │
│  ├── facturacion_factura          ← Almacena cada factura                 │
│  ├── facturacion_eventocartera    ← Almacena pagos, glosas, RTF            │
│  ├── facturacion_entidadresponsable                                         │
│  └── facturacion_calendariodimension                                        │
│                                                                              │
│  VISTAS SQL NUEVAS (Power BI queries):              ✨ NUEVA FASE          │
│  ├── v_facturas_con_kpi          ← Facturas + cálculos de edad/estado    │
│  ├── v_eventos_factura            ← Glosas, abonos agregados por factura  │
│  ├── v_kpi_por_erp                ← Resumen por cada ERP                  │
│  ├── v_cartera_por_edad           ← Cartera agrupada por rangos           │
│  ├── v_embudo_glosas              ← Análisis de conciliación             │
│  └── v_facturas_devueltas         ← Facturas rechazadas                  │
│                                                                              │
│  ÍNDICES DE OPTIMIZACIÓN:           ✨ NUEVA FASE                          │
│  ├── idx_factura_fecha_radicacion  ← Aceleran queries de Power BI         │
│  ├── idx_evento_tipo                                                       │
│  ├── idx_evento_factura            ← Optimizan agregaciones               │
│  └── ... (10+ índices más)                                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

            ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                         API REST DJANGO (api.py)           ✨ NUEVA FASE    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ENDPOINT 1: /api/kpi-dashboard/                                            │
│  └─→ SELECT ... FROM v_facturas_con_kpi + agregaciones                     │
│      Retorna: {"kpi_cartera": {...}, "kpi_glosas": {...}, ...}            │
│                                                                              │
│  ENDPOINT 2: /api/cartera-por-edades/                                       │
│  └─→ SELECT * FROM v_cartera_por_edad WHERE año = ? AND mes = ?           │
│      Retorna: {"rango_0_30": {...}, "rango_31_60": {...}, ...}            │
│                                                                              │
│  ENDPOINT 3: /api/top-erps/                                                 │
│  └─→ SELECT * FROM v_kpi_por_erp ORDER BY cartera DESC LIMIT 10          │
│      Retorna: [{"erp_nombre": "SANITAS", "cartera": 4.5M}, ...]          │
│                                                                              │
│  ENDPOINT 4: /api/embudo-glosas/                                            │
│  └─→ SELECT * FROM v_embudo_glosas                                         │
│      Retorna: {"radicadas": {...}, "glosadas": {...}, ...}                │
│                                                                              │
│  ENDPOINT 5: /api/trazabilidad-abonos/                                      │
│  └─→ SELECT * FROM Factura + eventos JOIN EventoCartera                   │
│      Retorna: [{"num_factura": "FE001", "abonos": [2M, 1M, ...], ...}    │
│                                                                              │
│  ENDPOINT 6: /api/facturas-devueltas/                                       │
│  └─→ SELECT * FROM v_facturas_devueltas ORDER BY fecha_devolucion DESC    │
│      Retorna: [{"num_factura": "FE002", "dias_dev": 18, ...}, ...]       │
│                                                                              │
│  ┌─ FILTROS COMUNES en TODOS los endpoints: ────────────────────┐         │
│  │ ?ano=2026&mes=5&nit_erp=800123456&tipo_erp=Contributivo     │         │
│  └──────────────────────────────────────────────────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

            ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                    POWER BI DESKTOP (Windows App)         ✨ NUEVA FASE     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OPCIÓN A: Conexión Directa PostgreSQL                                      │
│  ┌─────────────────────────────────────────┐                               │
│  │ Get Data → PostgreSQL Database          │                               │
│  │ Server: 127.0.0.1                       │                               │
│  │ Database: soft_clinic_db                │                               │
│  │ Select tables/views → Load data         │                               │
│  └─────────────────────────────────────────┘                               │
│                                                                              │
│  OPCIÓN B: API REST endpoints (más flexible)                               │
│  ┌─────────────────────────────────────────┐                               │
│  │ Get Data → Web                          │                               │
│  │ URL: http://localhost:8000/api/...      │                               │
│  │ Extract JSON → Transform to table       │                               │
│  └─────────────────────────────────────────┘                               │
│                                                                              │
│  MEDIDAS DAX CREADAS (10 KPIs):                                             │
│  ├── Total Cartera Neta = SUMX(Facturas, Saldo)                           │
│  ├── % Glosa Inicial = (SUM(Glosa_Ini) / SUM(Valor_Neto)) * 100          │
│  ├── % Glosa Aceptada = (SUM(Glosa_Acep) / SUM(Valor_Neto)) * 100        │
│  ├── Tasa Recuperación Glosa % = (SUM(Glosa_Lev) / SUM(Glosa_Ini)) * 100 │
│  ├── % Recaudo = (SUM(Abonos) / SUM(Valor_Neto)) * 100                   │
│  ├── DSO Promedio = AVG(Días desde Radicación)                            │
│  ├── % Devoluciones = (COUNT(Devueltas) / COUNT(Total)) * 100            │
│  ├── RTF por Millón = SUM(RTF) / (SUM(Valor_Neto) / 1M)                  │
│  ├── Saldo en Discusión = SUM(Glosa_Ini - Glosa_Acep - Glosa_Lev)       │
│  └── % Radicación Efectiva = (COUNT(Radicadas) / COUNT(Emitidas)) * 100 │
│                                                                              │
│  VISUALIZACIONES:                                                           │
│  ├── [Tarjeta]      Total Cartera Neta (KPI grande en rojo/verde)         │
│  ├── [Barras]       Cartera por Edades (0-30, 31-60, 61-90, +90)         │
│  ├── [Waterfall]    Embudo de Glosas (Radicadas → Glosadas → ...)       │
│  ├── [Tabla]        Top 10 ERPs por Cartera                               │
│  ├── [Tabla]        Trazabilidad de Abonos (Factura + 4 pagos)           │
│  ├── [Alerta]       Facturas Devueltas (Rojo si > 10)                    │
│  ├── [Línea]        Tendencia DSO (Trend mensual)                        │
│  └── [Scatter]      Matriz 2x2 (Volumen vs Velocidad de pago)           │
│                                                                              │
│  FILTROS GLOBALES (Slicers):                                               │
│  ├── Año (2024, 2025, 2026, ...)                                          │
│  ├── Mes (1-12)                                                             │
│  ├── ERP (dropdown con nombres)                                            │
│  ├── Tipo ERP (Contributivo, Subsidiado, ARL, SOAT, ...)                 │
│  ├── Estado (Radicado, No Radicado, Devuelto)                            │
│  └── Rango Mora (0-30, 31-60, 61-90, +90)                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

            ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                  POWER BI SERVICE (Cloud) - Publicación        ✨ NUEVA FASE │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  File → Publish → Select Workspace                                          │
│  ├── Configurar refresco automático (diario 08:00 AM)                      │
│  ├── Configurar credenciales PostgreSQL                                    │
│  └── Dashboard disponible en: app.powerbi.com/                             │
│                                                                              │
│  ACCESO POR USUARIOS:                                                       │
│  ├── Gerencia: Ver todos los KPIs + Filtros globales                      │
│  ├── Auditoría: Ver detalles de glosas + Trazabilidad de abonos           │
│  ├── Facturación: Ver alertas de devoluciones + DSO por ERP              │
│  └── CFO: Ver resumen ejecutivo + Flujo de caja proyectado                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 CICLO DE ACTUALIZACIÓN

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CICLO DE DATOS DIARIO                                │
└─────────────────────────────────────────────────────────────────────────────┘

DÍA ANTERIOR (ERP prepara archivos)
        ↓
        MAÑANA (08:00 AM - Equipo Facturación):
        ├── 08:00 → Recibe Excel de Sanitas, Nueva EPS, etc.
        │
        ├── 08:05 → Entra a ClinicSoft-IPS (Django app)
        │           └─→ Panel Subir → Selecciona archivo DIF
        │               Selecciona tipo_erp = "Régimen Contributivo"
        │               Clic: Importar
        │
        ├── 08:10 → Sistema importa_excel_cartera()
        │           ├─ Limpia datos
        │           ├─ Valida: Bruto - Copago = Neto
        │           ├─ Crea/actualiza Facturas en PostgreSQL
        │           └─ ✅ "150 nuevas, 45 actualizadas"
        │
        ├── 08:15 → Carga archivo PAE (Glosas + Abonos)
        │           └─→ Panel Subir → Selecciona archivo PAE
        │               Clic: Importar
        │
        ├── 08:20 → Sistema importa_eventos_pae()
        │           ├─ Procesa glosas iniciales
        │           ├─ Procesa abonos (hasta 4 por factura)
        │           ├─ Procesa retenciones (RTF)
        │           ├─ Actualiza saldo_actual en cada Factura
        │           └─ ✅ "200 eventos procesados"
        │
        ├── 08:25 → PostgreSQL genera VISTAS SQL automáticamente
        │           ├─ v_facturas_con_kpi ← Actualizada
        │           ├─ v_kpi_por_erp ← Actualizada
        │           ├─ v_cartera_por_edad ← Actualizada
        │           └─ (todas las demás vistas)
        │
        ├── 09:00 → Power BI Desktop refresh (manual o automático)
        │           ├─ Conexión a PostgreSQL
        │           ├─ Carga datos de vistas
        │           ├─ Recalcula medidas DAX
        │           └─ Dashboard actualizado
        │
        └── 09:30 → Power BI Service refresh (automático)
                    └─ Dashboard público accesible para Gerencia

GERENCIA VE (09:30 AM en adelante):
        └─→ Power BI Dashboard actualizado
            ├── Cartera Total: $12.3M (Actualizado)
            ├── % Glosa Inicial: 13.5% (Actualizado)
            ├── Top 3 ERPs: Sanitas, Nueva EPS, Salud Bolívar
            ├── Cartera por Edades: 0-30 días = $3M (Verde)
            └── ALERTAS: 5 facturas devueltas (Rojo)

```

---

## 📈 EJEMPLO: Flujo de UNA FACTURA

```
INICIO: Factura Sanitas por $5,000,000

PASO 1: Carga DIF
├── Excel contiene:
│   ├── num_factura: "FE00012345"
│   ├── fecha_factura: "2026-03-15"
│   ├── fecha_radicacion: "2026-03-20" (5 días después)
│   ├── total_factura: $5,000,000
│   ├── copago: $200,000
│   └── total_final: $4,800,000
│
└── Django crea Factura + EntidadResponsable
    └── saldo_actual = $4,800,000 (por cobrar)

PASO 2: Carga PAE (15 días después)
├── Excel contiene:
│   ├── num_factura: "FE00012345"
│   ├── valor_glosa_inicial: $600,000
│   ├── vlr_aceptado_ips: $300,000 (nosotros aceptamos perder esto)
│   ├── vlr_p_1: $2,000,000 (Primer abono)
│   ├── fecha_p_1: "2026-04-10"
│   └── vlr_p_2: $1,800,000 (Segundo abono)
│       fecha_p_2: "2026-04-20"
│
└── Django procesa eventos:
    ├── GLO_INI: $600,000 (informativo)
    ├── GLO_ACEP: $300,000 (afecta saldo: -$300k)
    ├── ABONO: $2,000,000 (afecta saldo: -$2M)
    ├── ABONO: $1,800,000 (afecta saldo: -$1.8M)
    └── Calcula saldo_actual = $4,800,000 - $300,000 - $2,000,000 - $1,800,000
                             = $700,000 (aún pendiente)

PASO 3: Consulta en Power BI Dashboard
├── Vista: v_facturas_con_kpi
│   └── Muestra:
│       ├── num_factura: "FE00012345"
│       ├── erp_nombre: "SANITAS SA EPS-C"
│       ├── valor_neto: $4,800,000
│       ├── saldo_actual: $700,000
│       ├── valor_glosa_inicial: $600,000
│       ├── dias_desde_radicacion: 42 (hoy es 2026-05-01)
│       ├── rango_mora: "31-60 días" ⚠️
│       └── estado_gestion: "Radicado"
│
├── Vista: v_eventos_factura (agregados)
│   └── Muestra:
│       ├── glosa_inicial_total: $600,000
│       ├── glosa_aceptada_total: $300,000
│       ├── abonos_total: $3,800,000
│       ├── cantidad_abonos: 2
│       ├── fecha_primer_abono: "2026-04-10"
│       └── fecha_ultimo_abono: "2026-04-20"
│
└── KPI "% Recaudo" para esta factura:
    └── $3,800,000 / $4,800,000 = 79% ✅ Buen porcentaje

RESULTADO EN DASHBOARD:
└── La factura aparece en:
    ├── Gráfico "Cartera por Edades" → Rango "31-60 días" por $700k
    ├── Tabla "Top ERPs" → Sanitas con $700k pendiente
    ├── Embudo "Glosas" → En la etapa "En discusión" $300k no resueltos
    └── Tabla "Trazabilidad de Abonos" → 2 de 4 abonos completados
```

---

## 🎯 RESUMEN ARQUITECTÓNICO

```
ENTRADA → PROCESAMIENTO → ALMACENAMIENTO → CONSULTA → VISUALIZACIÓN
  Excel      Django           PostgreSQL      API        Power BI
            (services.py)   (vistas SQL)   (endpoints)  (Dashboard)
  
DIF  ──────────────────┐
                       ├──→ [DB Actualizada] ──→ [Vistas SQL] ──→ [API REST] ──→ [Power BI]
PAE  ──────────────────┘                                           ↑
                                                                   │
                                      (Sin cambios en la lógica)  │
```

---

## ⏱️ TIMELINE

```
FASE 1 (YA COMPLETADA - 28/05/2026):
├── Semana 1: ✅ Desarrollar API + Vistas SQL
├── Semana 2: ✅ Documentar DAX + Configuración
└── Semana 3: ⏳ Manual - Instalar + Conectar Power BI

FASE 2 (PRÓXIMA):
├── Semana 4: Dashboard Power BI completo
└── Semana 5: Validar indicadores

FASE 3:
└── Mejorar UI + Agregar validaciones
```

---

## 🚀 ESTADO: LISTO PARA IMPLEMENTAR

**Código**: 100% completado y documentado
**Documentación**: Guías paso a paso incluidas
**Próximo**: Ejecutar los 5 pasos del CHECKLIST_FASE1.md
