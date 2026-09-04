#!/usr/bin/env python
"""
Script para ejecutar vistas SQL de Power BI en PostgreSQL
"""

import psycopg2
from psycopg2 import sql
import sys

# Conexión a la base de datos
conn = psycopg2.connect(
    host="127.0.0.1",
    database="soft_clinic_db",
    user="postgres",
    password="Wnjr9367",
    port="5432"
)

cursor = conn.cursor()

# Leer el archivo SQL
try:
    with open('facturacion/sql/vistas_power_bi.sql', 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    print("✓ Archivo SQL cargado correctamente")
    print("=" * 60)
    
    # Dividir por comentarios y ejecutar cada vista
    statements = [s.strip() for s in sql_script.split(';') if s.strip() and not s.strip().startswith('--')]
    
    for i, statement in enumerate(statements, 1):
        try:
            cursor.execute(statement)
            print(f"✓ PASO {i}: Vista creada exitosamente")
        except Exception as e:
            print(f"✗ PASO {i}: Error - {str(e)}")
            conn.rollback()
            cursor.close()
            conn.close()
            sys.exit(1)
    
    # Confirmar los cambios
    conn.commit()
    
    print("=" * 60)
    print("✓ Todas las vistas SQL se crearon exitosamente")
    print("\nVistas creadas:")
    print("  1. v_facturas_con_kpi")
    print("  2. v_eventos_factura")
    print("  3. v_kpi_por_erp")
    print("  4. v_cartera_por_edad")
    print("  5. v_embudo_glosas")
    print("  6. v_facturas_devueltas")
    
    # Ahora ejecutar los índices
    print("\n" + "=" * 60)
    print("Ejecutando índices de optimización...\n")
    
    with open('facturacion/sql/indices_optimizacion.sql', 'r', encoding='utf-8') as f:
        indices_script = f.read()
    
    indices = [s.strip() for s in indices_script.split(';') if s.strip() and not s.strip().startswith('--')]
    
    for i, statement in enumerate(indices, 1):
        try:
            cursor.execute(statement)
            print(f"✓ Índice {i} creado")
        except Exception as e:
            # Algunos índices podrían existir ya, lo cual es OK
            if "already exists" in str(e).lower():
                print(f"⚠ Índice {i}: Ya existe (es normal)")
            else:
                print(f"✗ Índice {i}: Error - {str(e)}")
    
    conn.commit()
    print("\n" + "=" * 60)
    print("✓ Índices de optimización creados correctamente")
    
    cursor.close()
    conn.close()
    
    print("\n🎉 PASO 3 COMPLETADO EXITOSAMENTE")
    print("Las vistas y índices están listos para Power BI\n")

except FileNotFoundError as e:
    print(f"✗ Error: Archivo no encontrado - {e}")
    sys.exit(1)
except psycopg2.Error as e:
    print(f"✗ Error de conexión a PostgreSQL: {e}")
    sys.exit(1)
