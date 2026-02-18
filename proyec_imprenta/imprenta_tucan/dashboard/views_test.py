import subprocess
import re
from django.shortcuts import render
from django.views import View

import os
import tempfile
import threading
import time

class DashboardTestView(View):
    template_name = "dashboard/tests_result.html"
    result_file = os.path.join(tempfile.gettempdir(), "dashboard_tests_result.txt")
    lock = threading.Lock()

    def get(self, request):
        # Leer el último resultado guardado
        output = ""
        if os.path.exists(self.result_file):
            with open(self.result_file, "r", encoding="utf-8") as f:
                output = f.read()
        resumen, clases = self.parse_output(output)
        return render(request, self.template_name, {"resumen": resumen, "clases": clases, "output": output})

    def post(self, request):
        # Lanzar los tests en un hilo aparte para no bloquear el servidor
        def run_tests():
            test_files = [
                "proyec_imprenta/imprenta_tucan/clientes/tests.py",
                "proyec_imprenta/imprenta_tucan/pedidos/tests/test_alta_pedido.py",
                "proyec_imprenta/imprenta_tucan/pedidos/tests/test_consumo.py",
                "proyec_imprenta/imprenta_tucan/pedidos/tests/test_stock_pedido.py",
                "proyec_imprenta/imprenta_tucan/productos/tests.py",
                "proyec_imprenta/imprenta_tucan/insumos/tests.py",
                "proyec_imprenta/imprenta_tucan/proveedores/tests.py",
                "proyec_imprenta/imprenta_tucan/dashboard/tests.py",
            ]
            try:
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
                result = subprocess.run(
                    [
                        "..{}imprenta_tuc{}Scripts{}python.exe".format(
                            "\\", "\\", "\\"
                        ),
                        "-m",
                        "pytest",
                        *test_files,
                        "--tb=short",
                        "-q"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=project_root
                )
                output = result.stdout + "\n" + result.stderr
            except Exception as e:
                output = f"Error ejecutando tests: {e}"
            with self.lock:
                with open(self.result_file, "w", encoding="utf-8") as f:
                    f.write(output)
        threading.Thread(target=run_tests, daemon=True).start()
        # Esperar un poco para que el hilo inicie y el usuario recargue
        time.sleep(1)
        return self.get(request)

    def parse_output(self, output):
        resumen = {
            "passed": "failed" not in output.lower(),
            "total_tests": 0,
            "total_assertions": 0,
            "total_time": "-"
        }
        clases = []
        test_re = re.compile(r"([\w_]+)\.(test_[\w_]+)\s+(PASSED|FAILED|ERROR|SKIPPED)\s*\[(\d+)ms\]?(.*)")
        resumen_match = re.search(r"(\d+) (passed|failed|skipped).*in ([\d\.]+)s", output)
        if resumen_match:
            resumen["total_tests"] = int(resumen_match.group(1))
            resumen["total_time"] = resumen_match.group(3)
        for line in output.splitlines():
            m = test_re.search(line)
            if m:
                clase, nombre, estado, duracion, detalle = m.groups()
                if not clases or clases[-1]["nombre"] != clase:
                    clases.append({"nombre": clase, "tests": []})
                clases[-1]["tests"].append({
                    "nombre": nombre,
                    "estado": estado,
                    "duracion": duracion,
                    "descripcion": "",
                    "detalle": detalle.strip() if detalle else ""
                })
        if not clases:
            clases = [{"nombre": "Sin resultados", "tests": []}]
        return resumen, clases
