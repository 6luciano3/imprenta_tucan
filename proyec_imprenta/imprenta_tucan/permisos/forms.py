from django import forms
from django.core.exceptions import ValidationError
from .models import Permiso


class PermisoForm(forms.ModelForm):
    """Form de creación / modificación de Permiso.

    - Convierte el campo acciones texto (separado por comas) a lista para JSONField.
    - En edición, muestra las acciones existentes como texto separado por comas.
    - Valida unicidad del nombre excluyendo el propio registro cuando está en modo edición.
    """
    class Meta:
        model = Permiso
        fields = ['nombre', 'descripcion', 'modulo', 'acciones']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Ej: Gestionar Usuarios',
                'autofocus': 'autofocus'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 3,
                'placeholder': 'Descripción breve del permiso'
            }),
            'modulo': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Ej: Usuarios'
            }),
            'acciones': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 2,
                'placeholder': 'Ej: Crear, Listar, Editar, Eliminar'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostrar acciones como texto separado por comas si es una lista (edición)
        import json
        if self.instance and self.instance.pk:
            acciones_val = self.instance.acciones
            if isinstance(acciones_val, str):
                try:
                    acciones_list = json.loads(acciones_val)
                    if isinstance(acciones_list, (list, tuple)):
                        self.initial['acciones'] = ', '.join(acciones_list)
                except Exception:
                    pass
            elif isinstance(acciones_val, (list, tuple)):
                self.initial['acciones'] = ', '.join(acciones_val)

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise ValidationError('Este campo es obligatorio.')
        qs = Permiso.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Ya existe un permiso con ese nombre.')
        return nombre

    def clean(self):
        cleaned = super().clean()
        # Normalizar campos simples, evitando llamar strip() sobre listas
        for f in ['descripcion', 'modulo']:
            val = cleaned.get(f)
            if isinstance(val, str):
                val = val.strip()
            if not val:
                self.add_error(f, 'Este campo es obligatorio.')
            else:
                cleaned[f] = val
        # 'acciones' se procesa en clean_acciones, aquí solo chequeo presencia para evitar doble validación.
        acciones_val = cleaned.get('acciones')
        if acciones_val in [None, '', []]:
            self.add_error('acciones', 'Este campo es obligatorio.')
        return cleaned

    def clean_acciones(self):
        import json
        data = self.cleaned_data.get('acciones')
        # Puede venir como lista (por JS) o como string (textarea)
        if isinstance(data, list):
            partes = [p.strip() for p in data if isinstance(p, str) and p.strip()]
        else:
            raw = (data or '').strip()
            if not raw:
                raise ValidationError('Este campo es obligatorio.')
            # Separar por coma o salto de línea
            partes = [p.strip() for p in raw.replace('\n', ',').split(',') if p.strip()]
        # Deduplicar preservando orden
        seen = set()
        dedup = []
        for p in partes:
            if p.lower() not in seen:
                seen.add(p.lower())
                dedup.append(p)
        if not dedup:
            raise ValidationError('Debe ingresar al menos una acción válida.')
        # Serializar como JSON para guardar en el modelo
        return json.dumps(dedup)
