import django, os, sys
sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "impre_tucan.settings"
django.setup()

from clientes.models import Cliente
from productos.models import Producto
from pedidos.models import Pedido, LineaPedido, EstadoPedido
from insumos.models import Insumo
from auditoria.models import AuditEntry
from datetime import date, timedelta
import json

luciano = Cliente.objects.get(pk=130)
carpeta = Producto.objects.get(idProducto=8)
estado_pendiente = EstadoPedido.objects.get(id=1)
estado_proceso = EstadoPedido.objects.get(id=2)
print(f"Estados: pendiente={estado_pendiente.nombre} | proceso={estado_proceso.nombre}")

cartulina = Insumo.objects.get(codigo="CAR-ILU-350")
plancha = Insumo.objects.get(codigo="PLA-ALU-STD")
print(f"Stock ANTES - Cartulina 350g: {cartulina.stock}")
print(f"Stock ANTES - Plancha:        {plancha.stock}")

pedido = Pedido.objects.create(
    cliente=luciano,
    fecha_entrega=date.today() + timedelta(days=7),
    monto_total=85772,
    estado=estado_pendiente,
)
LineaPedido.objects.create(
    pedido=pedido,
    producto=carpeta,
    cantidad=100,
    precio_unitario=carpeta.precioUnitario,
)
print(f"\nPedido #{pedido.id} creado en: {pedido.estado.nombre}")

pedido.estado = estado_proceso
pedido.save()
print(f"Pedido #{pedido.id} pasado a: {pedido.estado.nombre}")

cartulina.refresh_from_db()
plancha.refresh_from_db()
print(f"\nStock DESPUES - Cartulina 350g: {cartulina.stock}")
print(f"Stock DESPUES - Plancha:        {plancha.stock}")

entries = AuditEntry.objects.filter(app_label="insumos", model="Insumo").order_by("-id")[:4]
print(f"\nRegistros en Auditoria:")
for e in entries:
    cambios = json.loads(e.changes or "{}")
    print(f"  {e.object_repr} | stock: {cambios.get('stock')} | motivo: {cambios.get('motivo')}")
