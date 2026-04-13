from django import forms
from django.forms import formset_factory
from clientes.models import Cliente
from productos.models import Producto
from .models import EstadoPedido, PagoFactura


class AltaPedidoHeaderForm(forms.Form):
    """Cabecera del pedido: cliente y fecha de entrega común."""
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        label="Cliente",
        widget=forms.Select(attrs={"class": "form-select"}),
        to_field_name=None,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostrar solo nombre y apellido en el select
        self.fields['cliente'].label_from_instance = lambda obj: f"{obj.nombre} {obj.apellido}"
    fecha_entrega = forms.DateField(
        label="Fecha de Entrega",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control", "required": True}),
    )
    aplicar_iva = forms.BooleanField(
        label="IVA 21%",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    DESCUENTO_CHOICES = [
        ("0", "Sin descuento"),
        ("5", "Descuento 5% — Nuevo"),
        ("7", "Descuento 7% — Estándar"),
        ("10", "Descuento 10% — Estratégico"),
        ("15", "Descuento 15% — Premium"),
        ("20", "Descuento 20% (manual)"),
    ]
    descuento = forms.ChoiceField(
        label="Descuento",
        choices=DESCUENTO_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        initial="0"
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
        min_value=0,
        max_value=1_000_000,
        widget=forms.NumberInput(attrs={"class": "form-control cantidad-input", "min": "0", "max": "1000000", "required": True}),
    )
    especificaciones = forms.CharField(
        label="Especificaciones",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional"}),
    )


# Formset para múltiples líneas
LineaPedidoFormSet = formset_factory(LineaPedidoForm, extra=0, can_delete=True)


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
    estado = forms.ModelChoiceField(
        queryset=EstadoPedido.objects.all().order_by("nombre"),
        label="Estado",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fecha_entrega = forms.DateField(
        label="Fecha de Entrega",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control", "required": True}),
    )
    aplicar_iva = forms.BooleanField(
        label="IVA 21%",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    DESCUENTO_CHOICES = [
        ("0",  "Sin descuento"),
        ("5",  "Descuento 5% — Nuevo"),
        ("7",  "Descuento 7% — Estándar"),
        ("10", "Descuento 10% — Estratégico"),
        ("15", "Descuento 15% — Premium"),
        ("20", "Descuento 20% (manual)"),
    ]
    descuento = forms.ChoiceField(
        label="Descuento",
        choices=DESCUENTO_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        initial="0"
    )


class PagoFacturaForm(forms.ModelForm):
    class Meta:
        model = PagoFactura
        fields = ['fecha_pago', 'metodo_pago', 'referencia', 'notas']
        widgets = {
            'fecha_pago': forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            'metodo_pago': forms.Select(attrs={"class": "form-select"}),
            'referencia': forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: CBU, N° cheque (opcional)"}),
            'notas': forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Observaciones (opcional)"}),
        }
        labels = {
            'fecha_pago': 'Fecha de pago',
            'metodo_pago': 'Método de pago',
            'referencia': 'Referencia',
            'notas': 'Notas',
        }
