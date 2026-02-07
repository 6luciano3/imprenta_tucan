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


class OfertasReglasForm(forms.Form):
    reglas_json = forms.CharField(
        label="Reglas de Ofertas (JSON)",
        widget=forms.Textarea(attrs={
            'rows': 18,
            'class': 'w-full font-mono text-sm',
            'placeholder': '[{"nombre":"Descuento","condiciones":{},"accion":{}}]'
        }),
        help_text="Pegá o edita el JSON de reglas. Validamos estructura básica.",
    )

    def clean_reglas_json(self):
        import json
        raw = self.cleaned_data['reglas_json']
        try:
            data = json.loads(raw)
        except Exception as e:
            raise forms.ValidationError(f"JSON inválido: {e}")
        # Validación básica de estructura: lista de reglas con 'condiciones' y 'accion'
        if not isinstance(data, list):
            raise forms.ValidationError("El JSON debe ser una lista de reglas.")
        for i, regla in enumerate(data):
            if not isinstance(regla, dict):
                raise forms.ValidationError(f"Regla #{i+1} debe ser un objeto.")
            if 'accion' not in regla or 'condiciones' not in regla:
                raise forms.ValidationError(f"Regla #{i+1} debe incluir 'condiciones' y 'accion'.")
            accion = regla.get('accion', {})
            if not isinstance(accion, dict):
                raise forms.ValidationError(f"Regla #{i+1}: 'accion' debe ser un objeto.")
            if 'tipo' not in accion:
                raise forms.ValidationError(f"Regla #{i+1}: 'accion.tipo' es requerido (descuento, fidelizacion, prioridad_stock, promocion).")
        return raw
