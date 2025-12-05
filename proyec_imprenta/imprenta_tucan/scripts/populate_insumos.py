from proveedores.models import Proveedor
from insumos.models import Insumo
from django.db import transaction, connection, IntegrityError
import os
import django
from decimal import Decimal
from dataclasses import dataclass

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


# -----------------------------
# Utilidades
# -----------------------------


def parse_precio(valor: str) -> Decimal:
    """Convierte precios con separadores de miles por espacio a Decimal.
    Ejemplos: "8 200" -> Decimal('8200'); "260" -> Decimal('260')
    """
    limpio = valor.replace(' ', '').replace('\u00a0', '')  # remover espacios/espacios duros
    return Decimal(limpio)


def estado_a_activo(estado: str) -> bool:
    """Mapeo de estado textual a booleano activo.
    - Disponible -> True
    - En reposición -> True (sigue activo)
    - Discontinuado -> False
    """
    e = (estado or '').strip().lower()
    if 'discontinuado' in e:
        return False
    return True


def gen_cuit_para(nombre: str) -> str:
    """Genera un CUIT pseudo-determinístico válido en formato XX-XXXXXXXX-X.
    Usamos prefijo 30 (jurídicas) + hash del nombre + dígito de control simple.
    """
    base_num = abs(hash(nombre)) % 10**8
    base = f"{base_num:08d}"
    check = sum(int(d) for d in base) % 10
    return f"30-{base}-{check}"


RUBROS_KEYWORDS = {
    'tinta': 'Tintas',
    'plancha': 'Planchas',
    'mantilla': 'Mantillas',
    'alcohol': 'Alcoholes',
    'goma': 'Gomas',
    'rodillo': 'Rodillos',
    'limpieza': 'Limpieza',
    'solución': 'Soluciones',
    'solucion': 'Soluciones',
    'solvente': 'Solventes',
    'barniz': 'Barnices',
    'papel': 'Papeles',
    'cartulina': 'Papeles/Cartulinas',
    'cartón': 'Papeles/Cartulinas',
    'adhesivo': 'Adhesivos',
    'lubricante': 'Lubricantes',
    'repuesto': 'Repuestos',
    'color': 'Colorimetría',
    'densitómetro': 'Colorimetría',
    'guante': 'Seguridad',
    'trapo': 'Limpieza',
    'spray': 'Químicos',
    'desengrasante': 'Químicos',
    'disolvente': 'Químicos',
    'filtro': 'Filtros',
    'engrana': 'Repuestos',
    'sensor': 'Repuestos',
    'fusible': 'Repuestos',
    'tornillo': 'Repuestos',
    'cinta': 'Cintas',
}


def guess_rubro_por_nombre_insumo(nombre_insumo: str) -> str:
    n = (nombre_insumo or '').lower()
    for kw, rubro in RUBROS_KEYWORDS.items():
        if kw in n:
            return f"Industria Gráfica - {rubro}"
    return 'Industria Gráfica'


@dataclass
class InsumoRow:
    nombre: str
    codigo: str
    proveedor: str
    cantidad: int
    precio_unitario: str
    estado: str


# -----------------------------
# Datos (100 filas)
# -----------------------------
RAW_DATA = [
    InsumoRow('Tinta Negra Offset 1 kg', 'IN-001', 'Tintas Offset Argentinas SA', 45, '8 200', 'Disponible'),
    InsumoRow('Tinta Cyan Offset 1 kg', 'IN-002', 'Tintas Offset Argentinas SA', 32, '8 600', 'Disponible'),
    InsumoRow('Tinta Magenta Offset 1 kg', 'IN-003', 'Tintas Offset Argentinas SA', 30, '8 600', 'Disponible'),
    InsumoRow('Tinta Amarilla Offset 1 kg', 'IN-004', 'Tintas Offset Argentinas SA', 28, '8 600', 'En reposición'),
    InsumoRow('Planchas Presensibilizadas A3', 'IN-005', 'Planchas Offset Sur SA', 150, '1 250', 'Disponible'),
    InsumoRow('Planchas Presensibilizadas A2', 'IN-006', 'Planchas Offset Sur SA', 85, '2 100', 'Disponible'),
    InsumoRow('Planchas Térmicas Kodak A3', 'IN-007', 'PlanchaPlus Argentina', 60, '3 500', 'Disponible'),
    InsumoRow('Mantilla Vulcan 0,95 mm', 'IN-008', 'Mantillas Premium SRL', 25, '11 000', 'Disponible'),
    InsumoRow('Mantilla Continental 1 mm', 'IN-009', 'Mantillas Premium SRL', 18, '10 800', 'En reposición'),
    InsumoRow('Alcohol Isopropílico 5 L', 'IN-010', 'Alcoholes Técnicos SRL', 40, '9 200', 'Disponible'),
    InsumoRow('Solución Humectante Premium 1 L', 'IN-011', 'Soluciones de Fuente SRL', 70, '3 500', 'Disponible'),
    InsumoRow('Goma Arábiga 5 L', 'IN-012', 'Gomas y Soluciones Buenos Aires', 33, '7 900', 'Disponible'),
    InsumoRow('Rodillo de Tinta Heidelberg', 'IN-013', 'Rodillos PrintRoll SA', 12, '18 500', 'Disponible'),
    InsumoRow('Rodillo Humectador Heidelberg', 'IN-014', 'Rodillos PrintRoll SA', 10, '17 900', 'En reposición'),
    InsumoRow('Trapos Técnicos 10 kg', 'IN-015', 'Productos de Limpieza Gráfica SA', 25, '5 400', 'Disponible'),
    InsumoRow('Limpiador de Cilindros 5 L', 'IN-016', 'Solventes y Limpiadores Offset', 45, '8 000', 'Disponible'),
    InsumoRow('Desengrasante Universal 1 L', 'IN-017', 'GrafiChem Argentina SRL', 60, '2 300', 'Disponible'),
    InsumoRow('Barniz Brillante UV 1 kg', 'IN-018', 'Barnices Offset del Litoral', 22, '6 800', 'Disponible'),
    InsumoRow('Barniz Mate UV 1 kg', 'IN-019', 'Barnices Offset del Litoral', 20, '6 800', 'Disponible'),
    InsumoRow('Barniz Acrílico 1 L', 'IN-020', 'Barnices Offset del Litoral', 30, '4 900', 'En reposición'),
    InsumoRow('Papel Ilustración 150 g A3', 'IN-021', 'Papeles Gráficos del Plata SRL', 250, '200', 'Disponible'),
    InsumoRow('Papel Ilustración 300 g A3', 'IN-022', 'Papeles Gráficos del Plata SRL', 180, '340', 'Disponible'),
    InsumoRow('Cartulina Duplex 350 g', 'IN-023', 'Cartones y Papeles del Sur SA', 120, '410', 'Disponible'),
    InsumoRow('Papel Obra 80 g A4', 'IN-024', 'Papeles Offset Norte', 500, '100', 'Disponible'),
    InsumoRow('Papel Bond 90 g A4', 'IN-025', 'Papeles Offset Norte', 480, '120', 'Disponible'),
    InsumoRow('Spray Antiestático 400 ml', 'IN-026', 'Distribuidora Técnica Offset', 15, '4 300', 'Disponible'),
    InsumoRow('Paño Microfibra 10 unid', 'IN-027', 'Productos de Limpieza Gráfica SA', 35, '2 200', 'Disponible'),
    InsumoRow('Cinta Doble Faz 50 mm x 25 m', 'IN-028', 'Cintas & Adhesivos SA', 40, '1 500', 'Disponible'),
    InsumoRow('Adhesivo PVA 5 L', 'IN-029', 'Adhesivos Offset Patagonia', 28, '6 200', 'En reposición'),
    InsumoRow('Aceite Lubricante Gráfico 1 L', 'IN-030', 'Lubricantes Gráficos SRL', 33, '3 700', 'Disponible'),
    InsumoRow('Filtros para Fuente 5 unid', 'IN-031', 'Soluciones de Fuente SRL', 18, '4 000', 'Disponible'),
    InsumoRow('Limpiador de Planchas 1 L', 'IN-032', 'Emulsiones y Reveladores SRL', 22, '3 900', 'Disponible'),
    InsumoRow('Revelador de Planchas 1 L', 'IN-033', 'Emulsiones y Reveladores SRL', 26, '4 400', 'Disponible'),
    InsumoRow('Film Antiadherente 1 m x 50 m', 'IN-034', 'Distribuidora Técnica Offset', 20, '5 200', 'En reposición'),
    InsumoRow('Calzos de Registro (Set)', 'IN-035', 'Offset Solutions Rosario SA', 40, '1 100', 'Disponible'),
    InsumoRow('Cinta Engomada 70 mm', 'IN-036', 'Cintas & Adhesivos SA', 25, '1 700', 'Disponible'),
    InsumoRow('Lupa de Enfoque 10x', 'IN-037', 'Colorimetría Total SRL', 12, '9 800', 'Disponible'),
    InsumoRow('Densitómetro Manual', 'IN-038', 'Colorimetría Total SRL', 6, '85 000', 'Disponible'),
    InsumoRow('Guantes de Nitrilo (Caja 100 u)', 'IN-039', 'Insumos del Taller Gráfico', 25, '6 100', 'Disponible'),
    InsumoRow('Gamuza de Limpieza', 'IN-040', 'Productos de Limpieza Gráfica SA', 50, '800', 'Disponible'),
    InsumoRow('Cartucho Humectante', 'IN-041', 'Soluciones de Fuente SRL', 10, '7 600', 'Disponible'),
    InsumoRow('Tinta Pantone 185C 1 kg', 'IN-042', 'ColorMix Offset SA', 20, '9 200', 'Disponible'),
    InsumoRow('Tinta Pantone Reflex Blue 1 kg', 'IN-043', 'ColorMix Offset SA', 18, '9 200', 'Disponible'),
    InsumoRow('Pasta Antihumedad 500 g', 'IN-044', 'Solventes y Limpiadores Offset', 30, '2 000', 'Disponible'),
    InsumoRow('Sellador para Planchas 1 L', 'IN-045', 'Emulsiones y Reveladores SRL', 16, '4 600', 'En reposición'),
    InsumoRow('Líquido Antiempaste 1 L', 'IN-046', 'GrafiChem Argentina SRL', 18, '5 000', 'Disponible'),
    InsumoRow('Spray Desbloqueante 500 ml', 'IN-047', 'Lubricantes Gráficos SRL', 25, '3 100', 'Disponible'),
    InsumoRow('Tiza de Marcar Registro (Pack 12)', 'IN-048', 'Insumos del Taller Gráfico', 45, '1 400', 'Disponible'),
    InsumoRow('Espátula de Acero', 'IN-049', 'Insumos del Taller Gráfico', 60, '900', 'Disponible'),
    InsumoRow('Aceite para Compresor 1 L', 'IN-050', 'Lubricantes Gráficos SRL', 20, '4 500', 'En reposición'),
    InsumoRow('Planchas Violetas Agfa A3', 'IN-051', 'PlanchaPlus Argentina', 40, '3 900', 'Disponible'),
    InsumoRow('Planchas Violetas Agfa A2', 'IN-052', 'PlanchaPlus Argentina', 35, '4 700', 'Disponible'),
    InsumoRow('Pasta de Lavado 1 kg', 'IN-053', 'Solventes y Limpiadores Offset', 20, '3 200', 'Disponible'),
    InsumoRow('Solución Humectante Económica', 'IN-054', 'Soluciones de Fuente SRL', 50, '2 600', 'Disponible'),
    InsumoRow('Papel Autoadhesivo A4', 'IN-055', 'Papeles Offset Norte', 120, '350', 'Disponible'),
    InsumoRow('Papel Kraft 80 g', 'IN-056', 'Papeles Offset Norte', 100, '220', 'Disponible'),
    InsumoRow('Papel Vegetal 90 g', 'IN-057', 'Papeles Gráficos del Plata SRL', 90, '330', 'Disponible'),
    InsumoRow('Barniz de Máquina 1 L', 'IN-058', 'Barnices Offset del Litoral', 20, '5 600', 'Disponible'),
    InsumoRow('Removedor de Tinta 1 L', 'IN-059', 'GrafiChem Argentina SRL', 18, '3 900', 'Disponible'),
    InsumoRow('Disolvente Universal 5 L', 'IN-060', 'Solventes y Limpiadores Offset', 28, '7 800', 'Disponible'),
    InsumoRow('Engranaje para Alimentador Heidelberg', 'IN-061',
              'Repuestos Gráficos Federal SRL', 6, '23 000', 'Disponible'),
    InsumoRow('Sensor Óptico GTO52', 'IN-062', 'Repuestos Gráficos Federal SRL', 4, '28 000', 'Disponible'),
    InsumoRow('Fusible de Seguridad 10A', 'IN-063', 'Repuestos Gráficos Federal SRL', 40, '500', 'Disponible'),
    InsumoRow('Tornillos Inox M5x30 (Bolsa 50 u)', 'IN-064', 'Distribuidora Técnica Offset', 15, '2 200', 'Disponible'),
    InsumoRow('Cinta Kapton 30 mm', 'IN-065', 'Cintas & Adhesivos SA', 25, '2 800', 'En reposición'),
    InsumoRow('Cepillo de Rodillo', 'IN-066', 'Insumos del Taller Gráfico', 20, '1 700', 'Disponible'),
    InsumoRow('Cuchilla de Corte 15”', 'IN-067', 'Distribuidora Técnica Offset', 10, '9 000', 'Disponible'),
    InsumoRow('Disolvente Desengrasante 1 L', 'IN-068', 'GrafiChem Argentina SRL', 30, '3 600', 'Disponible'),
    InsumoRow('Limpiador de Mantillas 5 L', 'IN-069', 'Solventes y Limpiadores Offset', 16, '9 500', 'Disponible'),
    InsumoRow('Filtro de Aire Compresor', 'IN-070', 'Lubricantes Gráficos SRL', 10, '6 000', 'En reposición'),
    InsumoRow('Papel Autocopiativo Blanco A4', 'IN-071', 'Papeles Offset Norte', 200, '240', 'Disponible'),
    InsumoRow('Papel Autocopiativo Color A4', 'IN-072', 'Papeles Offset Norte', 180, '260', 'Disponible'),
    InsumoRow('Goma Protectora 1 L', 'IN-073', 'Gomas y Soluciones Buenos Aires', 20, '4 200', 'Disponible'),
    InsumoRow('Pasta Limpiadora de Rodillos', 'IN-074', 'Solventes y Limpiadores Offset', 18, '3 400', 'Disponible'),
    InsumoRow('Alcohol Desnaturalizado 5 L', 'IN-075', 'Alcoholes Técnicos SRL', 22, '7 600', 'Disponible'),
    InsumoRow('Dispersante Universal 1 L', 'IN-076', 'GrafiChem Argentina SRL', 20, '5 200', 'Disponible'),
    InsumoRow('Cinta Teflón 19 mm', 'IN-077', 'Cintas & Adhesivos SA', 25, '1 800', 'Disponible'),
    InsumoRow('Planchas Poliéster Económicas', 'IN-078', 'Planchas Offset Sur SA', 50, '1 900', 'Disponible'),
    InsumoRow('Cinta Reflectiva Amarilla', 'IN-079', 'Cintas & Adhesivos SA', 30, '2 000', 'Disponible'),
    InsumoRow('Grasa de Alta Temperatura 250 g', 'IN-080', 'Lubricantes Gráficos SRL', 20, '3 300', 'Disponible'),
    InsumoRow('Cinta Métrica Acero 5 m', 'IN-081', 'Insumos del Taller Gráfico', 35, '1 200', 'Disponible'),
    InsumoRow('Aceite Hidráulico ISO 46', 'IN-082', 'Lubricantes Gráficos SRL', 15, '4 800', 'Disponible'),
    InsumoRow('Aceite Neumático ISO 32', 'IN-083', 'Lubricantes Gráficos SRL', 12, '4 500', 'Disponible'),
    InsumoRow('Pasta Antideslizante 1 kg', 'IN-084', 'GrafiChem Argentina SRL', 25, '3 900', 'Disponible'),
    InsumoRow('Cinta Plástica Roja 50 mm', 'IN-085', 'Cintas & Adhesivos SA', 50, '1 300', 'Disponible'),
    InsumoRow('Calibrador de Espesor Digital', 'IN-086', 'Colorimetría Total SRL', 8, '52 000', 'Disponible'),
    InsumoRow('Kit de Limpieza de Planchas', 'IN-087', 'Emulsiones y Reveladores SRL', 14, '6 200', 'Disponible'),
    InsumoRow('Paño Absorbente Industrial', 'IN-088', 'Productos de Limpieza Gráfica SA', 40, '2 700', 'Disponible'),
    InsumoRow('Removedor de Barniz 1 L', 'IN-089', 'Barnices Offset del Litoral', 10, '4 300', 'Disponible'),
    InsumoRow('Manta Antiestática', 'IN-090', 'Mantillas Premium SRL', 12, '10 500', 'Disponible'),
    InsumoRow('Pasta Anticorrosiva 500 g', 'IN-091', 'GrafiChem Argentina SRL', 15, '3 200', 'Disponible'),
    InsumoRow('Desengrasante Alcalino 5 L', 'IN-092', 'Solventes y Limpiadores Offset', 18, '8 800', 'Disponible'),
    InsumoRow('Planchas Offset Importadas A1', 'IN-093', 'PlanchaPlus Argentina', 30, '5 800', 'Disponible'),
    InsumoRow('Pasta de Engrase 250 g', 'IN-094', 'Lubricantes Gráficos SRL', 25, '2 800', 'Disponible'),
    InsumoRow('Pasta Abrillantadora 1 kg', 'IN-095', 'GrafiChem Argentina SRL', 16, '3 600', 'Disponible'),
    InsumoRow('Pasta Abrasiva Suave 1 kg', 'IN-096', 'GrafiChem Argentina SRL', 18, '3 700', 'Disponible'),
    InsumoRow('Alcohol Isopropílico 20 L', 'IN-097', 'Alcoholes Técnicos SRL', 12, '28 000', 'Disponible'),
    InsumoRow('Pasta Neutralizante 1 L', 'IN-098', 'Emulsiones y Reveladores SRL', 15, '4 500', 'En reposición'),
    InsumoRow('Guantes de Cuero Industrial', 'IN-099', 'Insumos del Taller Gráfico', 25, '5 000', 'Disponible'),
    InsumoRow('Papel Couché Brillante 115 g', 'IN-100', 'Papeles Gráficos del Plata SRL', 300, '260', 'Disponible'),
]


@transaction.atomic
def poblar_insumos():
    print("Cargando datos de Insumos (100 filas) ...")
    creados, actualizados, proveedores_creados = 0, 0, 0

    proveedores_cache = {}

    for row in RAW_DATA:
        # Proveedor
        prov = proveedores_cache.get(row.proveedor)
        if prov is None:
            try:
                prov, creado = Proveedor.objects.get_or_create(
                    nombre=row.proveedor,
                    defaults={
                        'cuit': gen_cuit_para(row.proveedor),
                        'email': f"{row.proveedor.lower().replace(' ', '.').replace('&', 'y')}@proveedores.local",
                        'telefono': '+54 11 4000-0000',
                        'direccion': 'Dirección no especificada',
                        'rubro': guess_rubro_por_nombre_insumo(row.nombre),
                        'activo': True,
                    }
                )
            except Exception:
                # Base de datos con columna extra NOT NULL (p.ej. 'apellido').
                # Creamos el registro por SQL crudo incluyendo valor por defecto.
                cuit_val = gen_cuit_para(row.proveedor)
                email_val = f"{row.proveedor.lower().replace(' ', '.').replace('&', 'y')}@proveedores.local"
                rubro_val = guess_rubro_por_nombre_insumo(row.nombre)
                inserted_id = None
                # Usar cursor crudo de sqlite3 para evitar debug_sql de Django que falla con placeholders '?'
                if connection.connection is None:
                    connection.ensure_connection()
                cur = connection.connection.cursor()
                try:
                    # Detectar columnas extra y preparar INSERT acorde
                    cur.execute("PRAGMA table_info('proveedores_proveedor')")
                    cols = {r[1] for r in cur.fetchall()}

                    columns = [
                        'nombre', 'cuit', 'email', 'telefono', 'direccion', 'rubro', 'activo'
                    ]
                    values = [
                        row.proveedor,
                        cuit_val,
                        email_val,
                        '+54 11 4000-0000',
                        'Dirección no especificada',
                        rubro_val,
                        1,
                    ]

                    # Columnas legacy obligatorias
                    if 'apellido' in cols:
                        columns.append('apellido')
                        values.append('')
                    if 'empresa' in cols:
                        columns.append('empresa')
                        values.append(row.proveedor)

                    # fecha_creacion al final con CURRENT_TIMESTAMP
                    columns.append('fecha_creacion')

                    placeholders = ', '.join(['?'] * (len(columns) - 1)) + ", CURRENT_TIMESTAMP"
                    sql = f"INSERT INTO proveedores_proveedor ({', '.join(columns)}) VALUES ({placeholders})"
                    cur.execute(sql, tuple(values))
                    inserted_id = cur.lastrowid
                finally:
                    cur.close()
                prov = Proveedor.objects.get(pk=inserted_id)
                creado = True
            proveedores_cache[row.proveedor] = prov
            if creado:
                proveedores_creados += 1

        # Insumo
        defaults = {
            'nombre': row.nombre,
            'proveedor': prov,
            'cantidad': int(row.cantidad),
            'precio_unitario': parse_precio(row.precio_unitario),
            'categoria': guess_rubro_por_nombre_insumo(row.nombre),
            'stock': int(row.cantidad),
            'precio': parse_precio(row.precio_unitario),
            'activo': estado_a_activo(row.estado),
        }
        insumo, creado_ins = Insumo.objects.update_or_create(
            codigo=row.codigo,
            defaults=defaults
        )
        if creado_ins:
            creados += 1
        else:
            actualizados += 1
        print(f" - {'[+]' if creado_ins else '[~]'} {row.codigo} {row.nombre} ({'Activo' if insumo.activo else 'Inactivo'})")

    print("\nResumen:")
    print(f" - Proveedores creados: {proveedores_creados}")
    print(f" - Insumos creados: {creados}")
    print(f" - Insumos actualizados: {actualizados}")


if __name__ == '__main__':
    try:
        poblar_insumos()
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario")
    except Exception as e:
        import traceback
        print(f"\nError inesperado: {e}")
        traceback.print_exc()
