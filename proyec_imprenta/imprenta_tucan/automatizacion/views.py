from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import OrdenSugerida, OfertaAutomatica
from django.views.decorators.csrf import csrf_exempt


def panel(request):
    ordenes = OrdenSugerida.objects.select_related('pedido', 'insumo').order_by('-generada')[:10]
    ofertas = OfertaAutomatica.objects.select_related('cliente').order_by('-generada')[:10]
    return render(request, 'automatizacion/panel.html', {
        'ordenes': ordenes,
        'ofertas': ofertas,
    })


def lista_ordenes(request):
    # Si no hay órdenes sugeridas, generar algunas entradas de demostración automáticamente
    if not OrdenSugerida.objects.exists():
        try:
            _ensure_demo_ordenes()
        except Exception:
            # Fallo silencioso: mantener la página funcional aunque no se puedan generar datos
            pass

    qs = OrdenSugerida.objects.select_related('pedido', 'insumo').order_by('-generada')
    try:
        from configuracion.services import get_page_size
        page_size = get_page_size()
    except Exception:
        page_size = 10
    paginator = Paginator(qs, page_size)
    page = request.GET.get('page')
    ordenes = paginator.get_page(page)
    return render(request, 'automatizacion/ordenes.html', {'ordenes': ordenes})


def lista_ofertas(request):
    qs = OfertaAutomatica.objects.select_related('cliente').order_by('-generada')
    try:
        from configuracion.services import get_page_size
        page_size = get_page_size()
    except Exception:
        page_size = 10
    paginator = Paginator(qs, page_size)
    page = request.GET.get('page')
    ofertas = paginator.get_page(page)
    return render(request, 'automatizacion/ofertas.html', {'ofertas': ofertas})


@csrf_exempt
def generar_demo(request):
    """Genera datos de demo para órdenes sugeridas y ofertas automáticas."""
    if request.method not in ('POST', 'GET'):
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    created = {'ordenes': 0, 'ofertas': 0}
    try:
        # Asegurar órdenes sugeridas de demo si no existen
        if not OrdenSugerida.objects.exists():
            try:
                _ensure_demo_ordenes()
            except Exception:
                pass
        # Crear órdenes sugeridas en base a pedidos existentes
        from pedidos.models import Pedido
        from insumos.models import Insumo
        insumo = Insumo.objects.order_by('id').first()
        pedidos = list(Pedido.objects.order_by('-fecha_pedido')[:3])
        if insumo and pedidos:
            cantidades = [5, 10, 15]
            for idx, p in enumerate(pedidos):
                OrdenSugerida.objects.create(
                    pedido=p,
                    insumo=insumo,
                    cantidad=cantidades[idx % len(cantidades)]
                )
                created['ordenes'] += 1

        # Crear ofertas automáticas para clientes existentes
        from clientes.models import Cliente
        from django.utils import timezone
        from datetime import timedelta
        clientes = list(Cliente.objects.order_by('id')[:2])
        ventana = timezone.now()
        for c in clientes:
            OfertaAutomatica.objects.create(
                cliente=c,
                descripcion=f"Descuento especial para {c.nombre}",
                fecha_inicio=ventana - timedelta(days=1),
                fecha_fin=ventana + timedelta(days=7),
                activa=True
            )
            created['ofertas'] += 1

        return JsonResponse({'created': created})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _ensure_demo_ordenes():
    """Crea entradas de `OrdenSugerida` si no existen, usando datos básicos del sistema."""
    from pedidos.models import Pedido
    from insumos.models import Insumo
    from django.utils import timezone
    from datetime import timedelta

    insumo = Insumo.objects.order_by('idInsumo').first()
    pedidos = list(Pedido.objects.order_by('-fecha_pedido')[:3])

    if not insumo:
        # Crear un insumo demo minimal si no existe ninguno
        insumo = Insumo.objects.create(
            nombre="Papel demo",
            codigo="DEMO-001",
            cantidad=100,
            stock=100,
            precio_unitario=0,
            precio=0,
            activo=True,
        )

    if not pedidos:
        # Crear un pedido mínimo de demostración si no hay ninguno
        try:
            from clientes.models import Cliente
            from pedidos.models import EstadoPedido
            from productos.models import Producto
            from configuracion.models import Formula

            cliente, _ = Cliente.objects.get_or_create(
                email="demo@tucan.local",
                defaults={
                    "nombre": "Demo",
                    "apellido": "Cliente",
                    "razon_social": "Imprenta Tucán",
                    "direccion": "Av. Demo 123",
                    "ciudad": "Posadas",
                    "provincia": "Misiones",
                    "pais": "Argentina",
                    "telefono": "000000",
                    "estado": "Activo",
                },
            )

            estado, _ = EstadoPedido.objects.get_or_create(nombre="pendiente")

            # Asegurar una fórmula mínima asociada al insumo demo
            formula, _ = Formula.objects.get_or_create(
                codigo="DEMO-FORM-001",
                defaults={
                    "insumo": insumo,
                    "nombre": "Fórmula Demo",
                    "descripcion": "Fórmula mínima para producto demo",
                    "expresion": "cantidad * 1",
                    "variables_json": [],
                    "activo": True,
                },
            )
            # Si la fórmula existía pero con otro insumo, aseguramos vínculo
            if formula.insumo_id != insumo.pk:
                formula.insumo = insumo
                formula.save()

            producto = Producto.objects.order_by('idProducto').first()
            if not producto:
                from decimal import Decimal
                producto = Producto.objects.create(
                    nombreProducto="Producto demo",
                    descripcion="Producto de demostración",
                    precioUnitario=Decimal("100.00"),
                    formula=formula,
                )

            nuevo_pedido = Pedido.objects.create(
                cliente=cliente,
                producto=producto,
                fecha_entrega=timezone.now().date() + timedelta(days=7),
                cantidad=10,
                especificaciones="Pedido demo",
                monto_total=1000,
                estado=estado,
            )
            pedidos = [nuevo_pedido]
        except Exception:
            # Si falla la creación del pedido demo, abortar silenciosamente
            return

    cantidades = [5, 10, 15]
    for idx, p in enumerate(pedidos):
        # Evitar duplicados si la página se carga varias veces
        exists = OrdenSugerida.objects.filter(pedido=p, insumo=insumo).exists()
        if exists:
            continue
        OrdenSugerida.objects.create(
            pedido=p,
            insumo=insumo,
            cantidad=cantidades[idx % len(cantidades)]
        )
