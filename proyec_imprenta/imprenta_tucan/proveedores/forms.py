from django import forms
from .models import Proveedor, Rubro


class ProveedorForm(forms.ModelForm):
    rubro_lookup = forms.ModelChoiceField(
        queryset=Rubro.objects.filter(activo=True).order_by('nombre'),
        required=False,
        label='Rubro (catálogo)',
        empty_label='-- Seleccione un rubro --',
        widget=forms.Select(attrs={'class': 'form-select w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'})
    )

    class Meta:
        model = Proveedor
        fields = [
            'nombre', 'cuit', 'email', 'telefono',
            'telefono_e164', 'whatsapp', 'api_stock_url',
            'direccion', 'rubro_fk',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'placeholder': 'Nombre del proveedor',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            }),
            'cuit': forms.TextInput(attrs={
                'placeholder': '20-12345678-9',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'correo@ejemplo.com',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            }),
            'telefono': forms.TextInput(attrs={
                'placeholder': 'Ej: 0381-4123456',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            }),
            'telefono_e164': forms.TextInput(attrs={
                'placeholder': '+5493816123456',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            }),
            'whatsapp': forms.TextInput(attrs={
                'placeholder': '+5493816123456 (opcional, si difiere del teléfono)',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            }),
            'api_stock_url': forms.URLInput(attrs={
                'placeholder': 'https://api.proveedor.com/stock',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            }),
            'direccion': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Dirección completa',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            }),
            'rubro_fk': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Campos opcionales
        self.fields['cuit'].required = False
        self.fields['telefono'].required = False
        self.fields['telefono_e164'].required = False
        self.fields['whatsapp'].required = False
        self.fields['api_stock_url'].required = False
        self.fields['direccion'].required = False
        # Pre-seleccionar rubro desde instancia existente
        if self.instance and self.instance.pk:
            if self.instance.rubro_fk:
                self.fields['rubro_lookup'].initial = self.instance.rubro_fk
            elif self.instance.rubro:
                try:
                    self.fields['rubro_lookup'].initial = Rubro.objects.get(
                        nombre__iexact=self.instance.rubro
                    )
                except Rubro.DoesNotExist:
                    pass

    def clean(self):
        cleaned = super().clean()
        rl = cleaned.get('rubro_lookup')
        if rl:
            cleaned['rubro_fk'] = rl
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Sincronizar campo de texto rubro desde FK
        if instance.rubro_fk:
            instance.rubro = instance.rubro_fk.nombre
        else:
            instance.rubro = ''
        if commit:
            instance.save()
        return instance


class RubroForm(forms.ModelForm):
    class Meta:
        model = Rubro
        fields = ['nombre', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nombre del rubro'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Descripción opcional'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
