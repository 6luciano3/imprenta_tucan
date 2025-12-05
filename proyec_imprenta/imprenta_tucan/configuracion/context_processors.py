from typing import Dict


def module_visibility(request) -> Dict[str, bool]:
    """
    Context processor que expone banderas de visibilidad por módulo, basadas en
    los permisos activos del rol del usuario autenticado. Para administración,
    permite ver Roles/Permisos si el usuario es staff o superuser.
    """
    flags: Dict[str, bool] = {
        'show_usuarios': False,
        'show_clientes': False,
        'show_productos': False,
        'show_roles': False,
        'show_permisos': False,
        'show_proveedores': False,
        'show_insumos': False,
        'show_pedidos': False,
        'show_reportes': False,
        'show_presupuestos': False,
        'show_auditoria': False,
        'show_configuracion': False,
    }

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return flags

    modules = set()
    rol = getattr(user, 'rol', None)
    try:
        if rol:
            modules = set(rol.permisos.filter(estado='Activo').values_list('modulo', flat=True))
    except Exception:
        # Si algo falla (p.ej. tabla no migrada aún), dejamos flags por defecto
        return flags

    flags.update({
        'show_usuarios': 'Usuarios' in modules or bool(user.is_staff or user.is_superuser),
        'show_clientes': 'Clientes' in modules or bool(user.is_staff or user.is_superuser),
        'show_productos': 'Productos' in modules or bool(user.is_staff or user.is_superuser),
        'show_proveedores': 'Proveedores' in modules or bool(user.is_staff or user.is_superuser),
        'show_insumos': 'Insumos' in modules or bool(user.is_staff or user.is_superuser),
        'show_pedidos': 'Pedidos' in modules or bool(user.is_staff or user.is_superuser),
        'show_reportes': 'Reportes' in modules or bool(user.is_staff or user.is_superuser),
        'show_presupuestos': 'Presupuestos' in modules or bool(user.is_staff or user.is_superuser),
        'show_auditoria': 'Auditoria' in modules or bool(user.is_staff or user.is_superuser),
        'show_configuracion': 'Configuracion' in modules or bool(user.is_staff or user.is_superuser),
    })

    # Roles/Permisos visibles solo si hay permisos explícitos para esos módulos
    # o si el usuario es staff/superuser (administración del sistema)
    flags['show_roles'] = ('Roles' in modules) or bool(user.is_staff or user.is_superuser)
    flags['show_permisos'] = ('Permisos' in modules) or bool(user.is_staff or user.is_superuser)

    # ----- Acciones por módulo (InsuMOS) para UX en botones -----
    # Construir mapa modulo -> set(acciones) desde permisos activos del rol
    acciones_por_mod: Dict[str, set] = {}
    try:
        if rol:
            for p in rol.permisos.filter(estado='Activo').only('modulo', 'acciones'):
                accs = set(p.acciones or [])
                if p.modulo not in acciones_por_mod:
                    acciones_por_mod[p.modulo] = set()
                acciones_por_mod[p.modulo].update(accs)
    except Exception:
        pass

    def has_any(mod: str, opts):
        return bool(acciones_por_mod.get(mod, set()) & set(opts))

    # Sinónimos básicos alineados con el backend
    flags.update({
        'can_insumos_ver': has_any('Insumos', ['Ver', 'Listar', 'Detalle']) or bool(user.is_staff or user.is_superuser),
        'can_insumos_crear': has_any('Insumos', ['Crear', 'Alta']) or bool(user.is_staff or user.is_superuser),
        'can_insumos_editar': has_any('Insumos', ['Editar', 'Actualizar']) or bool(user.is_staff or user.is_superuser),
        'can_insumos_eliminar': has_any('Insumos', ['Eliminar', 'Borrar', 'Quitar', 'Baja', 'Desactivar']) or bool(user.is_staff or user.is_superuser),
        'can_insumos_activar': has_any('Insumos', ['Activar', 'Reactivar']) or bool(user.is_staff or user.is_superuser),
        # Productos
        'can_productos_ver': has_any('Productos', ['Ver', 'Listar', 'Detalle']) or bool(user.is_staff or user.is_superuser),
        'can_productos_crear': has_any('Productos', ['Crear', 'Alta']) or bool(user.is_staff or user.is_superuser),
        'can_productos_editar': has_any('Productos', ['Editar', 'Actualizar']) or bool(user.is_staff or user.is_superuser),
        'can_productos_eliminar': has_any('Productos', ['Eliminar', 'Borrar', 'Quitar', 'Baja', 'Desactivar']) or bool(user.is_staff or user.is_superuser),
        'can_productos_activar': has_any('Productos', ['Activar', 'Reactivar']) or bool(user.is_staff or user.is_superuser),
    })

    return flags
