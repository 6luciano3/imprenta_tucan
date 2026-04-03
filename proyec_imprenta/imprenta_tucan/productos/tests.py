from django.test import TestCase, Client
from django.urls import reverse
from .models import Producto, CategoriaProducto, TipoProducto, UnidadMedida, ProductoInsumo
from .forms import ProductoForm, ProductoInsumoForm
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


class ProductoFormCleanNombreTest(TestCase):
    """Tests para ProductoForm.clean_nombreProducto()."""

    def setUp(self):
        from insumos.models import Insumo
        from configuracion.models import Formula
        self.insumo = Insumo.objects.create(
            nombre="Papel test", codigo="PT-001", stock=50
        )
        self.formula = Formula.objects.create(
            insumo=self.insumo, codigo="F-TEST", nombre="Fórmula test",
            expresion="tirada * 1", variables_json=[], version=1, activo=True,
        )
        self.producto = Producto.objects.create(
            nombreProducto="Folleto Existente",
            precioUnitario=100,
            formula=self.formula,
        )

    def _form_data(self, nombre, pk=None):
        """Construye datos mínimos para ProductoForm."""
        data = {
            'nombreProducto': nombre,
            'precioUnitario': '100.00',
            'formula': self.formula.pk,
            'activo': True,
        }
        instance = Producto.objects.get(pk=pk) if pk else None
        return ProductoForm(data=data, instance=instance)

    def test_nombre_unico_ok(self):
        form = self._form_data("Folleto Nuevo")
        self.assertTrue(form.is_valid(), form.errors)

    def test_nombre_duplicado_rechazado(self):
        form = self._form_data("Folleto Existente")
        self.assertFalse(form.is_valid())
        self.assertIn('nombreProducto', form.errors)

    def test_nombre_duplicado_case_insensitive(self):
        form = self._form_data("folleto existente")
        self.assertFalse(form.is_valid())
        self.assertIn('nombreProducto', form.errors)

    def test_editar_propio_nombre_permitido(self):
        """Al editar, el mismo nombre no debe considerarse duplicado."""
        form = self._form_data("Folleto Existente", pk=self.producto.pk)
        self.assertTrue(form.is_valid(), form.errors)

    def test_editar_con_nombre_de_otro_rechazado(self):
        otro = Producto.objects.create(
            nombreProducto="Afiche",
            precioUnitario=200,
            formula=self.formula,
        )
        form = self._form_data("Folleto Existente", pk=otro.pk)
        self.assertFalse(form.is_valid())
        self.assertIn('nombreProducto', form.errors)


class ProductoInsumoFormCleanInsumoTest(TestCase):
    """Tests para ProductoInsumoForm.clean_insumo() — validación de duplicados en receta."""

    def setUp(self):
        from insumos.models import Insumo
        from configuracion.models import Formula
        self.insumo_a = Insumo.objects.create(
            nombre="Tinta Cyan", codigo="TK-C", stock=100, tipo='directo'
        )
        self.insumo_b = Insumo.objects.create(
            nombre="Papel Bond", codigo="PB-B", stock=200, tipo='directo'
        )
        formula = Formula.objects.create(
            insumo=self.insumo_a, codigo="F-R", nombre="Formula receta",
            expresion="tirada * 1", variables_json=[], version=1, activo=True,
        )
        self.producto = Producto.objects.create(
            nombreProducto="Folleto Receta",
            precioUnitario=150,
            formula=formula,
        )
        # Insumo A ya está en la receta
        ProductoInsumo.objects.create(
            producto=self.producto,
            insumo=self.insumo_a,
            cantidad_por_unidad=2,
        )

    def _form(self, insumo, cantidad=1):
        form = ProductoInsumoForm(
            data={'insumo': insumo.pk, 'cantidad_por_unidad': str(cantidad), 'es_costo_fijo': False},
            producto=self.producto,
        )
        return form

    def test_insumo_nuevo_permitido(self):
        form = self._form(self.insumo_b)
        self.assertTrue(form.is_valid(), form.errors)

    def test_insumo_duplicado_rechazado(self):
        form = self._form(self.insumo_a)
        self.assertFalse(form.is_valid())
        self.assertIn('insumo', form.errors)

    def test_cantidad_cero_rechazada(self):
        form = self._form(self.insumo_b, cantidad=0)
        self.assertFalse(form.is_valid())
        self.assertIn('cantidad_por_unidad', form.errors)

    def test_cantidad_negativa_rechazada(self):
        form = self._form(self.insumo_b, cantidad=-5)
        self.assertFalse(form.is_valid())
        self.assertIn('cantidad_por_unidad', form.errors)

    def test_cantidad_positiva_ok(self):
        form = self._form(self.insumo_b, cantidad=3)
        self.assertTrue(form.is_valid(), form.errors)
