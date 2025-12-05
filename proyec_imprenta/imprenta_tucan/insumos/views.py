from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db.models import Q

from .forms import InsumoForm, AltaInsumoForm, BuscarInsumoForm, ModificarInsumoForm
from configuracion.permissions import require_perm
from .models import Insumo, ProyeccionInsumo
from usuarios.models import Usuario, Notificacion
from roles.models import Rol
from django.core.mail import send_mail

# --- FUNCION PARA ENVIAR REPORTE DE PROYECCIONES ---
def enviar_reporte_proyecciones(mensaje):
    roles = ['Administrador', 'Personal de Administración']
    destinatarios = Usuario.objects.filter(rol__nombreRol__in=roles, estado='Activo')
    emails = destinatarios.values_list('email', flat=True)
    # Email
    send_mail(
        'Reporte de Proyecciones de Insumos',
        mensaje,
        'no-reply@tusistema.com',
        list(emails),
        fail_silently=False,
    )
    # Mensaje interno
    for usuario in destinatarios:
        Notificacion.objects.create(usuario=usuario, mensaje=mensaje)
from proveedores.models import Proveedor
from insumos.models import ProyeccionInsumo
from pedidos.models import OrdenCompra


@require_perm('Insumos', 'Listar')
def lista_insumos(request):
    """Lista de Insumos unificada: búsqueda (q), orden (order_by/direction) y paginación."""
    query = request.GET.get('q', '') or request.GET.get('criterio', '')
    order_by = request.GET.get('order_by', 'idInsumo')
    direction = request.GET.get('direction', 'desc')

    valid_order_fields = ['idInsumo', 'codigo', 'nombre', 'categoria', 'stock', 'precio', 'created_at']
    if order_by not in valid_order_fields:
        order_by = 'idInsumo'

    qs = Insumo.objects.all()

    if query:
        qs = qs.filter(
            Q(nombre__icontains=query) |
            Q(codigo__icontains=query) |
            Q(categoria__icontains=query) |
            Q(proveedor__nombre__icontains=query)
        )

    order_field = f'-{order_by}' if direction == 'desc' else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'insumos': page_obj,
        'query': query,
        'order_by': order_by,
        'direction': direction,
    }
    return render(request, 'insumos/lista_insumos.html', context)


@require_perm('Insumos', 'Crear', redirect_to='lista_insumos')
def crear_insumo(request):
    if request.method == 'POST':
        form = InsumoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Insumo creado correctamente.')
            return redirect('lista_insumos')
    else:
        form = InsumoForm()

    return render(request, 'insumos/crear_insumo.html', {
        'form': form,
        'return_url': 'lista_insumos',
    })


@require_perm('Insumos', 'Crear', redirect_to='lista_insumos')
def alta_insumo(request):
    if request.method == "POST":
        form = AltaInsumoForm(request.POST)
        if form.is_valid():
            try:
                insumo = form.save(commit=False)
                # Sincronizar con campos legacy para mantener listas actuales
                insumo.stock = insumo.cantidad
                insumo.precio = insumo.precio_unitario
                insumo.save()
                messages.success(request, "El insumo ha sido registrado correctamente.")
                return redirect('lista_insumos')
            except Exception as e:
                messages.error(request, f"Error al registrar el insumo: {str(e)}")
    else:
        form = AltaInsumoForm()

    return render(request, 'insumos/alta_insumo.html', {"form": form})


@require_perm('Insumos', 'Editar', redirect_to='lista_insumos')
def editar_insumo(request, pk: int):
    insumo = get_object_or_404(Insumo, pk=pk)
    if request.method == 'POST':
        form = InsumoForm(request.POST, instance=insumo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Insumo actualizado correctamente.')
            return redirect('lista_insumos')
    else:
        form = InsumoForm(instance=insumo)

    return render(request, 'insumos/editar_insumo.html', {
        'form': form,
        'return_url': 'lista_insumos',
    })


@require_perm('Insumos', 'Ver', redirect_to='lista_insumos')
def detalle_insumo(request, pk: int):
    insumo = get_object_or_404(Insumo, pk=pk)
    return render(request, 'insumos/detalle_insumo.html', {
        'insumo': insumo,
    })


def _filtro_industria_grafica_queryset():
    terms = ["papel", "tinta", "quím", "quim", "repuesto", "placa", "barniz"]
    q = Q()
    for t in terms:
        q |= Q(rubro__icontains=t)
    proveedores_ids = list(Proveedor.objects.filter(activo=True).filter(q).values_list('id', flat=True))
    return proveedores_ids


def modificarInsumo(idInsumo: int) -> Insumo:
    """Recupera el insumo a modificar o devuelve 404.

    Este nombre sigue el diagrama provisto.
    """
    return get_object_or_404(Insumo, pk=idInsumo)


def modificarDatos(insumo: Insumo, form: ModificarInsumoForm) -> Insumo:
    """Aplica cambios del formulario y sincroniza campos legacy.

    - Sincroniza stock con cantidad.
    - Sincroniza precio con precio_unitario.
    """
    insumo_mod = form.save(commit=False)
    insumo_mod.stock = insumo_mod.cantidad
    insumo_mod.precio = insumo_mod.precio_unitario
    insumo_mod.save()
    return insumo_mod


def bajaInsumo(idInsumo: int) -> Insumo:
    """Recupera el insumo a dar de baja o devuelve 404."""
    return get_object_or_404(Insumo, pk=idInsumo)


def cambiarEstado(insumo: Insumo, estado: str) -> None:
    """Cambia el estado lógico del insumo.

    El modelo usa un booleano `activo`; mapeamos:
    - "Activo" -> True
    - "Inactivo" -> False
    """
    if estado.lower() == "activo":
        insumo.activo = True
    else:
        insumo.activo = False
    insumo.save(update_fields=["activo", "updated_at"]) if hasattr(insumo, "updated_at") else insumo.save()


def confirmarBaja(insumo: Insumo) -> None:
    """Confirma la baja del insumo cambiando su estado a Inactivo."""
    cambiarEstado(insumo, "Inactivo")


def buscar_insumo(request):
    """Vista legacy: redirige a la lista unificada preservando el querystring."""
    params = request.GET.urlencode()
    url = "/insumos/"
    if params:
        url = f"{url}?{params}"
    return redirect(url)


def seleccionar_insumo(request, pk: int):
    criterio = request.GET.get('criterio', '').strip()
    if not criterio:
        messages.error(request, 'No se encontraron insumos que coincidan con el criterio.')
        return redirect('buscar_insumo')

    # Reaplicar el mismo filtro para validar la selección
    qs = Insumo.objects.filter(
        Q(nombre__icontains=criterio) |
        Q(codigo__icontains=criterio) |
        Q(categoria__icontains=criterio) |
        Q(proveedor__nombre__icontains=criterio)
    )
    proveedores_ids = _filtro_industria_grafica_queryset()
    if proveedores_ids:
        qs = qs.filter(proveedor_id__in=proveedores_ids)

    if not qs.filter(pk=pk).exists():
        messages.error(request, 'No se encontraron insumos que coincidan con el criterio.')
        return redirect('buscar_insumo')

    # Selección válida: mostrar detalle
    return redirect('detalle_insumo', pk=pk)


def _es_personal_administrativo(user) -> bool:
    """Permite acceso solo a personal administrativo (staff)."""
    return user.is_authenticated and user.is_staff


@require_perm('Insumos', 'Editar', redirect_to='lista_insumos')
def modificar_insumo(request, idInsumo: int):
    """Pantalla para modificar un insumo (Personal Administrativo).

    Flujo:
    - Selecciona insumo -> modificarInsumo(idInsumo)
    - Muestra formulario precargado
    - Valida y, si es correcto, modificarDatos(...)
    - Muestra mensajes de éxito o detalle de errores
    """
    insumo = modificarInsumo(idInsumo)

    if request.method == 'POST':
        form = ModificarInsumoForm(request.POST, instance=insumo)
        if form.is_valid():
            try:
                modificarDatos(insumo, form)
                messages.success(request, 'El insumo ha sido modificado correctamente.')
                return redirect('lista_insumos')
            except Exception as e:
                messages.error(request, f'Datos inválidos: {str(e)}')
        else:
            # Construir un mensaje detallado de errores del formulario
            errores = []
            for campo, lista in form.errors.items():
                for err in lista:
                    errores.append(f"{campo}: {err}")
            if errores:
                messages.error(request, 'Datos inválidos: ' + '; '.join(errores))
    else:
        form = ModificarInsumoForm(instance=insumo)

    return render(request, 'insumos/modificar_insumo.html', {
        'form': form,
        'insumo': insumo,
    })


@require_perm('Insumos', 'Desactivar', redirect_to='lista_insumos')
def baja_insumo(request, idInsumo: int):
    """Pantalla de confirmación de baja para un insumo (Personal Administrativo).

    Flujo:
    - Selecciona insumo -> bajaInsumo(idInsumo)
    - Muestra datos y pide confirmación
    - POST con "confirmar" -> confirmarBaja()
    - POST con "cancelar" o link -> mensaje de cancelación
    """
    insumo = bajaInsumo(idInsumo)

    if request.method == 'POST':
        if 'confirmar' in request.POST:
            confirmarBaja(insumo)
            messages.success(request, 'El insumo ha sido dado de baja correctamente.')
            return redirect('lista_insumos')
        else:
            messages.info(request, 'Operación cancelada.')
            return redirect('lista_insumos')

    return render(request, 'insumos/baja_insumo.html', {
        'insumo': insumo,
    })


@require_perm('Insumos', 'Activar', redirect_to='lista_insumos')
def activar_insumo(request, idInsumo: int):
    """Activar/desactivar insumo (toggle) como en proveedores y clientes."""
    insumo = get_object_or_404(Insumo, pk=idInsumo)

    if request.method == 'POST':
        insumo.activo = not insumo.activo
        insumo.save(update_fields=["activo", "updated_at"]) if hasattr(insumo, "updated_at") else insumo.save()
        estado_txt = 'activado' if insumo.activo else 'desactivado'
        messages.success(request, f'El insumo {insumo.codigo} - {insumo.nombre} ha sido {estado_txt}.')
        return redirect('lista_insumos')

    return redirect('lista_insumos')


@require_perm('Insumos', 'Eliminar', redirect_to='lista_insumos')
def eliminar_insumo(request, idInsumo: int):
    """Eliminar Insumo con confirmación (POST)."""
    insumo = get_object_or_404(Insumo, pk=idInsumo)

    if request.method == 'POST':
        nombre = f"{insumo.codigo} - {insumo.nombre}"
        insumo.delete()
        messages.success(request, f'El insumo {nombre} ha sido eliminado exitosamente.')
        return redirect('lista_insumos')

    # Si no es POST, redirigir sin acción
    return redirect('lista_insumos')


@login_required
def lista_proyecciones(request):
    from configuracion.services import get_page_size
    proyecciones_qs = ProyeccionInsumo.objects.filter(periodo=timezone.now().strftime('%Y-%m'))
    paginator = Paginator(proyecciones_qs, get_page_size())
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'insumos/lista_proyecciones.html', {'proyecciones': page_obj})


@login_required
def validar_proyeccion(request, pk):
    proyeccion = get_object_or_404(ProyeccionInsumo, pk=pk)
    if request.method == 'POST':
        cantidad = request.POST.get('cantidad_validada')
        proveedor_id = request.POST.get('proveedor_validado')
        estado = request.POST.get('estado')
        comentario = request.POST.get('comentario_admin')
        proyeccion.cantidad_validada = cantidad
        proyeccion.proveedor_validado_id = proveedor_id
        proyeccion.estado = estado
        proyeccion.comentario_admin = comentario
        proyeccion.administrador = request.user
        proyeccion.fecha_validacion = timezone.now()
        proyeccion.save()
        # Actualizar stock proyectado si se acepta o modifica
        if estado in ['aceptada', 'modificada'] and cantidad:
            insumo = proyeccion.insumo
            insumo.stock += int(cantidad)
            insumo.save(update_fields=["stock"])
            # Generar orden sugerida de compra
            OrdenCompra.objects.create(
                insumo=insumo,
                cantidad=cantidad,
                proveedor_id=proveedor_id,
                estado='sugerida',
                comentario=f"Generada por proyección automática. {comentario}"
            )
        messages.success(request, 'Proyección validada correctamente.')
        return redirect('lista_proyecciones')
    proveedores = Proveedor.objects.all()
    return render(request, 'insumos/validar_proyeccion.html', {'proyeccion': proyeccion, 'proveedores': proveedores})
