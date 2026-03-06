"""
Signals de tiempo real para la app insumos.

Cuando el stock de un insumo cambia y cae por debajo del mínimo sugerido,
se crea una Notificacion para todos los usuarios staff automáticamente,
sin esperar al ciclo diario de Celery.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Cache temporal: guarda el stock anterior antes de guardar
_stock_previo: dict[int, int] = {}


@receiver(pre_save, sender='insumos.Insumo')
def _capturar_stock_previo(sender, instance, **kwargs):
    """Guarda el stock actual antes de la actualización para detectar el cambio."""
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list('stock', flat=True).first()
            _stock_previo[instance.pk] = int(old or 0)
        except Exception:
            pass


@receiver(post_save, sender='insumos.Insumo')
def _alerta_stock_bajo(sender, instance, created, **kwargs):
    """
    Dispara una Notificacion a todos los staff cuando:
      - El stock cae por debajo del mínimo sugerido (cruce de umbral, no solo si está bajo).
      - El stock llega a 0 (alerta crítica inmediata).
    Solo notifica si el stock realmente bajó en este guardado (evita spam).
    """
    try:
        stock_actual = int(instance.stock or 0)
        stock_previo = _stock_previo.pop(instance.pk, stock_actual)
        stock_minimo = int(instance.stock_minimo_sugerido or 0)

        # Solo actuar si el stock bajó en este guardado
        if stock_actual >= stock_previo:
            return

        # Alerta crítica: llegó a 0
        if stock_actual == 0 and stock_previo > 0:
            _crear_notificaciones_staff(
                f'⚠️ STOCK AGOTADO: {instance.nombre} [{instance.codigo}] — '
                f'stock en 0. Compra inmediata requerida.'
            )
            return

        # Alerta de mínimo: cruzó el umbral (estaba arriba, ahora está abajo)
        if stock_minimo > 0 and stock_previo >= stock_minimo and stock_actual < stock_minimo:
            faltante = stock_minimo - stock_actual
            _crear_notificaciones_staff(
                f'🔔 Stock bajo mínimo: {instance.nombre} [{instance.codigo}] — '
                f'stock={stock_actual}, mínimo={stock_minimo}. '
                f'Reponer al menos {faltante} unidades.'
            )

    except Exception as exc:
        logger.exception('Error en signal _alerta_stock_bajo para insumo %s: %s', getattr(instance, 'pk', '?'), exc)


def _crear_notificaciones_staff(mensaje: str) -> None:
    """Crea una Notificacion por cada usuario staff activo."""
    try:
        from usuarios.models import Usuario, Notificacion
        staff = Usuario.objects.filter(is_staff=True, estado='Activo').values_list('id', flat=True)
        Notificacion.objects.bulk_create(
            [Notificacion(usuario_id=uid, mensaje=mensaje) for uid in staff],
            ignore_conflicts=True,
        )
        logger.info('Notificación stock enviada a %d usuarios staff: %s', len(staff), mensaje[:80])
    except Exception as exc:
        logger.exception('Error creando notificaciones staff: %s', exc)
