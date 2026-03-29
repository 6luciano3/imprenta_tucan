import json
import re
import uuid
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Sum, Q
from .models import ConversacionChatbot

try:
    from pedidos.models import Pedido, EstadoPedido
except ImportError:
    Pedido = None
    EstadoPedido = None

try:
    from clientes.models import Cliente
except ImportError:
    Cliente = None

try:
    from productos.models import Producto
except ImportError:
    Producto = None

try:
    from insumos.models import Insumo
except ImportError:
    Insumo = None

try:
    from presupuestos.models import Presupuesto
except ImportError:
    Presupuesto = None


RESPUESTAS = {
    'saludos': [
        r'hola|buenos?|buenas|saludos|hello|hi|hey',
        """¡Hola! 👋 Bienvenido al asistente de Imprenta Tucán

Soy tu asistente virtual y puedo ayudarte con:

📋 PEDIDOS
   • "busca el pedido 123"
   • "qué pedidos hay pendientes?"
   • "pedidos de hoy"
   • "estado del pedido 5"

👥 CLIENTES
   • "busca cliente Juan Pérez"
   • "clientes sin email"
   • "cuántos clientes hay?"

📦 PRODUCTOS
   • "qué productos tienen?"
   • "busca stickers"
   • "productos con precio menor a 1000"

📄 PRESUPUESTOS
   • "presupuestos de hoy"
   • "presupuestos aceptados esta semana"
   • "presupuestos pendientes"

📊 ESTADÍSTICAS
   • "ventas de hoy"
   • "cuántos pedidos esta semana"
   • "mejores clientes del mes"

🛒 INSUMOS
   • "stock de papel"
   • "insumos bajos"
   • "qué tinta hay?"

💡 OTRO
   • "ayuda" para ver todos los comandos
   • "gracias" """
    ],
    
    'ayuda': [
        r'ayuda|comandos|qué puedes hacer|ayúdame',
        """📚 COMANDOS DISPONIBLES:

📋 PEDIDOS:
• "busca el pedido [número]"
• "qué pedidos hay pendientes?"
• "pedidos de hoy"
• "pedidos del cliente [nombre]"

👥 CLIENTES:
• "busca cliente [nombre]"
• "clientes sin email"
• "cuántos clientes hay?"

📦 PRODUCTOS:
• "qué productos tienen?"
• "busca [producto]"
• "productos con precio..."

📄 PRESUPUESTOS:
• "presupuestos de hoy"
• "presupuestos aceptados"
• "presupuestos pendientes"

📊 ESTADÍSTICAS:
• "ventas de hoy"
• "pedidos esta semana"
• "mejores clientes"

🛒 INSUMOS:
• "stock de papel"
• "insumos bajos"

Escribí lo que necesitás!"""
    ],
    
    'gracias': [
        r'gracias|thank|agradecid|ok|perfecto|genial',
        """¡De nada! 😊

¿Hay algo más en lo que pueda ayudarte?

Recordá que podés consultarme sobre:
📋 Pedidos, 👥 Clientes, 📦 Productos, 📊 Estadísticas"""
    ],
    
    'despedida': [
        r'chau|adios|bye|salir|nos vemos|hasta luego',
        """¡Chau! 👋

Fue un placer ayudarte.
¿Volvés pronto?

💙 Imprenta Tucán"""
    ],
    
    'default': [
        r'.*',
        """No entiendo esa consulta 😕

Puedo ayudarte con:
📋 Pedidos | 👥 Clientes | 📦 Productos
📄 Presupuestos | 📊 Estadísticas | 🛒 Insumos

Escribí "ayuda" para ver todos los comandos."""
    ]
}


def buscar_pedido(texto):
    if not Pedido:
        return None
    
    numeros = re.findall(r'\d+', texto)
    if numeros:
        num = numeros[0]
        pedido = Pedido.objects.filter(id=num).first()
        if pedido:
            estado = pedido.estado.nombre if pedido.estado else "Sin estado"
            return f"""📋 PEDIDO #{pedido.id}

Cliente: {pedido.cliente.nombre} {pedido.cliente.apellido}
Fecha: {pedido.fecha_pedido}
Entrega: {pedido.fecha_entrega}
Estado: {estado}
Monto: ${pedido.monto_total}

¿Necesitás más información?"""
    
    if 'pendiente' in texto.lower() or 'sin confirmar' in texto.lower() or 'sin aprobar' in texto.lower():
        estados = EstadoPedido.objects.filter(nombre__icontains='pendiente') if EstadoPedido else []
        if estados:
            pedidos = list(Pedido.objects.filter(estado__in=estados)[:5])
        else:
            pedidos = list(Pedido.objects.filter(estado__nombre__icontains='pendiente')[:5]) if EstadoPedido else []
        
        if pedidos:
            lista = "\n".join([f"• #{p.id} - {p.cliente.nombre} {p.cliente.apellido} - ${p.monto_total}" for p in pedidos])
            return f"📋 PEDIDOS PENDIENTES:\n\n{lista}\n\nTotal: {len(pedidos)} pedidos"
        return "No hay pedidos pendientes 🎉"
    
    if 'confirmado' in texto.lower() or 'aprobado' in texto.lower():
        estados = EstadoPedido.objects.filter(nombre__icontains='confirmado') if EstadoPedido else []
        if not estados:
            estados = EstadoPedido.objects.filter(nombre__icontains='aprobado') if EstadoPedido else []
        if estados:
            pedidos = list(Pedido.objects.filter(estado__in=estados)[:5])
        else:
            return "No hay pedidos confirmados actualmente"
        
        if pedidos:
            lista = "\n".join([f"• #{p.id} - {p.cliente.nombre} {p.cliente.apellido} - ${p.monto_total}" for p in pedidos])
            return f"📋 PEDIDOS CONFIRMADOS:\n\n{lista}\n\nTotal: {len(pedidos)} pedidos"
        return "No hay pedidos confirmados"
    
    if 'hoy' in texto.lower():
        hoy = timezone.now().date()
        pedidos = Pedido.objects.filter(fecha_pedido=hoy)[:5]
        if pedidos:
            lista = "\n".join([f"• #{p.id} - {p.cliente.nombre} - ${p.monto_total}" for p in pedidos])
            return f"📋 PEDIDOS DE HOY:\n\n{lista}\n\nTotal: {pedidos.count()} pedidos"
        return "No hay pedidos hoy 📭"
    
    return None


def buscar_cliente(texto):
    if not Cliente:
        return None
    
    match = re.search(r'cliente (.+)', texto.lower())
    if match:
        nombre = match.group(1).strip()
        clientes = Cliente.objects.filter(
            Q(nombre__icontains=nombre) | Q(apellido__icontains=nombre)
        )[:5]
        if clientes:
            lista = "\n".join([f"• {c.nombre} {c.apellido} - {c.email or 'Sin email'} - {c.celular or 'Sin celular'}" for c in clientes])
            return f"👥 CLIENTES ENCONTRADOS:\n\n{lista}"
        return f"No encontré clientes con '{nombre}'"
    
    if 'sin email' in texto.lower():
        clientes = Cliente.objects.filter(Q(email__isnull=True) | Q(email=''))[:5]
        if clientes:
            lista = "\n".join([f"• {c.nombre} {c.apellido} - {c.celular or 'Sin celular'}" for c in clientes])
            return f"👥 CLIENTES SIN EMAIL:\n\n{lista}\n\nTotal: {clientes.count()}"
        return "Todos los clientes tienen email ✓"
    
    if 'cuántos' in texto.lower() and 'cliente' in texto.lower():
        total = Cliente.objects.count()
        return f"👥 Total de clientes: {total}"
    
    if 'sin pedido' in texto.lower() or 'no tiene pedido' in texto.lower() or 'no tienen pedido' in texto.lower():
        if not Pedido:
            return None
        clientes_con_pedidos = Pedido.objects.values('cliente').distinct()
        clientes_sin = Cliente.objects.exclude(id__in=clientes_con_pedidos)[:10]
        if clientes_sin:
            lista = "\n".join([f"• {c.nombre} {c.apellido} - {c.email or 'Sin email'}" for c in clientes_sin])
            return f"👥 CLIENTES SIN PEDIDOS:\n\n{lista}\n\nTotal: {clientes_sin.count()}"
        return "Todos los clientes tienen al menos un pedido ✓"
    
    return None


def buscar_producto(texto):
    if not Producto:
        return None
    
    if 'qué producto' in texto.lower() or 'productos tienen' in texto:
        productos = Producto.objects.all()[:10]
        if productos:
            lista = "\n".join([f"• {p.nombre} - ${p.precio}" for p in productos])
            return f"📦 PRODUCTOS ({productos.count()}):\n\n{lista}"
        return "No hay productos registrados"
    
    match = re.search(r'busca (.+)', texto.lower())
    if match:
        nombre = match.group(1).strip()
        productos = Producto.objects.filter(nombre__icontains=nombre)[:5]
        if productos:
            lista = "\n".join([f"• {p.nombre} - ${p.precio}" for p in productos])
            return f"📦 PRODUCTOS ENCONTRADOS:\n\n{lista}"
        return f"No encontré productos con '{nombre}'"
    
    match = re.search(r'precio.*?(\d+)', texto.lower())
    if match and 'menor' in texto.lower():
        precio = int(match.group(1))
        productos = Producto.objects.filter(precio__lt=precio)[:5]
        if productos:
            lista = "\n".join([f"• {p.nombre} - ${p.precio}" for p in productos])
            return f"📦 PRODUCTOS < ${precio}:\n\n{lista}"
    
    return None


def buscar_presupuesto(texto):
    if not Presupuesto:
        return None
    
    if 'hoy' in texto.lower():
        hoy = timezone.now().date()
        presupuestos = Presupuesto.objects.filter(fecha=hoy)[:5]
        if presupuestos:
            lista = "\n".join([f"• #{p.numero} - {p.cliente.nombre} ${p.total} ({p.estado})" for p in presupuestos])
            return f"📄 PRESUPUESTOS DE HOY:\n\n{lista}\n\nTotal: {presupuestos.count()}"
        return "No hay presupuestos hoy 📭"
    
    if 'aceptado' in texto.lower():
        presupuestos = Presupuesto.objects.filter(respuesta_cliente='aceptado')[:5]
        if presupuestos:
            lista = "\n".join([f"• #{p.numero} - {p.cliente.nombre} ${p.total}" for p in presupuestos])
            return f"📄 PRESUPUESTOS ACEPTADOS:\n\n{lista}\n\nTotal: {presupuestos.count()}"
        return "No hay presupuestos aceptados"
    
    if 'pendiente' in texto.lower():
        presupuestos = Presupuesto.objects.filter(respuesta_cliente__isnull=True)[:5]
        if presupuestos:
            lista = "\n".join([f"• #{p.numero} - {p.cliente.nombre} ${p.total}" for p in presupuestos])
            return f"📄 PRESUPUESTOS PENDIENTES:\n\n{lista}\n\nTotal: {presupuestos.count()}"
        return "No hay presupuestos pendientes 🎉"
    
    return None


def buscar_estadisticas(texto):
    if not Pedido or not Cliente or not Presupuesto:
        return None
    
    if 'ventas de hoy' in texto.lower() or 'venta de hoy' in texto.lower():
        hoy = timezone.now().date()
        total = Pedido.objects.filter(fecha_pedido=hoy).aggregate(Sum('monto_total'))['monto_total__sum'] or 0
        cantidad = Pedido.objects.filter(fecha_pedido=hoy).count()
        return f"📊 VENTAS DE HOY:\n\n💰 Total: ${total:,.2f}\n📋 Pedidos: {cantidad}"
    
    if 'esta semana' in texto.lower() or 'semana' in texto.lower():
        semana = timezone.now().date() - timedelta(days=7)
        total = Pedido.objects.filter(fecha_pedido__gte=semana).aggregate(Sum('monto_total'))['monto_total__sum'] or 0
        cantidad = Pedido.objects.filter(fecha_pedido__gte=semana).count()
        return f"📊 ESTA SEMANA:\n\n💰 Total: ${total:,.2f}\n📋 Pedidos: {cantidad}"
    
    if 'mejores cliente' in texto.lower():
        clientes_top = Pedido.objects.values('cliente__nombre', 'cliente__apellido').annotate(
            total=Sum('monto_total')
        ).order_by('-total')[:5]
        if clientes_top:
            lista = "\n".join([f"• {c['cliente__nombre']} {c['cliente__apellido']}: ${c['total']:,.2f}" for c in clientes_top])
            return f"🏆 MEJORES CLIENTES:\n\n{lista}"
        return "No hay datos de clientes"
    
    if 'cuántos pedido' in texto.lower():
        total = Pedido.objects.count()
        return f"📋 Total de pedidos: {total}"
    
    return None


def buscar_insumos(texto):
    try:
        from insumos.models import Insumo
    except ImportError:
        return None
    
    texto_lower = texto.lower()
    
    if 'stock' in texto_lower or 'hay' in texto_lower or 'tiene' in texto_lower or 'cuanto' in texto_lower:
        palabra = ''
        
        patrones = [
            r'stock del\s+(.+?)\s*$',
            r'stock de la\s+(.+?)\s*$',
            r'stock de\s+(.+?)\s*$',
            r'stock\s+(.+?)\s*$',
            r'hay de\s+(.+?)\s*$',
            r'tiene\s+(.+?)\s*$',
            r'cuanto\s+(.+?)\s*$',
        ]
        
        for patron in patrones:
            match = re.search(patron, texto_lower)
            if match:
                palabra = match.group(1).strip()
                break
        
        palabra = palabra.rstrip('?').strip()
        
        if palabra and len(palabra) > 1:
            insumos = Insumo.objects.filter(nombre__icontains=palabra)[:5]
            if not insumos:
                palabras = palabra.split()
                for p in palabras:
                    if len(p) > 2:
                        insumos = Insumo.objects.filter(nombre__icontains=p)[:5]
                        if insumos:
                            break
        else:
            insumos = Insumo.objects.all()[:5]
        
        if insumos:
            lista = "\n".join([f"• {i.nombre} - Stock: {i.stock} {i.unidad_medida or ''}" for i in insumos])
            return f"🛒 INSUMOS:\n\n{lista}"
        
        insumos = Insumo.objects.all()[:5]
        if insumos:
            lista = "\n".join([f"• {i.nombre} - Stock: {i.stock} {i.unidad_medida or ''}" for i in insumos])
            return f"🛒 INSUMOS:\n\n{lista}"
        
        return "No hay insumos registrados"
    
    if 'bajo' in texto_lower or 'falta' in texto_lower:
        insumos = Insumo.objects.filter(stock__lte=10)[:5]
        if insumos:
            lista = "\n".join([f"• {i.nombre} - Stock: {i.stock} {i.unidad_medida or ''}" for i in insumos])
            return f"⚠️ INSUMOS BAJOS:\n\n{lista}\n\n¡Considerar reponer!"
        return "No hay insumos con stock bajo ✓"
    
    return None


def obtener_respuesta(mensaje):
    texto = mensaje.lower().strip()
    
    for clave, datos in RESPUESTAS.items():
        patrones, respuesta = datos
        if re.search(patrones, texto, re.IGNORECASE):
            if clave != 'default':
                return respuesta
    
    funciones = [
        buscar_cliente,
        buscar_pedido,
        buscar_insumos,
        buscar_producto,
        buscar_presupuesto,
        buscar_estadisticas,
    ]
    
    for func in funciones:
        result = func(texto)
        if result:
            return result
    
    return RESPUESTAS['default'][1]


@csrf_exempt
@require_http_methods(["POST"])
def chatbot_api(request):
    try:
        data = json.loads(request.body)
        mensaje = data.get('mensaje', '').strip()
        session_id = data.get('session_id', '')
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        if not mensaje:
            return JsonResponse({'error': 'Mensaje vacío'}, status=400)
        
        respuesta = obtener_respuesta(mensaje)
        
        ConversacionChatbot.objects.create(
            session_id=session_id,
            mensaje=mensaje,
            respuesta=respuesta,
            es_cliente=True
        )
        
        ConversacionChatbot.objects.create(
            session_id=session_id,
            mensaje=respuesta,
            respuesta='',
            es_cliente=False
        )
        
        return JsonResponse({
            'respuesta': respuesta,
            'session_id': session_id,
            'timestamp': timezone.now().isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def obtener_historial(session_id, limite=10):
    return ConversacionChatbot.objects.filter(
        session_id=session_id
    ).order_by('-fecha')[:limite]
