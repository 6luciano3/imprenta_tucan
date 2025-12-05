# Test settings override to ease migrations in CI/tests
from .settings import *  # noqa

# Disable migrations for specific apps that cause issues with SQLite JSON1
MIGRATION_MODULES = {
    'permisos': None,
    'auditoria': None,
    'roles': None,
    'usuarios': None,
}

# Use in-memory SQLite for speed (keeps default if already configured)
DATABASES['default']['NAME'] = ':memory:'
