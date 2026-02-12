from django import forms
from .models import Insumo
from proveedores.models import Proveedor
from django.db.models import Q


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = [
            'codigo',
            'nombre',
            'categoria',
            'stock',
            'precio',
            'activo',
        ]


class AltaInsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ["nombre", "codigo", "proveedor", "cantidad", "precio_unitario"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "required": True, "maxlength": 100}),
            "codigo": forms.TextInput(attrs={"class": "form-control", "required": True, "maxlength": 20}),
            "proveedor": forms.Select(attrs={"class": "form-select", "required": True}),
            "cantidad": forms.NumberInput(attrs={"class": "form-control", "required": True, "min": 1, "step": 1}),
            "precio_unitario": forms.NumberInput(attrs={"class": "form-control", "required": True, "min": 0.01, "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar proveedores activos de la industria gráfica (papel, tintas, químicos, repuestos, etc.)
        terms = ["papel", "tinta", "quím", "quim", "repuesto", "placa", "barniz"]
        q = Q()
        for t in terms:
            q |= Q(rubro__icontains=t)
        qs = Proveedor.objects.filter(activo=True)
        if q:
            qs = qs.filter(q)
        self.fields["proveedor"].queryset = qs.order_by("nombre")

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get("cantidad")
        if cantidad is None or cantidad <= 0:
            raise forms.ValidationError("La cantidad debe ser un número positivo.")
        return cantidad

    def clean_precio_unitario(self):
        precio = self.cleaned_data.get("precio_unitario")
        if precio is None or precio <= 0:
            raise forms.ValidationError("El precio unitario debe ser un número positivo.")
        return precio


class BuscarInsumoForm(forms.Form):
    criterio_busqueda = forms.CharField(
        label="Criterio de búsqueda",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nombre, código, categoría o proveedor..."
        })
    )


class ConsumoRealInsumoForm(forms.ModelForm):
    class Meta:
        from .models import ConsumoRealInsumo
        model = ConsumoRealInsumo
        fields = ["insumo", "periodo", "cantidad_consumida", "comentario"]
        widgets = {
            "insumo": forms.Select(attrs={"class": "form-select", "required": True}),
            "periodo": forms.TextInput(attrs={"class": "form-control", "required": True, "placeholder": "YYYY-MM"}),
            "cantidad_consumida": forms.NumberInput(attrs={"class": "form-control", "required": True, "min": 1, "step": 1}),
            "comentario": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Comentario opcional"}),
        }

    def clean_cantidad_consumida(self):
        cantidad = self.cleaned_data.get("cantidad_consumida")
        if cantidad is None or cantidad <= 0:
            raise forms.ValidationError("La cantidad consumida debe ser un número positivo.")
        return cantidad

    def clean_periodo(self):
        periodo = self.cleaned_data.get("periodo", "").strip()
        if not periodo:
            raise forms.ValidationError("El periodo es obligatorio.")
        # Validar formato YYYY-MM
        import re
        if not re.match(r"^\d{4}-\d{2}$", periodo):
            raise forms.ValidationError("El periodo debe tener formato YYYY-MM.")
        return periodo

    def clean_insumo(self):
        insumo = self.cleaned_data.get("insumo")
        if not insumo:
            raise forms.ValidationError("Debe seleccionar un insumo.")
        return insumo

class ModificarInsumoForm(forms.ModelForm):
    """Formulario para modificar insumos por Personal Administrativo.

    Incluye validaciones de negocio y aplica estilos Bootstrap 5.
    """

    class Meta:
        model = Insumo
        fields = ["nombre", "codigo", "proveedor", "cantidad", "precio_unitario"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "required": True, "maxlength": 100}),
            "codigo": forms.TextInput(attrs={"class": "form-control", "required": True, "maxlength": 20}),
            "proveedor": forms.Select(attrs={"class": "form-select", "required": True}),
            "cantidad": forms.NumberInput(attrs={"class": "form-control", "required": True, "min": 1, "step": 1}),
            "precio_unitario": forms.NumberInput(attrs={"class": "form-control", "required": True, "min": 0.01, "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar proveedores activos de la industria gráfica (papel, tintas, químicos, repuestos, placas, barniz)
        terms = ["papel", "tinta", "quím", "quim", "repuesto", "placa", "barniz"]
        q = Q()
        for t in terms:
            q |= Q(rubro__icontains=t)
        qs = Proveedor.objects.filter(activo=True)
        if q:
            qs = qs.filter(q)
        self.fields["proveedor"].queryset = qs.order_by("nombre")

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get("cantidad")
        if cantidad is None or cantidad <= 0:
            raise forms.ValidationError("La cantidad debe ser un número positivo.")
        return cantidad

    def clean_precio_unitario(self):
        precio = self.cleaned_data.get("precio_unitario")
        if precio is None or precio <= 0:
            raise forms.ValidationError("El precio unitario debe ser un número positivo.")
        return precio

    def clean_codigo(self):
        """Validar código único permitiendo mantener el del propio insumo."""
        codigo = self.cleaned_data.get("codigo", "").strip()
        if not codigo:
            raise forms.ValidationError("El código es obligatorio.")
        qs = Insumo.objects.filter(codigo__iexact=codigo)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Código duplicado. Ingrese un código único.")
        return codigo
