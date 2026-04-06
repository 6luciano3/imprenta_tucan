# productos/forms.py
from django import forms
from .models import Producto, CategoriaProducto, TipoProducto, UnidadMedida, ProductoInsumo


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombreProducto', 'descripcion', 'precioUnitario',
                  'categoriaProducto', 'tipoProducto', 'unidadMedida',
                  'formula', 'activo']
        widgets = {
            'nombreProducto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Descripción (opcional)', 'rows': 3}),
            'precioUnitario': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Precio unitario', 'step': '0.01', 'min': '0', 'max': '1000000'}),
            'categoriaProducto': forms.Select(attrs={'class': 'form-select'}),
            'tipoProducto': forms.Select(attrs={'class': 'form-select'}),
            'unidadMedida': forms.Select(attrs={'class': 'form-select'}),
            'formula': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from configuracion.models import Formula, UnidadDeMedida
        self.fields['formula'].queryset = Formula.objects.filter(activo=True).order_by('codigo')
        self.fields['formula'].required = False
        self.fields['formula'].empty_label = '— Sin fórmula (opcional) —'
        self.fields['unidadMedida'].queryset = UnidadDeMedida.objects.filter(activo=True).order_by('nombre')

    def clean_nombreProducto(self):
        nombre = self.cleaned_data.get('nombreProducto')
        if not nombre:
            raise forms.ValidationError('El nombre del producto es obligatorio.')
        qs = Producto.objects.filter(nombreProducto__iexact=nombre)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f'Ya existe un producto con el nombre "{nombre}".')
        return nombre

    def clean_precioUnitario(self):
        precio = self.cleaned_data.get('precioUnitario')
        if precio is None or precio < 0:
            raise forms.ValidationError('El precio unitario debe ser un número positivo.')
        return precio


class CategoriaProductoForm(forms.ModelForm):
    class Meta:
        model = CategoriaProducto
        fields = ['nombreCategoria', 'descripcion']
        widgets = {
            'nombreCategoria': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la categoría'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Descripción (opcional)', 'rows': 3}),
        }


class TipoProductoForm(forms.ModelForm):
    class Meta:
        model = TipoProducto
        fields = ['nombreTipoProducto', 'descripcion']
        widgets = {
            'nombreTipoProducto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del tipo'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Descripción (opcional)', 'rows': 3}),
        }


class UnidadMedidaForm(forms.ModelForm):
    class Meta:
        model = UnidadMedida
        fields = ['nombreUnidad', 'abreviatura']
        widgets = {
            'nombreUnidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la unidad (p. ej., Metro)'}),
            'abreviatura': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Abreviatura (p. ej., m)'}),
        }


class ProductoInsumoAltaForm(forms.ModelForm):
    """Form para agregar insumos inline durante el alta de producto."""
    class Meta:
        model = ProductoInsumo
        fields = ['insumo', 'cantidad_por_unidad', 'es_costo_fijo']
        widgets = {
            'insumo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_por_unidad': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.001', 'min': '0.001', 'placeholder': 'Cantidad'
            }),
            'es_costo_fijo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'insumo': 'Insumo',
            'cantidad_por_unidad': 'Cant. por unidad',
            'es_costo_fijo': 'Costo fijo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from insumos.models import Insumo
        self.fields['insumo'].queryset = Insumo.objects.filter(tipo='directo').order_by('nombre')
        self.fields['insumo'].empty_label = '— Seleccionar insumo —'

    def clean_cantidad_por_unidad(self):
        cantidad = self.cleaned_data.get('cantidad_por_unidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que cero.')
        return cantidad


class ProductoInsumoForm(forms.ModelForm):
    class Meta:
        model = ProductoInsumo
        fields = ['insumo', 'cantidad_por_unidad', 'es_costo_fijo']
        widgets = {
            'insumo': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'cantidad_por_unidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cantidad necesaria por unidad de producto',
                'step': '0.001',
                'min': '0',
                'required': True
            }),
            'es_costo_fijo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'insumo': 'Insumo requerido',
            'cantidad_por_unidad': 'Cantidad por unidad',
            'es_costo_fijo': 'Costo fijo',
        }

    def __init__(self, *args, **kwargs):
        producto = kwargs.pop('producto', None)
        super().__init__(*args, **kwargs)
        self._producto = producto

        # Si ya hay un insumo asignado, excluirlo de las opciones
        from insumos.models import Insumo
        if producto:
            insumos_ya_usados = ProductoInsumo.objects.filter(producto=producto).values_list('insumo_id', flat=True)
            self.fields['insumo'].queryset = Insumo.objects.filter(tipo='directo').exclude(idInsumo__in=insumos_ya_usados).order_by('nombre')
        else:
            self.fields['insumo'].queryset = Insumo.objects.filter(tipo='directo').order_by('nombre')
    
    def clean_insumo(self):
        insumo = self.cleaned_data.get('insumo')
        if insumo and self.instance.pk is None:
            # Solo al agregar: verificar que el insumo no esté ya en la receta del producto
            producto = getattr(self, '_producto', None)
            if producto and ProductoInsumo.objects.filter(producto=producto, insumo=insumo).exists():
                raise forms.ValidationError(f'"{insumo.nombre}" ya está en la receta de este producto.')
        return insumo

    def clean_cantidad_por_unidad(self):
        cantidad = self.cleaned_data.get('cantidad_por_unidad')
        if cantidad is None or cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser un número positivo mayor que cero.')
        return cantidad
