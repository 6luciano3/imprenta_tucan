import os
import sys


def main():
    """Ejecutar el servidor Django directamente"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')

    print("🚀 Iniciando servidor Imprenta Tucan...")
    print("📍 Servidor disponible en: http://127.0.0.1:8000/")
    print("⏹️  Presiona Ctrl+C para detener")
    print("-" * 40)

    try:
        from django.core.management import execute_from_command_line
        execute_from_command_line(['manage.py', 'runserver'])
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. ¿Está instalado y "
            "disponible en tu PYTHONPATH? ¿Olvidaste activar "
            "el entorno virtual?"
        ) from exc
    except KeyboardInterrupt:
        print("\n✅ Servidor detenido correctamente")


if __name__ == '__main__':
    main()
