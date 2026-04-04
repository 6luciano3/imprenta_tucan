import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def alertar_ordenes_vencidas():
    """
    Revisa diariamente las Órdenes de Compra que superaron su fecha_entrega
    sin haber sido recibidas y notifica a todos los usuarios staff.

    Condiciones para alertar:
    - fecha_entrega < hoy
    - No tiene remito asociado (sin recepción)
    - Estado no es Cancelada ni Recibida
    """
    from .models import OrdenCompra
    from usuarios.models import Usuario, Notificacion

    hoy = timezone.now().date()
    estados_excluidos = ['Cancelada', 'Recibida']

    ordenes_vencidas = (
        OrdenCompra.objects
        .select_related('proveedor', 'estado')
        .filter(fecha_entrega__lt=hoy)
        .exclude(estado__nombre__in=estados_excluidos)
        .filter(remitos__isnull=True)
        .distinct()
    )

    if not ordenes_vencidas.exists():
        return "Sin órdenes vencidas."

    staff_ids = list(
        Usuario.objects.filter(is_staff=True, estado='Activo').values_list('id', flat=True)
    )
    if not staff_ids:
        return "Sin usuarios staff activos para notificar."

    notificaciones = []
    for orden in ordenes_vencidas:
        dias_retraso = (hoy - orden.fecha_entrega).days
        mensaje = (
            f"⚠️ OC-{orden.pk:04d} VENCIDA: {orden.proveedor.nombre} debía entregar "
            f"el {orden.fecha_entrega.strftime('%d/%m/%Y')} "
            f"({dias_retraso} día{'s' if dias_retraso != 1 else ''} de retraso). "
            f"Estado: {orden.estado.nombre}."
        )
        for uid in staff_ids:
            notificaciones.append(Notificacion(usuario_id=uid, mensaje=mensaje))

    Notificacion.objects.bulk_create(notificaciones, ignore_conflicts=True)
    logger.info("alertar_ordenes_vencidas: %d órdenes vencidas notificadas.", ordenes_vencidas.count())
    return f"{ordenes_vencidas.count()} órdenes vencidas notificadas."
