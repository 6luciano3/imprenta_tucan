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
    import re
    import tempfile
    import pathlib
    from datetime import datetime
    try:
        with tempfile.NamedTemporaryFile('w+', delete=False, suffix='.py', encoding='utf-8') as f:
            f.write('import runpy; runpy.run_path(' + repr(str(pathlib.Path(manage_py))) + ', run_name="__main__")\n')
            temp_script = f.name
        result = subprocess.run(
            [python_exec, temp_script, 'test', 'dashboard', '--verbosity=2'],
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

    # Filtrar líneas técnicas (DEBUG, PYTHON_PATH, etc.)
    filtered_lines = []
    for line in output.splitlines():
        if any(s in line for s in ["DEBUG settings", "PYTHON_PATH", "PYTHON_EXECUTABLE", "BASE_DIR:", "STATICFILES_DIRS:", "STATIC_ROOT:", "MEDIA_ROOT:", "EMAIL_FILE_PATH:", "DEFAULT_FROM_EMAIL:", "AWS_REGION:", "TEMPLATES:", "DATABASES:", "manage.py", "runpy.run_path"]):
            continue
        filtered_lines.append(line)
    filtered_output = '\n'.join(filtered_lines)

    # Parsear resumen de tests
    total_tests = passed_tests = failed_tests = 0
    total_time = "-"
    all_passed = False
    percent_passed = 0

    # Buscar líneas tipo: "Ran 15 tests in 30.418s"
    for line in filtered_lines:
        m = re.search(r"Ran (\d+) test[s]? in ([\d\.]+)s", line)
        if m:
            total_tests = int(m.group(1))
            total_time = f"{float(m.group(2)):.2f}s"
    # Buscar líneas tipo: "FAILED (failures=4)" o "OK"
    for line in filtered_lines:
        if line.strip().startswith("OK"):
            passed_tests = total_tests
            failed_tests = 0
            all_passed = True
        elif line.strip().startswith("FAILED"):
            all_passed = False
            # Buscar fallos
            m = re.search(r"failures=(\d+)", line)
            if m:
                failed_tests = int(m.group(1))
                passed_tests = total_tests - failed_tests
    if total_tests > 0:
        percent_passed = int((passed_tests / total_tests) * 100)
    else:
        percent_passed = 0

    # Construir pasos del pipeline
    # Definir los pasos esperados y asociarles detalles del output
    pipeline_steps = [
        {'key': 'found', 'label': '', 'detail': '', 'status': 'pending'},
        {'key': 'system_check', 'label': '', 'detail': '', 'status': 'pending'},
        {'key': 'create_db', 'label': '', 'detail': '', 'status': 'pending'},
        {'key': 'run_tests', 'label': '', 'detail': '', 'status': 'pending'},
        {'key': 'destroy_db', 'label': '', 'detail': '', 'status': 'pending'},
    ]
    # Mapear líneas del output a pasos
    found_line = next((l for l in filtered_lines if l.strip().startswith('Found') and 'test' in l), None)
    syscheck_line = next((l for l in filtered_lines if 'System check identified' in l), None)
    create_db_line = next((l for l in filtered_lines if 'Creating test database' in l), None)
    run_lines = []
    destroy_db_line = next((l for l in filtered_lines if 'Destroying test database' in l), None)
    # Agrupar detalles de ejecución de tests
    in_run = False
    for l in filtered_lines:
        if 'Creating test database' in l:
            in_run = True
            continue
        if 'Destroying test database' in l:
            in_run = False
        if in_run:
            run_lines.append(l)

    # Asignar labels y detalles
    pipeline_steps[0]['label'] = found_line or 'Found X tests'
    pipeline_steps[0]['detail'] = found_line or ''
    pipeline_steps[0]['status'] = 'complete' if found_line else 'pending'

    pipeline_steps[1]['label'] = syscheck_line or 'System check'
    pipeline_steps[1]['detail'] = syscheck_line or ''
    pipeline_steps[1]['status'] = 'complete' if syscheck_line else 'pending'

    pipeline_steps[2]['label'] = create_db_line or 'Creating test database'
    pipeline_steps[2]['detail'] = create_db_line or ''
    pipeline_steps[2]['status'] = 'complete' if create_db_line else 'pending'

    # Paso de ejecución de tests
    run_summary = '\n'.join(run_lines).strip()
    pipeline_steps[3]['label'] = 'Running tests'
    pipeline_steps[3]['detail'] = run_summary or 'Sin detalles.'
    if failed_tests > 0:
        pipeline_steps[3]['status'] = 'error'
    elif passed_tests == total_tests and total_tests > 0:
        pipeline_steps[3]['status'] = 'complete'
    elif run_summary:
        pipeline_steps[3]['status'] = 'active'
    else:
        pipeline_steps[3]['status'] = 'pending'

    pipeline_steps[4]['label'] = destroy_db_line or 'Destroying test database'
    pipeline_steps[4]['detail'] = destroy_db_line or ''
    pipeline_steps[4]['status'] = 'complete' if destroy_db_line else 'pending'

    # --- PARSEAR TESTS INDIVIDUALES ---
    # Buscar bloques de tests individuales: "test_xxx (app.tests.TestClass) ... ok|FAIL"
    test_case_pattern = re.compile(r"^(test\w+.*?) \((.*?)\)\s+\.\.\.\s+(ok|FAIL|ERROR|SKIP)", re.MULTILINE)
    test_cases = []
    for m in test_case_pattern.finditer(filtered_output):
        name = m.group(1)
        cls = m.group(2)
        status = m.group(3)
        test_cases.append({
            'name': name,
            'class': cls,
            'status': status,
        })

    # Buscar detalles de fallos (si existen)
    # Django suele imprimir: "FAIL: test_xxx (app.tests.TestClass)" seguido de traceback
    fail_details = {}
    fail_block_pattern = re.compile(r"^(FAIL|ERROR): (test\w+.*?) \((.*?)\)\n(-+)(.*?)\n=+", re.DOTALL | re.MULTILINE)
    for m in fail_block_pattern.finditer(filtered_output + '\n====='):
        key = f"{m.group(2)}|{m.group(3)}"
        fail_details[key] = m.group(5).strip()

    # Enlazar detalles a test_cases
    for tc in test_cases:
        key = f"{tc['name']}|{tc['class']}"
        tc['detail'] = fail_details.get(key, '')

    # Contar por estado para barra proporcional
    count_passed = sum(1 for t in test_cases if t['status'] == 'ok')
    count_failed = sum(1 for t in test_cases if t['status'] in ('FAIL', 'ERROR'))
    count_skipped = sum(1 for t in test_cases if t['status'] == 'SKIP')
    count_total = len(test_cases)
    percent_passed = int((count_passed / count_total) * 100) if count_total else 0
    percent_failed = int((count_failed / count_total) * 100) if count_total else 0
    percent_skipped = 100 - percent_passed - percent_failed if count_total else 0

    # Agrupar tests por clase para el template nuevo
    clases_dict = {}
    for t in test_cases:
        # Extraer solo el nombre de la clase (sin módulo)
        class_full = t.get('class', '')
        class_name = class_full.split('.')[-2] if '.' in class_full else class_full
        if class_name not in clases_dict:
            clases_dict[class_name] = []
        # Simular duración y estado
        clases_dict[class_name].append({
            'nombre': t['name'],
            'estado': 'ok' if t['status'] == 'ok' else ('fail' if t['status'] in ('FAIL', 'ERROR') else 'error'),
            'duracion': '—',
            'detalle': t.get('detail', ''),
        })
    clases = [{'nombre': k, 'tests': v} for k, v in clases_dict.items()]
    resumen = {
        'total': count_total,
        'ok': count_passed,
        'fail': count_failed,
        'error': 0,  # Si tienes parsing de errores, cámbialo aquí
        'duracion': total_time,
    }
    context = {
        'resumen': resumen,
        'clases': clases,
        'running': False,
    }
    return render(request, 'dashboard/tests_result.html', context)
