from django import forms
from .models import Usuario


class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Ingrese nueva contraseña',
            'class': 'form-input rounded-lg h-14 p-[15px] text-base bg-slate-50 dark:bg-slate-800/50 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50'
        }),
        label="Contraseña"
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirme la contraseña',
            'class': 'form-input rounded-lg h-14 p-[15px] text-base bg-slate-50 dark:bg-slate-800/50 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50'
        }),
        label="Confirmar Contraseña"
    )

    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'email', 'telefono', 'rol']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre', 'class': 'form-input'}),
            'apellido': forms.TextInput(attrs={'placeholder': 'Apellido', 'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Correo electrónico', 'class': 'form-input'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Teléfono', 'class': 'form-input'}),
            'rol': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Aplicar clase visual si hay errores
        for field_name, field in self.fields.items():
            if self.errors.get(field_name):
                base_class = field.widget.attrs.get('class', '')
                if 'border-red-600' not in base_class:
                    field.widget.attrs['class'] = f"{base_class} border-red-600 focus:ring-red-500"

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Usuario.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario con este correo electrónico.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")

        # Si es nuevo usuario, la contraseña es obligatoria
        if self.instance.pk is None and not password:
            self.add_error('password', "Este campo es obligatorio.")

        if password or confirm:
            if password != confirm:
                self.add_error('confirm_password', "Las contraseñas no coinciden.")

    def save(self, commit=True):
        usuario = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            usuario.set_password(password)
        if commit:
            usuario.save()
        return usuario
