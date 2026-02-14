from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

# ...existing code...

@login_required
@require_POST
def crear_propuesta_para_insumo(request):
    from automatizacion.models import CompraPropuesta
    from insumos.models import Insumo
    insumo_id = request.POST.get('insumo_id')
    if not insumo_id:
        messages.error(request, 'Falta el ID de insumo.')
        return redirect('compras_propuestas')
    try:
        insumo = Insumo.objects.get(idInsumo=insumo_id)
    except Insumo.DoesNotExist:
        messages.error(request, 'Insumo no encontrado.')
        return redirect('compras_propuestas')
    # Crear propuesta mínima (ajustar lógica según negocio)
    propuesta = CompraPropuesta.objects.create(
        insumo=insumo,
        cantidad_requerida=1,
        motivo_trigger='faltante_stock',
        estado='pendiente',
    )
    messages.success(request, f'Propuesta creada para {insumo.nombre}. Completa los datos desde la edición.')
    return redirect('compras_propuestas')
# Endpoints públicos para aceptar/rechazar desde email
from .models import OfertaPropuesta, AccionCliente
from django.utils import timezone

def aceptar_oferta_token(request, token):
    oferta = get_object_or_404(OfertaPropuesta, token_email=token)
    if oferta.estado != 'aceptada':
        oferta.estado = 'aceptada'
        oferta.fecha_validacion = timezone.now()
        oferta.save()
        AccionCliente.objects.create(
            cliente=oferta.cliente,
            oferta=oferta,
            tipo='aceptar',
            canal='email',
            detalle='Cliente aceptó la oferta desde el email',
        )
    return redirect('/automatizacion/propuestas/')

def rechazar_oferta_token(request, token):
    oferta = get_object_or_404(OfertaPropuesta, token_email=token)
    if oferta.estado != 'rechazada':
        oferta.estado = 'rechazada'
        oferta.fecha_validacion = timezone.now()
        oferta.save()
        AccionCliente.objects.create(
            cliente=oferta.cliente,
            oferta=oferta,
            tipo='rechazar',
            canal='email',
            detalle='Cliente rechazó la oferta desde el email',
        )
    return redirect('/automatizacion/propuestas/')
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
# --- Importaciones necesarias ---
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
# --- Tracking pixel para registrar "leído" ---
@csrf_exempt
def pixel_leido(request):
    """Vista para tracking pixel: registra acción 'leido' al cargar la imagen."""
    cliente_id = request.GET.get('cliente_id')
    oferta_id = request.GET.get('oferta_id')
    tipo = request.GET.get('tipo', 'leido')
    canal = request.GET.get('canal', 'email')
    if cliente_id and oferta_id:
        from .models import AccionCliente, OfertaPropuesta
        try:
            oferta = OfertaPropuesta.objects.filter(pk=oferta_id, cliente_id=cliente_id).first()
            if oferta:
                AccionCliente.objects.create(
                    cliente_id=cliente_id,
                    oferta=oferta,
                    tipo=tipo,
                    canal=canal,
                    detalle='Tracking pixel (leído)',
                )
        except Exception:
            pass
    # 1x1 GIF transparente
    gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    return HttpResponse(gif, content_type='image/gif')
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, F, Count
from clientes.models import Cliente
from django.http import JsonResponse
from .models import OrdenSugerida, OfertaAutomatica, RankingCliente, RankingHistorico, OfertaPropuesta
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django import forms
from .services import enviar_oferta_email


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


def lista_ranking_clientes(request):
    """Listado de Ranking de Clientes con métricas del período actual."""
    # Determinar período actual (mensual por defecto)
    from configuracion.models import Parametro
    now = timezone.now()
    periodo_conf = Parametro.get('RANKING_PERIODICIDAD', 'mensual')
    if periodo_conf == 'trimestral':
        q = (now.month - 1) // 3 + 1
        periodo_str = f"{now.year}-Q{q}"
    else:
        periodo_str = now.strftime('%Y-%m')

    qs = RankingCliente.objects.select_related('cliente').order_by('-score')
    try:
        from configuracion.services import get_page_size
        page_size = get_page_size()
    except Exception:
        page_size = 10
    paginator = Paginator(qs, page_size)
    page = request.GET.get('page')
    ranking = paginator.get_page(page)

    # Adjuntar métricas del histórico del período
    historicos = {rh.cliente_id: rh for rh in RankingHistorico.objects.filter(periodo=periodo_str)}
    items = []
    for rc in ranking:
        rh = historicos.get(rc.cliente_id)
        metricas = rh.metricas if rh else {}
        # Clasificación estratégica por umbral configurable
        try:
            umbral_estrategico = float(Parametro.get('RANKING_SCORE_ESTRATEGICO_UMBRAL', 90))
        except Exception:
            umbral_estrategico = 90.0
        clasificacion = 'Estratégico' if float(rc.score or 0) >= umbral_estrategico else 'Estándar'
        items.append({
            'cliente': rc.cliente,
            'score': rc.score,
            'variacion': (rh.variacion if rh else 0),
            'metricas': metricas,
            'clasificacion': clasificacion,
        })

    return render(request, 'automatizacion/ranking_clientes.html', {
        'items': items,
        'page_obj': ranking,
        'periodo': periodo_str,
    })


# --- Gestión de ofertas propuestas (Administrador) ---
@login_required
def ofertas_propuestas_admin(request):
    # Mostrar una sola oferta por cliente: la de mayor score (si empata, la más reciente)
    base_qs = OfertaPropuesta.objects.select_related('cliente')
    best_id_sub = base_qs.filter(cliente_id=OuterRef('cliente_id')).order_by('-score_al_generar', '-creada').values('id')[:1]
    from .models import MensajeOferta, AccionCliente
    # Último estado de mensaje por oferta
    last_msg_state_sub = MensajeOferta.objects.filter(oferta_id=OuterRef('pk')).order_by('-actualizado').values('estado')[:1]
    last_msg_time_sub = MensajeOferta.objects.filter(oferta_id=OuterRef('pk')).order_by('-actualizado').values('actualizado')[:1]
    # Última acción del cliente por oferta y cantidad total de acciones
    last_action_type_sub = AccionCliente.objects.filter(oferta_id=OuterRef('pk')).order_by('-creado').values('tipo')[:1]
    last_action_time_sub = AccionCliente.objects.filter(oferta_id=OuterRef('pk')).order_by('-creado').values('creado')[:1]
    actions_count_sub = (
        AccionCliente.objects
        .filter(oferta_id=OuterRef('pk'))
        .order_by()
        .values('oferta_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )
    qs = (
        base_qs
        .annotate(best_id=Subquery(best_id_sub))
        .filter(id=F('best_id'))
        .annotate(
            estado_mensaje=Subquery(last_msg_state_sub),
            mensaje_actualizado=Subquery(last_msg_time_sub),
            ultima_accion=Subquery(last_action_type_sub),
            accion_actualizada=Subquery(last_action_time_sub),
            acciones_count=Subquery(actions_count_sub),
        )
        .order_by('-score_al_generar', '-creada')
    )
    # Mostrar exactamente 10 clientes por página
    page_size = 10
    paginator = Paginator(qs, page_size)
    page = request.GET.get('page')
    ofertas = paginator.get_page(page)
    msg = request.GET.get('msg')
    ok = request.GET.get('ok')
    return render(request, 'automatizacion/ofertas_propuestas.html', {'ofertas': ofertas, 'msg': msg, 'ok': ok})


class OfertaManualForm(forms.Form):
    cliente_email = forms.EmailField(label='Email del cliente', required=False)
    cliente_id = forms.IntegerField(label='ID del cliente', required=False, min_value=1)
    titulo = forms.CharField(max_length=120)
    descripcion = forms.CharField(widget=forms.Textarea)
    tipo = forms.ChoiceField(choices=[
        ('descuento', 'Descuento'),
        ('fidelizacion', 'Fidelización'),
        ('prioridad_stock', 'Prioridad en stock'),
        ('promocion', 'Promoción'),
    ])
    parametros = forms.CharField(label='Parámetros (JSON)', required=False)
    score_al_generar = forms.FloatField(label='Score (opcional)', required=False)
    enviar_ahora = forms.BooleanField(label='Enviar inmediatamente', required=False)


@login_required
def nueva_oferta_manual(request):
    """Crear y opcionalmente enviar una oferta manual a un cliente específico."""
    if request.method == 'POST':
        form = OfertaManualForm(request.POST)
        if form.is_valid():
            from clientes.models import Cliente
            cliente = None
            cid = form.cleaned_data.get('cliente_id')
            email = form.cleaned_data.get('cliente_email')
            if cid:
                cliente = Cliente.objects.filter(pk=cid).first()
            elif email:
                cliente = Cliente.objects.filter(email=email).first()
            if not cliente:
                messages.error(request, 'Cliente no encontrado por ID o email.')
                return render(request, 'automatizacion/oferta_nueva.html', {'form': form})

            parametros_raw = form.cleaned_data.get('parametros') or ''
            try:
                import json
                parametros = json.loads(parametros_raw) if parametros_raw.strip() else {}
            except Exception:
                parametros = {}

            score = form.cleaned_data.get('score_al_generar')
            try:
                score = float(score) if score is not None else None
            except Exception:
                score = None
            # Si no hay score, intentar usar RankingCliente
            if score is None:
                rc = RankingCliente.objects.filter(cliente=cliente).first()
                score = float(rc.score) if rc else 0.0

            oferta = OfertaPropuesta.objects.create(
                cliente=cliente,
                titulo=form.cleaned_data['titulo'],
                descripcion=form.cleaned_data['descripcion'],
                tipo=form.cleaned_data['tipo'],
                parametros=parametros,
                score_al_generar=score or 0.0,
                estado='pendiente',
                administrador=request.user,
            )

            if form.cleaned_data.get('enviar_ahora'):
                oferta.estado = 'enviada'
                oferta.fecha_validacion = timezone.now()
                oferta.save()
                try:
                    from .models import MensajeOferta
                    ok, err = enviar_oferta_email(oferta, request=request)
                    MensajeOferta.objects.create(
                        oferta=oferta,
                        cliente=cliente,
                        estado='enviado' if ok else 'fallido',
                        detalle='Oferta enviada manualmente por admin' if ok else f'Error al enviar: {err}',
                    )
                    messages.success(request, 'Oferta creada y enviada correctamente.' if ok else f'Oferta creada pero el envío falló: {err}')
                except Exception:
                    pass
            else:
                oferta.save()
                messages.success(request, 'Oferta creada como pendiente. Puedes enviarla desde la lista.')
            return redirect('ofertas_propuestas')
        else:
            return render(request, 'automatizacion/oferta_nueva.html', {'form': form})
    else:
        form = OfertaManualForm()
        return render(request, 'automatizacion/oferta_nueva.html', {
            'form': form,
        })


@login_required
def aprobar_oferta(request, oferta_id):
    oferta = get_object_or_404(OfertaPropuesta, pk=oferta_id)
    oferta.estado = 'enviada'
    oferta.fecha_validacion = timezone.now()
    oferta.administrador = request.user
    oferta.save()
    # Enviar email al cliente y registrar estado de mensaje
    try:
        from .models import MensajeOferta
        ok, err = enviar_oferta_email(oferta, request=request)
        MensajeOferta.objects.create(
            oferta=oferta,
            cliente=oferta.cliente,
            estado='enviado' if ok else 'fallido',
            detalle='Oferta enviada automáticamente' if ok else f'Error al enviar: {err}',
        )
    except Exception:
        pass
    return redirect('ofertas_propuestas')


@login_required
def rechazar_oferta(request, oferta_id):
    oferta = get_object_or_404(OfertaPropuesta, pk=oferta_id)
    oferta.estado = 'rechazada'
    oferta.fecha_validacion = timezone.now()
    oferta.administrador = request.user
    oferta.save()
    # Notificar área comercial y registrar log
    try:
        from usuarios.models import Usuario, Notificacion
        from .models import AutomationLog
        mensaje = f"Oferta rechazada por admin para {oferta.cliente.nombre} {oferta.cliente.apellido}: {oferta.titulo}"
        for u in Usuario.objects.filter(is_staff=True):
            Notificacion.objects.create(usuario=u, mensaje=mensaje)
        AutomationLog.objects.create(
            evento='oferta_rechazada_admin',
            descripcion=mensaje,
            usuario=request.user,
            datos={'oferta_id': oferta.id, 'cliente_id': oferta.cliente_id}
        )
    except Exception:
        pass
    return redirect('ofertas_propuestas')


@login_required
def eliminar_oferta(request, oferta_id):
    # Seguridad: solo permitir vía POST
    if request.method != 'POST':
        return redirect("/automatizacion/propuestas/?ok=0&msg=Confirmaci%C3%B3n%20requerida")
    oferta = get_object_or_404(OfertaPropuesta, pk=oferta_id)
    try:
        oferta.delete()
        return redirect("/automatizacion/propuestas/?ok=1&msg=Oferta%20eliminada")
    except Exception:
        return redirect("/automatizacion/propuestas/?ok=0&msg=No%20se%20pudo%20eliminar")


@csrf_exempt
def mensaje_callback(request):
    """Webhook para actualizar estado de mensajes de ofertas.
    Espera JSON con: estado (enviado|entregado|leido|fallido), oferta_id, cliente_id,
    opcional: canal (email|sms|whatsapp), provider_id, detalle.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método inválido'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    estado = payload.get('estado')
    oferta_id = payload.get('oferta_id')
    cliente_id = payload.get('cliente_id')
    canal = (payload.get('canal') or 'email').lower()
    provider_id = payload.get('provider_id') or ''
    detalle = payload.get('detalle') or ''

    from .models import MensajeOferta, OfertaPropuesta

    # Validaciones básicas
    valid_estados = {k for k, _ in MensajeOferta.ESTADOS}
    valid_canales = {k for k, _ in MensajeOferta.CANALES}
    if not (estado and oferta_id and cliente_id):
        return JsonResponse({'ok': False, 'error': 'Campos requeridos: estado, oferta_id, cliente_id'}, status=400)
    if estado not in valid_estados:
        return JsonResponse({'ok': False, 'error': 'Estado inválido'}, status=400)
    if canal not in valid_canales:
        return JsonResponse({'ok': False, 'error': 'Canal inválido'}, status=400)

    oferta = OfertaPropuesta.objects.filter(pk=oferta_id, cliente_id=cliente_id).first()
    if not oferta:
        return JsonResponse({'ok': False, 'error': 'Oferta/Cliente no encontrado'}, status=404)

    msg = MensajeOferta.objects.create(
        oferta=oferta,
        cliente_id=cliente_id,
        estado=estado,
        canal=canal,
        provider_id=provider_id,
        detalle=detalle,
    )
    return JsonResponse({'ok': True, 'mensaje_id': msg.id})


# --- Ofertas para cliente (confirmación/rechazo) ---
@login_required
def mis_ofertas_cliente(request):
    # Mapear usuario -> cliente por email
    from clientes.models import Cliente
    cliente = Cliente.objects.filter(email=request.user.email).first()
    if not cliente:
        return render(request, 'automatizacion/mis_ofertas.html', {'ofertas': [], 'cliente': None})
    qs = OfertaPropuesta.objects.filter(cliente=cliente, estado__in=['enviada', 'pendiente']).order_by('-creada')
    return render(request, 'automatizacion/mis_ofertas.html', {'ofertas': qs, 'cliente': cliente})


@login_required
def confirmar_oferta_cliente(request, oferta_id):
    oferta = get_object_or_404(OfertaPropuesta, pk=oferta_id)
    # Solo permitir si corresponde al cliente del usuario
    if oferta.cliente.email != request.user.email:
        return redirect('mis_ofertas_cliente')
    oferta.estado = 'aceptada'
    oferta.fecha_validacion = timezone.now()
    oferta.save()
    # Registrar acción del cliente
    try:
        from .models import AccionCliente
        AccionCliente.objects.create(
            cliente=oferta.cliente,
            oferta=oferta,
            tipo='aceptar',
            canal='web',
            detalle='Cliente confirmó la oferta desde el portal',
        )
    except Exception:
        pass
    return redirect('mis_ofertas_cliente')


@login_required
def rechazar_oferta_cliente(request, oferta_id):
    oferta = get_object_or_404(OfertaPropuesta, pk=oferta_id)
    if oferta.cliente.email != request.user.email:
        return redirect('mis_ofertas_cliente')
    oferta.estado = 'rechazada'
    oferta.fecha_validacion = timezone.now()
    oferta.save()
    # Registrar acción del cliente
    try:
        from .models import AccionCliente
        AccionCliente.objects.create(
            cliente=oferta.cliente,
            oferta=oferta,
            tipo='rechazar',
            canal='web',
            detalle='Cliente rechazó la oferta desde el portal',
        )
    except Exception:
        pass
    # Notificar área comercial y registrar log
    try:
        from usuarios.models import Usuario, Notificacion
        from .models import AutomationLog
        mensaje = f"Oferta rechazada por {oferta.cliente.nombre} {oferta.cliente.apellido}: {oferta.titulo}"
        for u in Usuario.objects.filter(is_staff=True):
            Notificacion.objects.create(usuario=u, mensaje=mensaje)
        AutomationLog.objects.create(
            evento='oferta_rechazada',
            descripcion=mensaje,
            usuario=request.user,
            datos={'oferta_id': oferta.id, 'cliente_id': oferta.cliente_id}
        )
    except Exception:
        pass
    return redirect('mis_ofertas_cliente')


@csrf_exempt
def accion_callback(request):
    """Webhook genérico para registrar acciones del cliente.
    Espera JSON con: cliente_id, oferta_id (opcional), tipo (vista|click|aceptar|rechazar|consulta|leido),
    opcional: canal (web|email|sms|whatsapp), detalle, metadata.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método inválido'}, status=405)
    try:
        import json
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    cliente_id = payload.get('cliente_id')
    oferta_id = payload.get('oferta_id')
    tipo = (payload.get('tipo') or '').lower()
    canal = (payload.get('canal') or 'web').lower()
    detalle = payload.get('detalle') or ''
    metadata = payload.get('metadata') or {}

    from .models import AccionCliente, OfertaPropuesta
    # Validaciones básicas
    valid_tipos = {k for k, _ in AccionCliente.TIPOS}
    valid_canales = {k for k, _ in AccionCliente.CANALES}
    if not (cliente_id and tipo):
        return JsonResponse({'ok': False, 'error': 'Campos requeridos: cliente_id, tipo'}, status=400)
    if tipo not in valid_tipos:
        return JsonResponse({'ok': False, 'error': 'Tipo inválido'}, status=400)
    if canal not in valid_canales:
        return JsonResponse({'ok': False, 'error': 'Canal inválido'}, status=400)

    kwargs = {
        'cliente_id': cliente_id,
        'tipo': tipo,
        'canal': canal,
        'detalle': detalle,
        'metadata': metadata,
    }
    if oferta_id:
        of = OfertaPropuesta.objects.filter(pk=oferta_id, cliente_id=cliente_id).first()
        if not of:
            return JsonResponse({'ok': False, 'error': 'Oferta/Cliente no encontrado'}, status=404)
        kwargs['oferta'] = of
    accion = AccionCliente.objects.create(**kwargs)
    return JsonResponse({'ok': True, 'accion_id': accion.id})


# --- Acción manual: generar propuestas de ofertas ---
@login_required
def generar_propuestas(request):
    # Solo staff o grupo Comercial
    if request.method != 'POST':
        return redirect('ofertas_propuestas')
    permitido = request.user.is_staff or request.user.groups.filter(name='Comercial').exists()
    if not permitido:
        return redirect('ofertas_propuestas')
    try:
        from automatizacion.tasks import tarea_generar_ofertas
        resultado = tarea_generar_ofertas()
        return redirect(f"/automatizacion/propuestas/?ok=1&msg={resultado}")
    except Exception as e:
        return redirect(f"/automatizacion/propuestas/?ok=0&msg=Error%20al%20generar:%20{e}")


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


# Logs de Automatización removidos del panel y rutas


# --- Automatización de presupuestos con criterios ponderados (Admin) ---
from django.views.decorators.http import require_POST


@login_required
def compras_propuestas_admin(request):
    from automatizacion.models import CompraPropuesta
    from insumos.models import Insumo
    try:
        from configuracion.services import get_page_size
        page_size = get_page_size()
    except Exception:
        page_size = 10

    # Get all Tintas and Papeles (with grammage in name or category)
    tintas = list(Insumo.objects.filter(categoria__icontains='tinta', activo=True))
    papeles = list(Insumo.objects.filter(categoria__icontains='papel', activo=True))
    # Optionally, filter papeles with grammage in name (e.g., contains 'gr')
    # papeles = [p for p in papeles if 'gr' in p.nombre.lower() or 'gr' in p.categoria.lower()]

    # Get all proposals (excluding instrumentos/calibradores)
    propuestas_qs = CompraPropuesta.objects.select_related('insumo', 'proveedor_recomendado', 'borrador_oc', 'consulta_stock') \
        .exclude(insumo__categoria__icontains='instrumento') \
        .exclude(insumo__categoria__icontains='calibrador')

    # Build a dict: insumo_id -> propuesta
    propuestas_dict = {p.insumo.pk: p for p in propuestas_qs}

    # Compose all insumos to show: union of (tintas + papeles) and ALL insumos de propuestas
    all_insumos = {i.pk: i for i in tintas + papeles}
    for p in propuestas_qs:
        all_insumos[p.insumo.pk] = p.insumo

    # Crear propuestas mínimas automáticamente para insumos sin propuesta
    from automatizacion.models import CompraPropuesta
    from django.db import transaction
    from proveedores.models import Proveedor
    nuevos = []
    with transaction.atomic():
        for insumo in all_insumos.values():
            if insumo.pk not in propuestas_dict:
                proveedor = None
                # Asignar solo si el insumo tiene proveedor relacionado directamente
                if hasattr(insumo, 'proveedor') and insumo.proveedor and getattr(insumo.proveedor, 'activo', True):
                    proveedor = insumo.proveedor
                propuesta = CompraPropuesta.objects.create(
                    insumo=insumo,
                    cantidad_requerida=1,
                    motivo_trigger='faltante_stock',
                    estado='pendiente',
                    proveedor_recomendado=proveedor
                )
                nuevos.append(propuesta)
                propuestas_dict[insumo.pk] = propuesta

    # Volver a obtener todas las propuestas (incluyendo las recién creadas)
    propuestas_qs = CompraPropuesta.objects.select_related('insumo', 'proveedor_recomendado', 'borrador_oc', 'consulta_stock') \
        .exclude(insumo__categoria__icontains='instrumento') \
        .exclude(insumo__categoria__icontains='calibrador')

    # Build rows: solo propuestas reales
    rows = list(propuestas_qs)
    # Sort: propuestas por nombre de insumo
    rows.sort(key=lambda x: str(x.insumo.nombre))

    # Paginate
    paginator = Paginator(rows, page_size)
    page = request.GET.get('page')
    propuestas = paginator.get_page(page)
    return render(request, 'automatizacion/compras_propuestas.html', {'propuestas': propuestas})


@login_required
@require_POST
def consultar_stock_propuesta(request, propuesta_id):
    from automatizacion.models import CompraPropuesta, ConsultaStockProveedor
    propuesta = get_object_or_404(CompraPropuesta, pk=propuesta_id)
    # Simulación de consulta: establecer estado según input admin (si viene)
    estado = request.POST.get('estado')  # 'disponible'|'parcial'|'no'
    detalle = request.POST.get('detalle', '')
    consulta = propuesta.consulta_stock
    if not consulta:
        from decimal import Decimal
        consulta = ConsultaStockProveedor.objects.create(
            proveedor=propuesta.proveedor_recomendado,
            insumo=propuesta.insumo,
            cantidad=int(Decimal(str(propuesta.cantidad_requerida))),
            estado='pendiente',
            respuesta={}
        )
        propuesta.consulta_stock = consulta
    if estado in {'disponible', 'parcial', 'no'}:
        consulta.estado = estado
        consulta.respuesta = {'detalle': detalle}
        consulta.save()
        propuesta.estado = 'respuesta_disponible' if estado == 'disponible' else ('parcial' if estado == 'parcial' else 'no_disponible')
        propuesta.save()
        messages.success(request, f"Consulta de stock marcada: {estado}.")
    else:
        consulta.estado = 'pendiente'
        consulta.save()
        messages.info(request, "Consulta de stock pendiente.")
    return redirect('compras_propuestas')


from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
@login_required
@require_POST

def aceptar_compra_propuesta(request, propuesta_id):
    from automatizacion.models import CompraPropuesta
    propuesta = get_object_or_404(CompraPropuesta, pk=propuesta_id)
    oc = propuesta.borrador_oc
    if oc:
        oc.estado = 'confirmada'
        oc.save()
    # Impacto en registros: actualizar proveedor del insumo y stock proyectado
    try:
        insumo = propuesta.insumo
        proveedor = propuesta.proveedor_recomendado or (oc.proveedor if oc else None)
        if proveedor:
            insumo.proveedor = proveedor
        # Incrementa stock como compromiso asegurado (pendiente de recepción)
        insumo.stock = (insumo.stock or 0) + int(propuesta.cantidad_requerida or 0)
        insumo.save(update_fields=['proveedor', 'stock'])
    except Exception:
        pass
    propuesta.estado = 'aceptada'
    propuesta.administrador = request.user
    propuesta.decision = 'aceptar'
    propuesta.comentario_admin = request.POST.get('comentario', '')
    # Feedback opcional
    try:
        feedback = {
            'precio': float(request.POST.get('feedback_precio', 0) or 0),
            'cumplimiento': float(request.POST.get('feedback_cumplimiento', 0) or 0),
            'incidencias': float(request.POST.get('feedback_incidencias', 0) or 0),
            'disponibilidad': float(request.POST.get('feedback_disponibilidad', 0) or 0),
        }
        propuesta.feedback_pesos = feedback
        from automatizacion.api.services import ProveedorInteligenteService
        ProveedorInteligenteService.actualizar_pesos_feedback(feedback)
    except Exception:
        pass
    propuesta.save()

    # --- Enviar orden de compra al proveedor por email ---
    if oc and oc.proveedor and oc.proveedor.email:
        try:
            # Renderizar el cuerpo del email usando el mismo template de orden de compra
            context = {
                'orden': oc,
                'proveedor': oc.proveedor,
                'empresa': {
                    'razon_social': 'Imprenta Tucán S.A.',
                    'cuit': '30-12345678-9',
                    'domicilio': 'Av. Principal 123, Tucumán',
                    'telefono': '381-4000000',
                    'email': 'info@imprentatucan.com',
                    'condicion_iva': 'Responsable Inscripto',
                },
                'subtotal': '{:.2f}'.format(float(oc.insumo.precio_unitario) * oc.cantidad),
                'iva': '{:.2f}'.format(float(oc.insumo.precio_unitario) * oc.cantidad * 0.21),
                'total': '{:.2f}'.format(float(oc.insumo.precio_unitario) * oc.cantidad * 1.21),
            }
            html_message = render_to_string('pedidos/orden_compra_detalle.html', context)
            send_mail(
                subject=f"Orden de Compra #{oc.id:06d} - Imprenta Tucán",
                message="Adjuntamos la orden de compra generada.",
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@imprentatucan.com'),
                recipient_list=[oc.proveedor.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception as e:
            messages.warning(request, f"No se pudo enviar el email al proveedor: {e}")

    messages.success(request, 'Propuesta aceptada. Orden confirmada, abastecimiento actualizado y orden enviada al proveedor.')
    return redirect('compras_propuestas')


@login_required
@require_POST
def rechazar_compra_propuesta(request, propuesta_id):
    from automatizacion.models import CompraPropuesta
    propuesta = get_object_or_404(CompraPropuesta, pk=propuesta_id)
    oc = propuesta.borrador_oc
    if oc:
        oc.estado = 'rechazada'
        oc.save()
    propuesta.estado = 'rechazada'
    propuesta.administrador = request.user
    propuesta.decision = 'rechazar'
    propuesta.comentario_admin = request.POST.get('comentario', '')
    propuesta.save()
    return redirect('compras_propuestas')


@login_required
def recalcular_alternativo_propuesta(request, propuesta_id):
    from automatizacion.models import CompraPropuesta
    from automatizacion.api.services import ProveedorInteligenteService
    propuesta = get_object_or_404(CompraPropuesta, pk=propuesta_id)
    # Elegir alternativa (segundo mejor)
    alt = None
    try:
        # Generar ranking simple y tomar segundo
        from proveedores.models import Proveedor
        candidatos = []
        for p in Proveedor.objects.filter(activo=True):
            sc = ProveedorInteligenteService.calcular_score(p, propuesta.insumo)
            candidatos.append((p, sc))
        candidatos.sort(key=lambda x: x[1], reverse=True)
        if len(candidatos) > 1:
            alt = candidatos[1][0]
    except Exception:
        alt = None
    if alt:
        propuesta.proveedor_recomendado = alt
        propuesta.estado = 'modificada'
        propuesta.decision = 'modificar'
        propuesta.administrador = request.user
        propuesta.save()
        oc = propuesta.borrador_oc
        if oc:
            oc.proveedor = alt
            oc.save()
    return redirect('compras_propuestas')


@login_required
def generar_compras_propuestas_demo(request):
    # Ejecuta la lógica de generación de propuestas (sin Celery) y redirige a la lista
    try:
        from automatizacion.tasks import tarea_automatizacion_presupuestos_ponderada
        tarea_automatizacion_presupuestos_ponderada()
        messages.success(request, 'Se generaron propuestas automáticamente.')
    except Exception as e:
        messages.warning(request, f'No se pudieron generar propuestas: {e}')
    return redirect('compras_propuestas')


@login_required
def recalcular_scores_proveedores(request):
    """Acción rápida: recalcula `ScoreProveedor` para todos los proveedores activos."""
    try:
        from automatizacion.tasks import tarea_recalcular_scores_proveedores
        tarea_recalcular_scores_proveedores()
        messages.success(request, 'Scores de proveedores recalculados correctamente.')
    except Exception as e:
        messages.warning(request, f'No se pudieron recalcular los scores: {e}')
    # Volver al panel de automatización para visualizar cambios
    return redirect('automatizacion_panel')


@csrf_exempt
def webhook_consulta_stock(request, propuesta_id):
    """Webhook externo para que proveedores reporten disponibilidad de stock.
    Autenticación simple por token en encabezado `X-Webhook-Token` o parámetro `token`.
    """
    from automatizacion.models import CompraPropuesta, ConsultaStockProveedor
    from configuracion.models import Parametro
    # Validación de token
    token = request.headers.get('X-Webhook-Token') or request.POST.get('token') or request.GET.get('token')
    expected = Parametro.get('WEBHOOK_TOKEN', '')
    if not expected or token != expected:
        return JsonResponse({'error': 'forbidden'}, status=403)
    # Datos
    estado = request.POST.get('estado') or request.GET.get('estado')  # 'disponible'|'parcial'|'no'
    detalle = request.POST.get('detalle') or request.GET.get('detalle') or ''
    propuesta = get_object_or_404(CompraPropuesta, pk=propuesta_id)
    consulta = propuesta.consulta_stock
    if not consulta:
        # crear consulta si no existiera
        consulta = ConsultaStockProveedor.objects.create(
            proveedor=propuesta.proveedor_recomendado,
            insumo=propuesta.insumo,
            cantidad=int(propuesta.cantidad_requerida or 0),
            estado='pendiente',
            respuesta={}
        )
        propuesta.consulta_stock = consulta
    if estado in {'disponible', 'parcial', 'no'}:
        consulta.estado = estado
        consulta.respuesta = {'detalle': detalle}
        consulta.save()
        propuesta.estado = 'respuesta_disponible' if estado == 'disponible' else ('parcial' if estado == 'parcial' else 'no_disponible')
        propuesta.save()
        return JsonResponse({'ok': True, 'estado': estado})
    else:
        consulta.estado = 'pendiente'
        consulta.save()
        return JsonResponse({'ok': True, 'estado': 'pendiente'})
