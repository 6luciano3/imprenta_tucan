from django.test import TestCase, Client
from django.urls import reverse
from .models import Producto, CategoriaProducto, TipoProducto, UnidadMedida

class ProductoListaViewTest(TestCase):
    def setUp(self):
        categoria = CategoriaProducto.objects.create(nombreCategoria="Papelería")
        tipo = TipoProducto.objects.create(nombreTipoProducto="Resma")
        unidad = UnidadMedida.objects.create(nombreUnidad="Paquete")
        Producto.objects.create(nombreProducto="Resma A4", descripcion="Papel A4", precioUnitario=100, categoriaProducto=categoria, tipoProducto=tipo, unidadMedida=unidad)
        Producto.objects.create(nombreProducto="Resma Oficio", descripcion="Papel Oficio", precioUnitario=120, categoriaProducto=categoria, tipoProducto=tipo, unidadMedida=unidad)
        self.client = Client()

    def test_lista_productos_status(self):
        response = self.client.get(reverse('lista_productos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resma A4")
        self.assertContains(response, "Resma Oficio")

    def test_busqueda_producto(self):
        response = self.client.get(reverse('lista_productos'), {'q': 'A4'})
        self.assertContains(response, "Resma A4")
        self.assertNotContains(response, "Resma Oficio")

    def test_orden_ascendente(self):
        response = self.client.get(reverse('lista_productos'), {'order_by': 'nombreProducto', 'direction': 'asc'})
        productos = response.context['productos'].object_list
        self.assertEqual(productos[0].nombreProducto, "Resma A4")
        self.assertEqual(productos[1].nombreProducto, "Resma Oficio")

    def test_orden_descendente(self):
        response = self.client.get(reverse('lista_productos'), {'order_by': 'nombreProducto', 'direction': 'desc'})
        productos = response.context['productos'].object_list
        self.assertEqual(productos[0].nombreProducto, "Resma Oficio")
        self.assertEqual(productos[1].nombreProducto, "Resma A4")
