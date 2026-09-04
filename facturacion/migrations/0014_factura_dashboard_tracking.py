from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('facturacion', '0013_alter_entidadresponsable_environment_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='factura',
            name='causal_glosa',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='factura',
            name='fecha_glosa_inicial',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='factura',
            name='fecha_limite_respuesta_glosa',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='factura',
            name='fecha_pago',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='factura',
            name='numero_recaudo',
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
    ]
