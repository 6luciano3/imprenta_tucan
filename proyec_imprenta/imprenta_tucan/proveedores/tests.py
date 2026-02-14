from django.test import TestCase, Client
from django.urls import reverse
from .models import Proveedor

class ProveedorListaViewTest(TestCase):
    def setUp(self):
        Proveedor.objects.create(nombre="Proveedor A", email="a@proveedor.com", telefono="1111", direccion="Calle 1")
        Proveedor.objects.create(nombre="Proveedor B", email="b@proveedor.com", telefono="2222", direccion="Calle 2")
        self.client = Client()

    def test_lista_proveedores_status(self):
        response = self.client.get(reverse('lista_proveedores'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Proveedor A")
        self.assertContains(response, "Proveedor B")

    def test_busqueda_proveedor(self):
        response = self.client.get(reverse('lista_proveedores'), {'q': 'Proveedor A'})
        self.assertContains(response, "Proveedor A")
        self.assertNotContains(response, "Proveedor B")

    def test_orden_ascendente(self):
        response = self.client.get(reverse('lista_proveedores'), {'order_by': 'nombre', 'direction': 'asc'})
        proveedores = response.context['proveedores'].object_list
        self.assertEqual(proveedores[0].nombre, "Proveedor A")
        self.assertEqual(proveedores[1].nombre, "Proveedor B")

    def test_orden_descendente(self):
        response = self.client.get(reverse('lista_proveedores'), {'order_by': 'nombre', 'direction': 'desc'})
        proveedores = response.context['proveedores'].object_list
        self.assertEqual(proveedores[0].nombre, "Proveedor B")
        self.assertEqual(proveedores[1].nombre, "Proveedor A")
