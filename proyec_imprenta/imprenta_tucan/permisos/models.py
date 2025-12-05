from django.db import models


class Permiso(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField()
    modulo = models.CharField(max_length=100)
    # Usar TextField para máxima compatibilidad (evita dependencia de JSON1 en SQLite durante tests)
    # Guardar como JSON serializado (por ejemplo, "[\"Crear\", \"Leer\"]") si se requiere estructura.
    acciones = models.TextField(default='[]')  # Guarda JSON serializado (lista de strings)

    def save(self, *args, **kwargs):
        import json
        # Si acciones es lista, serializar a JSON
        if isinstance(self.acciones, (list, tuple)):
            self.acciones = json.dumps(list(self.acciones))
        # Si es string, intentar cargar y volver a serializar para asegurar formato
        elif isinstance(self.acciones, str):
            try:
                acciones_val = json.loads(self.acciones)
                if isinstance(acciones_val, (list, tuple)):
                    self.acciones = json.dumps(list(acciones_val))
                else:
                    self.acciones = json.dumps([])
            except Exception:
                self.acciones = json.dumps([])
        super().save(*args, **kwargs)
    estado = models.CharField(max_length=10, choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')], default='Activo')

    def __str__(self):
        return self.nombre
