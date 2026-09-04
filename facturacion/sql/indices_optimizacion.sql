-- facturacion/sql/indices_optimizacion.sql
-- Índices para optimizar las vistas y consultas de Power BI
-- Ejecutar DESPUÉS de crear las vistas_power_bi.sql

-- Índice para búsquedas por fecha de radicación (MÁS IMPORTANTE)
CREATE INDEX IF NOT EXISTS idx_factura_fecha_radicacion 
ON facturacion_factura(fecha_radicacion_inicial);

-- Índice para búsquedas por fecha de devolución
CREATE INDEX IF NOT EXISTS idx_factura_fecha_devolucion 
ON facturacion_factura(fecha_devolucion);

-- Índice para búsquedas por fecha de factura
CREATE INDEX IF NOT EXISTS idx_factura_fecha_factura 
ON facturacion_factura(fecha_factura);

-- Índice compuesto para filtros comunes (Año + Mes)
CREATE INDEX IF NOT EXISTS idx_factura_radicacion_composite 
ON facturacion_factura(
    EXTRACT(YEAR FROM fecha_radicacion_inicial),
    EXTRACT(MONTH FROM fecha_radicacion_inicial)
);

-- Índice para búsquedas por ERP
CREATE INDEX IF NOT EXISTS idx_factura_erp 
ON facturacion_factura(erp_id);

-- Índice para búsquedas por saldo (útil para cartera pendiente)
CREATE INDEX IF NOT EXISTS idx_factura_saldo 
ON facturacion_factura(saldo_actual);

-- Índices en EventoCartera para agregaciones rápidas
CREATE INDEX IF NOT EXISTS idx_evento_factura 
ON facturacion_eventocartera(factura_id);

CREATE INDEX IF NOT EXISTS idx_evento_tipo 
ON facturacion_eventocartera(tipo);

CREATE INDEX IF NOT EXISTS idx_evento_fecha 
ON facturacion_eventocartera(fecha);

-- Índice compuesto para eventos (Factura + Tipo)
CREATE INDEX IF NOT EXISTS idx_evento_factura_tipo 
ON facturacion_eventocartera(factura_id, tipo);

-- Índice para EntidadResponsable
CREATE INDEX IF NOT EXISTS idx_erp_tipo 
ON facturacion_entidadresponsable(tipo_erp_id);

-- Crear estadísticas de tabla para Query Planner (optimización automática)
ANALYZE facturacion_factura;
ANALYZE facturacion_eventocartera;
ANALYZE facturacion_entidadresponsable;

-- Mostrar índices creados
SELECT * FROM pg_indexes WHERE tablename LIKE 'facturacion_%';
