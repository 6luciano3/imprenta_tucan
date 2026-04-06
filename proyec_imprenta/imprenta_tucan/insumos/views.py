from django.contrib import messages
from permisos.decorators import requiere_permiso

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db.models import Q

from .forms import InsumoForm, AltaInsumoForm, BuscarInsumoForm, ModificarInsumoForm, ConsumoRealInsumoForm
from configuracion.permissions import require_perm
from .models import Insumo, ProyeccionInsumo, ConsumoRealInsumo
from usuarios.models import Usuario, Notificacion
from roles.models import Rol
from proveedores.models import Proveedor
from pedidos.models import OrdenCompra

# --- FUNCION PARA ENVIAR REPORTE DE PROYECCIONES ---
@login_required
@requiere_permiso("Insumos", "Crear")
def registrar_consumo_real(request):
    """Registrar consumo real de insumo."""
    if request.method == 'POST':
        form = ConsumoRealInsumoForm(request.POST)
        if form.is_valid():
            consumo = form.save(commit=False)
            consumo.usuario = request.user
            consumo.save()
            messages.success(request, 'Consumo real registrado correctamente.')
            return redirect('lista_insumos')
        else:
            messages.error(request, 'Datos inválidos. Corrige los errores.')
    else:
        form = ConsumoRealInsumoForm()
    return render(request, 'insumos/registrar_consumo_real.html', {'form': form})


# --- FUNCION PARA ENVIAR REPORTE DE PROYECCIONES ---
def enviar_reporte_proyecciones(mensaje):
    from core.notifications.engine import enviar_notificacion
    roles = ['Administrador', 'Personal de Administración']
    destinatarios = Usuario.objects.filter(rol__nombreRol__in=roles, estado='Activo')
    for usuario in destinatarios:
        if usuario.email:
            enviar_notificacion(
                destinatario=usuario.email,
                mensaje=mensaje,
                canal='email',
                asunto='Reporte de Proyecciones de Insumos',
            )
        Notificacion.objects.create(usuario=usuario, mensaje=mensaje)


@require_perm('Insumos', 'Listar')
@login_required
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
@login_required
def crear_insumo(request):
    return redirect('alta_insumo')


@require_perm('Insumos', 'Crear', redirect_to='lista_insumos')
@login_required
def alta_insumo(request):
    if request.method == "POST":
        form = AltaInsumoForm(request.POST)
        if form.is_valid():
            try:
                insumo = form.save(commit=False)
                insumo.save()
                messages.success(request, "El insumo ha sido registrado correctamente.")
                return redirect('lista_insumos')
            except Exception as e:
                messages.error(request, f"Error al registrar el insumo: {str(e)}")
    else:
        form = AltaInsumoForm()

    return render(request, 'insumos/alta_insumo.html', {"form": form})


@require_perm('Insumos', 'Editar', redirect_to='lista_insumos')
@login_required
def editar_insumo(request, pk: int):
    insumo = get_object_or_404(Insumo, idInsumo=pk)
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
@login_required
def detalle_insumo(request, pk: int):
    from compras.models import HistorialPrecioInsumo
    insumo = get_object_or_404(Insumo, idInsumo=pk)
    historial_reciente = (
        HistorialPrecioInsumo.objects
        .filter(insumo=insumo)
        .select_related('usuario', 'remito')
        .order_by('-fecha')[:5]
    )
    return render(request, 'insumos/detalle_insumo.html', {
        'insumo': insumo,
        'historial_reciente': historial_reciente,
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
    return get_object_or_404(Insumo, idInsumo=idInsumo)


def modificarDatos(insumo: Insumo, form: ModificarInsumoForm) -> Insumo:
    """Aplica cambios del formulario y sincroniza campos legacy.

    - Sincroniza stock con cantidad.
    - Sincroniza precio con precio_unitario.
    """
    insumo_mod = form.save(commit=False)
    insumo_mod.save()
    return insumo_mod


def bajaInsumo(idInsumo: int) -> Insumo:
    """Recupera el insumo a dar de baja o devuelve 404."""
    return get_object_or_404(Insumo, idInsumo=idInsumo)


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


@login_required
def buscar_insumo(request):
    """Vista legacy: redirige a la lista unificada preservando el querystring."""
    params = request.GET.urlencode()
    url = "/insumos/"
    if params:
        url = f"{url}?{params}"
    return redirect(url)


@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@requiere_permiso("Insumos")
def lista_proyecciones(request):
    # T-06: la generacion de proyecciones fue movida a insumos.tasks.generar_proyecciones_insumos
    # que Celery ejecuta diariamente. Esta vista es solo lectura.
    from configuracion.services import get_page_size
    
    # Obtener el último período con proyecciones
    ultimo_periodo = ProyeccionInsumo.objects.order_by('-periodo').values_list('periodo', flat=True).first()
    periodo_actual = ultimo_periodo or timezone.now().strftime('%Y-%m')
    proyecciones_qs = ProyeccionInsumo.objects.filter(periodo=periodo_actual)

    # Obtener prediccion para cada proyeccion (solo lectura, sin escribir en BD)
    from insumos.models import predecir_demanda_media_movil
    proyecciones = []
    for p in proyecciones_qs.order_by('insumo__nombre'):
        prediccion = predecir_demanda_media_movil(p.insumo, p.periodo, meses=3)
        p.prediccion_media_movil = prediccion
        proyecciones.append(p)

    paginator = Paginator(proyecciones, get_page_size())
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    sin_proyecciones = not proyecciones_qs.exists()
    return render(request, 'insumos/lista_proyecciones.html', {
        'proyecciones': page_obj,
        'sin_proyecciones': sin_proyecciones,
    })


@login_required
@requiere_permiso("Insumos")
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
            # Generar Remito automatico en App Compras en vez de modificar stock directo
            from django.db import transaction
            try:
                with transaction.atomic():
                    from compras.models import Remito, DetalleRemito, EstadoCompra
                    from django.utils import timezone
                    estado_rec, _ = EstadoCompra.objects.get_or_create(nombre='Recibida')
                    remito = Remito.objects.create(
                        proveedor=proyeccion.proveedor_validado or insumo.proveedor,
                        numero=f'PROY-{proyeccion.pk:06d}',
                        fecha=timezone.now().date(),
                        observaciones=f'Remito automatico por validacion de ProyeccionInsumo #{proyeccion.pk}',
                    )
                    DetalleRemito.objects.create(remito=remito, insumo=insumo, cantidad=int(cantidad))
                    insumo.stock += int(cantidad)
                    insumo.save(update_fields=["stock"])
            except Exception as e_r:
                import logging
                logging.getLogger(__name__).warning(f'Error creando Remito para proyeccion #{proyeccion.pk}: {e_r}')
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


@login_required
@requiere_permiso("Insumos")
def rechazar_proyeccion(request, pk):
    proyeccion = get_object_or_404(ProyeccionInsumo, pk=pk)
    proyeccion.estado = 'rechazada'
    proyeccion.save(update_fields=['estado'])
    messages.success(request, 'Proyección rechazada correctamente.')
    return redirect('lista_proyecciones')


@login_required
@requiere_permiso("Insumos")
def eliminar_proyeccion(request, pk):
    proyeccion = get_object_or_404(ProyeccionInsumo, pk=pk)
    proyeccion.delete()
    messages.success(request, 'Proyección eliminada correctamente.')
    return redirect('lista_proyecciones')
