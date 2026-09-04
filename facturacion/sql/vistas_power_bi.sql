-- facturacion/sql/vistas_power_bi.sql
-- Vistas SQL optimizadas para Power BI
-- Ejecutar estas vistas directamente en PostgreSQL

-- Vista 1: Detalle de Facturas con KPIs calculados
CREATE OR REPLACE VIEW v_facturas_con_kpi AS
SELECT 
    f.id,
    f.num_factura,
    e.nit AS erp_nit,
    e.nombre AS erp_nombre,
    te.nombre AS tipo_erp,
    f.historia_clinica,
    f.nombre_paciente,
    f.fecha_factura,
    f.fecha_radicacion_inicial,
    f.fecha_devolucion,
    f.total_factura,
    f.total_final AS valor_neto,
    f.copago,
    f.saldo_actual,
    f.valor_glosa_inicial,
    f.cerrada,
    f.liquidada,
    -- Cálculos de edad de cartera
    EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial)::INT AS dias_desde_radicacion,
    CASE 
        WHEN f.fecha_radicacion_inicial IS NULL THEN 'No Radicado'
        WHEN f.fecha_devolucion IS NOT NULL THEN 'Devuelta'
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 30 THEN '0-30 días'
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 60 THEN '31-60 días'
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 90 THEN '61-90 días'
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 180 THEN '91-180 días'
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 360 THEN '181-360 días'
        ELSE '+360 días (CRÍTICO)'
    END AS rango_mora,
    -- Estado
    CASE 
        WHEN f.fecha_factura IS NULL THEN 'No Facturado'
        WHEN f.fecha_radicacion_inicial IS NULL THEN 'No Radicado'
        ELSE 'Radicado'
    END AS estado_gestion,
    EXTRACT(YEAR FROM f.fecha_radicacion_inicial) AS ano_radicacion,
    EXTRACT(MONTH FROM f.fecha_radicacion_inicial) AS mes_radicacion,
    TO_CHAR(f.fecha_radicacion_inicial, 'YYYY-MM') AS periodo_radicacion
FROM facturacion_factura f
LEFT JOIN facturacion_entidadresponsable e ON f.erp_id = e.nit
LEFT JOIN facturacion_tipooerp te ON e.tipo_erp_id = te.id;


-- Vista 2: Eventos agregados por factura (Glosas, Abonos, RTF)
CREATE OR REPLACE VIEW v_eventos_factura AS
SELECT 
    f.num_factura,
    f.erp_id,
    -- Glosa Inicial
    COALESCE(SUM(CASE WHEN ec.tipo = 'GLO_INI' THEN ec.valor ELSE 0 END), 0) AS glosa_inicial_total,
    MAX(CASE WHEN ec.tipo = 'GLO_INI' THEN ec.fecha END) AS fecha_glosa_inicial,
    -- Glosa Aceptada
    COALESCE(SUM(CASE WHEN ec.tipo = 'GLO_ACEP' THEN ec.valor ELSE 0 END), 0) AS glosa_aceptada_total,
    MAX(CASE WHEN ec.tipo = 'GLO_ACEP' THEN ec.fecha END) AS fecha_glosa_aceptada,
    -- Glosa Levantada
    COALESCE(SUM(CASE WHEN ec.tipo = 'GLO_LEV' THEN ec.valor ELSE 0 END), 0) AS glosa_levantada_total,
    -- Abonos
    COALESCE(SUM(CASE WHEN ec.tipo = 'ABONO' THEN ec.valor ELSE 0 END), 0) AS abonos_total,
    COUNT(CASE WHEN ec.tipo = 'ABONO' THEN 1 END) AS cantidad_abonos,
    MIN(CASE WHEN ec.tipo = 'ABONO' THEN ec.fecha END) AS fecha_primer_abono,
    MAX(CASE WHEN ec.tipo = 'ABONO' THEN ec.fecha END) AS fecha_ultimo_abono,
    -- RTF
    COALESCE(SUM(CASE WHEN ec.tipo = 'RTF' THEN ec.valor ELSE 0 END), 0) AS rtf_total,
    -- Devoluciones
    MAX(CASE WHEN ec.tipo = 'DEV' THEN ec.fecha END) AS fecha_devolucion_evento
FROM facturacion_factura f
LEFT JOIN facturacion_eventocartera ec ON f.id = ec.factura_id
GROUP BY f.id, f.num_factura, f.erp_id;


-- Vista 3: KPI por ERP (Resumen de cada entidad responsable)
CREATE OR REPLACE VIEW v_kpi_por_erp AS
SELECT 
    e.nit,
    e.nombre,
    te.nombre AS tipo_erp,
    COUNT(DISTINCT f.id) AS cantidad_facturas,
    COALESCE(SUM(f.total_final), 0) AS valor_facturado_total,
    COALESCE(SUM(f.saldo_actual), 0) AS cartera_pendiente,
    COALESCE(SUM(f.valor_glosa_inicial), 0) AS glosa_inicial_total,
    COALESCE(SUM(CASE WHEN ec.tipo = 'GLO_ACEP' THEN ec.valor ELSE 0 END), 0) AS glosa_aceptada_total,
    COALESCE(SUM(CASE WHEN ec.tipo = 'ABONO' THEN ec.valor ELSE 0 END), 0) AS abonos_total,
    COALESCE(SUM(CASE WHEN ec.tipo = 'RTF' THEN ec.valor ELSE 0 END), 0) AS rtf_total,
    ROUND(100.0 * COALESCE(SUM(CASE WHEN ec.tipo = 'ABONO' THEN ec.valor ELSE 0 END), 0) / 
          NULLIF(SUM(f.total_final), 0), 2) AS pct_recaudo,
    ROUND(COALESCE(AVG(EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial)), 0), 1) AS dso_promedio
FROM facturacion_entidadresponsable e
LEFT JOIN facturacion_tipooerp te ON e.tipo_erp_id = te.id
LEFT JOIN facturacion_factura f ON e.nit = f.erp_id
LEFT JOIN facturacion_eventocartera ec ON f.id = ec.factura_id AND f.fecha_radicacion_inicial IS NOT NULL
GROUP BY e.nit, e.nombre, te.nombre;


-- Vista 4: Cartera por rango de edad (para gráfico de barras)
CREATE OR REPLACE VIEW v_cartera_por_edad AS
SELECT 
    CASE 
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 30 THEN '0-30 días'
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 60 THEN '31-60 días'
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 90 THEN '61-90 días'
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 180 THEN '91-180 días'
        WHEN EXTRACT(DAY FROM NOW() - f.fecha_radicacion_inicial) <= 360 THEN '181-360 días'
        ELSE '+360 días'
    END AS rango_edad,
    COUNT(DISTINCT f.id) AS cantidad_facturas,
    COALESCE(SUM(f.saldo_actual), 0) AS valor_cartera,
    COALESCE(SUM(f.valor_glosa_inicial), 0) AS valor_glosas
FROM facturacion_factura f
WHERE f.fecha_radicacion_inicial IS NOT NULL
  AND f.fecha_devolucion IS NULL
GROUP BY rango_edad
ORDER BY rango_edad;


-- Vista 5: Embudo de Glosas (análisis de conciliación)
CREATE OR REPLACE VIEW v_embudo_glosas AS
SELECT 
    COUNT(DISTINCT f.id) AS facturas_radicadas,
    COALESCE(SUM(f.total_final), 0) AS valor_radicado,
    COUNT(CASE WHEN f.valor_glosa_inicial > 0 THEN 1 END) AS facturas_glosadas,
    COALESCE(SUM(f.valor_glosa_inicial), 0) AS valor_glosa_inicial,
    COALESCE(SUM(CASE WHEN ec.tipo = 'GLO_ACEP' THEN ec.valor ELSE 0 END), 0) AS valor_glosa_aceptada,
    COALESCE(SUM(CASE WHEN ec.tipo = 'GLO_LEV' THEN ec.valor ELSE 0 END), 0) AS valor_glosa_levantada,
    COALESCE(SUM(f.valor_glosa_inicial), 0) - 
    COALESCE(SUM(CASE WHEN ec.tipo = 'GLO_ACEP' THEN ec.valor ELSE 0 END), 0) - 
    COALESCE(SUM(CASE WHEN ec.tipo = 'GLO_LEV' THEN ec.valor ELSE 0 END), 0) AS valor_en_discusion
FROM facturacion_factura f
LEFT JOIN facturacion_eventocartera ec ON f.id = ec.factura_id AND f.fecha_radicacion_inicial IS NOT NULL;


-- Vista 6: Facturas devueltas por ERP (Requieren refacturación urgente)
CREATE OR REPLACE VIEW v_facturas_devueltas AS
SELECT 
    f.num_factura,
    e.nombre AS erp_nombre,
    f.fecha_devolucion,
    EXTRACT(DAY FROM NOW() - f.fecha_devolucion)::INT AS dias_desde_devolucion,
    f.total_final AS valor_factura,
    f.historia_clinica,
    f.nombre_paciente
FROM facturacion_factura f
LEFT JOIN facturacion_entidadresponsable e ON f.erp_id = e.nit
WHERE f.fecha_devolucion IS NOT NULL
ORDER BY f.fecha_devolucion DESC;
