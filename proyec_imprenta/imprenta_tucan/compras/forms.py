from django import forms
from django.forms import formset_factory
from .models import OrdenCompra, DetalleOrdenCompra, Remito, DetalleRemito, EstadoCompra
from proveedores.models import Proveedor
from insumos.models import Insumo


class OrdenCompraForm(forms.ModelForm):
    class Meta:
        model = OrdenCompra
        fields = ["solicitud_cotizacion", "proveedor", "estado", "fecha_recepcion", "observaciones"]
        widgets = {
            "solicitud_cotizacion": forms.Select(attrs={"class": "form-select", "id": "id_solicitud_cotizacion"}),
            "proveedor": forms.Select(attrs={"class": "form-select", "required": True}),
            "estado": forms.Select(attrs={"class": "form-select", "required": True}),
            "fecha_recepcion": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        self.fields["proveedor"].queryset = Proveedor.objects.filter(activo=True).order_by("nombre")
        self.fields["proveedor"].label_from_instance = lambda obj: obj.nombre
        self.fields["estado"].queryset = EstadoCompra.objects.all()
        self.fields["fecha_recepcion"].label = "Fecha de Recepcion"
        # Defaults automaticos
        if not self.initial.get("fecha_recepcion"):
            self.initial["fecha_recepcion"] = timezone.now().date()
        if not self.initial.get("estado"):
            try:
                estado_recibida = EstadoCompra.objects.get(nombre="Recibida")
                self.initial["estado"] = estado_recibida.pk
            except EstadoCompra.DoesNotExist:
                pass
        from automatizacion.models import SolicitudCotizacion
        self.fields["solicitud_cotizacion"].queryset = SolicitudCotizacion.objects.filter(
            estado="confirmada"
        ).select_related("proveedor").order_by("-creada")
        self.fields["solicitud_cotizacion"].required = False
        self.fields["solicitud_cotizacion"].label = "Importar desde Solicitud de Cotizacion (opcional)"
        self.fields["solicitud_cotizacion"].label_from_instance = lambda obj: f"SC-{obj.pk:04d} | {obj.proveedor} | {obj.creada.strftime('%d/%m/%Y')}"


class DetalleOrdenCompraForm(forms.Form):
    insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.filter(activo=True).order_by("nombre"),
        widget=forms.Select(attrs={"class": "form-select insumo-select"}),
        label="Insumo"
    )
    cantidad = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
        label="Cantidad"
    )
    precio_unitario = forms.DecimalField(
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
        label="Precio Unitario"
    )

    def subtotal(self):
        cd = self.cleaned_data
        return cd.get("cantidad", 0) * cd.get("precio_unitario", 0)


DetalleOrdenCompraFormSet = formset_factory(DetalleOrdenCompraForm, extra=1, min_num=1, validate_min=True)


class RemitoForm(forms.ModelForm):
    class Meta:
        model = Remito
        fields = ["proveedor", "numero", "fecha", "orden_compra", "observaciones"]
        widgets = {
            "proveedor": forms.Select(attrs={"class": "form-select", "required": True}),
            "numero": forms.TextInput(attrs={"class": "form-control", "required": True, "placeholder": "Ej: R-0001"}),
            "fecha": forms.DateInput(attrs={"class": "form-control", "type": "date", "required": True}),
            "orden_compra": forms.Select(attrs={"class": "form-select"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(activo=True).order_by("nombre")
        self.fields["proveedor"].label_from_instance = lambda obj: obj.nombre
        self.fields["orden_compra"].queryset = OrdenCompra.objects.exclude(
            estado__nombre="Cancelada"
        ).order_by("-creado_en")
        self.fields["orden_compra"].required = False
        self.fields["orden_compra"].label_from_instance = lambda obj: str(obj)


class DetalleRemitoForm(forms.Form):
    insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.filter(activo=True).order_by("nombre"),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Insumo"
    )
    cantidad = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
        label="Cantidad"
    )


DetalleRemitoFormSet = formset_factory(DetalleRemitoForm, extra=1, min_num=1, validate_min=True)
