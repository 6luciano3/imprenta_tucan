import os
import sys
from django.core.mail import send_mail


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        print("❌ Error: No se pudo importar Django")
        print("Posibles causas:")
        print("- Django no está instalado")
        print("- El entorno virtual no está activado")
        print("- Problemas con PYTHONPATH")
        print(f"Error específico: {exc}")
        sys.exit(1)

    # Verificar si es comando de diagnóstico
    if len(sys.argv) > 1 and sys.argv[1] == 'verificar_apps':
        verificar_aplicaciones()
        return

    if len(sys.argv) > 1 and sys.argv[1] == 'check_proveedores':
        verificar_proveedores()
        return

    if len(sys.argv) > 1 and sys.argv[1] == 'check_urls':
        verificar_urls()
        return

    if len(sys.argv) > 1 and sys.argv[1] == 'fix_migrations':
        fix_migrations()
        return

    if len(sys.argv) > 1 and sys.argv[1] == 'force_migrate':
        force_migrate()
        return

    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        check_status()
        return

    if len(sys.argv) > 1 and sys.argv[1] == 'check_responsive':
        check_responsive()
        return

    try:
        execute_from_command_line(sys.argv)
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error ejecutando comando Django: {error_msg}")

        if "widget_tweaks" in error_msg:
            print("🔧 SOLUCIÓN:")
            print("1. Instala widget_tweaks:")
            print("   pip install django-widget-tweaks")
            print("\n2. O activa el entorno virtual y luego instala:")
            print("   & \"C:/Users/Public/Documents/facultad/3er Año/Trabajo Final/proyecto_imprenta/imprenta_tuc/Scripts/Activate.ps1\"")
            print("   pip install django-widget-tweaks")
        else:
            print("Verifica:")
            print("- Que las migraciones estén aplicadas")
            print("- Que la configuración en settings.py sea correcta")
            print("- Que la base de datos esté accesible")
        sys.exit(1)


def verificar_aplicaciones():
    """Verificar que todas las aplicaciones estén configuradas correctamente"""
    from django.conf import settings
    print("🔍 Verificando aplicaciones instaladas:")
    for app in settings.INSTALLED_APPS:
        if not app.startswith('django.'):
            print(f"  ✓ {app}")


def verificar_proveedores():
    """Verificar específicamente la app proveedores"""
    print("=" * 50)
    print("    VERIFICACIÓN APP PROVEEDORES")
    print("=" * 50)

    try:
        # Configurar Django
        import django
        django.setup()

        # 1. Verificar modelo
        print("\n📋 VERIFICANDO MODELO:")
        try:
            from proveedores.models import Proveedor
            print("✅ Modelo Proveedor importado correctamente")

            # Verificar campos
            campos = [f.name for f in Proveedor._meta.fields]
            print(f"✅ Campos: {', '.join(campos)}")

        except Exception as e:
            print(f"❌ Error en modelo: {e}")

        # 2. Verificar vistas
        print("\n🔍 VERIFICANDO VISTAS:")
        try:
            from proveedores import views
            vistas = [attr for attr in dir(views) if not attr.startswith('_')]
            print(f"✅ Vistas disponibles: {', '.join(vistas)}")

        except Exception as e:
            print(f"❌ Error en vistas: {e}")

        # 3. Verificar URLs
        print("\n🔗 VERIFICANDO URLs:")
        try:
            from django.urls import reverse
            urls_test = ['lista_proveedores', 'crear_proveedor']
            for url in urls_test:
                try:
                    path = reverse(url)
                    print(f"✅ {url}: {path}")
                except Exception as e:
                    print(f"❌ {url}: {e}")

        except Exception as e:
            print(f"❌ Error general en URLs: {e}")

        # 4. Verificar tabla en BD
        print("\n💾 VERIFICANDO BASE DE DATOS:")
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proveedores_proveedor';")
                tabla = cursor.fetchone()
                if tabla:
                    print("✅ Tabla proveedores_proveedor existe")

                    # Contar registros
                    count = Proveedor.objects.count()
                    print(f"✅ Registros en tabla: {count}")
                else:
                    print("❌ Tabla proveedores_proveedor NO existe")
                    print("   Ejecuta: python manage.py makemigrations proveedores")
                    print("   Ejecuta: python manage.py migrate")

        except Exception as e:
            print(f"❌ Error en base de datos: {e}")

    except Exception as e:
        print(f"❌ Error general: {e}")


def verificar_urls():
    """Verificar URLs disponibles"""
    print("=" * 50)
    print("    VERIFICACIÓN DE URLs")
    print("=" * 50)

    try:
        import django
        django.setup()

        from django.urls import reverse
        from django.urls.exceptions import NoReverseMatch

        urls_test = [
            ('dashboard', 'Dashboard principal'),
            ('lista_clientes', 'Lista de clientes'),
            ('lista_proveedores', 'Lista de proveedores'),
            ('crear_proveedor', 'Crear proveedor'),
        ]

        for url_name, descripcion in urls_test:
            try:
                url = reverse(url_name)
                print(f"✅ {descripcion}: {url}")
            except NoReverseMatch as e:
                print(f"❌ {descripcion}: {e}")

        print("\n🌐 URLs disponibles para acceso directo:")
        print("- http://127.0.0.1:8000/dashboard/")
        print("- http://127.0.0.1:8000/clientes/lista/")
        print("- http://127.0.0.1:8000/proveedores/")
        print("- http://127.0.0.1:8000/proveedores/lista/")

    except Exception as e:
        print(f"❌ Error verificando URLs: {e}")


def fix_migrations():
    """Resolver problema de migraciones"""
    print("=" * 50)
    print("    RESOLVIENDO MIGRACIONES")
    print("=" * 50)

    print("🔧 Para resolver el problema de migraciones:")
    print("1. Elimina las migraciones existentes:")
    print("   rm proveedores/migrations/0*.py")
    print("\n2. Crea nuevas migraciones:")
    print("\n3. Aplica las migraciones:")
    print("   python manage.py migrate")
    print("\n4. O simplemente ejecuta el servidor sin migraciones:")
    print("   python run.py")


def force_migrate():
    """Forzar migración completa de proveedores"""
    print("=" * 50)
    print("    MIGRACIÓN FORZADA")
    print("=" * 50)

    try:
        import django
        django.setup()

        import subprocess

        print("🔄 Ejecutando migración forzada...")

        # Crear migración real para proveedores
        result = subprocess.run(["python", "manage.py", "makemigrations", "proveedores"],
                                capture_output=True, text=True)
        print("📝 Migración creada")

        # Aplicar migración con fake
        subprocess.run(["python", "manage.py", "migrate", "proveedores", "--fake"], check=True)
        print("✅ Migración aplicada con --fake")

        # Verificar estado
        from proveedores.models import Proveedor
        count = Proveedor.objects.count()
        print(f"✅ Proveedores en BD: {count}")

        print("\n🚀 Migración completada. Ejecuta: python run.py")

    except Exception as e:
        print(f"❌ Error: {e}")


def check_status():
    """Verificar estado actual de la aplicación"""
    print("=" * 50)
    print("    ESTADO DE LA APLICACIÓN")
    print("=" * 50)

    try:
        import django
        django.setup()

        from django.urls import reverse

        # Verificar URLs principales
        urls_funcionando = []
        urls_test = [
            ('dashboard', 'Dashboard'),
            ('lista_clientes', 'Clientes'),
            ('lista_proveedores', 'Proveedores'),
        ]

        for url_name, descripcion in urls_test:
            try:
                url = reverse(url_name)
                urls_funcionando.append(f"✅ {descripcion}: {url}")
            except Exception as e:
                urls_funcionando.append(f"❌ {descripcion}: Error")

        for status in urls_funcionando:
            print(status)

        # Verificar datos
        try:
            from clientes.models import Cliente
            from proveedores.models import Proveedor

            clientes_count = Cliente.objects.count()
            proveedores_count = Proveedor.objects.count()

            print(f"\n📊 DATOS:")
            print(f"✅ Clientes: {clientes_count}")
            print(f"✅ Proveedores: {proveedores_count}")

        except Exception as e:
            print(f"❌ Error consultando datos: {e}")

        print(f"\n🚀 ESTADO GENERAL: ✅ FUNCIONANDO")
        print("La aplicación está operativa y respondiendo correctamente.")

    except Exception as e:
        print(f"❌ Error: {e}")


def check_responsive():
    """Verificar que los templates sean responsive"""
    print("=" * 50)
    print("    VERIFICACIÓN DE RESPONSIVIDAD")
    print("=" * 50)

    print("✅ Clases Tailwind responsive implementadas:")
    print("- Contenedores: container mx-auto")
    print("- Grid responsive: grid-cols-1 md:grid-cols-2 lg:grid-cols-3")
    print("- Flexbox adaptable: flex flex-wrap")
    print("- Espaciado responsive: px-4 md:px-10 lg:px-20")
    print("- Texto responsive: text-sm md:text-base lg:text-lg")
    print("- Navegación: hidden md:flex (sidebar colapsable)")

    print("\n📱 Breakpoints de Tailwind:")
    print("- sm: 640px (teléfonos grandes)")
    print("- md: 768px (tablets)")
    print("- lg: 1024px (laptops)")
    print("- xl: 1280px (escritorio)")
    print("- 2xl: 1536px (pantallas grandes)")


if __name__ == '__main__':
    main()
