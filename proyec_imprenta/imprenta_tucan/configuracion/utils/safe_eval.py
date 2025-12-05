import ast
import operator as op
import math

ALLOWED_NODES = {
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Name, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.UAdd, ast.USub,
    ast.Call, ast.Tuple, ast.List, ast.Constant
}

SAFE_FUNCTIONS = {
    'min': min,
    'max': max,
    'round': round,
    'ceil': math.ceil,
    'floor': math.floor,
    'abs': abs,
}


def _check_node(node):
    if type(node) not in ALLOWED_NODES:
        raise ValueError(f"Uso de operador/nodo no permitido: {type(node).__name__}")
    for child in ast.iter_child_nodes(node):
        _check_node(child)


def safe_eval(expr: str, variables: dict):
    parsed = ast.parse(expr, mode='eval')
    _check_node(parsed)
    code = compile(parsed, '<string>', 'eval')
    env = {}
    env.update(SAFE_FUNCTIONS)
    env.update(variables)
    return eval(code, {"__builtins__": {}}, env)
