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
    python_exec = os.environ.get('PYTHON_EXEC', 'python')
    try:
        result = subprocess.run(
            [python_exec, manage_py, 'test'],
            capture_output=True,
            text=True,
            cwd=project_dir
        )
        output = result.stdout + '\n' + result.stderr
    except Exception as e:
        output = f"Error ejecutando pruebas: {e}"
    return render(request, 'dashboard/tests_result.html', {'output': output})
