from permisos.decorators import requiere_permiso
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from .models import Cliente
from .forms import ClienteForm
from configuracion.permissions import require_perm

ESTADOS_BLOQUEANTES = ["Pendiente", "En Proceso", "Completado"]


# Alta de cliente
@require_perm("Clientes", "Crear")
@login_required
@requiere_permiso("Clientes", "Crear")
def alta_cliente(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"El cliente {cliente.nombre} {cliente.apellido} ha sido creado exitosamente.")
            return redirect("lista_clientes")
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = ClienteForm()
    return render(request, "clientes/alta.html", {"form": form})


# Lista de clientes unificada con busqueda y ordenamiento
@require_perm("Clientes", "Listar")
@login_required
@requiere_permiso("Clientes")
def lista_clientes(request):
    query = request.GET.get("q", "") or request.GET.get("criterio", "")
    order_by = request.GET.get("order_by", "apellido")
    direction = request.GET.get("direction", "asc")

    valid_order_fields = ["id", "nombre", "apellido", "email", "telefono", "direccion"]
    if order_by not in valid_order_fields:
        order_by = "apellido"

    clientes_qs = Cliente.objects.all()
    if query:
        if order_by == "id" and query.isdigit():
            clientes_qs = clientes_qs.filter(id=int(query))
        else:
            clientes_qs = clientes_qs.filter(
                Q(nombre__icontains=query) |
                Q(apellido__icontains=query) |
                Q(razon_social__icontains=query) |
                Q(email__icontains=query) |
                Q(telefono__icontains=query) |
                Q(direccion__icontains=query)
            )

    order_field = f"-{order_by}" if direction == "desc" else order_by
    clientes_qs = clientes_qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(clientes_qs, get_page_size())
    page = request.GET.get("page")
    clientes = paginator.get_page(page)

    return render(request, "clientes/lista_clientes.html", {
        "clientes": clientes,
        "query": query,
        "order_by": order_by,
        "direction": direction,
    })


# Detalle de cliente
@require_perm("Clientes", "Ver")
@login_required
@requiere_permiso("Clientes")
def detalle_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    return render(request, "clientes/detalle_cliente.html", {"cliente": cliente})


# Editar cliente
@require_perm("Clientes", "Editar")
@login_required
@requiere_permiso("Clientes", "Editar")
def editar_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente_actualizado = form.save()
            messages.success(
                request, f"El cliente {cliente_actualizado.nombre} {cliente_actualizado.apellido} ha sido actualizado exitosamente.")
            return redirect("lista_clientes")
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = ClienteForm(instance=cliente)
    return render(request, "clientes/editar_cliente.html", {"form": form, "cliente": cliente})


# Eliminar cliente
@require_perm("Clientes", "Eliminar")
@login_required
@requiere_permiso("Clientes", "Eliminar")
def eliminar_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    if not cliente.puede_eliminarse():
        messages.error(
            request,
            f"No se puede eliminar a {cliente.nombre} {cliente.apellido} porque tiene pedidos asociados."
        )
        return redirect("lista_clientes")
    if request.method == "POST":
        nombre_cliente = f"{cliente.nombre} {cliente.apellido}"
        cliente.delete()
        messages.success(request, f"El cliente {nombre_cliente} ha sido eliminado exitosamente.")
        return redirect("lista_clientes")
    return redirect("lista_clientes")


# Activar/desactivar cliente (toggle)
@require_perm("Clientes", "Activar")
@login_required
@requiere_permiso("Clientes")
def activar_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    if request.method == "POST":
        cliente.estado = "Inactivo" if cliente.estado == "Activo" else "Activo"
        cliente.save()
        estado_txt = "activado" if cliente.estado == "Activo" else "desactivado"
        messages.success(request, f"El cliente {cliente.nombre} {cliente.apellido} ha sido {estado_txt}.")
    return redirect("lista_clientes")


# Buscar cliente
@require_perm("Clientes", "Listar")
@login_required
@requiere_permiso("Clientes")
def buscar_cliente(request):
    params = request.GET.urlencode()
    url = "/clientes/lista/"
    if params:
        url = f"{url}?{params}"
    return redirect(url)


# Confirmar eliminacion de cliente
@require_perm("Clientes", "Eliminar")
@login_required
@requiere_permiso("Clientes")
def confirmar_eliminacion_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    if not cliente.puede_eliminarse():
        pedidos = cliente.pedidos_bloqueantes()
        messages.error(
            request,
            f"No se puede eliminar a {cliente.nombre} {cliente.apellido} porque tiene {pedidos.count()} pedido(s) activo(s)."
        )
        return redirect("lista_clientes")
    if request.method == "POST":
        if not cliente.puede_eliminarse():
            messages.error(request, "El cliente tiene pedidos activos y no puede eliminarse.")
            return redirect("lista_clientes")
        cliente.delete()
        messages.success(request, "El cliente ha sido eliminado exitosamente.")
        return redirect("lista_clientes")
    return render(request, "clientes/confirmar_eliminacion.html", {"cliente": cliente})


@require_perm('Clientes', 'Ver')
@login_required
def clientes_inactivos(request):
    """Vista para mostrar clientes inactivos y enviar notificaciones de reactivación."""
    from django.utils import timezone
    from datetime import timedelta
    from pedidos.models import Pedido
    from configuracion.models import Parametro

    dias_inactividad = 90
    try:
        dias_param = Parametro.get('CLIENTE_DIAS_INACTIVIDAD')
        if dias_param:
            dias_inactividad = int(dias_param)
    except Exception:
        pass

    fecha_limite = timezone.now().date() - timedelta(days=dias_inactividad)

    clientes_activos = Cliente.objects.filter(estado='Activo').values_list('id', flat=True)
    
    clientes_con_pedidos_recientes = Pedido.objects.filter(
        cliente__in=clientes_activos,
        fecha_pedido__gt=fecha_limite
    ).values_list('cliente_id', flat=True).distinct()


    # Paginación igual que en lista_clientes
    clientes_inactivos_qs = Cliente.objects.filter(
        estado='Activo'
    ).exclude(
        id__in=clientes_con_pedidos_recientes
    ).select_related(None).prefetch_related('pedido_set')

    # Anotar días sin pedido
    for cliente in clientes_inactivos_qs:
        ultimo_pedido = cliente.pedido_set.order_by('-fecha_pedido').first()
        cliente.dias_sin_pedido = 0
        if ultimo_pedido:
            cliente.dias_sin_pedido = (timezone.now().date() - ultimo_pedido.fecha_pedido).days

    # Paginación
    from configuracion.services import get_page_size
    paginator = Paginator(list(clientes_inactivos_qs), get_page_size())
    page = request.GET.get("page")
    clientes_inactivos = paginator.get_page(page)

    mensaje_resultado = None
    if request.method == 'POST' and 'enviar_notificaciones' in request.POST:
        from automatizacion.tasks import tarea_clientes_inactivos
        try:
            resultado = tarea_clientes_inactivos()
            mensaje_resultado = resultado
        except Exception as e:
            mensaje_resultado = f"Error: {str(e)}"

    from automatizacion.models import RespuestaCliente, EmailTracking
    from django.db import models
    
    respuestas_recientes = RespuestaCliente.objects.select_related('cliente').order_by('-recibido_en')[:20]
    
    tracking_stats = EmailTracking.objects.filter(tipo='cliente_inactivo').values(
        'estado'
    ).annotate(total=models.Count('id'))

    context = {
        'clientes_inactivos': clientes_inactivos,
        'dias_inactividad': dias_inactividad,
        'mensaje_resultado': mensaje_resultado,
        'respuestas_recientes': respuestas_recientes,
        'tracking_stats': tracking_stats,
    }
    return render(request, 'clientes/clientes_inactivos.html', context)
