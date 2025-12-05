from .models import Formula, RecetaProducto
from django import forms
from .models import UnidadDeMedida


class UnidadDeMedidaForm(forms.ModelForm):
    class Meta:
        model = UnidadDeMedida
        fields = ['nombre', 'simbolo', 'descripcion', 'activo']


class RecetaProductoForm(forms.ModelForm):
    class Meta:
        model = RecetaProducto
        fields = ['producto', 'insumos', 'descripcion', 'activo']
        widgets = {
            'insumos': forms.CheckboxSelectMultiple,
            'descripcion': forms.Textarea(attrs={'rows': 2}),
        }


class FormulaForm(forms.ModelForm):
    class Meta:
        model = Formula
        fields = ['codigo', 'nombre', 'descripcion', 'expresion', 'variables_json', 'activo']
        widgets = {
            'variables_json': forms.TextInput(attrs={'placeholder': '["tiraje","area","rendimiento"]'}),
        }
