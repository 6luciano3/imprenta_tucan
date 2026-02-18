from django.test import TestCase, Client
from django.urls import reverse
from .models import Producto, CategoriaProducto, TipoProducto, UnidadMedida
from usuarios.models import Usuario

class ProductoListaViewTest(TestCase):
    def setUp(self):
        from roles.models import Rol
        from permisos.models import Permiso
        # Crear permiso activo para Productos con acción Listar
        import json
        permiso = Permiso.objects.create(nombre="Permiso Productos", descripcion="Permite listar productos", modulo="Productos", acciones=json.dumps(["Listar"]), estado="Activo")
        rol = Rol.objects.create(nombreRol="Rol Test", estado="Activo")
        rol.permisos.add(permiso)
        self.user = Usuario.objects.create_user(email="testuser@test.com", password="testpass", nombre="Test", apellido="User", telefono="1234", rol=rol)
        self.client = Client()
        self.client.force_login(self.user)
        categoria = CategoriaProducto.objects.create(nombreCategoria="Papelería")
        tipo = TipoProducto.objects.create(nombreTipoProducto="Resma")
        unidad = UnidadMedida.objects.create(nombreUnidad="Paquete")
        # Crear un insumo para la fórmula
        from insumos.models import Insumo
        insumo = Insumo.objects.create(nombre="Papel base", descripcion="Papel para fórmula", codigo="PB-001", stock=100)
        from configuracion.models import Formula
        formula = Formula.objects.create(insumo=insumo, codigo="F-001", nombre="Fórmula Test", descripcion="desc", expresion="x+y", variables_json=[], version=1, activo=True)
        Producto.objects.create(nombreProducto="Resma A4", descripcion="Papel A4", precioUnitario=100, categoriaProducto=categoria, tipoProducto=tipo, unidadMedida=unidad, formula=formula)
        Producto.objects.create(nombreProducto="Resma Oficio", descripcion="Papel Oficio", precioUnitario=120, categoriaProducto=categoria, tipoProducto=tipo, unidadMedida=unidad, formula=formula)

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
