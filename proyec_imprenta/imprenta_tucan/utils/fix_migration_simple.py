import os
import subprocess


def fix_simple():
    print("🔧 Arreglando migraciones...")

    # Eliminar migraciones problemáticas
    migrations_dir = "proveedores/migrations"
    if os.path.exists(migrations_dir):
        for file in os.listdir(migrations_dir):
            if file.startswith('00') and file.endswith('.py'):
                try:
                    os.remove(os.path.join(migrations_dir, file))
                    print(f"Eliminado: {file}")
                except:
                    pass

    print("Ejecutando comandos...")
    subprocess.run(["python", "manage.py", "makemigrations", "proveedores", "--empty"], check=True)
    subprocess.run(["python", "manage.py", "migrate", "--fake"], check=True)

    print("✅ Listo! Ahora ejecuta: python run.py")


if __name__ == '__main__':
    fix_simple()
