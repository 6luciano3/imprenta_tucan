from django.db import connection
cursor = connection.cursor()
cursor.execute("DROP TABLE IF EXISTS pedidos_ordenproduccion")
cursor.execute("""
    CREATE TABLE pedidos_ordenproduccion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER NOT NULL UNIQUE REFERENCES pedidos_pedido(id) ON DELETE CASCADE,
        estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
        fecha_creacion DATETIME NOT NULL
    )
""")
print("Tabla pedidos_ordenproduccion recreada con todas las columnas.")
