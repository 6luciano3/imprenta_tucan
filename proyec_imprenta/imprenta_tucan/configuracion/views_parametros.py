from django.shortcuts import render, redirect
from django.contrib import messages
from configuracion.models import Parametro, GrupoParametro
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET", "POST"])
def parametros_automatizacion(request):
    grupo = GrupoParametro.objects.filter(codigo="AUTOMATIZACION").first()
    if not grupo:
        parametros = []
    else:
        parametros = Parametro.objects.filter(grupo=grupo, activo=True, editable=True)

    if request.method == "POST":
        for p in parametros:
            nuevo_valor = request.POST.get(f"valor_{p.codigo}")
            if nuevo_valor is not None:
                p.valor = nuevo_valor
                p.save()
        messages.success(request, "Parámetros actualizados correctamente.")
        return redirect("/configuracion/parametros/")

    return render(request, "configuracion/parametros_automatizacion.html", {
        "parametros": parametros,
        "grupo": grupo,
    })
