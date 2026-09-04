"""
Management command para generar la tabla de Calendario Dimensión.
Uso: python manage.py generar_calendario --years 2024-2026
"""
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from facturacion.models import CalendarioDimension
import calendar

NOMBRES_MESES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

NOMBRES_DIAS = {
    0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves',
    4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
}

class Command(BaseCommand):
    help = 'Genera la tabla de Calendario Dimensión para años específicos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--years',
            type=str,
            default='2024-2026',
            help='Rango de años: 2024-2026 o año único: 2024'
        )

    def handle(self, *args, **options):
        years_str = options['years']
        
        # Parsear el rango de años
        if '-' in years_str:
            start_year, end_year = map(int, years_str.split('-'))
        else:
            start_year = end_year = int(years_str)
        
        total_creadas = 0
        
        for year in range(start_year, end_year + 1):
            # Generar cada día del año
            fecha_inicio = datetime(year, 1, 1).date()
            fecha_fin = datetime(year, 12, 31).date()
            fecha_actual = fecha_inicio
            
            while fecha_actual <= fecha_fin:
                # Calcular valores
                mes = fecha_actual.month
                dia = fecha_actual.day
                ano = fecha_actual.year
                nombre_mes = NOMBRES_MESES[mes]
                nombre_dia = NOMBRES_DIAS[fecha_actual.weekday()]
                trimestre = f"Q{(mes - 1) // 3 + 1}"
                semana = fecha_actual.isocalendar()[1]
                es_fin_semana = fecha_actual.weekday() >= 5
                
                # Crear o actualizar
                obj, created = CalendarioDimension.objects.get_or_create(
                    fecha=fecha_actual,
                    defaults={
                        'ano': ano,
                        'mes': mes,
                        'dia': dia,
                        'nombre_mes': nombre_mes,
                        'nombre_dia': nombre_dia,
                        'trimestre': trimestre,
                        'semana': semana,
                        'es_fin_semana': es_fin_semana,
                        'es_festivo': False,
                    }
                )
                
                if created:
                    total_creadas += 1
                
                fecha_actual += timedelta(days=1)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Calendario generado: {total_creadas} fechas para {start_year}-{end_year}'
            )
        )
