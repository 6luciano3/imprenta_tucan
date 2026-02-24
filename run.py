#!/usr/bin/env python

import os
import sys
import subprocess

def main():
    # Cargar variables de entorno desde .env si existe
    # (Eliminado uso de dotenv para evitar errores si no está instalado)
    print("=" * 50)
    print("    INICIANDO SERVIDOR IMPRENTA TUCAN")
    print("=" * 50)
    
    # Ruta del proyecto y entorno Python desde variables de entorno o valores por defecto
    project_path = os.environ.get('PROJECT_PATH', os.path.join(os.path.dirname(__file__), 'proyec_imprenta', 'imprenta_tucan'))
    python_env = os.environ.get('PYTHON_ENV', os.path.join(os.path.dirname(__file__), 'imprenta_tuc', 'Scripts', 'python.exe'))
    
    # Cambiar al directorio del proyecto
    os.chdir(project_path)
    
    print(f"📁 Directorio: {os.getcwd()}")
    
    # Ejecutar migraciones automáticamente
    print("🔄 Aplicando migraciones...")
    try:
        print("  📋 Migraciones generales...")
        subprocess.run([python_env, "manage.py", "makemigrations"], check=False)
        
        print("  💾 Aplicando migraciones...")
        subprocess.run([python_env, "manage.py", "migrate"], check=False)
        print("✅ Migraciones aplicadas")
    except Exception as e:
        print(f"⚠️ Advertencia en migraciones: {e}")
    
    print("🚀 Iniciando servidor Django...")
    print("🌐 Servidor disponible en: http://127.0.0.1:8000/")
    print("⏹️ Presiona Ctrl+C para detener el servidor")
    print("-" * 50)
    
    try:
        # Ejecutar el servidor Django
        subprocess.run([python_env, "manage.py", "runserver"], check=True)
    except KeyboardInterrupt:
        print("\n✅ Servidor detenido por el usuario")
    except Exception as e:
        print(f"❌ Error al iniciar el servidor: {e}")
        input("Presiona Enter para salir...")

if __name__ == '__main__':
    main()
