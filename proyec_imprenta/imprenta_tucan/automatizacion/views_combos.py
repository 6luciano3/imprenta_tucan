from django.shortcuts import render
from django.core.mail import send_mail
from django.utils import timezone
from .propuestas.models import ComboOferta, ComboOfertaProducto
from productos.models import Producto
from clientes.models import Cliente


def crear_combos_inventados():
    # Solo crear si no existen combos
    if ComboOferta.objects.count() > 0:
        return
    productos = list(Producto.objects.all()[:5])
    clientes = list(Cliente.objects.all()[:3])
    combos_data = [
        {
            'nombre': 'Combo Impresión Full',
            'descripcion': 'Incluye folleto, tarjeta y afiche con descuento especial.',
            'productos': productos[:3],
            'descuento': 15,
        },
        {
            'nombre': 'Combo Papelería Premium',
            'descripcion': 'Tarjetas, sobres y papel membretado para empresas.',
            'productos': productos[1:4],
            'descuento': 10,
        },
        {
            'nombre': 'Combo Publicidad Express',
            'descripcion': 'Afiche, banner y flyer para campañas rápidas.',
            'productos': productos[2:5],
            'descuento': 20,
        },
    ]
    for i, cliente in enumerate(clientes):
        combo_info = combos_data[i % len(combos_data)]
        combo = ComboOferta.objects.create(
            cliente=cliente,
            nombre=combo_info['nombre'],
            descripcion=combo_info['descripcion'],
            descuento=combo_info['descuento'],
            fecha_inicio=timezone.now(),
            fecha_fin=timezone.now() + timezone.timedelta(days=7),
        )
        for prod in combo_info['productos']:
            ComboOfertaProducto.objects.create(combo=combo, producto=prod, cantidad=2)
        # Simular envío de email solo si el email es válido
        import re
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if re.match(email_regex, cliente.email):
            send_mail(
                f"Oferta especial: {combo.nombre}",
                f"Estimado {cliente.nombre},\n\nTe ofrecemos el siguiente combo:\n{combo.descripcion}\n\nProductos incluidos: " + ", ".join([p.nombreProducto for p in combo_info['productos']]) + f"\nDescuento: {combo.descuento}%\n\n¡Aprovecha esta oportunidad!",
                'no-reply@imprenta.local',
                [cliente.email],
                fail_silently=True,
            )

def lista_combos_oferta(request):
    crear_combos_inventados()
    combos = ComboOferta.objects.all()
    combos_data = []
    for combo in combos:
        items = combo.comboofertaproducto_set.all()
        productos = []
        subtotal = 0
        for item in items:
            precio_unitario = float(item.producto.precioUnitario)
            cantidad = item.cantidad
            subtotal_item = precio_unitario * cantidad
            productos.append({
                'nombre': item.producto.nombreProducto,
                'cantidad': cantidad,
                'precio_unitario': precio_unitario,
                'subtotal': subtotal_item,
            })
            subtotal += subtotal_item
        descuento = float(combo.descuento)
        descuento_valor = subtotal * descuento / 100
        total_final = subtotal - descuento_valor
        combos_data.append({
            'nombre': combo.nombre,
            'descripcion': combo.descripcion,
            'productos': productos,
            'subtotal': subtotal,
            'descuento': descuento,
            'descuento_valor': descuento_valor,
            'total_final': total_final,
        })
    return render(request, 'automatizacion/lista_combos_oferta.html', {'combos': combos_data})
