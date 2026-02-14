from django.test import TestCase, Client
from django.urls import reverse
from insumos.models import Insumo

class InsumoListaViewTest(TestCase):
    def setUp(self):
        Insumo.objects.create(nombre="Papel A4", descripcion="Resma de papel tamaño A4", stock=100)
        Insumo.objects.create(nombre="Tinta Negra", descripcion="Cartucho de tinta negra", stock=50)
        self.client = Client()

    def test_lista_insumos_status(self):
        response = self.client.get(reverse('lista_insumos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Papel A4")
        self.assertContains(response, "Tinta Negra")

    def test_busqueda_insumo(self):
        response = self.client.get(reverse('lista_insumos'), {'q': 'Papel'})
        self.assertContains(response, "Papel A4")
        self.assertNotContains(response, "Tinta Negra")

    def test_orden_ascendente(self):
        response = self.client.get(reverse('lista_insumos'), {'order_by': 'nombre', 'direction': 'asc'})
        insumos = response.context['insumos'].object_list
        self.assertEqual(insumos[0].nombre, "Papel A4")
        self.assertEqual(insumos[1].nombre, "Tinta Negra")

    def test_orden_descendente(self):
        response = self.client.get(reverse('lista_insumos'), {'order_by': 'nombre', 'direction': 'desc'})
        insumos = response.context['insumos'].object_list
        self.assertEqual(insumos[0].nombre, "Tinta Negra")
        self.assertEqual(insumos[1].nombre, "Papel A4")
