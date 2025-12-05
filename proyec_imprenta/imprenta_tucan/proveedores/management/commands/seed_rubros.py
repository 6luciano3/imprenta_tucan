from django.core.management.base import BaseCommand
from proveedores.models import Rubro


class Command(BaseCommand):
    help = 'Carga 10 rubros de ejemplo para la industria gráfica.'

    def handle(self, *args, **options):
        rubros = [
            ("Tintas offset", "Tintas especiales para impresión offset, alta calidad y variedad de colores."),
            ("Papeles para offset", "Papeles diseñados para impresión offset, diferentes gramajes y acabados."),
            ("Mantillas y cauchos", "Materiales para transferencia de tinta en prensas offset."),
            ("Planchas presensibilizadas", "Planchas listas para grabado y uso en impresión offset."),
            ("Soluciones humectantes", "Líquidos para mantener la humedad y calidad en impresión offset."),
            ("Químicos para offset", "Productos químicos para limpieza y mantenimiento de equipos offset."),
            ("Rodillos y repuestos", "Rodillos y piezas de recambio para maquinaria offset."),
            ("Barnices UV y acrílicos", "Barnices para acabados especiales, protección y brillo."),
            ("Alcohol isopropílico y solventes", "Solventes para limpieza y preparación de equipos de impresión."),
            ("Gomas arábigas y soluciones de limpieza", "Soluciones para limpieza y conservación de planchas y rodillos."),
            ("Mezclas de tintas", "Combinaciones de tintas para efectos y colores personalizados."),
            ("Papeles y cartulinas para impresión", "Materiales para impresión comercial y publicitaria."),
            ("Adhesivos de encuadernación", "Pegamentos y adhesivos para procesos de encuadernación."),
            ("Insumos offset generales", "Accesorios y materiales de uso general en impresión offset."),
            ("Limpiadores, desengrasantes y solventes", "Productos para limpieza profunda de maquinaria y piezas."),
            ("Cauchos y mantillas", "Materiales para transferencia y protección en impresión offset."),
            ("Insumos técnicos y mantenimiento", "Herramientas y productos para mantenimiento técnico de equipos."),
            ("Rodillos, correas, engranajes", "Componentes mecánicos para el funcionamiento de prensas offset."),
            ("Tintas de alta densidad", "Tintas especiales para impresiones con gran cobertura y saturación."),
            ("Cartones duplex y triplex", "Cartones de diferentes capas para packaging y aplicaciones gráficas."),
            ("Solventes y trapos técnicos", "Materiales para limpieza y mantenimiento profesional."),
            ("Químicos para planchas", "Productos para el tratamiento y limpieza de planchas de impresión."),
            ("Recarga de tintas y químicos", "Servicios y productos para recarga y reposición de insumos."),
            ("Planchas térmicas y violetas", "Planchas avanzadas para impresión offset de alta tecnología."),
            ("Equipos de medición de color", "Instrumentos para control y ajuste de color en impresión."),
            ("Papeles y sustratos offset", "Variedad de papeles y materiales para impresión offset."),
            ("Lubricantes y aceites técnicos", "Lubricantes especializados para maquinaria gráfica."),
            ("Distribución integral de insumos offset", "Servicios de logística y distribución de insumos gráficos."),
            ("Preprensa y planchas offset", "Materiales y equipos para procesos de preprensa y planchas."),
            ("Químicos y soluciones técnicas", "Soluciones químicas para procesos gráficos avanzados."),
        ]
        Rubro.objects.all().delete()
        for nombre, descripcion in rubros:
            obj, created = Rubro.objects.get_or_create(
                nombre=nombre, defaults={"descripcion": descripcion, "activo": True})
            self.stdout.write(self.style.SUCCESS(f"Rubro '{nombre}' cargado."))
        self.stdout.write(self.style.SUCCESS("Carga de rubros detallados finalizada."))
