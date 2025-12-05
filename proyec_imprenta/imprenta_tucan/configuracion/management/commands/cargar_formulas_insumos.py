from django.core.management.base import BaseCommand
from django.db import transaction
from insumos.models import Insumo
from configuracion.models import Formula
import json


class Command(BaseCommand):
    help = 'Carga todas las fórmulas de insumos en la base de datos.'

    FORMULAS = [
        # Tintas
        {'insumo': 'Tinta Negra Offset grs', 'codigo': 'TINTA_NEGRA_OFFSET_GRS', 'descripcion': 'Consumo de Tinta Negra Offset (en gramos).', 'expresion': '(ancho_cm * alto_cm * tirada * cobertura) / 10000', 'variables': {
            'ancho_cm': 'Ancho del pliego en cm', 'alto_cm': 'Alto del pliego en cm', 'tirada': 'Cantidad de impresiones', 'cobertura': 'Cobertura en g/m2'}},
        {'insumo': 'Tinta Cyan Offset', 'codigo': 'TINTA_CYAN_OFFSET', 'descripcion': 'Consumo de Tinta Cyan Offset (en gramos).', 'expresion': '(ancho_cm * alto_cm * tirada * cobertura) / 10000', 'variables': {
            'ancho_cm': 'Ancho del pliego en cm', 'alto_cm': 'Alto del pliego en cm', 'tirada': 'Cantidad de impresiones', 'cobertura': 'Cobertura en g/m2'}},
        {'insumo': 'Tinta Magenta Offset 1 kg', 'codigo': 'TINTA_MAGENTA_OFFSET_1KG', 'descripcion': 'Consumo de Tinta Magenta Offset (en gramos).', 'expresion': '(ancho_cm * alto_cm * tirada * cobertura) / 10000', 'variables': {
            'ancho_cm': 'Ancho del pliego en cm', 'alto_cm': 'Alto del pliego en cm', 'tirada': 'Cantidad de impresiones', 'cobertura': 'Cobertura en g/m2'}},
        {'insumo': 'Tinta Amarilla Offset 1 kg', 'codigo': 'TINTA_AMARILLA_OFFSET_1KG', 'descripcion': 'Consumo de Tinta Amarilla Offset (en gramos).', 'expresion': '(ancho_cm * alto_cm * tirada * cobertura) / 10000', 'variables': {
            'ancho_cm': 'Ancho del pliego en cm', 'alto_cm': 'Alto del pliego en cm', 'tirada': 'Cantidad de impresiones', 'cobertura': 'Cobertura en g/m2'}},
        {'insumo': 'Tinta Pantone 185C 1 kg', 'codigo': 'TINTA_PANTONE_185C_1KG', 'descripcion': 'Consumo de Tinta Pantone 185C (en gramos).', 'expresion': '(ancho_cm * alto_cm * tirada * cobertura) / 10000', 'variables': {
            'ancho_cm': 'Ancho del pliego en cm', 'alto_cm': 'Alto del pliego en cm', 'tirada': 'Cantidad de impresiones', 'cobertura': 'Cobertura en g/m2'}},
        {'insumo': 'Tinta Pantone Reflex Blue 1 kg', 'codigo': 'TINTA_PANTONE_REFLEX_BLUE_1KG', 'descripcion': 'Consumo de Tinta Pantone Reflex Blue (en gramos).', 'expresion': '(ancho_cm * alto_cm * tirada * cobertura) / 10000', 'variables': {
            'ancho_cm': 'Ancho del pliego en cm', 'alto_cm': 'Alto del pliego en cm', 'tirada': 'Cantidad de impresiones', 'cobertura': 'Cobertura en g/m2'}},
        # Planchas
        {'insumo': 'Planchas Presensibilizadas A3', 'codigo': 'PLANCHAS_PS_A3', 'descripcion': 'Planchas presensibilizadas A3: cantidad necesaria (plaquetas).', 'expresion': 'ceil(paginas_totales / paginas_por_plancha)', 'variables': {
            'paginas_totales': 'Total de páginas a imprimir', 'paginas_por_plancha': 'Páginas que entran por plancha según formato'}},
        {'insumo': 'Planchas Presensibilizadas A2', 'codigo': 'PLANCHAS_PS_A2', 'descripcion': 'Planchas presensibilizadas A2: cantidad necesaria.',
            'expresion': 'ceil(paginas_totales / paginas_por_plancha)', 'variables': {'paginas_totales': 'Total de páginas a imprimir', 'paginas_por_plancha': 'Páginas que entran por plancha según formato'}},
        {'insumo': 'Planchas Térmicas Kodak A3', 'codigo': 'PLANCHAS_TERM_KODAK_A3', 'descripcion': 'Planchas térmicas Kodak A3: cantidad necesaria.',
            'expresion': 'ceil(paginas_totales / paginas_por_plancha)', 'variables': {'paginas_totales': 'Total de páginas a imprimir', 'paginas_por_plancha': 'Páginas que entran por plancha según formato'}},
        {'insumo': 'Planchas Violetas Agfa A3', 'codigo': 'PLANCHAS_VIOLETA_AGFA_A3', 'descripcion': 'Planchas violetas Agfa A3: cantidad necesaria.',
            'expresion': 'ceil(paginas_totales / paginas_por_plancha)', 'variables': {'paginas_totales': 'Total de páginas a imprimir', 'paginas_por_plancha': 'Páginas que entran por plancha según formato'}},
        {'insumo': 'Planchas Violetas Agfa A2', 'codigo': 'PLANCHAS_VIOLETA_AGFA_A2', 'descripcion': 'Planchas violetas Agfa A2: cantidad necesaria.',
            'expresion': 'ceil(paginas_totales / paginas_por_plancha)', 'variables': {'paginas_totales': 'Total de páginas a imprimir', 'paginas_por_plancha': 'Páginas que entran por plancha según formato'}},
        {'insumo': 'Planchas Poliéster Económicas', 'codigo': 'PLANCHAS_POLIESTER_ECONOMICAS', 'descripcion': 'Planchas poliéster económicas: cantidad necesaria.',
            'expresion': 'ceil(paginas_totales / paginas_por_plancha)', 'variables': {'paginas_totales': 'Total de páginas a imprimir', 'paginas_por_plancha': 'Páginas que entran por plancha segun formato'}},
        {'insumo': 'Planchas Offset Importadas A1 u', 'codigo': 'PLANCHAS_OFFSET_IMPORT_A1', 'descripcion': 'Planchas offset importadas A1: cantidad necesaria.',
            'expresion': 'ceil(paginas_totales / paginas_por_plancha)', 'variables': {'paginas_totales': 'Total de páginas a imprimir', 'paginas_por_plancha': 'Páginas por plancha según formato A1'}},
        # Papeles
        {'insumo': 'Papel Ilustración 150 g A3', 'codigo': 'PAPEL_ILUSTRACION_150_A3', 'descripcion': 'Hojas de Papel Ilustración 150 g A3: cantidad necesaria (hojas).', 'expresion': 'tirada * (1 + desperdicio)', 'variables': {
            'tirada': 'Tirada o cantidad de ejemplares', 'desperdicio': 'Porcentaje de desperdicio (ej: 0.05 para 5%)'}},
        {'insumo': 'Papel Ilustración 300 g A3', 'codigo': 'PAPEL_ILUSTRACION_300_A3', 'descripcion': 'Hojas de Papel Ilustración 300 g A3: cantidad necesaria.',
            'expresion': 'tirada * (1 + desperdicio)', 'variables': {'tirada': 'Tirada o cantidad de ejemplares', 'desperdicio': 'Porcentaje de desperdicio (ej: 0.05 para 5%)'}},
        {'insumo': 'Cartulina Duplex 350 g', 'codigo': 'CARTULINA_DUPLEX_350G', 'descripcion': 'Cartulina Duplex 350 g: cantidad necesaria (hojas).', 'expresion': 'tirada * (1 + desperdicio)', 'variables': {
            'tirada': 'Tirada', 'desperdicio': 'Porcentaje de desperdicio'}},
        {'insumo': 'Papel Obra 80 g A4', 'codigo': 'PAPEL_OBRA_80_A4', 'descripcion': 'Papel Obra 80 g A4: cantidad necesaria (hojas).', 'expresion': 'tirada * (1 + desperdicio)', 'variables': {
            'tirada': 'Tirada', 'desperdicio': 'Porcentaje de desperdicio'}},
        {'insumo': 'Papel Bond 90 g A4', 'codigo': 'PAPEL_BOND_90_A4', 'descripcion': 'Papel Bond 90 g A4: cantidad necesaria (hojas).', 'expresion': 'tirada * (1 + desperdicio)', 'variables': {
            'tirada': 'Tirada', 'desperdicio': 'Porcentaje de desperdicio'}},
        {'insumo': 'Papel Autoadhesivo A4', 'codigo': 'PAPEL_AUToadhesivo_A4', 'descripcion': 'Papel Autoadhesivo A4: cantidad necesaria (hojas).', 'expresion': 'tirada * (1 + desperdicio)', 'variables': {
            'tirada': 'Tirada', 'desperdicio': 'Porcentaje de desperdicio'}},
        # Consumibles líquidos
        {'insumo': 'Alcohol Isopropílico 5 L', 'codigo': 'ALCOHOL_ISOPROP_5L', 'descripcion': 'Alcohol Isopropílico 5 L: consumo en litros basado en horas de funcionamiento.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de impresión o funcionamiento', 'consumo_por_hora': 'Consumo por hora en litros (ej: 0.15)'}},
        {'insumo': 'Alcohol Isopropílico 20 L', 'codigo': 'ALCOHOL_ISOPROP_20L', 'descripcion': 'Alcohol Isopropílico 20 L: consumo en litros.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de impresión', 'consumo_por_hora': 'Consumo por hora en litros'}},
        # Consumibles líquidos
        {'insumo': 'Solución Humectante Premium 1 L', 'codigo': 'SOLUCION_HUMECTANTE_PREMIUM_1L', 'descripcion': 'Solución humectante premium: litros por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de impresión', 'consumo_por_hora': 'Consumo por hora en litros'}},
        {'insumo': 'Solución Humectante Económica', 'codigo': 'SOLUCION_HUMECTANTE_ECONOMICA', 'descripcion': 'Solución humectante económica: litros por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de impresión', 'consumo_por_hora': 'Consumo por hora en litros'}},
        {'insumo': 'Goma Arábiga 5 L', 'codigo': 'GOMA_ARABIGA_5L', 'descripcion': 'Goma arábiga: litros consumidos por hora según uso.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de trabajo', 'consumo_por_hora': 'Consumo por hora en litros'}},
        {'insumo': 'Limpiador de Cilindros 5 L', 'codigo': 'LIMPIADOR_CILINDROS_5L', 'descripcion': 'Limpiador de cilindros: litros por hora de limpieza.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de uso', 'consumo_por_hora': 'Consumo por hora en litros'}},
        {'insumo': 'Desengrasante Universal 1 L', 'codigo': 'DESENGRASANTE_UNIVERSAL_1L', 'descripcion': 'Desengrasante universal: litros por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de trabajo', 'consumo_por_hora': 'Consumo por hora en litros'}},
        {'insumo': 'Revelador de Planchas 1 L', 'codigo': 'REVELADOR_PLANCHAS_1L', 'descripcion': 'Revelador de planchas: litros por hora de proceso.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de revelado', 'consumo_por_hora': 'Consumo por hora en litros'}},
        {'insumo': 'Limpiador de Planchas 1 L', 'codigo': 'LIMPIADOR_PLANCHAS_1L', 'descripcion': 'Limpiador de planchas: litros por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de limpieza', 'consumo_por_hora': 'Consumo por hora en litros'}},
        {'insumo': 'Barniz Brillante UV 1 kg', 'codigo': 'BARNIZ_BRILLANTE_UV_1KG', 'descripcion': 'Barniz brillante UV: gramos o litros según presentación (consumo por hora).', 'expresion': 'horas * consumo_por_hora', 'variables': {
            'horas': 'Horas de aplicación', 'consumo_por_hora': 'Consumo por hora (L ó kg)'}},
        {'insumo': 'Barniz Mate UV 1 kg', 'codigo': 'BARNIZ_MATE_UV_1KG', 'descripcion': 'Barniz mate UV: consumo por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de aplicación', 'consumo_por_hora': 'Consumo por hora'}},
        {'insumo': 'Barniz Acrílico 1 L', 'codigo': 'BARNIZ_ACRILICO_1L', 'descripcion': 'Barniz acrílico: litros por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de aplicación', 'consumo_por_hora': 'Consumo por hora'}},
        {'insumo': 'Removedor de Tinta 1 L', 'codigo': 'REMOVEDOR_TINTA_1L', 'descripcion': 'Removedor de tinta: litros por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de limpieza', 'consumo_por_hora': 'Consumo por hora'}},
        {'insumo': 'Disolvente Universal 5 L', 'codigo': 'DISOLVENTE_UNIVERSAL_5L', 'descripcion': 'Disolvente universal: litros por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de uso', 'consumo_por_hora': 'Consumo por hora'}},
        {'insumo': 'Disolvente Desengrasante 1 L', 'codigo': 'DISOLVENTE_DESENGRASANTE_1L', 'descripcion': 'Disolvente desengrasante: litros por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de uso', 'consumo_por_hora': 'Consumo por hora'}},
        {'insumo': 'Alcohol Desnaturalizado 5 L', 'codigo': 'ALCOHOL_DESNAT_5L', 'descripcion': 'Alcohol desnaturalizado: litros por hora.',
            'expresion': 'horas * consumo_por_hora', 'variables': {'horas': 'Horas de uso', 'consumo_por_hora': 'Consumo por hora'}},
        # Accesorios / Repuestos
        {'insumo': 'Mantilla Vulcan 0,95 mm', 'codigo': 'MANTILLA_VULCAN_095MM',
            'descripcion': 'Mantilla Vulcan 0,95 mm: reemplazo por unidad.', 'expresion': '1', 'variables': {}},
        {'insumo': 'Mantilla Continental 1 mm', 'codigo': 'MANTILLA_CONTINENTAL_1MM',
            'descripcion': 'Mantilla Continental 1 mm: reemplazo por unidad.', 'expresion': '1', 'variables': {}},
        {'insumo': 'Rodillo de Tinta Heidelberg', 'codigo': 'RODILLO_TINTA_HEIDELBERG',
            'descripcion': 'Rodillo de tinta Heidelberg: unidad por reemplazo.', 'expresion': '1', 'variables': {}},
        {'insumo': 'Rodillo Humectador Heidelberg', 'codigo': 'RODILLO_HUMECTADOR_HEIDELBERG',
            'descripcion': 'Rodillo humectador Heidelberg: unidad por reemplazo.', 'expresion': '1', 'variables': {}},
        {'insumo': 'Trapos Técnicos 10 kg', 'codigo': 'TRAPOS_TECNICOS_10KG',
            'descripcion': 'Trapos técnicos 10 kg: unidades o kit por reemplazo.', 'expresion': '1', 'variables': {}},
        {'insumo': 'Paño Microfibra 10 unid', 'codigo': 'PAÑO_MICROFIBRA_10UN',
            'descripcion': 'Paño microfibra pack 10: reemplazo unitario (pack).', 'expresion': '1', 'variables': {}},
        # ...continúa el resto del listado (misceláneos, duplicados, etc.)...
    ]

    def handle(self, *args, **options):
        with transaction.atomic():
            for f in self.FORMULAS:
                try:
                    insumo = Insumo.objects.get(nombre=f['insumo'])
                except Insumo.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"No existe el insumo: {f['insumo']}"))
                    continue
                formula, created = Formula.objects.get_or_create(
                    insumo=insumo,
                    codigo=f['codigo'],
                    defaults={
                        'descripcion': f['descripcion'],
                        'expresion': f['expresion'],
                        'variables_json': json.dumps(f['variables'], ensure_ascii=False),
                        'activo': True,
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Fórmula creada: {f['codigo']} para insumo {insumo.nombre}"))
                else:
                    self.stdout.write(f"Fórmula ya existe: {f['codigo']} para insumo {insumo.nombre}")
