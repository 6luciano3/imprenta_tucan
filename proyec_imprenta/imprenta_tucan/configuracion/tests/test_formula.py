import pytest
from configuracion.utils.safe_eval import safe_eval
from django.test import Client


def test_safe_eval_basic():
    expr = "(tiraje * area)/rendimiento"
    res = safe_eval(expr, {'tiraje': 1000, 'area': 0.21, 'rendimiento': 5})
    assert abs(res - 42.0) < 1e-6


def test_safe_eval_error():
    expr = "import os; os.system('rm -rf /')"
    try:
        safe_eval(expr, {})
        assert False, "Debe lanzar excepción por uso no permitido"
    except Exception:
        assert True


def test_safe_eval_funciones():
    expr = "ceil(tiraje / rendimiento)"
    res = safe_eval(expr, {'tiraje': 100, 'rendimiento': 33})
    assert res == 4


def test_validar_formula_api(client: Client):
    c = Client()
    resp = c.post('/api/configuracion/formula/validate/',
                  data='{"expresion": "(tiraje*area)/rendimiento", "variables": {"tiraje":1000,"area":0.21,"rendimiento":5}}',
                  content_type='application/json')
    assert resp.status_code == 200
    data = resp.json()
    assert data['ok'] and abs(data['resultado'] - 42.0) < 1e-6


def test_validar_formula_api_error(client: Client):
    c = Client()
    resp = c.post('/api/configuracion/formula/validate/',
                  data='{"expresion": "import os", "variables": {}}',
                  content_type='application/json')
    assert resp.status_code == 400
    data = resp.json()
    assert not data['ok']
