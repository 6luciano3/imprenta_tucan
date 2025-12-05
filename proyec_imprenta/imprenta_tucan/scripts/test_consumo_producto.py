from insumos.models import Insumo
from pedidos.services import calcular_consumo_producto, verificar_stock_consumo
from productos.models import Producto
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


def mostrar(producto_nombre: str, cantidad: int):
    p = Producto.objects.get(nombreProducto__iexact=producto_nombre)
    consumo = calcular_consumo_producto(p, cantidad)
    ids = list(consumo.keys())
    insumos = {i.idInsumo: i for i in Insumo.objects.filter(idInsumo__in=ids)}

    total_req = 0.0
    total_stock = 0.0
    total_faltan = 0.0

    print(f"Producto: {p.nombreProducto} | Cantidad: {cantidad}")
    for iid, req in consumo.items():
        ins = insumos.get(iid)
        stock = float(ins.stock) if ins else 0.0
        faltan = max(0.0, float(req) - stock)
        total_req += float(req)
        total_stock += stock
        total_faltan += faltan
        print(f" - {ins.codigo if ins else iid} {ins.nombre if ins else ''} | requerido={float(req)} | stock={stock} | faltan={faltan}")

    ok, faltantes = verificar_stock_consumo(consumo)
    print(f"Resumen => ok={ok} | total_req={total_req} | total_stock={total_stock} | total_faltan={total_faltan}")


if __name__ == '__main__':
    mostrar('Folleto A4 Color', 100)
    print('-' * 60)
    mostrar('Tarjeta Personal Color', 240)
    print('-' * 60)
    mostrar('Afiche A3 Color', 10)
