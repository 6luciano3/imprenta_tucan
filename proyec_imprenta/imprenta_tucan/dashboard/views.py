from django.shortcuts import render
from django.urls import reverse
from django.conf import settings
import subprocess
import os

def dashboard_tests(request):
    """
    Vista para mostrar resultados de pruebas unitarias.
    Ejecuta 'manage.py test' y muestra el resultado en la tarjeta.
    """
    project_dir = settings.BASE_DIR
    manage_py = os.path.join(project_dir, 'manage.py')
    # Forzar el uso del ejecutable de Python del entorno virtual
    venv_python = os.path.join(settings.BASE_DIR, '..', '..', 'imprenta_tuc', 'Scripts', 'python.exe')
    python_exec = os.path.abspath(venv_python)
    try:
        # Ejecuta un pequeño script antes de los tests para mostrar el entorno Python
        import tempfile
        import pathlib
        with tempfile.NamedTemporaryFile('w+', delete=False, suffix='.py', encoding='utf-8') as f:
            f.write('import sys\n')
            f.write('print("PYTHON_EXECUTABLE:", sys.executable)\n')
            f.write('print("PYTHON_PATH:", sys.path)\n')
            f.write('print("---INICIO TESTS---")\n')
            # Usar repr para asegurar que la ruta se escriba correctamente como string literal
            f.write('import runpy; runpy.run_path(' + repr(str(pathlib.Path(manage_py))) + ', run_name="__main__")\n')
            temp_script = f.name
        result = subprocess.run(
            [python_exec, temp_script, 'test'],
            capture_output=True,
            text=True,
            cwd=project_dir,
            encoding='utf-8',
            errors='replace'
        )
        stdout = result.stdout if result.stdout is not None else ''
        stderr = result.stderr if result.stderr is not None else ''
        output = stdout + '\n' + stderr
    except Exception as e:
        output = f"Error ejecutando pruebas: {e}"
    return render(request, 'dashboard/tests_result.html', {'output': output})
