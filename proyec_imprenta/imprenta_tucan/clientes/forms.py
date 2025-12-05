from django import forms
from django.core.exceptions import ValidationError
import re
from .models import Cliente
from configuracion.services import get_param
from geo.models import Ciudad


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellido', 'razon_social', 'email', 'telefono', 'celular',
                  'direccion', 'ciudad', 'provincia', 'pais', 'estado']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Ingrese el nombre',
                'maxlength': '50'
            }),
            'apellido': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Ingrese el apellido',
                'maxlength': '50'
            }),
            'razon_social': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Empresa o razón social'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'ejemplo@correo.com'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': '+54 381 1234567'
            }),
            'celular': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': '+54 9 381 1234567'
            }),
            'direccion': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Calle, número, piso, depto'
            }),
            # El widget definitivo para ciudad se define dinámicamente en __init__
            'provincia': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Tucumán'
            }),
            'pais': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Argentina'
            }),
            'estado': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if not nombre:
            raise ValidationError("El nombre es obligatorio.")

        # Solo letras y espacios
        if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', nombre):
            raise ValidationError("El nombre solo puede contener letras y espacios.")

        # Longitud mínima
        if len(nombre.strip()) < 2:
            raise ValidationError("El nombre debe tener al menos 2 caracteres.")

        # No números negativos implícitos
        if any(char.isdigit() for char in nombre):
            raise ValidationError("El nombre no puede contener números.")

        return nombre.strip().title()

    def clean_apellido(self):
        apellido = self.cleaned_data.get('apellido')
        if not apellido:
            raise ValidationError("El apellido es obligatorio.")

        # Solo letras y espacios
        if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', apellido):
            raise ValidationError("El apellido solo puede contener letras y espacios.")

        # Longitud mínima
        if len(apellido.strip()) < 2:
            raise ValidationError("El apellido debe tener al menos 2 caracteres.")

        # No números
        if any(char.isdigit() for char in apellido):
            raise ValidationError("El apellido no puede contener números.")

        return apellido.strip().title()

    def clean_razon_social(self):
        razon_social = self.cleaned_data.get('razon_social')
        if razon_social and len(razon_social.strip()) < 3:
            raise ValidationError("La razón social debe tener al menos 3 caracteres.")
        return razon_social.strip() if razon_social else razon_social

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("El email es obligatorio.")

        # Validación adicional de formato
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError("Ingrese un email válido.")

        # Verificar que no exista otro cliente con el mismo email
        if Cliente.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ya existe un cliente con este email.")

        return email.lower()

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')
        if not telefono:
            raise ValidationError("El teléfono es obligatorio.")

        # Remover espacios y caracteres especiales para validación
        telefono_clean = re.sub(r'[^\d+]', '', telefono)

        # Debe contener solo números, espacios, guiones y +
        if not re.match(r'^[\d\s\-\+\(\)]+$', telefono):
            raise ValidationError(
                "El teléfono solo puede contener números, espacios, guiones, paréntesis y el símbolo +.")

        # Longitud mínima de dígitos
        digits_only = re.sub(r'[^\d]', '', telefono)
        if len(digits_only) < 8:
            raise ValidationError("El teléfono debe tener al menos 8 dígitos.")

        # No puede ser solo ceros o números negativos
        if digits_only == '0' * len(digits_only):
            raise ValidationError("El teléfono no puede ser solo ceros.")

        # Validar formato argentino básico
        if telefono.startswith('+54') and len(digits_only) < 10:
            raise ValidationError("Para números argentinos (+54), debe tener al menos 10 dígitos.")

        return telefono.strip()

    def clean_celular(self):
        celular = self.cleaned_data.get('celular')
        if celular:
            # Similar validación al teléfono
            digits_only = re.sub(r'[^\d]', '', celular)
            if len(digits_only) < 8:
                raise ValidationError("El celular debe tener al menos 8 dígitos.")
        return celular.strip() if celular else celular

    def clean_direccion(self):
        direccion = self.cleaned_data.get('direccion')
        if direccion:
            # Longitud mínima si se proporciona
            if len(direccion.strip()) < 5:
                raise ValidationError("La dirección debe tener al menos 5 caracteres.")

            # No puede ser solo números
            if direccion.strip().isdigit():
                raise ValidationError("La dirección no puede ser solo números.")

            return direccion.strip()
        return direccion

    def clean_ciudad(self):
        ciudad = self.cleaned_data.get('ciudad')
        if ciudad:
            # Si hay lista parametrizada, validamos pertenencia
            opciones = get_param('CLIENTES_CIUDADES', None)
            if isinstance(opciones, list) and opciones:
                if ciudad not in opciones:
                    raise ValidationError("Seleccione una ciudad válida.")
            else:
                if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', ciudad):
                    raise ValidationError("La ciudad solo puede contener letras y espacios.")
                if len(ciudad.strip()) < 2:
                    raise ValidationError("La ciudad debe tener al menos 2 caracteres.")
        return ciudad.strip().title() if isinstance(ciudad, str) and ciudad else ciudad

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Parametrizar 'ciudad': si existe CLIENTES_CIUDADES (JSON list), usar Select; si no, TextInput.
        # Reemplazar el input por Select con nombres si hay ciudades activas creadas via CRUD
        if Ciudad.objects.exists():
            choices = list(Ciudad.objects.filter(activo=True).order_by('nombre').values_list('nombre', 'nombre'))
            if choices:
                self.fields['ciudad'].widget = forms.Select(
                    choices=choices,
                    attrs={
                        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
                    }
                )
                default_ciudad = get_param('CLIENTES_CIUDAD_DEFAULT', None)
                if default_ciudad and not self.initial.get('ciudad') and not (self.instance and self.instance.pk):
                    self.initial['ciudad'] = default_ciudad
        else:
            # Fallback a campo de texto si no existen ciudades todavía
            self.fields['ciudad'].widget = forms.TextInput(
                attrs={
                    'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                    'placeholder': 'San Miguel de Tucumán'
                }
            )

    def clean_provincia(self):
        provincia = self.cleaned_data.get('provincia')
        if provincia:
            if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', provincia):
                raise ValidationError("La provincia solo puede contener letras y espacios.")
            if len(provincia.strip()) < 2:
                raise ValidationError("La provincia debe tener al menos 2 caracteres.")
        return provincia.strip().title() if provincia else provincia

    def clean_pais(self):
        pais = self.cleaned_data.get('pais')
        if pais:
            if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', pais):
                raise ValidationError("El país solo puede contener letras y espacios.")
            if len(pais.strip()) < 2:
                raise ValidationError("El país debe tener al menos 2 caracteres.")
        return pais.strip().title() if pais else pais

    def clean(self):
        cleaned_data = super().clean()
        nombre = cleaned_data.get('nombre')
        apellido = cleaned_data.get('apellido')

        # Validación cruzada: nombre y apellido no pueden ser iguales
        if nombre and apellido and nombre.lower() == apellido.lower():
            raise ValidationError("El nombre y apellido no pueden ser iguales.")

        return cleaned_data
