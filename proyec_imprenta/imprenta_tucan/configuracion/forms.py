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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from insumos.models import Insumo
        self.fields['insumos'].queryset = Insumo.objects.filter(tipo='directo').order_by('codigo')


class FormulaForm(forms.ModelForm):
    class Meta:
        model = Formula
        fields = ['codigo', 'nombre', 'descripcion', 'expresion', 'variables_json', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: TINTA_CYAN_OFFSET'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre descriptivo'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'expresion': forms.Textarea(attrs={'class': 'form-control font-mono', 'rows': 3, 'placeholder': 'Ej: (ancho_cm * alto_cm * tirada * cobertura) / 10000'}),
            'variables_json': forms.HiddenInput(),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def _parse_variables(self, raw):
        """Normaliza variables_json a lista de strings (nombres de variables)."""
        import json
        if not raw:
            return []
        if isinstance(raw, list):
            return [v if isinstance(v, str) else str(v) for v in raw]
        if isinstance(raw, dict):
            return list(raw.keys())
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        if isinstance(parsed, dict):
            return list(parsed.keys())
        if isinstance(parsed, list):
            return [v if isinstance(v, str) else str(v) for v in parsed]
        return []

    def clean_variables_json(self):
        raw = self.data.get('variables_json', '')
        return self._parse_variables(raw)

    def clean_expresion(self):
        from configuracion.utils.safe_eval import safe_eval
        expresion = self.cleaned_data.get('expresion', '').strip()
        if not expresion:
            raise forms.ValidationError('La expresión es obligatoria.')
        # Construir variables dummy a partir del campo crudo (aún no limpiado)
        nombres = self._parse_variables(self.data.get('variables_json', ''))
        dummy_vars = {n: 1 for n in nombres if n}
        try:
            safe_eval(expresion, dummy_vars)
        except ValueError as e:
            raise forms.ValidationError(f'Expresión inválida: {e}')
        except NameError:
            # Variables referenciadas no están en dummy → no es error de sintaxis
            pass
        except Exception:
            pass
        return expresion


class OfertasReglasForm(forms.Form):
    reglas_json = forms.CharField(
        label="Reglas de Ofertas (JSON)",
        widget=forms.HiddenInput(),
        required=True,
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
