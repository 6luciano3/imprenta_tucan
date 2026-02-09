from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from django.apps import apps
from .models import AuditEntry
from .middleware import get_current_request, get_current_user
import json


EXCLUDE_MODELS = {'AuditEntry'}  # evitar loguear la propia auditoría
# Evitar loguear apps/sistemas internos y el registrador de migraciones
EXCLUDE_APPS = {
    'admin', 'auth', 'contenttypes', 'sessions', 'messages', 'staticfiles',
    'migrations'
}


def serialize_value(val):
    """Convierte valores a tipos JSON serializables."""
    try:
        from datetime import datetime, date, time
        from decimal import Decimal
        import uuid
    except Exception:
        datetime = date = time = Decimal = uuid = None

    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if datetime and isinstance(val, (datetime, date, time)):
        # ISO 8601
        try:
            return val.isoformat()
        except Exception:
            return str(val)
    if Decimal and isinstance(val, Decimal):
        return float(val)
    if uuid and isinstance(val, uuid.UUID):
        return str(val)
    # Como fallback, representación de texto
    return str(val)


def get_field_value(instance, field):
    value = getattr(instance, field.name, None)
    if value is None:
        return None
    # Representar FK por su PK
    if field.many_to_one or field.one_to_one:
        try:
            return serialize_value(getattr(value, 'pk', None))
        except Exception:
            return None
    return serialize_value(value)


def build_diff(before, after):
    changes = {}
    for name in after.keys():
        if before.get(name) != after.get(name):
            changes[name] = {'before': before.get(name), 'after': after.get(name)}
    return changes


@receiver(pre_save)
def audit_pre_save(sender, instance, **kwargs):
    model_name = sender.__name__
    if model_name in EXCLUDE_MODELS or sender._meta.app_label in EXCLUDE_APPS:
        return
    # Evitar registrar cambios del propio registrador de migraciones
    # (e.g., django.db.migrations.recorder)
    if sender.__module__.startswith('django.db.migrations'):
        return
    if not instance.pk:
        # se manejará en post_save como create
        instance._audit_before = None
    else:
        # Capturar estado previo desde la base de datos para detectar cambios reales
        try:
            current = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            instance._audit_before = None
            return
        before = {}
        for f in sender._meta.get_fields():
            if getattr(f, 'editable', False) and hasattr(f, 'attname') and not f.many_to_many and not f.one_to_many:
                # Obtener valor del registro persistido (current)
                try:
                    value = getattr(current, f.name, None)
                except Exception:
                    value = None
                # Serializar valor
                if value is None:
                    before[f.name] = None
                else:
                    # Representar FK por PK si aplica
                    if f.many_to_one or f.one_to_one:
                        try:
                            before[f.name] = serialize_value(getattr(value, 'pk', None))
                        except Exception:
                            before[f.name] = None
                    else:
                        before[f.name] = serialize_value(value)
        instance._audit_before = before


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    model_name = sender.__name__
    if model_name in EXCLUDE_MODELS or sender._meta.app_label in EXCLUDE_APPS:
        return
    if sender.__module__.startswith('django.db.migrations'):
        return
    after = {}
    for f in sender._meta.get_fields():
        if getattr(f, 'editable', False) and hasattr(f, 'attname') and not f.many_to_many and not f.one_to_many:
            after[f.name] = get_field_value(instance, f)

    if created:
        changes = {k: {'before': None, 'after': v} for k, v in after.items() if v is not None}
        action = AuditEntry.ACTION_CREATE
        before = {}
    else:
        before = getattr(instance, '_audit_before', {}) or {}
        changes = build_diff(before, after)
        if not changes:
            return  # nada cambió
        action = AuditEntry.ACTION_UPDATE

    request = get_current_request()
    user = get_current_user()

    # Serializar a JSON válido si corresponde para compatibilidad con SQLite JSON1
    try:
        changes_json = json.dumps(changes, ensure_ascii=False) if changes else None
    except TypeError:
        # Fallback: convertir valores no serializables a str
        def _stringify(o):
            try:
                return json.dumps(o, ensure_ascii=False)
            except Exception:
                return str(o)
        changes_json = json.dumps({k: {sk: _stringify(sv) for sk, sv in v.items()}
                                  for k, v in (changes or {}).items()}, ensure_ascii=False) if changes else None

    # Agregar información específica para movimientos de stock de Insumo
    extra_json = None
    try:
        if model_name == 'Insumo' and 'stock' in changes:
            before_stock = changes['stock']['before'] if 'stock' in changes else before.get('stock')
            after_stock = changes['stock']['after'] if 'stock' in changes else after.get('stock')
            try:
                delta = (after_stock or 0) - (before_stock or 0)
            except Exception:
                delta = None

            # Inferir origen según el path
            path = getattr(request, 'path', '') if request else ''
            method = getattr(request, 'method', '') if request else ''
            if path.startswith('/pedidos/'):
                reason = 'pedido'
            elif path.startswith('/insumos/alta') or path.startswith('/insumos/editar'):
                reason = 'insumo-form'
            elif path.startswith('/automatizacion/') or '/compras/' in path:
                reason = 'automatizacion'
            else:
                reason = 'desconocido'

            extra_payload = {
                'category': 'stock-movement',
                'delta': delta,
                'before': before_stock,
                'after': after_stock,
                'source': {
                    'path': path,
                    'method': method,
                    'reason': reason,
                }
            }
            extra_json = json.dumps(extra_payload, ensure_ascii=False)
    except Exception:
        # no bloquear auditoría por error en extra
        extra_json = None

    AuditEntry.objects.create(
        user=user,
        ip_address=getattr(request, 'META', {}).get('REMOTE_ADDR') if request else None,
        path=getattr(request, 'path', '') if request else '',
        method=getattr(request, 'method', '') if request else '',
        app_label=sender._meta.app_label,
        model=model_name,
        object_id=str(instance.pk),
        object_repr=str(instance),
        action=action,
        changes=changes_json,
        extra=extra_json or json.dumps({'category': sender._meta.app_label}, ensure_ascii=False),
    )


@receiver(pre_delete)
def audit_pre_delete(sender, instance, **kwargs):
    model_name = sender.__name__
    if model_name in EXCLUDE_MODELS or sender._meta.app_label in EXCLUDE_APPS:
        return
    if sender.__module__.startswith('django.db.migrations'):
        return
    request = get_current_request()
    user = get_current_user()

    # estado previo para referencia
    before = {}
    for f in sender._meta.get_fields():
        if getattr(f, 'editable', False) and hasattr(f, 'attname') and not f.many_to_many and not f.one_to_many:
            before[f.name] = get_field_value(instance, f)

    try:
        changes_json = json.dumps({'before': before}, ensure_ascii=False) if before else None
    except TypeError:
        changes_json = json.dumps({'before': str(before)}, ensure_ascii=False) if before else None

    # Categoría por defecto basada en app
    default_extra = json.dumps({'category': sender._meta.app_label}, ensure_ascii=False)
    AuditEntry.objects.create(
        user=user,
        ip_address=getattr(request, 'META', {}).get('REMOTE_ADDR') if request else None,
        path=getattr(request, 'path', '') if request else '',
        method=getattr(request, 'method', '') if request else '',
        app_label=sender._meta.app_label,
        model=model_name,
        object_id=str(instance.pk),
        object_repr=str(instance),
        action=AuditEntry.ACTION_DELETE,
        changes=changes_json,
        extra=default_extra,
    )
