import pytest
import time
from collections import defaultdict

class VSCodeStyleReporter:
    def __init__(self, config):
        self.results = defaultdict(list)
        self.start_times = {}
        self.total_tests = 0
        self.total_asserts = 0
        self.passed = 0
        self.failed = 0
        self.start_time = None
        self.end_time = None
        self.config = config

    @pytest.hookimpl
    def pytest_sessionstart(self, session):
        self.start_time = time.time()

    @pytest.hookimpl
    def pytest_runtest_logstart(self, nodeid, location):
        self.start_times[nodeid] = time.time()

    @pytest.hookimpl
    def pytest_runtest_logreport(self, report):
        if report.when != 'call':
            return
        duration = (time.time() - self.start_times.get(report.nodeid, time.time())) * 1000
        test_class = report.nodeid.split("::")[0]
        test_name = report.nodeid.split("::")[-1]
        status = '✅' if report.passed else '❌'
        if report.passed:
            self.passed += 1
        else:
            self.failed += 1
        self.total_tests += 1
        self.total_asserts += getattr(report, 'asserts', 1)
        self.results[test_class].append({
            'status': status,
            'name': test_name,
            'duration': duration,
            'outcome': report.outcome,
            'longrepr': str(report.longrepr) if report.failed else '',
        })

    @pytest.hookimpl
    def pytest_sessionfinish(self, session, exitstatus):
        self.end_time = time.time()
        total_time = self.end_time - self.start_time
        all_passed = self.failed == 0
        summary_icon = '✅' if all_passed else '❌'
        print()
        print(f"{summary_icon} {'Todas las pruebas superadas' if all_passed else 'Pruebas con errores'} | {self.total_tests} pruebas | {self.total_asserts} afirmaciones | Tiempo de ejecución: {total_time:.2f} s\n")
        for test_class, tests in self.results.items():
            print(f"\U0001F4C1 {test_class}")
            for test in tests:
                name = test['name']
                status = test['status']
                duration = test['duration']
                msg = ''
                if test['outcome'] == 'failed':
                    msg = f"Error: {test['longrepr'].splitlines()[-1] if test['longrepr'] else ''}"
                print(f"  {status} {name}: {msg} ({duration:.0f} ms)")
            print()
        print(f"Resumen final: {self.passed} pasadas, {self.failed} fallidas, tiempo total: {total_time:.2f} s\n")

def pytest_configure(config):
    reporter = VSCodeStyleReporter(config)
    config.pluginmanager.register(reporter, 'vscode-style-reporter')
