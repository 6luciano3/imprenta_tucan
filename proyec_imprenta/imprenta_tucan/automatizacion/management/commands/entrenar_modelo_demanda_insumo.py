"""
Comando de gestión: entrenar modelo ML de demanda de insumos.

Uso:
    python manage.py entrenar_modelo_demanda_insumo [--min-muestras 10]

Proceso:
    1. Para cada insumo con historial en ConsumoRealInsumo, construye pares
       (consumo_mes-3, consumo_mes-2, consumo_mes-1, tipo_directo) → consumo_mes.
    2. Si hay < --min-muestras pares reales, genera datos sintéticos.
    3. Entrena un Ridge regression (scikit-learn).
    4. Evalúa con RMSE y R² en hold-out 20%.
    5. Guarda el modelo en core/ai_ml/modelo_demanda_insumo.pkl.
"""
import os
import pickle
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

FEATURES = ['consumo_mes_1', 'consumo_mes_2', 'consumo_mes_3', 'tipo_directo']


def _model_path():
    from django.conf import settings
    return os.path.normpath(
        os.path.join(settings.BASE_DIR, '..', 'core', 'ai_ml', 'modelo_demanda_insumo.pkl')
    )


def _periodos_de_insumo(insumo_id):
    """
    Retorna dict {periodo: cantidad_consumida} para el insumo dado.
    Agrega registros del mismo periodo (puede haber varios con misma FK/periodo).
    """
    from insumos.models import ConsumoRealInsumo
    qs = (
        ConsumoRealInsumo.objects
        .filter(insumo_id=insumo_id)
        .values('periodo', 'cantidad_consumida')
    )
    acum = {}
    for row in qs:
        acum[row['periodo']] = acum.get(row['periodo'], 0) + row['cantidad_consumida']
    return acum


def _periodos_ordenados(mapa_periodos: dict) -> list:
    """Ordena los períodos YYYY-MM cronológicamente."""
    return sorted(mapa_periodos.keys())


class Command(BaseCommand):
    help = 'Entrena el modelo ML de demanda de insumos y lo guarda como pickle.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-muestras',
            type=int,
            default=10,
            help='Mínimo de muestras reales requeridas antes de rellenar con sintéticos.',
        )

    def handle(self, *args, **options):
        try:
            import numpy as np
            from sklearn.linear_model import Ridge
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_squared_error, r2_score
        except ImportError as e:
            self.stderr.write(self.style.ERROR(
                f'scikit-learn / numpy no disponible: {e}\n'
                'Instala: pip install scikit-learn numpy'
            ))
            return

        min_muestras = options['min_muestras']
        self.stdout.write('Construyendo pares de series temporales desde ConsumoRealInsumo...')

        X_real, y_real = self._construir_pares()
        self.stdout.write(f'  Pares reales encontrados: {len(y_real)}')

        if len(y_real) < min_muestras:
            faltantes = min_muestras - len(y_real)
            self.stdout.write(
                self.style.WARNING(
                    f'  Insuficientes muestras ({len(y_real)} < {min_muestras}). '
                    f'Generando {faltantes + 30} muestras sintéticas...'
                )
            )
            X_sint, y_sint = self._generar_sinteticos(faltantes + 30)
            if len(y_real) > 0:
                import numpy as np
                X_all = np.vstack([X_real, X_sint])
                y_all = np.concatenate([y_real, y_sint])
            else:
                X_all, y_all = X_sint, y_sint
        else:
            import numpy as np
            X_all, y_all = np.array(X_real), np.array(y_real)

        self.stdout.write(f'  Total muestras para entrenamiento: {len(y_all)}')

        import numpy as np
        if len(y_all) < 4:
            self.stderr.write(self.style.ERROR('No hay suficientes datos para entrenar.'))
            return

        test_size = 0.2 if len(y_all) >= 10 else 1
        X_train, X_test, y_train, y_test = train_test_split(
            X_all, y_all, test_size=test_size, random_state=42
        )

        model = Ridge(alpha=1.0)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2   = float(r2_score(y_test, y_pred))
        self.stdout.write(f'  RMSE: {rmse:.2f}  |  R²: {r2:.3f}')

        path = _model_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(model, f)
        self.stdout.write(self.style.SUCCESS(f'Modelo guardado en: {path}'))

        # Invalidar caché en memoria
        try:
            from core.ai_ml import demanda_insumo as di
            di._model = None
        except Exception:
            pass

    def _construir_pares(self):
        """
        Para cada insumo con ≥ 4 períodos de historial, genera ventanas deslizantes:
        (mes-3, mes-2, mes-1, tipo_directo) → mes.
        """
        import numpy as np
        try:
            from insumos.models import Insumo
        except ImportError:
            return np.empty((0, len(FEATURES))), np.array([])

        X, y = [], []
        for insumo in Insumo.objects.filter(activo=True):
            mapa = _periodos_de_insumo(insumo.idInsumo)
            periodos = _periodos_ordenados(mapa)
            if len(periodos) < 4:
                continue
            tipo_d = 1.0 if insumo.tipo == 'directo' else 0.0
            for i in range(3, len(periodos)):
                c1 = float(mapa[periodos[i - 1]])
                c2 = float(mapa[periodos[i - 2]])
                c3 = float(mapa[periodos[i - 3]])
                target = float(mapa[periodos[i]])
                X.append([c1, c2, c3, tipo_d])
                y.append(target)

        if not X:
            return np.empty((0, len(FEATURES))), np.array([])
        return np.array(X), np.array(y)

    def _generar_sinteticos(self, n: int):
        """
        Genera n muestras sintéticas de series de consumo mensual.
        Modela consumo como proceso AR(1) con ruido multiplicativo.
        """
        import numpy as np
        rng = np.random.default_rng(43)

        # Base de consumo mensual: distribución exponencial (muchos bajos, pocos altos)
        base = rng.exponential(scale=120, size=n)
        # AR(1): mes siguiente ≈ 0.85 * mes anterior + ruido
        c3 = base * rng.uniform(0.7, 1.3, n)
        c2 = c3 * rng.uniform(0.7, 1.3, n)
        c1 = c2 * rng.uniform(0.7, 1.3, n)
        target = c1 * rng.uniform(0.7, 1.3, n)
        tipo_d = rng.integers(0, 2, n).astype(float)

        X = np.column_stack([c1, c2, c3, tipo_d])
        return X, target
