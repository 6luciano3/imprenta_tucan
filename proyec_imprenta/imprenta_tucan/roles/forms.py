from django import forms
from django.core.exceptions import ValidationError
from .models import Rol
from permisos.models import Permiso


class RolForm(forms.ModelForm):
    class Meta:
        model = Rol
        # Según requerimiento: nombre, descripción y permisos (checkboxes)
        fields = ['nombreRol', 'descripcion', 'permisos']
        widgets = {
            'nombreRol': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Ej: Nombre del Rol',
                'autofocus': 'autofocus'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 3,
                'placeholder': 'Ej: Descripción del rol'
            }),
            'permisos': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        show_all_permissions = kwargs.pop('show_all_permissions', False)
        super().__init__(*args, **kwargs)
        # Limitar permisos a módulos Pedidos e Insumos activos por defecto; permitir todos en edición si se indica
        if show_all_permissions:
            self.fields['permisos'].queryset = Permiso.objects.filter(estado='Activo').order_by('modulo', 'nombre')
        else:
            self.fields['permisos'].queryset = Permiso.objects.filter(
                modulo__in=['Pedidos', 'Insumos'], estado='Activo').order_by('modulo', 'nombre')

    def clean_nombreRol(self):
        nombre = (self.cleaned_data.get('nombreRol') or '').strip()
        if not nombre:
            raise ValidationError('Este campo es obligatorio.')
        qs = Rol.objects.filter(nombreRol__iexact=nombre)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Ya existe un rol con ese nombre.')
        return nombre

    def clean(self):
        cleaned = super().clean()
        # Validar descripción obligatoria
        desc = (cleaned.get('descripcion') or '').strip()
        if not desc:
            self.add_error('descripcion', 'Este campo es obligatorio.')
        # Debe seleccionar al menos un permiso
        permisos = cleaned.get('permisos')
        if not permisos or len(permisos) == 0:
            self.add_error('permisos', 'Debe seleccionar al menos un permiso.')
        return cleaned
