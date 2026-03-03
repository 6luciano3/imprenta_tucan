# productos/forms.py
from django import forms
from .models import Producto, CategoriaProducto, TipoProducto, UnidadMedida, ProductoInsumo


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombreProducto', 'descripcion', 'precioUnitario',
                  'categoriaProducto', 'tipoProducto', 'unidadMedida']
        widgets = {
            'nombreProducto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Descripción (opcional)', 'rows': 3}),
            'precioUnitario': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Precio unitario', 'step': '0.01', 'min': '0'}),
            'categoriaProducto': forms.Select(attrs={'class': 'form-select'}),
            'tipoProducto': forms.Select(attrs={'class': 'form-select'}),
            'unidadMedida': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_precioUnitario(self):
        precio = self.cleaned_data.get('precioUnitario')
        if precio is None or precio < 0:
            raise forms.ValidationError('El precio unitario debe ser un número positivo.')
        return precio

    def clean_nombreProducto(self):
        nombre = self.cleaned_data.get('nombreProducto')
        if not nombre:
            raise forms.ValidationError('El nombre del producto es obligatorio.')
        return nombre


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


class ProductoInsumoForm(forms.ModelForm):
    class Meta:
        model = ProductoInsumo
        fields = ['insumo', 'cantidad_por_unidad']
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
        }
        labels = {
            'insumo': 'Insumo requerido',
            'cantidad_por_unidad': 'Cantidad por unidad',
        }

    def __init__(self, *args, **kwargs):
        producto = kwargs.pop('producto', None)
        super().__init__(*args, **kwargs)
        
        # Si ya hay un insumo asignado, excluirlo de las opciones
        if producto:
            insumos_ya_usados = ProductoInsumo.objects.filter(producto=producto).values_list('insumo_id', flat=True)
            from insumos.models import Insumo
            self.fields['insumo'].queryset = Insumo.objects.exclude(idInsumo__in=insumos_ya_usados).order_by('nombre')
        else:
            from insumos.models import Insumo
            self.fields['insumo'].queryset = Insumo.objects.all().order_by('nombre')
    
    def clean_cantidad_por_unidad(self):
        cantidad = self.cleaned_data.get('cantidad_por_unidad')
        if cantidad is None or cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser un número positivo mayor que cero.')
        return cantidad
