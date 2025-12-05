# Archivo de configuración central para textos, estados, emails, valores de referencia, etc.

# Mensajes
MESSAGES = {
    'user_login_error': 'Usuario o contraseña incorrectos.',
    'user_registered': 'El usuario {nombre} {apellido} fue registrado correctamente.',
    'user_modified': 'El usuario {nombre} {apellido} fue modificado correctamente.',
    'user_deactivated': 'El usuario {nombre} {apellido} fue dado de baja.',
    'user_reactivated': 'El usuario {nombre} {apellido} fue reactivado.',
}

# Estados
USER_STATES = ['Activo', 'Inactivo']

# Emails
DEFAULT_EMAIL = 'info@imprenta.com.ar'

# Valores de referencia
DEFAULT_PAGE_SIZE = 20

# Otros textos
LABELS = {
    'edit_user': 'Editar Usuario',
    'delete_user': 'Eliminar Usuario',
    'dashboard': 'Panel de Control',
}

# Puedes agregar más claves según lo que encuentres hardcodeado en views, models, templates, scripts, etc.
