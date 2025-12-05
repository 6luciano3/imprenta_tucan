from __future__ import annotations
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models, transaction
# --- Poblar unidades de medida automáticamente si la tabla está vacía ---
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def populate_unidades(sender, **kwargs):
    from .models import UnidadDeMedida
    if UnidadDeMedida.objects.count() == 0:
        unidades = [
            {"nombre": "Metro", "simbolo": "m", "descripcion": "Unidad de longitud", "activo": True},
            {"nombre": "Kilogramo", "simbolo": "kg", "descripcion": "Unidad de masa", "activo": True},
            {"nombre": "Litro", "simbolo": "L", "descripcion": "Unidad de volumen", "activo": True},
            {"nombre": "Unidad", "simbolo": "u", "descripcion": "Unidad básica", "activo": True},
            {"nombre": "Centímetro", "simbolo": "cm", "descripcion": "Submúltiplo de metro", "activo": True},
        ]
        for data in unidades:
            UnidadDeMedida.objects.get_or_create(
                nombre=data["nombre"],
                defaults={
                    "simbolo": data["simbolo"],
                    "descripcion": data["descripcion"],
                    "activo": data["activo"],
                }
            )


class RecetaProducto(models.Model):
    producto = models.ForeignKey('productos.Producto', on_delete=models.CASCADE, related_name='recetas')
    # La fórmula ahora está en Producto, no aquí
    insumos = models.ManyToManyField('insumos.Insumo', related_name='recetas')
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Receta de Producto'
        verbose_name_plural = 'Recetas de Productos'

    def __str__(self):
        return f"Receta de {self.producto}"


class GrupoParametro(models.Model):
    """Agrupa parámetros lógicamente (ej: PAGINACION, LISTAS, UI, INTEGRACIONES)."""

    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Grupo de Parámetros"
        verbose_name_plural = "Grupos de Parámetros"

    def __str__(self) -> str:  # pragma: no cover - simple
        return f"{self.codigo} - {self.nombre}" if self.nombre else self.codigo


class Parametro(models.Model):
    """Parámetro genérico clave/valor tipado.

    El valor se almacena como texto y se castea dinámicamente según `tipo`.
    """

    TIPO_CADENA = "str"
    TIPO_INT = "int"
    TIPO_FLOAT = "float"
    TIPO_BOOL = "bool"
    TIPO_JSON = "json"

    TIPOS = [
        (TIPO_CADENA, "Cadena"),
        (TIPO_INT, "Entero"),
        (TIPO_FLOAT, "Decimal"),
        (TIPO_BOOL, "Booleano"),
        (TIPO_JSON, "JSON"),
    ]

    codigo = models.CharField(max_length=100, unique=True, help_text="Clave única del parámetro")
    grupo = models.ForeignKey(GrupoParametro, on_delete=models.CASCADE, related_name="parametros")
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    tipo = models.CharField(max_length=10, choices=TIPOS, default=TIPO_CADENA)
    valor = models.TextField(help_text="Valor almacenado en formato texto")
    activo = models.BooleanField(default=True)
    editable = models.BooleanField(default=True, help_text="Si puede modificarse vía panel")
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Parámetro"
        verbose_name_plural = "Parámetros"
        ordering = ["codigo"]

    def __str__(self) -> str:  # pragma: no cover - simple
        return self.codigo

    CACHE_PREFIX = "parametro:"

    def cache_key(self) -> str:
        return f"{self.CACHE_PREFIX}{self.codigo}"

    def parse_value(self):
        raw = self.valor
        if self.tipo == self.TIPO_BOOL:
            return raw.lower() in {"1", "true", "t", "yes", "y", "on"}
        if self.tipo == self.TIPO_INT:
            try:
                return int(raw)
            except ValueError:
                return 0
        if self.tipo == self.TIPO_FLOAT:
            try:
                return float(raw)
            except ValueError:
                return 0.0
        if self.tipo == self.TIPO_JSON:
            import json

            try:
                return json.loads(raw)
            except Exception:  # pragma: no cover - robustez
                return None
        return raw

    def save(self, *args, **kwargs):  # noqa: D401 - extendido
        super().save(*args, **kwargs)
        # Invalida y repuebla caché inmediata para coherencia.
        cache.set(self.cache_key(), self.parse_value(), timeout=None)

    @classmethod
    def get(cls, codigo: str, default=None):
        key = f"{cls.CACHE_PREFIX}{codigo}"
        val = cache.get(key)
        if val is not None:
            return val
        try:
            obj = cls.objects.get(codigo=codigo, activo=True)
        except cls.DoesNotExist:
            return default
        parsed = obj.parse_value()
        cache.set(key, parsed, timeout=None)
        return parsed

    @classmethod
    def set(cls, codigo: str, valor, tipo: str | None = None, **meta):
        """Crea/actualiza un parámetro atómico, retornando su valor parseado."""
        with transaction.atomic():
            obj, _created = cls.objects.select_for_update().get_or_create(
                codigo=codigo,
                defaults={
                    "valor": str(valor) if tipo != cls.TIPO_JSON else _dump_json(valor),
                    "tipo": tipo or cls.TIPO_CADENA,
                    "grupo": meta.get("grupo") or GrupoParametro.objects.first(),
                    "nombre": meta.get("nombre", codigo),
                },
            )
            if not _created:
                if tipo and obj.tipo != tipo:
                    obj.tipo = tipo
                obj.valor = (
                    _dump_json(valor)
                    if (tipo or obj.tipo) == cls.TIPO_JSON
                    else str(valor)
                )
                if "grupo" in meta and meta["grupo"]:
                    obj.grupo = meta["grupo"]
                if "nombre" in meta:
                    obj.nombre = meta["nombre"]
                if "descripcion" in meta:
                    obj.descripcion = meta["descripcion"]
                obj.save()
            return obj.parse_value()


def _dump_json(value):  # pragma: no cover - util simple
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class FeatureFlag(models.Model):
    codigo = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"

    def __str__(self):  # pragma: no cover - simple
        return f"{self.codigo}={'ON' if self.activo else 'off'}"

    CACHE_PREFIX = "ff:"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.set(f"{self.CACHE_PREFIX}{self.codigo}", self.activo, timeout=None)

    @classmethod
    def is_active(cls, codigo: str, default=False):
        key = f"{cls.CACHE_PREFIX}{codigo}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        try:
            flag = cls.objects.get(codigo=codigo)
        except cls.DoesNotExist:
            return default
        cache.set(key, flag.activo, timeout=None)
        return flag.activo


class ListaConfig(models.Model):
    """Configura comportamiento de listados (paginación, orden, columnas)."""

    codigo = models.CharField(max_length=80, unique=True, help_text="Identificador del listado, ej: LISTA_PRODUCTOS")
    descripcion = models.CharField(max_length=200, blank=True)
    page_size = models.PositiveIntegerField(default=10)
    max_page_size = models.PositiveIntegerField(default=200)
    orden_default = models.CharField(max_length=120, blank=True,
                                     help_text="Campo(s) por defecto para orden, ej: '-creado'")
    columnas_visibles = models.TextField(blank=True, help_text="Lista CSV de columnas activas")
    activo = models.BooleanField(default=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de Lista"
        verbose_name_plural = "Configuraciones de Listas"

    def __str__(self):  # pragma: no cover - simple
        return self.codigo

    CACHE_PREFIX = "lista:"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.set(self.cache_key(), self.to_dict(), timeout=None)

    def cache_key(self):
        return f"{self.CACHE_PREFIX}{self.codigo}"

    def to_dict(self):
        return {
            "codigo": self.codigo,
            "page_size": self.page_size,
            "max_page_size": self.max_page_size,
            "orden_default": self.orden_default,
            "columnas": [c.strip() for c in self.columnas_visibles.split(",") if c.strip()],
        }

    @classmethod
    def get(cls, codigo: str, default=None):
        key = f"{cls.CACHE_PREFIX}{codigo}"
        data = cache.get(key)
        if data is not None:
            return data
        try:
            obj = cls.objects.get(codigo=codigo, activo=True)
        except cls.DoesNotExist:
            return default
        data = obj.to_dict()
        cache.set(key, data, timeout=None)

        return data


# --- Modelos para fórmulas configurables ---


class Formula(models.Model):
    insumo = models.ForeignKey('insumos.Insumo', on_delete=models.CASCADE, related_name='formulas')
    codigo = models.CharField(max_length=100, unique=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    expresion = models.TextField()
    variables_json = models.JSONField(default=list)
    version = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def variables(self):
        return self.variables_json or []


class FormulaHistorial(models.Model):
    formula = models.ForeignKey(Formula, on_delete=models.CASCADE, related_name='historial')
    version = models.PositiveIntegerField()
    expresion = models.TextField()
    usuario = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL)
    creado_en = models.DateTimeField(auto_now_add=True)


# Modelo independiente para UnidadDeMedida
class UnidadDeMedida(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    simbolo = models.CharField(max_length=10, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} ({self.simbolo})"
