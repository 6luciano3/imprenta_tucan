from django import forms
from .models import PresupuestoDetalle
from productos.models import Producto


class PresupuestoDetalleForm(forms.ModelForm):
    class Meta:
        model = PresupuestoDetalle
        fields = ['producto', 'cantidad', 'precio_unitario']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
        }
        labels = {
            'producto': 'Producto',
            'cantidad': 'Cantidad',
            'precio_unitario': 'Precio Unitario',
        }
        help_texts = {
            'producto': 'Seleccione el producto a presupuestar.',
            'cantidad': 'Cantidad de unidades.',
            'precio_unitario': 'Precio unitario acordado.',
        }
