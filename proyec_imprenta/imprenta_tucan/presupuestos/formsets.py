from django.forms import modelformset_factory
from .forms_detalle import PresupuestoDetalleForm
from .models import PresupuestoDetalle

PresupuestoDetalleFormSet = modelformset_factory(
    PresupuestoDetalle,
    form=PresupuestoDetalleForm,
    extra=1,
    can_delete=True
)
