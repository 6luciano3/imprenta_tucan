from django import forms
from .models import Proveedor, Rubro


class ProveedorForm(forms.ModelForm):
    rubro_lookup = forms.ModelChoiceField(
        queryset=Rubro.objects.filter(activo=True).order_by('nombre'),
        required=False,
        label='Rubro (catálogo)',
        widget=forms.Select(attrs={'class': 'form-input'})
    )

    class Meta:
        model = Proveedor
        fields = ['nombre', 'cuit', 'email', 'telefono', 'direccion', 'rubro']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ingrese el nombre del proveedor'}),
            'cuit': forms.TextInput(attrs={'placeholder': 'XX-XXXXXXXX-X'}),
            'email': forms.EmailInput(attrs={'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Ingrese el número de teléfono'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Ingrese la dirección completa'}),
            # Campo textual para mantener compatibilidad. Si se elige del catálogo, se sobrescribe en clean().
            'rubro': forms.TextInput(attrs={'placeholder': 'Escriba el rubro (si no usa catálogo)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si el proveedor tiene rubro textual y existe un Rubro con ese nombre, preseleccionar.
        if self.instance and self.instance.pk and self.instance.rubro:
            try:
                self.fields['rubro_lookup'].initial = Rubro.objects.get(nombre__iexact=self.instance.rubro)
            except Rubro.DoesNotExist:
                pass

    def clean(self):
        cleaned = super().clean()
        rl = cleaned.get('rubro_lookup')
        if rl:
            # Sobre-escribir campo rubro textual con el nombre del Rubro seleccionado
            cleaned['rubro'] = rl.nombre
        return cleaned


class RubroForm(forms.ModelForm):
    class Meta:
        model = Rubro
        fields = ['nombre', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nombre del rubro'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Descripción opcional'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
