import os
import django
from django.db import connection

# Detectar automáticamente el módulo de configuración
for root, dirs, files in os.walk('.'):
    if 'settings.py' in files:
        module_name = os.path.basename(root) + '.settings'
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', module_name)
        break

django.setup()

def arreglar_base_de_datos():
    with connection.cursor() as cursor:
        print("Iniciando reparación de base de datos...")
        
        # 1. Borramos el historial de migraciones para que Django se resetee
        cursor.execute("DELETE FROM django_migrations WHERE app = 'facturacion';")
        print("- Historial de migraciones reseteado.")

        # 2. Añadimos la columna saldo_actual manualmente
        try:
            cursor.execute("ALTER TABLE facturacion_factura ADD COLUMN saldo_actual DECIMAL(18, 2) DEFAULT 0 NOT NULL;")
            print("- Columna 'saldo_actual' añadida con éxito.")
        except Exception as e:
            print(f"- Nota: La columna tal vez ya existía ({e})")
            
        print("¡Reparación completada!")

if __name__ == "__main__":
    arreglar_base_de_datos()