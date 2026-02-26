import random
from django.db import connection

tipos = (
    ['premium'] * 12 +
    ['estrategico'] * 25 +
    ['estandar'] * 37 +
    ['nuevo'] * 49
)
random.shuffle(tipos)

rangos = {
    'premium':     list(range(90, 105, 5)),
    'estrategico': list(range(60, 90, 5)),
    'estandar':    list(range(30, 60, 5)),
    'nuevo':       list(range(15, 30, 5)),
}

cursor = connection.cursor()
cursor.execute("SELECT id FROM clientes_cliente ORDER BY id")
ids = [row[0] for row in cursor.fetchall()]

for i, cid in enumerate(ids):
    tipo = tipos[i]
    puntaje = random.choice(rangos[tipo])
    cursor.execute("UPDATE clientes_cliente SET tipo_cliente = %s, puntaje_estrategico = %s WHERE id = %s", [tipo, puntaje, cid])

print(f"Total: {len(ids)} clientes actualizados")
