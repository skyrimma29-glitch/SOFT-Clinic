from datetime import date
from decimal import Decimal
from io import BytesIO

import pandas as pd
from django.db.models import Sum
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from django.utils import timezone

from facturacion.models import Environment, EntidadResponsable, Factura, TipoERP, EventoCartera, ImportLog
from facturacion.environment import set_current_environment_id
from facturacion.services import (
    importar_excel_cartera,
    importar_eventos_pae,
    convertir_a_decimal_excel,
    convertir_a_json_compatible,
    validar_integridad_datos_excel,
    validar_consistencia_aritmetica_dif,
    buscar_factura_para_pae,
    construir_dataframe_exportacion_eas,
)


class DIFValidationTests(SimpleTestCase):
    def test_validar_consistencia_aritmetica_rechaza_total_final_incorrecto(self):
        es_valido, mensaje = validar_consistencia_aritmetica_dif('100.00', '20.00', '999.00')

        self.assertFalse(es_valido)
        self.assertIn('no coincide', mensaje.lower())

    def test_validar_consistencia_aritmetica_acepta_total_final_vacio(self):
        es_valido, mensaje = validar_consistencia_aritmetica_dif('100.00', '20.00', '')

        self.assertTrue(es_valido)
        self.assertIsNone(mensaje)

    def test_validar_consistencia_aritmetica_acepta_valores_correctos(self):
        es_valido, mensaje = validar_consistencia_aritmetica_dif('100.00', '20.00', '80.00')

        self.assertTrue(es_valido)
        self.assertIsNone(mensaje)

    def test_validar_consistencia_aritmetica_no_falla_con_valores_odd(self):
        es_valido, mensaje = validar_consistencia_aritmetica_dif([], '20.00', '80.00')

        self.assertTrue(es_valido)
        self.assertIsNone(mensaje)

    def test_validar_integridad_datos_excel_no_compara_copago(self):
        es_valido, mensaje = validar_integridad_datos_excel(
            total_factura=Decimal('100.00'),
            total_final=Decimal('80.00'),
            fecha_factura='2024-01-15',
            num_factura='FAC-001'
        )

        self.assertTrue(es_valido)
        self.assertIsNone(mensaje)

    def test_validar_integridad_datos_excel_acepta_total_final_vacio(self):
        es_valido, mensaje = validar_integridad_datos_excel(
            total_factura=Decimal('100.00'),
            total_final='',
            fecha_factura='2024-01-15',
            num_factura='FAC-001'
        )

        self.assertTrue(es_valido)
        self.assertIsNone(mensaje)

    def test_validar_integridad_datos_excel_detecta_tipo_incorrecto(self):
        es_valido, mensaje = validar_integridad_datos_excel(
            total_factura='abc',
            total_final=Decimal('80.00'),
            fecha_factura='2024-01-15',
            num_factura='FAC-001'
        )

        self.assertFalse(es_valido)
        self.assertIn('numérico', mensaje.lower())

    def test_convertir_a_decimal_excel_redondea_a_dos_decimales(self):
        valor, error = convertir_a_decimal_excel('1234567.890123')

        self.assertIsNone(error)
        self.assertEqual(valor, Decimal('1234567.89'))


class FacturaFilteringTests(TestCase):
    def test_lista_facturas_filters_by_facturada_status_not_by_date(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)

        Factura.objects.create(
            erp=entidad,
            num_factura='FAC-001',
            fecha_factura=date(2024, 1, 10),
            fecha_admision=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 1),
            total_factura=Decimal('100.00'),
            copago=Decimal('20.00'),
            saldo_actual=Decimal('80.00'),
            facturada_status='FACTURADA',
        )
        Factura.objects.create(
            erp=entidad,
            num_factura='NOFACT-TEST',
            fecha_factura=date(2024, 1, 11),
            fecha_admision=date(2024, 1, 11),
            fecha_radicacion_inicial=date(2024, 1, 2),
            total_factura=Decimal('50.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('50.00'),
            facturada_status='NOFACT',
        )

        response = self.client.get(reverse('lista_facturas'), {'solo_facturadas': '1'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'FAC-001')
        self.assertNotContains(response, 'NOFACT-TEST')

        response = self.client.get(reverse('lista_facturas'), {'sin_factura': '1'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NOFACT-TEST')
        self.assertNotContains(response, 'FAC-001')

    def test_lista_facturas_filters_by_status_and_value_range(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)

        Factura.objects.create(
            erp=entidad,
            num_factura='FAC-001',
            fecha_factura=date(2024, 1, 10),
            fecha_admision=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 1),
            total_factura=Decimal('100.00'),
            copago=Decimal('20.00'),
            saldo_actual=Decimal('80.00'),
            nom_canal='Régimen Contributivo',
        )
        Factura.objects.create(
            erp=entidad,
            num_factura='FAC-002',
            fecha_factura=None,
            fecha_admision=None,
            fecha_radicacion_inicial=None,
            total_factura=Decimal('0.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('0.00'),
            nom_canal='Régimen Subsidiado',
        )

        response = self.client.get(reverse('lista_facturas'), {
            'solo_radicadas': '1',
            'solo_facturadas': '1',
            'valor_neto_min': '50',
            'valor_neto_max': '100',
            'entidad': 'EPS Test',
            'canal': 'Régimen Contributivo',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'FAC-001')
        self.assertNotContains(response, 'FAC-002')


class FacturaDetailPropertiesTests(TestCase):
    def test_factura_properties_return_expected_values(self):
        factura = Factura(
            total_factura='100.00',
            copago='20.00',
            saldo_actual='80.00',
            valor_glosa_inicial='0.00',
        )

        self.assertEqual(factura.valor_neto, 100)
        self.assertEqual(factura.edad_cartera, 0)
        self.assertEqual(factura.estado_glosa, 'Available soon')

    def test_eliminar_facturas_preserva_filtros_en_redireccion(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-001',
            total_factura=Decimal('100.00'),
            copago=Decimal('20.00'),
            saldo_actual=Decimal('80.00'),
        )

        response = self.client.post(reverse('lista_facturas'), {
            'factura_ids': [factura.id],
            'q': 'FAC-001',
            'fecha_admision_desde': '2024-01-01',
            'solo_radicadas': '1',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('lista_facturas')}?q=FAC-001&fecha_admision_desde=2024-01-01&solo_radicadas=1"
        )


class DatabaseCleanupTests(TestCase):
    def test_limpiar_cartera_deletes_facturas_and_entities(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        Factura.objects.create(
            erp=entidad,
            num_factura='FAC-001',
            fecha_factura=date(2024, 1, 10),
            fecha_admision=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 1),
            total_factura=Decimal('100.00'),
            copago=Decimal('20.00'),
            saldo_actual=Decimal('80.00'),
        )

        response = self.client.get(reverse('limpiar_cartera'), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Factura.objects.exists())
        self.assertFalse(EntidadResponsable.objects.exists())
        self.assertContains(response, 'Base de datos limpia')


class PAEImportLogicTests(TestCase):
    def test_factura_expone_resumen_y_json_de_cambios_pae(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-001',
            id_atencion='ATT-77',
            total_factura=Decimal('100.00'),
            copago=Decimal('10.00'),
            saldo_actual=Decimal('90.00'),
            pae_cambios=[
                {'campo': 'Saldo actual', 'anterior': '90.00', 'nuevo': '80.00'},
                {'campo': 'Fecha de radicación', 'anterior': '—', 'nuevo': '15/01/2024'},
            ],
        )

        self.assertEqual(factura.campos_actualizados, 'Saldo actual, Fecha de radicación')
        self.assertIn('Saldo actual', factura.pae_cambios_preview)
        self.assertIn('Fecha de radicación', factura.pae_cambios_preview)
        self.assertIn('Saldo actual', factura.pae_cambios_json)

    def test_buscar_factura_para_pae_usa_id_atencion_cuando_num_factura_no_coincide(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-001',
            id_atencion='ATT-77',
            total_factura=Decimal('100.00'),
            copago=Decimal('10.00'),
            saldo_actual=Decimal('90.00'),
        )

        encontrada = buscar_factura_para_pae('NOEXISTE', 'ATT-77')

        self.assertIsNotNone(encontrada)
        self.assertEqual(encontrada.pk, factura.pk)

    def test_buscar_factura_para_pae_normaliza_facturas_con_punto_cero(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        Factura.objects.create(
            erp=entidad,
            num_factura='FAC-100',
            id_atencion='ATT-88',
            total_factura=Decimal('100.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('100.00'),
        )

        encontrada = buscar_factura_para_pae('FAC-100.0', '')

        self.assertIsNotNone(encontrada)
        self.assertEqual(encontrada.num_factura, 'FAC-100')


class PAEImportRegressionTests(TestCase):
    def test_importar_eventos_pae_registra_auditoria_por_factura(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        Factura.objects.create(
            erp=entidad,
            num_factura='FAC-100',
            fecha_factura=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 15),
            total_factura=Decimal('1000.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('1000.00'),
        )

        df = pd.DataFrame([
            {
                'num factura': 'FAC-100',
                'total factura': '1000.00',
                'fecha radicacion': '15/01/2024',
                'fecha devolucion': '',
                'fecha glosa inicial': '16/01/2024',
                'vlr glosa inicial': '50.00',
                'vlr aceptado ips': '20.00',
                'vlr levantado erp': '10.00',
                'vlr abono 1': '30.00',
                'fecha abono 1': '17/01/2024',
                'vlr abono 2': '15.00',
                'fecha abono 2': '18/01/2024',
                'vlr total abonos': '45.00',
                'vlr rtf': '5.00',
                'saldo factura': '925.00',
            }
        ])
        excel_bytes = BytesIO()
        df.to_excel(excel_bytes, index=False)
        excel_bytes.seek(0)

        archivo = SimpleUploadedFile(
            'pae.xlsx',
            excel_bytes.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        audit_log = []
        importar_eventos_pae(archivo, audit_log=audit_log)

        self.assertTrue(any(entry['factura'] == 'FAC-100' and entry['estado'] == 'procesada' for entry in audit_log))

    def test_importar_eventos_pae_acepta_alias_vlr_rtf_total(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-101',
            fecha_factura=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 15),
            total_factura=Decimal('1000.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('1000.00'),
        )

        df = pd.DataFrame([
            {
                'num factura': 'FAC-101',
                'total factura': '1000.00',
                'fecha radicacion': '15/01/2024',
                'fecha devolucion': '',
                'fecha glosa inicial': '16/01/2024',
                'vlr glosa inicial': '0.00',
                'vlr aceptado ips': '0.00',
                'vlr levantado erp': '0.00',
                'vlr abono 1': '30.00',
                'fecha abono 1': '17/01/2024',
                'vlr abono 2': '15.00',
                'fecha abono 2': '18/01/2024',
                'vlr total abonos': '45.00',
                'vlr rtf total': '7.50',
                'saldo factura': '925.00',
            }
        ])
        excel_bytes = BytesIO()
        df.to_excel(excel_bytes, index=False)
        excel_bytes.seek(0)

        archivo = SimpleUploadedFile(
            'pae.xlsx',
            excel_bytes.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        importar_eventos_pae(archivo)
        factura.refresh_from_db()

        self.assertEqual(factura.eventos.filter(tipo='RTF').aggregate(total=Sum('valor'))['total'] or Decimal('0.00'), Decimal('7.50'))

    def test_pagos_total_usa_aceptado_abonos_y_rtf_sin_copago(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-131',
            fecha_factura=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 15),
            total_factura=Decimal('1000.00'),
            copago=Decimal('50.00'),
            saldo_actual=Decimal('1000.00'),
        )

        EventoCartera.objects.create(factura=factura, tipo='GLO_ACEP', fecha=date(2024, 1, 20), valor=Decimal('100.00'))
        EventoCartera.objects.create(factura=factura, tipo='ABONO', fecha=date(2024, 1, 21), valor=Decimal('150.00'))
        EventoCartera.objects.create(factura=factura, tipo='RTF', fecha=date(2024, 1, 22), valor=Decimal('50.00'))

        self.assertEqual(factura.pagos_total, Decimal('300.00'))
        self.assertEqual(factura.valor_neto, Decimal('700.00'))

    def test_calcular_saldo_usa_valor_neto_y_resta_movimientos_pae(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-130',
            fecha_factura=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 15),
            total_factura=Decimal('1000.00'),
            copago=Decimal('200.00'),
            total_final=Decimal('1200.00'),
            saldo_actual=Decimal('1000.00'),
        )

        EventoCartera.objects.create(factura=factura, tipo='ABONO', fecha=date(2024, 1, 20), valor=Decimal('100.00'))
        EventoCartera.objects.create(factura=factura, tipo='RTF', fecha=date(2024, 1, 21), valor=Decimal('50.00'))

        factura.calcular_saldo()
        factura.refresh_from_db()

        self.assertEqual(factura.valor_neto, Decimal('850.00'))
        self.assertEqual(factura.saldo_actual, Decimal('850.00'))

    def test_importar_eventos_pae_usa_total_abonos_cuando_faltan_fechas(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-140',
            fecha_factura=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 15),
            total_factura=Decimal('200000.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('200000.00'),
        )

        df = pd.DataFrame([
            {
                'num factura': 'FAC-140',
                'total factura': '200000.00',
                'fecha radicacion': '15/01/2024',
                'fecha devolucion': '',
                'fecha glosa inicial': '16/01/2024',
                'vlr glosa inicial': '0.00',
                'vlr aceptado ips': '0.00',
                'vlr levantado erp': '0.00',
                'vlr abono 1': '75000.00',
                'fecha abono 1': '',
                'vlr abono 2': '50000.00',
                'fecha abono 2': '',
                'vlr total abonos': '125000.00',
                'vlr rtf': '10000.00',
                'saldo factura': '65000.00',
            }
        ])
        excel_bytes = BytesIO(); df.to_excel(excel_bytes, index=False); excel_bytes.seek(0)
        archivo = SimpleUploadedFile('pae.xlsx', excel_bytes.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        importar_eventos_pae(archivo)
        factura.refresh_from_db()

        self.assertEqual(factura.eventos.filter(tipo='ABONO').aggregate(total=Sum('valor'))['total'] or Decimal('0.00'), Decimal('125000.00'))
        self.assertEqual(factura.pagos_total, Decimal('135000.00'))
        self.assertEqual(factura.valor_neto, Decimal('65000.00'))

    def test_importar_eventos_pae_lee_cualquier_numero_de_abonos(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-120',
            fecha_factura=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 15),
            total_factura=Decimal('1000.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('1000.00'),
        )

        df = pd.DataFrame([
            {
                'num factura': 'FAC-120',
                'total factura': '1000.00',
                'fecha radicacion': '15/01/2024',
                'fecha devolucion': '',
                'fecha glosa inicial': '16/01/2024',
                'vlr glosa inicial': '0.00',
                'vlr aceptado ips': '0.00',
                'vlr levantado erp': '0.00',
                'vlr abono 1': '30.00',
                'fecha abono 1': '17/01/2024',
                'vlr abono 2': '40.00',
                'fecha abono 2': '18/01/2024',
                'vlr abono 3': '20.00',
                'fecha abono 3': '19/01/2024',
                'vlr abono 4': '25.00',
                'fecha abono 4': '20/01/2024',
                'vlr abono 5': '15.00',
                'fecha abono 5': '21/01/2024',
                'vlr total abonos': '130.00',
                'vlr rtf': '10.00',
                'saldo factura': '860.00',
            }
        ])
        excel_bytes = BytesIO()
        df.to_excel(excel_bytes, index=False)
        excel_bytes.seek(0)

        archivo = SimpleUploadedFile(
            'pae.xlsx',
            excel_bytes.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        resumen = importar_eventos_pae(archivo)
        factura.refresh_from_db()

        self.assertEqual(factura.eventos.filter(tipo='ABONO').count(), 5)
        self.assertEqual(factura.eventos.filter(tipo='ABONO').aggregate(total=Sum('valor'))['total'] or Decimal('0.00'), Decimal('130.00'))
        self.assertEqual(factura.saldo_actual, Decimal('860.00'))
        self.assertEqual(resumen['procesados'], 1)

    def test_importar_eventos_pae_calcula_saldo_desde_total_factura_y_eventos(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-100',
            fecha_factura=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 15),
            total_factura=Decimal('1000.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('1000.00'),
        )

        df = pd.DataFrame([
            {
                'num factura': 'FAC-100',
                'total factura': '1000.00',
                'fecha radicacion': '15/01/2024',
                'fecha devolucion': '',
                'fecha glosa inicial': '16/01/2024',
                'vlr glosa inicial': '50.00',
                'vlr aceptado ips': '20.00',
                'vlr levantado erp': '10.00',
                'vlr abono 1': '30.00',
                'fecha abono 1': '17/01/2024',
                'vlr abono 2': '15.00',
                'fecha abono 2': '18/01/2024',
                'vlr total abonos': '45.00',
                'vlr rtf': '5.00',
                'saldo factura': '925.00',
            }
        ])
        excel_bytes = BytesIO()
        df.to_excel(excel_bytes, index=False)
        excel_bytes.seek(0)

        archivo = SimpleUploadedFile(
            'pae.xlsx',
            excel_bytes.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        resumen = importar_eventos_pae(archivo)

        factura.refresh_from_db()
        self.assertEqual(resumen['procesados'], 1)
        self.assertEqual(factura.valor_glosa_inicial, Decimal('50.00'))
        self.assertEqual(factura.eventos.filter(tipo='ABONO').aggregate(total=Sum('valor'))['total'] or Decimal('0.00'), Decimal('45.00'))
        self.assertEqual(factura.eventos.filter(tipo='RTF').aggregate(total=Sum('valor'))['total'] or Decimal('0.00'), Decimal('5.00'))
        self.assertEqual(factura.saldo_actual, Decimal('930.00'))

    def test_importar_eventos_pae_valida_orden_de_fechas_iso(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        Factura.objects.create(
            erp=entidad,
            num_factura='HGE10196',
            fecha_factura=date(2026, 1, 15),
            fecha_radicacion_inicial=date(2026, 10, 1),
            total_factura=Decimal('1000.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('1000.00'),
        )

        df = pd.DataFrame([
            {
                'num factura': 'HGE10196',
                'total factura': '1000.00',
                'fecha radicacion': '2026-10-01',
                'fecha devolucion': '',
                'fecha glosa inicial': '2026-01-30',
                'vlr glosa inicial': '100.00',
                'vlr aceptado ips': '0.00',
                'vlr levantado erp': '0.00',
                'vlr abono 1': '0.00',
                'fecha abono 1': '',
                'vlr total abonos': '0.00',
                'vlr rtf': '0.00',
                'saldo factura': '900.00',
            }
        ])
        excel_bytes = BytesIO()
        df.to_excel(excel_bytes, index=False)
        excel_bytes.seek(0)

        archivo = SimpleUploadedFile(
            'pae.xlsx',
            excel_bytes.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        resumen = importar_eventos_pae(archivo)

        self.assertTrue(any(
            'fecha de glosa inicial 2026-01-30 no puede ser menor que la fecha de radicación 2026-10-01' in error
            for error in resumen['errores']
        ))

    def test_importar_eventos_pae_preserva_orden_exacto_de_fechas_iso(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        Factura.objects.create(
            erp=entidad,
            num_factura='HGE20261',
            fecha_factura=date(2026, 1, 1),
            fecha_radicacion_inicial=date(2026, 1, 15),
            total_factura=Decimal('1000.00'),
            copago=Decimal('0.00'),
            saldo_actual=Decimal('1000.00'),
        )

        df = pd.DataFrame([
            {
                'num factura': 'HGE20261',
                'total factura': '1000.00',
                'fecha radicacion': '2026-01-10',
                'fecha devolucion': '',
                'fecha glosa inicial': '2026-01-30',
                'vlr glosa inicial': '0.00',
                'vlr aceptado ips': '0.00',
                'vlr levantado erp': '0.00',
                'vlr abono 1': '0.00',
                'fecha abono 1': '',
                'vlr total abonos': '0.00',
                'vlr rtf': '0.00',
                'saldo factura': '1000.00',
            }
        ])
        excel_bytes = BytesIO()
        df.to_excel(excel_bytes, index=False)
        excel_bytes.seek(0)

        archivo = SimpleUploadedFile(
            'pae.xlsx',
            excel_bytes.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        resumen = importar_eventos_pae(archivo)
        factura = Factura.objects.get(num_factura='HGE20261')

        self.assertEqual(resumen['procesados'], 1)
        self.assertEqual(factura.fecha_radicacion_inicial, date(2026, 1, 10))
        self.assertEqual(factura.fecha_glosa_inicial, date(2026, 1, 30))


class ExportEASTests(TestCase):
    def test_construir_dataframe_exportacion_eas_combina_columnas_dif_y_pae(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-100',
            id_atencion='ATT-77',
            historia_clinica='HC-01',
            nombre_paciente='Paciente A',
            fecha_factura=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 15),
            total_factura=Decimal('1000.00'),
            copago=Decimal('50.00'),
            total_final=Decimal('950.00'),
            id_contrato='CTR-001',
            id_cajero='CAJ-1',
            nom_canal='Canal Test',
            nombre_ips='IPS Test',
            pae_datos_origen={
                'raw_row': {
                    'num_factura': 'FAC-100',
                    'Nombre_Tercero': 'EPS PAE',
                    'Nombre_Contrato': 'Contrato PAE',
                    'vlr_glosa_inicial': '30.00',
                    'vlr_Abono_1': '20.00',
                    'vlr_Total_Abonos': '20.00',
                    'vlr_rtf': '5.00',
                    'saldo_factura': '925.00',
                }
            },
        )

        df = construir_dataframe_exportacion_eas(Factura.objects.all())

        self.assertEqual(len(df), 1)
        self.assertIn('Id Tercero', df.columns)
        self.assertIn('Nombre_Tercero', df.columns)
        self.assertIn('vlr_glosa_inicial', df.columns)
        self.assertEqual(df.loc[0, 'Id Tercero'], '900123456')
        self.assertEqual(df.loc[0, 'Nombre_Tercero'], 'EPS PAE')
        self.assertEqual(df.loc[0, 'vlr_glosa_inicial'], Decimal('30.00'))
        self.assertEqual(df.loc[0, 'Id Atencion'], 'ATT-77')


class ExportEASTests(TestCase):
    def test_construir_dataframe_exportacion_eas_combina_columnas_dif_y_pae(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-100',
            id_atencion='ATT-77',
            historia_clinica='HC-01',
            nombre_paciente='Paciente A',
            fecha_factura=date(2024, 1, 10),
            fecha_radicacion_inicial=date(2024, 1, 15),
            total_factura=Decimal('1000.00'),
            copago=Decimal('50.00'),
            total_final=Decimal('950.00'),
            id_contrato='CTR-001',
            id_cajero='CAJ-1',
            nom_canal='Canal Test',
            nombre_ips='IPS Test',
            pae_datos_origen={
                'raw_row': {
                    'num_factura': 'FAC-100',
                    'Nombre_Tercero': 'EPS PAE',
                    'Nombre_Contrato': 'Contrato PAE',
                    'vlr_glosa_inicial': '30.00',
                    'vlr_Abono_1': '20.00',
                    'vlr_Total_Abonos': '20.00',
                    'vlr_rtf': '5.00',
                    'saldo_factura': '925.00',
                }
            },
        )

        df = construir_dataframe_exportacion_eas(Factura.objects.all())

        self.assertEqual(len(df), 1)
        self.assertIn('Id Tercero', df.columns)
        self.assertIn('Nombre_Tercero', df.columns)
        self.assertIn('vlr_glosa_inicial', df.columns)
        self.assertEqual(df.loc[0, 'Id Tercero'], '900123456')
        self.assertEqual(df.loc[0, 'Nombre_Tercero'], 'EPS PAE')
        self.assertEqual(df.loc[0, 'vlr_glosa_inicial'], Decimal('30.00'))
        self.assertEqual(df.loc[0, 'Id Atencion'], 'ATT-77')

    def test_construir_dataframe_exportacion_eas_fallback_a_factura_y_eventos(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-200',
            id_atencion='ATT-88',
            total_factura=Decimal('1200.00'),
            copago=Decimal('100.00'),
            total_final=Decimal('1100.00'),
            valor_glosa_inicial=Decimal('40.00'),
            saldo_actual=Decimal('1050.00'),
        )
        EventoCartera.objects.create(factura=factura, tipo='GLO_INI', fecha=date(2024, 2, 1), valor=Decimal('40.00'))
        EventoCartera.objects.create(factura=factura, tipo='ABONO', fecha=date(2024, 2, 2), valor=Decimal('20.00'))
        EventoCartera.objects.create(factura=factura, tipo='ABONO', fecha=date(2024, 2, 3), valor=Decimal('10.00'))
        EventoCartera.objects.create(factura=factura, tipo='RTF', fecha=date(2024, 2, 4), valor=Decimal('5.00'))

        df = construir_dataframe_exportacion_eas(Factura.objects.all())

        self.assertEqual(df.loc[0, 'vlr_glosa_inicial'], Decimal('40.00'))
        self.assertEqual(df.loc[0, 'vlr_Total_Abonos'], Decimal('30.00'))
        self.assertEqual(df.loc[0, 'vlr_rtf'], Decimal('5.00'))
        self.assertEqual(df.loc[0, 'saldo_factura'], Decimal('1165.00'))

    def test_construir_dataframe_exportacion_eas_usa_valor_neto_cuando_falta_total_final(self):
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        factura = Factura.objects.create(
            erp=entidad,
            num_factura='FAC-300',
            id_atencion='ATT-99',
            total_factura=Decimal('1000.00'),
            copago=Decimal('200.00'),
            total_final=Decimal('0.00'),
            valor_glosa_inicial=Decimal('0.00'),
            saldo_actual=Decimal('0.00'),
        )
        EventoCartera.objects.create(factura=factura, tipo='GLO_ACEP', fecha=date(2024, 3, 1), valor=Decimal('20.00'))
        EventoCartera.objects.create(factura=factura, tipo='ABONO', fecha=date(2024, 3, 2), valor=Decimal('30.00'))
        EventoCartera.objects.create(factura=factura, tipo='RTF', fecha=date(2024, 3, 3), valor=Decimal('10.00'))

        df = construir_dataframe_exportacion_eas(Factura.objects.all())

        self.assertEqual(df.loc[0, 'Total Final'], Decimal('940.00'))
        self.assertEqual(df.loc[0, 'saldo_factura'], Decimal('940.00'))


class DIFUploadTests(TestCase):
    def test_dif_form_does_not_show_regimen_selector(self):
        response = self.client.get(reverse('subir_cartera'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Tipo de ERP/Régimen')
        self.assertNotContains(response, 'name="tipo_erp"')

    @patch('facturacion.views.importar_excel_cartera')
    def test_dif_upload_uses_por_clasificar_by_default(self, mock_importar):
        mock_importar.return_value = {
            'creadas': 0,
            'actualizadas': 0,
            'alertas_aritmeticas': [],
            'tipo': 'DIF',
            'filas_en_excel': 0,
            'filas_procesadas': 0,
        }

        archivo = SimpleUploadedFile(
            'facturas.xlsx',
            b'contenido-de-prueba',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        response = self.client.post(reverse('subir_cartera'), {'archivo_dif': archivo}, follow=True)

        self.assertEqual(response.status_code, 200)
        mock_importar.assert_called_once()
        _, kwargs = mock_importar.call_args
        self.assertEqual(kwargs['tipo_erp_predefinido'], 'Por Clasificar')


class ImportLogTests(TestCase):
    def test_limpiar_import_logs_elimina_solo_los_seleccionados(self):
        primero = ImportLog.objects.create(codigo='DIF-LOG-001-20240101', tipo='DIF')
        segundo = ImportLog.objects.create(codigo='PAE-LOG-001-20240101', tipo='PAE')

        response = self.client.post(
            reverse('limpiar_import_logs'),
            data='{"ids": [%d]}' % primero.id,
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ImportLog.objects.filter(pk=primero.id).exists())
        self.assertTrue(ImportLog.objects.filter(pk=segundo.id).exists())

    def test_limpiar_import_logs_elimina_todos_los_logs(self):
        ImportLog.objects.create(codigo='DIF-LOG-001-20240101', tipo='DIF')
        ImportLog.objects.create(codigo='PAE-LOG-001-20240101', tipo='PAE')

        response = self.client.post(
            reverse('limpiar_import_logs'),
            data='{"modo": "all"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ImportLog.objects.count(), 0)

    def test_generar_codigo_log_incrementa_por_dia(self):
        from facturacion.views import generar_codigo_log

        hoy = timezone.localdate()
        primero = ImportLog.objects.create(
            codigo=f"DIF-LOG-001-{hoy.strftime('%Y%m%d')}",
            tipo='DIF',
            descripcion='Carga inicial',
            resumen={},
            detalles=[],
        )
        self.assertIsNotNone(primero)

        codigo_siguiente = generar_codigo_log('DIF')
        self.assertTrue(codigo_siguiente.startswith('DIF-LOG-002-'))
        self.assertTrue(codigo_siguiente.endswith(hoy.strftime('%Y%m%d')))

    def test_import_log_detail_view(self):
        log = ImportLog.objects.create(
            codigo='DIF-LOG-001-20240101',
            tipo='DIF',
            descripcion='Carga de prueba',
            resumen={'creadas': 1, 'actualizadas': 0},
            detalles=['Fila 1 procesada'],
        )

        response = self.client.get(reverse('import_log_detail', kwargs={'log_id': log.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, log.codigo)
        self.assertContains(response, 'Carga de prueba')
        self.assertContains(response, 'Fila 1 procesada')


class DIFImportDuplicateTests(TestCase):
    def setUp(self):
        self.tipo = TipoERP.objects.create(nombre='Contributivo')
        self.entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=self.tipo)

    def crear_archivo_excel(self, filas):
        df = pd.DataFrame(filas)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)
        return SimpleUploadedFile(
            'duplicados.xlsx',
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    def test_dif_omite_factura_existente_duplicada(self):
        Factura.objects.create(
            erp=self.entidad,
            num_factura='FAC-001',
            fecha_factura=date(2024, 1, 1),
            total_factura=Decimal('100.00'),
            total_final=Decimal('80.00'),
            copago=Decimal('20.00'),
            valor_pagado_caja=Decimal('0.00'),
            saldo_actual=Decimal('80.00'),
            facturada_status='FACTURADA',
        )

        archivo = self.crear_archivo_excel([
            {
                'NFact': 'FAC-001',
                'Fecha Factura': '2024-01-01',
                'Total Factura': '100.00',
                'Total Final': '80.00',
                'Copago': '20.00',
                'Nit Tercero': '900123456',
                'Nombre Tercero': 'EPS Test',
                'Hist Clinica': 'HC-001',
                'Nombre Paciente': 'Juan Perez',
            }
        ])

        resumen = importar_excel_cartera(archivo, tipo_erp_predefinido='Por Clasificar')

        factura = Factura.objects.get(num_factura='FAC-001')
        self.assertEqual(resumen['filas_duplicadas'], 1)
        self.assertEqual(factura.total_factura, Decimal('100.00'))
        self.assertEqual(factura.copago, Decimal('20.00'))
        self.assertEqual(factura.total_final, Decimal('80.00'))
        self.assertIn('omitieron por duplicada', resumen['duplicados'][0])

    def test_dif_omite_factura_existente_duplicada_con_fecha_distinta(self):
        Factura.objects.create(
            erp=self.entidad,
            num_factura='FAC-002',
            fecha_factura=date(2024, 1, 1),
            total_factura=Decimal('100.00'),
            total_final=Decimal('80.00'),
            copago=Decimal('20.00'),
            valor_pagado_caja=Decimal('0.00'),
            saldo_actual=Decimal('80.00'),
            facturada_status='FACTURADA',
        )

        archivo = self.crear_archivo_excel([
            {
                'NFact': 'FAC-002',
                'Fecha Factura': '2024-01-03',
                'Total Factura': '150.00',
                'Total Final': '120.00',
                'Copago': '30.00',
                'Nit Tercero': '900123456',
                'Nombre Tercero': 'EPS Test',
                'Hist Clinica': 'HC-002',
                'Nombre Paciente': 'Maria Lopez',
            }
        ])

        resumen = importar_excel_cartera(archivo, tipo_erp_predefinido='Por Clasificar')

        factura = Factura.objects.get(num_factura='FAC-002')
        self.assertEqual(resumen['filas_duplicadas'], 1)
        self.assertEqual(factura.fecha_factura, date(2024, 1, 1))
        self.assertEqual(factura.total_factura, Decimal('100.00'))
        self.assertEqual(factura.total_final, Decimal('80.00'))
        self.assertEqual(factura.copago, Decimal('20.00'))

    def test_dif_importa_columna_extra_nombre_clinica_sin_romper(self):
        archivo = self.crear_archivo_excel([
            {
                'NFact': 'FAC-EXTRA',
                'Fecha Factura': '2024-01-10',
                'Total Factura': '100.00',
                'Total Final': '80.00',
                'Copago': '20.00',
                'Nit Tercero': '900123456',
                'Nombre Tercero': 'EPS Test',
                'Hist Clinica': 'HC-EXTRA',
                'Nombre Paciente': 'Ana Gomez',
                'Nombre Clinica': 'Clínica San José',
            }
        ])

        resumen = importar_excel_cartera(archivo, tipo_erp_predefinido='Por Clasificar')

        self.assertEqual(resumen['creadas'], 1)
        factura = Factura.objects.get(num_factura='FAC-EXTRA')
        self.assertEqual(factura.nombre_ips, 'Clínica San José')


class EnvironmentIsolationTests(TestCase):
    def test_facturas_se_aislan_por_environment(self):
        environment_2 = Environment.objects.get(numero=2)
        tipo = TipoERP.objects.create(nombre='Contributivo')
        entidad = EntidadResponsable.objects.create(nit='900123456', nombre='EPS Test', tipo_erp=tipo)
        Factura.objects.create(erp=entidad, num_factura='ENV-1')

        token = set_current_environment_id(environment_2.pk)
        try:
            self.assertFalse(Factura.objects.filter(num_factura='ENV-1').exists())
            Factura.objects.create(erp=entidad, num_factura='ENV-2')
            self.assertEqual(Factura.objects.count(), 1)
        finally:
            set_current_environment_id(1)
