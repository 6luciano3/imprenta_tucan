from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from roles.models import Rol


class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El correo electrónico es obligatorio')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('estado', 'Activo')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class Notificacion(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    mensaje = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

class Usuario(AbstractUser):
    username = None  # Eliminamos el campo por defecto
    email = models.EmailField(unique=True, verbose_name="Correo Electrónico")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    telefono = models.CharField(max_length=15, blank=True, verbose_name="Teléfono")
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, verbose_name="Rol")
    estado = models.CharField(
        max_length=10,
        choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')],
        default='Activo',
        verbose_name="Estado"
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre', 'apellido', 'telefono']

    objects = UsuarioManager()

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ['-id']

    def __str__(self):
        return f"{self.nombre} {self.apellido} <{self.email}>"

    @property
    def codigo(self):
        return f"USR-{self.id:05d}"
