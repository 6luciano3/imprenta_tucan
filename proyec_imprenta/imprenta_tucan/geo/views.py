from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Ciudad
from .forms import CiudadForm
from django.views.decorators.clickjacking import xframe_options_sameorigin


@xframe_options_sameorigin
def lista_ciudades(request):
    query = request.GET.get('q', '').strip()
    order_by = request.GET.get('order_by', 'nombre')
    direction = request.GET.get('direction', 'asc')
    next_url = request.GET.get('next')  # Propagar para crear ciudad conservando retorno
    popup = request.GET.get('popup')

    valid_order_fields = ['id', 'nombre', 'provincia', 'activo']
    if order_by not in valid_order_fields:
        order_by = 'nombre'

    qs = Ciudad.objects.all()
    if query:
        qs = qs.filter(nombre__icontains=query)

    order_field = f'-{order_by}' if direction == 'desc' else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page = request.GET.get('page')
    ciudades = paginator.get_page(page)

    return render(request, 'geo/ciudades/lista_ciudades.html', {
        'ciudades': ciudades,
        'query': query,
        'order_by': order_by,
        'direction': direction,
        'next_url': next_url,
        'popup': popup,
    })


@xframe_options_sameorigin
def crear_ciudad(request):
    if request.method == 'POST':
        form = CiudadForm(request.POST)
        if form.is_valid():
            ciudad = form.save()
            messages.success(request, f'La ciudad {ciudad.nombre} fue creada.')
            popup = request.GET.get('popup') or request.POST.get('popup')
            next_url = request.GET.get('next') or request.POST.get('next')
            # En modo popup permanecemos dentro del listado para seguir gestionando
            if popup:
                from urllib.parse import urlencode
                base = 'lista_ciudades'
                params = {}
                if next_url:
                    params['next'] = next_url
                params['popup'] = '1'
                redirect_url = f"{redirect(base).url}?" + urlencode(params)
                return redirect(redirect_url)
            if next_url:
                from urllib.parse import urlencode
                sep = '&' if ('?' in next_url) else '?'
                return redirect(f"{next_url}{sep}" + urlencode({'ciudad': ciudad.nombre}))
            return redirect('lista_ciudades')
        else:
            messages.error(request, 'Corrija los errores.')
    else:
        form = CiudadForm()
    popup = request.GET.get('popup') or request.POST.get('popup')
    return render(request, 'geo/ciudades/alta_ciudad.html', {'form': form, 'popup': popup})


@xframe_options_sameorigin
def editar_ciudad(request, id):
    ciudad = get_object_or_404(Ciudad, id=id)
    if request.method == 'POST':
        form = CiudadForm(request.POST, instance=ciudad)
        if form.is_valid():
            ciudad = form.save()
            messages.success(request, f'La ciudad {ciudad.nombre} fue actualizada.')
            popup = request.GET.get('popup') or request.POST.get('popup')
            next_url = request.GET.get('next') or request.POST.get('next')
            if popup:
                from urllib.parse import urlencode
                params = {}
                if next_url:
                    params['next'] = next_url
                params['popup'] = '1'
                return redirect(f"{redirect('lista_ciudades').url}?" + urlencode(params))
            if next_url:
                return redirect(next_url)
            return redirect('lista_ciudades')
        else:
            messages.error(request, 'Corrija los errores.')
    else:
        form = CiudadForm(instance=ciudad)
    popup = request.GET.get('popup') or request.POST.get('popup')
    return render(request, 'geo/ciudades/editar_ciudad.html', {'form': form, 'ciudad': ciudad, 'popup': popup})


@xframe_options_sameorigin
def eliminar_ciudad(request, id):
    ciudad = get_object_or_404(Ciudad, id=id)
    if request.method == 'POST':
        nombre = ciudad.nombre
        ciudad.delete()
        messages.success(request, f'La ciudad {nombre} fue eliminada.')
        popup = request.GET.get('popup') or request.POST.get('popup')
        next_url = request.GET.get('next') or request.POST.get('next')
        if popup:
            from urllib.parse import urlencode
            params = {}
            if next_url:
                params['next'] = next_url
            params['popup'] = '1'
            return redirect(f"{redirect('lista_ciudades').url}?" + urlencode(params))
        if next_url:
            return redirect(next_url)
        return redirect('lista_ciudades')
    return redirect('lista_ciudades')


@xframe_options_sameorigin
def activar_ciudad(request, id):
    ciudad = get_object_or_404(Ciudad, id=id)
    if request.method == 'POST':
        ciudad.activo = not ciudad.activo
        ciudad.save()
        estado = 'activada' if ciudad.activo else 'desactivada'
        messages.success(request, f'La ciudad {ciudad.nombre} fue {estado}.')
        popup = request.GET.get('popup') or request.POST.get('popup')
        next_url = request.GET.get('next') or request.POST.get('next')
        if popup:
            from urllib.parse import urlencode
            params = {}
            if next_url:
                params['next'] = next_url
            params['popup'] = '1'
            return redirect(f"{redirect('lista_ciudades').url}?" + urlencode(params))
        if next_url:
            return redirect(next_url)
        return redirect('lista_ciudades')
    return redirect('lista_ciudades')
