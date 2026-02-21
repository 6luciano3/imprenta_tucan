from rest_framework import serializers
from .models import ComboOferta, ComboOfertaProducto
from productos.models import Producto

class ComboOfertaProductoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    class Meta:
        model = ComboOfertaProducto
        fields = ['id', 'producto', 'producto_nombre', 'cantidad']

class ComboOfertaSerializer(serializers.ModelSerializer):
    productos = ComboOfertaProductoSerializer(source='comboofertaproducto_set', many=True, read_only=True)
    class Meta:
        model = ComboOferta
        fields = [
            'id', 'cliente', 'nombre', 'descripcion', 'descuento', 'fecha_inicio', 'fecha_fin',
            'enviada', 'aceptada', 'rechazada', 'fecha_envio', 'fecha_respuesta', 'productos'
        ]
