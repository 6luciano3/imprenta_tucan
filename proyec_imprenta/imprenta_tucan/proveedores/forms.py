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
                'inputmode': 'tel',
                'pattern': r'[0-9\s\+\-\(\)\.]+',
                'title': 'Solo dígitos y los caracteres: + - ( ) espacio',
                'oninput': "this.value = this.value.replace(/[^0-9\\s\\+\\-\\(\\)\\.]/g, '')",
            }),
            'telefono_e164': forms.TextInput(attrs={
                'placeholder': '+5493816123456',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'inputmode': 'tel',
                'oninput': "this.value = this.value.replace(/[^0-9\\+]/g, '').replace(/(?!^)\\+/g, '')",
            }),
            'whatsapp': forms.TextInput(attrs={
                'placeholder': '+5493816123456 (opcional, si difiere del teléfono)',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'inputmode': 'tel',
                'oninput': "this.value = this.value.replace(/[^0-9\\+]/g, '').replace(/(?!^)\\+/g, '')",
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

    def clean_nombre(self):
        valor = self.cleaned_data.get('nombre', '').strip()
        if len(valor) < 2:
            raise forms.ValidationError('El nombre debe tener al menos 2 caracteres.')
        return valor

    def clean_telefono(self):
        import re
        valor = self.cleaned_data.get('telefono', '').strip()
        if not valor:
            return valor
        if not re.match(r'^[0-9\s\+\-\(\)\.]+$', valor):
            raise forms.ValidationError(
                'El teléfono solo puede contener dígitos y los caracteres: + - ( ) espacio'
            )
        digitos = re.sub(r'\D', '', valor)
        if len(digitos) < 6:
            raise forms.ValidationError('El teléfono debe tener al menos 6 dígitos.')
        return valor

    def clean_cuit(self):
        valor = self.cleaned_data.get('cuit', '').strip()
        if not valor:
            return None  # NULL en DB para evitar conflicto de unique con vacío
        from .models import validar_cuit
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validar_cuit(valor)
        except DjangoValidationError as e:
            raise forms.ValidationError(e.message)
        return valor

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
