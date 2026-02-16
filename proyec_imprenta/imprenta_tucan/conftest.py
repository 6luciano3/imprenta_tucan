def pytest_terminal_summary(terminalreporter, exitstatus):
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    total = passed + failed
    print(f"\n📊 Resumen: {total} pruebas | {passed} pasadas | {failed} fallidas")
