"""
Tests de procesos inteligentes – Imprenta Tucán
================================================
Cubre:
  1.  ProveedorInteligenteService.calcular_score
  2.  ProveedorInteligenteService.recomendar_proveedor
  3.  tarea_ranking_clientes (Celery task ejecutada in-process)
  4.  tarea_prediccion_demanda
  5.  tarea_anticipacion_compras
  6.  Generación automática de OfertaPropuesta (token unique)
  7.  Envío de oferta por email (mocked)
  8.  Aceptar oferta via token (URL)
  9.  Rechazar oferta via token (URL)
  10. AccionCliente registrada al aceptar/rechazar
  11. Descuento automático aplicado al crear Pedido
  12. Oferta marcada como 'aplicada' al crear Pedido
  13. Reserva de stock al pasar pedido a estado 'proceso'
  14. Webhook consulta stock (proveedor reporta disponibilidad)
  15. Recalculo de ScoreProveedor via recomendar_proveedor
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
import itertools

from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.utils import timezone
from django.core import mail

from clientes.models import Cliente
from insumos.models import Insumo
from pedidos.models import Pedido, EstadoPedido, OrdenCompra
from proveedores.models import Proveedor

from automatizacion.models import (
    RankingCliente,
    ScoreProveedor,
    OfertaPropuesta,
    MensajeOferta,
    AccionCliente,
    AutomationLog,
    ConsultaStockProveedor,
    CompraPropuesta,
)
from automatizacion.api.services import ProveedorInteligenteService, CRITERIOS_PESOS


# ---------------------------------------------------------------------------
# Contador global para garantizar unicidad en fixtures
# ---------------------------------------------------------------------------
_counter = itertools.count(1)


def _uid():
    """Retorna un entero único por ejecución del proceso de tests."""
    return next(_counter)


# ---------------------------------------------------------------------------
# Helpers de fixtures reutilizables
# ---------------------------------------------------------------------------

def make_proveedor(nombre=None, activo=True):
    n = _uid()
    nombre = nombre or f"Prov{n}"
    cuit = f"30-{n:08d}-1"
    return Proveedor.objects.create(
        nombre=nombre,
        apellido="SA",
        cuit=cuit,
        email=f"prov{n}@prov.com",
        telefono="381-1234567",
        direccion="Calle 1",
        rubro="Papeleria",
        activo=activo,
    )


def make_insumo(codigo=None, stock=100):
    n = _uid()
    codigo = codigo or f"INS-{n:04d}"
    return Insumo.objects.create(
        nombre=f"Insumo {n}",
        codigo=codigo,
        cantidad=stock,
        precio_unitario=Decimal("10.00"),
        categoria="Papel",
        stock=stock,
        precio=Decimal("10.00"),
        activo=True,
    )


def make_cliente(nombre=None, email=None):
    n = _uid()
    nombre = nombre or f"Cliente{n}"
    email = email or f"cliente{n}@test.com"
    cuit = f"{n:011d}"  # UNIQUE: 11 dígitos distintos por llamada
    return Cliente.objects.create(
        nombre=nombre,
        apellido="García",
        razon_social=f"{nombre} SRL",
        direccion="Av. 1",
        ciudad="Tucumán",
        provincia="Tucumán",
        pais="Argentina",
        telefono="381-0000000",
        email=email,
        cuit=cuit,
    )


# ===========================================================================
# 1-2: ProveedorInteligenteService
# ===========================================================================

class ProveedorInteligenteServiceTest(TestCase):
    def setUp(self):
        self.insumo = make_insumo()
        self.prov_bueno = make_proveedor("ProvBueno")
        self.prov_malo = make_proveedor("ProvMalo")

        # Historial: prov_bueno tiene 4 confirmadas, 0 rechazadas → cumplimiento 1.0, incidencias 0.0
        for _ in range(4):
            OrdenCompra.objects.create(
                insumo=self.insumo,
                cantidad=10,
                proveedor=self.prov_bueno,
                estado="confirmada",
            )
        # prov_malo tiene 0 confirmadas, 3 rechazadas → cumplimiento 0.0, incidencias 1.0
        for _ in range(3):
            OrdenCompra.objects.create(
                insumo=self.insumo,
                cantidad=10,
                proveedor=self.prov_malo,
                estado="rechazada",
            )

    def test_calcular_score_proveedor_bueno_mayor_que_malo(self):
        score_bueno = ProveedorInteligenteService.calcular_score(self.prov_bueno, self.insumo)
        score_malo = ProveedorInteligenteService.calcular_score(self.prov_malo, self.insumo)
        self.assertGreater(score_bueno, score_malo,
                           f"Score bueno ({score_bueno}) debería ser > score malo ({score_malo})")

    def test_calcular_score_rango_0_100(self):
        score = ProveedorInteligenteService.calcular_score(self.prov_bueno, self.insumo)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_recomendar_proveedor_retorna_el_mejor(self):
        recomendado = ProveedorInteligenteService.recomendar_proveedor(self.insumo)
        self.assertEqual(recomendado, self.prov_bueno,
                         "Debería recomendar al proveedor con mejor historial")

    def test_recomendar_proveedor_crea_score_registro(self):
        ProveedorInteligenteService.recomendar_proveedor(self.insumo)
        scores = ScoreProveedor.objects.filter(proveedor__in=[self.prov_bueno, self.prov_malo])
        self.assertEqual(scores.count(), 2, "Debe crear/actualizar ScoreProveedor para cada proveedor")

    def test_recomendar_proveedor_sin_proveedores_retorna_none(self):
        Proveedor.objects.all().update(activo=False)
        resultado = ProveedorInteligenteService.recomendar_proveedor(self.insumo)
        self.assertIsNone(resultado)

    def test_cumplimiento_sin_ordenes_es_1(self):
        nuevo = make_proveedor("ProvNuevo")
        cumplimiento = ProveedorInteligenteService._cumplimiento(nuevo)
        self.assertEqual(cumplimiento, 1, "Proveedor sin historial → cumplimiento neutro = 1")

    def test_incidencias_sin_ordenes_es_0(self):
        nuevo = make_proveedor("ProvNuevo2")
        incidencias = ProveedorInteligenteService._incidencias(nuevo)
        self.assertEqual(incidencias, 0, "Proveedor sin historial → incidencias = 0")

    def test_score_solo_confirmadas_es_consistente(self):
        """Proveedor con todas confirmadas debe tener score predecible."""
        score = ProveedorInteligenteService.calcular_score(self.prov_bueno, self.insumo)
        # precio=1 (neutro), cumplimiento=1, incidencias=0, disponibilidad=1
        # score = 0.4*(1-1) + 0.3*1 + 0.2*(1-0) + 0.1*1 = 0 + 0.3 + 0.2 + 0.1 = 0.6 → 60.0
        self.assertAlmostEqual(score, 60.0, places=1)


# ===========================================================================
# 3-5: Tareas Celery (ejecutadas in-process, sin broker)
# ===========================================================================

class TareasCeleryTest(TestCase):
    def setUp(self):
        make_insumo("INS-C01", stock=50)

    def test_tarea_prediccion_demanda_no_falla(self):
        from automatizacion.tasks import tarea_prediccion_demanda
        result = tarea_prediccion_demanda()
        self.assertIsInstance(result, str, "La tarea debe retornar un string con el resultado")

    def test_tarea_anticipacion_compras_no_falla(self):
        from automatizacion.tasks import tarea_anticipacion_compras
        result = tarea_anticipacion_compras()
        self.assertIsInstance(result, str)

    def test_tarea_ranking_clientes_menos_de_4_clientes_no_falla(self):
        """Con menos de 4 clientes usa el algoritmo real y no debe lanzar excepción."""
        make_cliente("Cliente1", "c1@test.com")
        from automatizacion.tasks import tarea_ranking_clientes
        result = tarea_ranking_clientes()
        self.assertIsInstance(result, str)

    def test_tarea_ranking_clientes_demo_4_clientes(self):
        """Con exactamente 4 clientes activa el modo demo."""
        for i in range(4):
            make_cliente(f"Demo{i}", f"demo{i}@test.com")
        from automatizacion.tasks import tarea_ranking_clientes
        result = tarea_ranking_clientes()
        self.assertIn("demo", result.lower(), "Debe retornar mensaje confirmando puntajes demo")
        self.assertEqual(RankingCliente.objects.count(), 4)

    def test_tarea_ranking_clientes_demo_crea_rankings(self):
        clientes = [make_cliente(f"RC{i}", f"rc{i}@test.com") for i in range(4)]
        from automatizacion.tasks import tarea_ranking_clientes
        tarea_ranking_clientes()
        scores = set(RankingCliente.objects.values_list('score', flat=True))
        self.assertIn(95, scores)
        self.assertIn(75, scores)
        self.assertIn(45, scores)
        self.assertIn(15, scores)


# ===========================================================================
# 6-10: Ofertas propuestas – generación, email, token, acciones
# ===========================================================================

class OfertaPropuestaTest(TestCase):
    def setUp(self):
        self.cliente = make_cliente("Luis", "luis@test.com")
        self.oferta = OfertaPropuesta.objects.create(
            cliente=self.cliente,
            titulo="10% OFF en tu próximo pedido",
            descripcion="Oferta especial por fidelidad.",
            tipo="descuento",
            estado="pendiente",
            parametros={"descuento": 10},
        )

    def test_token_email_generado_automaticamente(self):
        self.assertIsNotNone(self.oferta.token_email)
        self.assertEqual(len(self.oferta.token_email), 32)

    def test_token_email_unico_por_oferta(self):
        oferta2 = OfertaPropuesta.objects.create(
            cliente=self.cliente,
            titulo="Oferta 2",
            descripcion="Desc",
            tipo="fidelizacion",
            estado="pendiente",
            parametros={},
        )
        self.assertNotEqual(self.oferta.token_email, oferta2.token_email)

    def test_enviar_oferta_email_sin_email_cliente(self):
        from automatizacion.services import enviar_oferta_email
        self.oferta.cliente.email = ""
        self.oferta.cliente.save()
        ok, err = enviar_oferta_email(self.oferta)
        self.assertFalse(ok)
        self.assertIn("email", err.lower())

    def test_enviar_oferta_email_usa_send_mail(self):
        from automatizacion.services import enviar_oferta_email
        ok, err = enviar_oferta_email(self.oferta)
        # Django test runner usa backend de email en memoria
        self.assertTrue(ok, f"Envío falló: {err}")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.cliente.email, mail.outbox[0].to)

    def test_enviar_oferta_email_asunto_contiene_titulo(self):
        from automatizacion.services import enviar_oferta_email
        enviar_oferta_email(self.oferta)
        self.assertIn(self.oferta.titulo, mail.outbox[0].subject)

    def test_aceptar_oferta_via_token_cambia_estado(self):
        self.oferta.estado = "enviada"
        self.oferta.save()
        c = TestClient()
        url = reverse("aceptar_oferta_token", args=[self.oferta.token_email])
        c.post(url)
        self.oferta.refresh_from_db()
        self.assertEqual(self.oferta.estado, "aceptada")

    def test_rechazar_oferta_via_token_cambia_estado(self):
        self.oferta.estado = "enviada"
        self.oferta.save()
        c = TestClient()
        url = reverse("rechazar_oferta_token", args=[self.oferta.token_email])
        c.post(url)
        self.oferta.refresh_from_db()
        self.assertEqual(self.oferta.estado, "rechazada")

    def test_aceptar_via_token_registra_accion_cliente(self):
        self.oferta.estado = "enviada"
        self.oferta.save()
        c = TestClient()
        url = reverse("aceptar_oferta_token", args=[self.oferta.token_email])
        c.post(url)
        accion = AccionCliente.objects.filter(cliente=self.cliente, tipo="aceptar").first()
        self.assertIsNotNone(accion, "Debe crearse AccionCliente tipo 'aceptar'")
        self.assertEqual(accion.canal, "email")

    def test_rechazar_via_token_registra_accion_cliente(self):
        self.oferta.estado = "enviada"
        self.oferta.save()
        c = TestClient()
        url = reverse("rechazar_oferta_token", args=[self.oferta.token_email])
        c.post(url)
        accion = AccionCliente.objects.filter(cliente=self.cliente, tipo="rechazar").first()
        self.assertIsNotNone(accion, "Debe crearse AccionCliente tipo 'rechazar'")

    def test_token_invalido_retorna_404(self):
        c = TestClient()
        url = reverse("aceptar_oferta_token", args=["tokeninvalido00000000000000000000"])
        response = c.post(url)
        self.assertEqual(response.status_code, 404)


# ===========================================================================
# 11-12: Descuento automático al crear Pedido (Pedido.save)
# ===========================================================================

def make_estado(nombre):
    obj, _ = EstadoPedido.objects.get_or_create(nombre=nombre)
    return obj


class DescuentoAutomaticoEnPedidoTest(TestCase):
    def setUp(self):
        self.cliente = make_cliente()
        self.estado = make_estado("Pendiente")
        # Oferta de descuento 20% aceptada para este cliente
        self.oferta = OfertaPropuesta.objects.create(
            cliente=self.cliente,
            titulo="20% OFF",
            descripcion="Descuento especial",
            tipo="descuento",
            estado="aceptada",
            parametros={"descuento": 20},
        )

    def test_pedido_nuevo_aplica_descuento_oferta_aceptada(self):
        monto_original = Decimal("1000.00")
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            fecha_entrega=date.today() + timedelta(days=7),
            monto_total=monto_original,
            estado=self.estado,
        )
        # Monto debe haber bajado un 20%: 1000 * 0.8 = 800
        self.assertLess(pedido.monto_total, monto_original,
                        "El monto debe reducirse por el descuento de la oferta aceptada")
        self.assertAlmostEqual(float(pedido.monto_total), 800.0, places=1)

    def test_pedido_nuevo_marca_oferta_como_aplicada(self):
        Pedido.objects.create(
            cliente=self.cliente,
            fecha_entrega=date.today() + timedelta(days=7),
            monto_total=Decimal("500.00"),
            estado=self.estado,
        )
        self.oferta.refresh_from_db()
        self.assertEqual(self.oferta.estado, "aplicada",
                         "La oferta aceptada debe quedar en estado 'aplicada' al crear el pedido")

    def test_pedido_nuevo_sin_oferta_aceptada_no_aplica_descuento(self):
        otro_cliente = make_cliente("Sin Oferta", "sinoferta@test.com")
        monto = Decimal("1000.00")
        pedido = Pedido.objects.create(
            cliente=otro_cliente,
            fecha_entrega=date.today() + timedelta(days=7),
            monto_total=monto,
            estado=self.estado,
        )
        self.assertEqual(pedido.monto_total, monto,
                         "Sin oferta aceptada, el monto no debe cambiar")

    def test_oferta_aplicada_guarda_id_pedido_en_parametros(self):
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            fecha_entrega=date.today() + timedelta(days=7),
            monto_total=Decimal("200.00"),
            estado=self.estado,
        )
        self.oferta.refresh_from_db()
        self.assertEqual(
            self.oferta.parametros.get("aplicada_pedido_id"), pedido.pk,
            "Los parámetros deben guardar el ID del pedido donde se aplicó"
        )

    def test_descuento_parametrizable_5_porciento(self):
        """Verifica que el descuento respeta el porcentaje de los parámetros."""
        cliente5 = make_cliente()
        OfertaPropuesta.objects.create(
            cliente=cliente5,
            titulo="5% OFF",
            descripcion="Desc",
            tipo="descuento",
            estado="aceptada",
            parametros={"descuento": 5},
        )
        pedido = Pedido.objects.create(
            cliente=cliente5,
            fecha_entrega=date.today() + timedelta(days=7),
            monto_total=Decimal("1000.00"),
            estado=self.estado,
        )
        self.assertAlmostEqual(float(pedido.monto_total), 950.0, places=1)


# ===========================================================================
# 13: Reserva de stock al pasar estado a 'proceso'
# ===========================================================================

class ReservaStockAlPasarAProcesoTest(TestCase):
    def setUp(self):
        self.cliente = make_cliente()
        self.estado_pendiente = make_estado("Pendiente")
        self.estado_proceso = make_estado("Proceso")
        self.insumo = make_insumo(stock=200)

    def test_cambio_a_proceso_llama_reservar_insumos(self):
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            fecha_entrega=date.today() + timedelta(days=7),
            monto_total=Decimal("300.00"),
            estado=self.estado_pendiente,
        )
        # La función se importa dinámicamente desde pedidos.services → parchear en la fuente
        with patch("pedidos.services.reservar_insumos_para_pedido") as mock_reservar:
            pedido.estado = self.estado_proceso
            pedido.save()
            mock_reservar.assert_called_once_with(pedido)

    def test_pedido_en_pendiente_no_llama_reservar(self):
        """Cambio de estado que no involucra 'proceso' no dispara reserva."""
        estado_entregado = make_estado("Entregado")
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            fecha_entrega=date.today() + timedelta(days=7),
            monto_total=Decimal("300.00"),
            estado=self.estado_pendiente,
        )
        with patch("pedidos.services.reservar_insumos_para_pedido") as mock_reservar:
            pedido.estado = estado_entregado
            pedido.save()
            mock_reservar.assert_not_called()


# ===========================================================================
# 14: Webhook consulta stock (proveedor externo reporta disponibilidad)
# ===========================================================================

class WebhookConsultaStockTest(TestCase):
    def setUp(self):
        self.proveedor = make_proveedor()
        self.insumo = make_insumo(stock=5)
        # Crear una propuesta + consulta
        oc = OrdenCompra.objects.create(
            insumo=self.insumo,
            cantidad=20,
            proveedor=self.proveedor,
            estado="sugerida",
        )
        consulta = ConsultaStockProveedor.objects.create(
            proveedor=self.proveedor,
            insumo=self.insumo,
            cantidad=20,
            estado="pendiente",
            respuesta={},
        )
        self.propuesta = CompraPropuesta.objects.create(
            insumo=self.insumo,
            cantidad_requerida=20,
            proveedor_recomendado=self.proveedor,
            pesos_usados=CRITERIOS_PESOS,
            motivo_trigger="stock_minimo_vencido",
            estado="consultado",
            borrador_oc=oc,
            consulta_stock=consulta,
        )
        # El webhook importa Parametro localmente → parchear en la fuente
        self._patcher = patch(
            "configuracion.models.Parametro.get",
            side_effect=lambda codigo, default='': "token-secreto-test" if codigo == "WEBHOOK_TOKEN" else default
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_webhook_sin_token_retorna_403(self):
        c = TestClient()
        url = reverse("webhook_consulta_stock", args=[self.propuesta.pk])
        response = c.post(url, {"estado": "disponible"})
        self.assertEqual(response.status_code, 403)

    def test_webhook_con_token_correcto_actualiza_estado_disponible(self):
        c = TestClient()
        url = reverse("webhook_consulta_stock", args=[self.propuesta.pk])
        response = c.post(
            url,
            data={"estado": "disponible", "detalle": "En stock"},
            HTTP_X_WEBHOOK_TOKEN="token-secreto-test",
        )
        self.assertEqual(response.status_code, 200)
        self.propuesta.refresh_from_db()
        self.assertEqual(self.propuesta.estado, "respuesta_disponible")

    def test_webhook_con_token_correcto_actualiza_estado_no_disponible(self):
        c = TestClient()
        url = reverse("webhook_consulta_stock", args=[self.propuesta.pk])
        c.post(
            url,
            data={"estado": "no", "detalle": "Sin stock"},
            HTTP_X_WEBHOOK_TOKEN="token-secreto-test",
        )
        self.propuesta.refresh_from_db()
        self.assertEqual(self.propuesta.estado, "no_disponible")

    def test_webhook_actualiza_consulta_stock(self):
        c = TestClient()
        url = reverse("webhook_consulta_stock", args=[self.propuesta.pk])
        c.post(
            url,
            data={"estado": "parcial", "detalle": "Parcial"},
            HTTP_X_WEBHOOK_TOKEN="token-secreto-test",
        )
        self.propuesta.refresh_from_db()
        consulta = self.propuesta.consulta_stock
        self.assertEqual(consulta.estado, "parcial")


# ===========================================================================
# 15: AutomationLog – registro de decisiones automáticas
# ===========================================================================

class AutomationLogTest(TestCase):
    def test_registrar_log_crea_registro(self):
        from utils.automationlog_utils import registrar_automation_log
        registrar_automation_log(
            "TEST_EVENTO",
            "Descripción de prueba",
            datos={"key": "value"},
        )
        log = AutomationLog.objects.filter(evento="TEST_EVENTO").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.descripcion, "Descripción de prueba")
        self.assertEqual(log.datos["key"], "value")


# ===========================================================================
# 16: Mensaje callback (actualización de estado de mensajes enviados)
# ===========================================================================

class MensajeCallbackTest(TestCase):
    def setUp(self):
        self.cliente = make_cliente()
        self.oferta = OfertaPropuesta.objects.create(
            cliente=self.cliente,
            titulo="Oferta Callback",
            descripcion="Test",
            tipo="descuento",
            estado="enviada",
            parametros={"descuento": 15},
        )

    def test_callback_crea_mensaje_entregado(self):
        import json as _json
        url = reverse("mensaje_callback")
        payload = _json.dumps({
            "estado": "entregado",
            "oferta_id": self.oferta.pk,
            "cliente_id": self.cliente.pk,
            "canal": "email",
        }).encode("utf-8")
        response = self.client.generic(
            "POST", url, data=payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        msg = MensajeOferta.objects.filter(oferta=self.oferta, estado="entregado").first()
        self.assertIsNotNone(msg)

    def test_callback_estado_invalido_retorna_400(self):
        import json as _json
        url = reverse("mensaje_callback")
        payload = _json.dumps({
            "estado": "ESTADO_INVALIDO",
            "oferta_id": self.oferta.pk,
            "cliente_id": self.cliente.pk,
        }).encode("utf-8")
        response = self.client.generic(
            "POST", url, data=payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
