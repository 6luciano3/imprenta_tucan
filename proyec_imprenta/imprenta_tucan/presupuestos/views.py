from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Presupuesto, PresupuestoDetalle
from .forms import PresupuestoForm
from .formsets import PresupuestoDetalleFormSet


def index(request):
    return redirect('lista_presupuestos')


def lista_presupuestos(request):
    query = request.GET.get('q', '') or request.GET.get('criterio', '')
    order_by = request.GET.get('order_by', 'fecha')
    direction = request.GET.get('direction', 'desc')

    valid_order_fields = ['id', 'numero', 'cliente__apellido', 'cliente__nombre', 'fecha', 'validez', 'total', 'estado']
    if order_by not in valid_order_fields:
        order_by = 'fecha'

    qs = Presupuesto.objects.select_related('cliente').all()
    if query:
        qs = qs.filter(
            Q(numero__icontains=query) |
            Q(cliente__nombre__icontains=query) |
            Q(cliente__apellido__icontains=query) |
            Q(cliente__razon_social__icontains=query) |
            Q(estado__icontains=query)
        )

    order_field = f'-{order_by}' if direction == 'desc' else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page = request.GET.get('page')
    presupuestos = paginator.get_page(page)

    return render(request, 'presupuestos/lista_presupuestos.html', {
        'presupuestos': presupuestos,
        'query': query,
        'order_by': order_by,
        'direction': direction,
    })


def crear_presupuesto(request):
    from productos.models import Producto
    productos_queryset = Producto.objects.filter(activo=True)
    if request.method == 'POST':
        form = PresupuestoForm(request.POST)
        total_forms = int(request.POST.get('form-TOTAL_FORMS', 1))
        PresupuestoDetalleFormSetCustom = PresupuestoDetalleFormSet
        formset = PresupuestoDetalleFormSetCustom(request.POST, queryset=PresupuestoDetalle.objects.none())
        # Forzar queryset de productos en cada form del formset
        for f in formset.forms:
            f.fields['producto'].queryset = productos_queryset
        # Eliminar formularios vacíos
        formset.forms = [f for f in formset.forms if f.has_changed()]
        if form.is_valid() and formset.is_valid():
            # Generar número automático
            from datetime import datetime
            from presupuestos.models import Presupuesto
            ultimo = Presupuesto.objects.order_by('-id').first()
            if ultimo and ultimo.numero and ultimo.numero.startswith('P-'):
                try:
                    last_num = int(ultimo.numero.split('-')[1])
                except Exception:
                    last_num = ultimo.id
            else:
                last_num = ultimo.id if ultimo else 0
            nuevo_numero = f"P-{last_num+1:05d}"
            presupuesto = form.save(commit=False)
            presupuesto.numero = nuevo_numero
            presupuesto.save()
            detalles = formset.save(commit=False)
            for detalle in detalles:
                detalle.presupuesto = presupuesto
                detalle.save()
            return redirect('presupuestos:lista')
    else:
        form = PresupuestoForm()
        formset = PresupuestoDetalleFormSet(queryset=PresupuestoDetalle.objects.none())
        for f in formset.forms:
            f.fields['producto'].queryset = productos_queryset
    return render(request, 'presupuestos/crear_presupuesto.html', {'form': form, 'formset': formset})


def editar_presupuesto(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    if request.method == 'POST':
        form = PresupuestoForm(request.POST, instance=presupuesto)
        if form.is_valid():
            form.save()
            return redirect('presupuestos:lista')
    else:
        form = PresupuestoForm(instance=presupuesto)
    return render(request, 'presupuestos/crear_presupuesto.html', {'form': form, 'editar': True, 'presupuesto': presupuesto})


def eliminar_presupuesto(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    if request.method == 'POST':
        presupuesto.delete()
        return redirect('presupuestos:lista')
    return render(request, 'presupuestos/eliminar_presupuesto.html', {'presupuesto': presupuesto})
