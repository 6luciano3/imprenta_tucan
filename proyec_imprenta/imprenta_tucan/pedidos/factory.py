class ProductoFactory:
    @staticmethod
    def crear(tipo, **kwargs):
        from productos.models import Producto
        p = Producto(tipo=tipo, **kwargs)
        return p
