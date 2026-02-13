from django.test import TestCase, Client
from django.urls import reverse
from .models import Cliente

class ClienteListaViewTest(TestCase):
    def setUp(self):
        Cliente.objects.create(nombre="Juan", apellido="Pérez", email="juan@test.com", telefono="1234", direccion="Calle 1")
        Cliente.objects.create(nombre="Ana", apellido="García", email="ana@test.com", telefono="5678", direccion="Calle 2")
        Cliente.objects.create(nombre="Pedro", apellido="López", email="pedro@test.com", telefono="9999", direccion="Calle 3")
        self.client = Client()

    def test_busqueda_por_nombre(self):
        response = self.client.get(reverse('lista_clientes'), {'q': 'Juan'})
        self.assertContains(response, "Juan")
        self.assertNotContains(response, "Ana")

    def test_orden_descendente(self):
        response = self.client.get(reverse('lista_clientes'), {'order_by': 'nombre', 'direction': 'desc'})
        clientes = response.context['page_obj'].object_list
        self.assertEqual(clientes[0].nombre, "Pedro")
        self.assertEqual(clientes[1].nombre, "Juan")
        self.assertEqual(clientes[2].nombre, "Ana")

    def test_orden_ascendente(self):
        response = self.client.get(reverse('lista_clientes'), {'order_by': 'nombre', 'direction': 'asc'})
        clientes = response.context['page_obj'].object_list
        self.assertEqual(clientes[0].nombre, "Ana")
        self.assertEqual(clientes[1].nombre, "Juan")
        self.assertEqual(clientes[2].nombre, "Pedro")
