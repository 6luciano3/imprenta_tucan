from django import forms
from django.forms import formset_factory
from clientes.models import Cliente
from productos.models import Producto
from .models import EstadoPedido


class AltaPedidoHeaderForm(forms.Form):
    """Cabecera del pedido: cliente y fecha de entrega común."""
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        label="Cliente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fecha_entrega = forms.DateField(
        label="Fecha de Entrega",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control", "required": True}),
    )
    aplicar_iva = forms.BooleanField(
        label="Aplicar IVA 21%",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class LineaPedidoForm(forms.Form):
    """Línea del pedido con producto, cantidad y especificaciones opcionales."""
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.all(),
        label="Producto",
        widget=forms.Select(attrs={"class": "form-select producto-select"}),
    )
    cantidad = forms.IntegerField(
        label="Cantidad",
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control cantidad-input", "min": "1", "required": True}),
    )
    especificaciones = forms.CharField(
        label="Especificaciones",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional"}),
    )


# Formset para múltiples líneas
LineaPedidoFormSet = formset_factory(LineaPedidoForm, extra=1, can_delete=True)


class SeleccionarClienteForm(forms.Form):
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        label="Seleccione un Cliente",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="-- Elija un cliente --",
    )


class ModificarPedidoForm(forms.Form):
    """Formulario para modificar un pedido existente.

    Campos editables: producto, fecha_entrega, cantidad, especificaciones.
    El monto total se calcula automáticamente del lado del cliente y del servidor.
    """
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.all(),
        label="Producto",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    estado = forms.ModelChoiceField(
        queryset=EstadoPedido.objects.all().order_by("nombre"),
        label="Estado",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fecha_entrega = forms.DateField(
        label="Fecha de Entrega",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control", "required": True}),
    )
    cantidad = forms.IntegerField(
        label="Cantidad",
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1", "required": True}),
    )
    especificaciones = forms.CharField(
        label="Especificaciones",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Opcional"}),
    )
