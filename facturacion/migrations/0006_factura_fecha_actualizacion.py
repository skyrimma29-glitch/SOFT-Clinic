# Generated manually to add fecha_actualizacion to Factura
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0005_factura_fecha_importacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='factura',
            name='fecha_actualizacion',
            field=models.DateField(blank=True, null=True),
        ),
    ]
