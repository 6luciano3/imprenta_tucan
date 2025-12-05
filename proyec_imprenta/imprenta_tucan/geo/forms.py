from django import forms
from .models import Ciudad


class CiudadForm(forms.ModelForm):
    class Meta:
        model = Ciudad
        fields = ["nombre", "provincia", "activo"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Nombre de la ciudad",
                }
            ),
            "provincia": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Provincia (opcional)",
                }
            ),
            "activo": forms.CheckboxInput(
                attrs={"class": "h-4 w-4 text-blue-600 border-gray-300 rounded"}
            ),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get("nombre", "").strip()
        if len(nombre) < 2:
            raise forms.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return nombre.title()
