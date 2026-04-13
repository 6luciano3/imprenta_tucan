from django.shortcuts import render, redirect, get_object_or_404
from permisos.decorators import requiere_permiso

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Usuario
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import UsuarioForm

USER_STATES = ['Activo', 'Inactivo']
MESSAGES = {
    'user_login_error': 'Usuario o contraseña incorrectos.',
    'user_registered': 'El usuario {nombre} {apellido} fue registrado exitosamente.',
    'user_modified': 'El usuario {nombre} {apellido} fue modificado exitosamente.',
    'user_deactivated': 'El usuario {nombre} {apellido} fue desactivado.',
    'user_reactivated': 'El usuario {nombre} {apellido} fue reactivado.',
}

# Redirección inicial


def inicio(request):
    return redirect('login')

# Login


def iniciar_sesion(request):
    if request.method == 'POST':
        usuario = request.POST.get('username')
        clave = request.POST.get('password')
        user = authenticate(request, username=usuario, password=clave)
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, MESSAGES['user_login_error'])
    return render(request, 'usuarios/login.html')

# Logout


@login_required
@requiere_permiso("Usuarios")
def cerrar_sesion(request):
    logout(request)
    return redirect('login')

# Alta de usuario


@login_required
@requiere_permiso("Usuarios")
def alta_usuario(request):
    form = UsuarioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        nuevo_usuario = form.save()
        messages.success(request, MESSAGES['user_registered'].format(
            nombre=nuevo_usuario.nombre, apellido=nuevo_usuario.apellido))
        return redirect('lista_usuarios')
    return render(request, 'usuarios/alta_usuario.html', {'form': form})

# Modificación de usuario


@login_required
@requiere_permiso("Usuarios")
def modificar_usuario(request, idUsuario):
    usuario = get_object_or_404(Usuario, id=idUsuario)
    form = UsuarioForm(request.POST or None, instance=usuario)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, MESSAGES['user_modified'].format(nombre=usuario.nombre, apellido=usuario.apellido))
        return redirect('lista_usuarios')
    return render(request, 'usuarios/modificar_usuario.html', {'form': form, 'usuario': usuario})

# Detalle de usuario


@login_required
@requiere_permiso("Usuarios")
def detalle_usuario(request, idUsuario):
    usuario = get_object_or_404(Usuario, id=idUsuario)
    return render(request, 'usuarios/detalle_usuario.html', {'usuario': usuario})

# Baja lógica


@login_required
@requiere_permiso("Usuarios")
def baja_usuario(request, idUsuario):
    usuario = get_object_or_404(Usuario, id=idUsuario)
    usuario.estado = USER_STATES[1]  # 'Inactivo'
    usuario.save()
    messages.success(request, MESSAGES['user_deactivated'].format(nombre=usuario.nombre, apellido=usuario.apellido))
    return redirect('lista_usuarios')

# Reactivación


@login_required
@requiere_permiso("Usuarios")
def reactivar_usuario(request, idUsuario):
    usuario = get_object_or_404(Usuario, id=idUsuario)
    usuario.estado = USER_STATES[0]  # 'Activo'
    usuario.save()
    messages.success(request, MESSAGES['user_reactivated'].format(nombre=usuario.nombre, apellido=usuario.apellido))
    return redirect('lista_usuarios')

# Listado y búsqueda


@login_required
@requiere_permiso("Usuarios")
def lista_usuarios(request):
    # Unificar parámetros: 'q' principal, 'criterio' como alias
    query = request.GET.get('q', '') or request.GET.get('criterio', '')
    order_by = request.GET.get('order_by', 'id')
    direction = request.GET.get('direction', 'asc')

    valid_order_fields = ['id', 'nombre', 'apellido', 'email', 'telefono', 'rol__nombreRol', 'estado']
    if order_by not in valid_order_fields:
        order_by = 'id'

    qs = Usuario.objects.all()
    if query:
        qs = qs.filter(
            Q(nombre__icontains=query) |
            Q(apellido__icontains=query) |
            Q(email__icontains=query) |
            Q(telefono__icontains=query) |
            Q(rol__nombreRol__icontains=query)
        )

    order_field = f'-{order_by}' if direction == 'desc' else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page = request.GET.get('page')
    usuarios = paginator.get_page(page)

    return render(request, 'usuarios/lista_usuarios.html', {
        'usuarios': usuarios,
        'query': query,
        'order_by': order_by,
        'direction': direction,
    })

# Alias para búsqueda directa (público)


def buscar_usuario(request):
    return lista_usuarios(request)


@login_required
def dashboard(request):
    notificaciones = []
    if request.user.is_authenticated:
        from usuarios.models import Notificacion
        notificaciones = Notificacion.objects.filter(usuario=request.user, leida=False).order_by('-fecha')[:5]
    # ...otros datos del dashboard...
    puede_configurar_ofertas = False
    if request.user.is_authenticated:
        try:
            puede_configurar_ofertas = request.user.is_staff or request.user.groups.filter(name='Comercial').exists()
        except Exception:
            puede_configurar_ofertas = request.user.is_staff
    facturas_pendientes = 0
    try:
        from pedidos.models import Factura
        from django.db.models import Sum as _Sum
        _ids_pagadas = [
            f.pk for f in Factura.objects.prefetch_related('pagos').annotate(
                _pagado=_Sum('pagos__monto')
            ) if (f._pagado or 0) >= f.monto_total
        ]
        facturas_pendientes = Factura.objects.exclude(pk__in=_ids_pagadas).count()
    except Exception:
        pass

    context = {
        'notificaciones': notificaciones,
        'puede_configurar_ofertas': puede_configurar_ofertas,
        'facturas_pendientes': facturas_pendientes,
    }
    return render(request, 'usuarios/dashboard_paneles.html', context)
