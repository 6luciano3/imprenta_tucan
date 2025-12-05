from django import forms
from .models import Presupuesto


from clientes.models import Cliente


class PresupuestoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].queryset = Cliente.objects.all()
        self.fields['cliente'].label_from_instance = lambda obj: f"{obj.apellido}, {obj.nombre}"

    class Meta:
        model = Presupuesto
        fields = [
            'cliente',
            'razon_social',
            'validez',
            'total',
            'estado',
            'observaciones',
        ]
        widgets = {
            'cliente': forms.Select(attrs={
                'class': 'form-control',
            }),
            'razon_social': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Razón social vinculada al presupuesto',
            }),
            'validez': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'total': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Total'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-control',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
            }),
        }
        labels = {
            'numero': 'N° Presupuesto',
            'cliente': 'Cliente',
            'razon_social': 'Razón Social',
            'validez': 'Validez hasta',
            'total': 'Total',
            'estado': 'Estado',
            'observaciones': 'Observaciones',
        }
        help_texts = {
            'numero': 'Identificador único del presupuesto.',
            'razon_social': 'Razón social vinculada a este presupuesto. Puede diferir de la del cliente.',
            'validez': 'Fecha límite de validez del presupuesto.',
            'total': 'Importe total del presupuesto.',
            'estado': 'Estado actual del presupuesto.',
        }
