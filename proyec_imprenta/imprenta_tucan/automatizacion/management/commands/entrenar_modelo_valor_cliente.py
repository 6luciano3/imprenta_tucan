"""
Comando de gestión: entrenar modelo ML de valor de cliente.

Uso:
    python manage.py entrenar_modelo_valor_cliente [--min-muestras 10]

Proceso:
    1. Lee pares (features_periodo_N → score_periodo_N+1) de RankingHistorico.
    2. Si hay < --min-muestras pares reales, rellena con datos sintéticos generados
       a partir de las métricas actuales del ranking.
    3. Entrena un GradientBoostingRegressor (scikit-learn).
    4. Evalúa con RMSE y R² en hold-out 20%.
    5. Guarda el modelo en core/ai_ml/modelo_valor_cliente.pkl.
"""
import os
import pickle
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


def _model_path():
    """
    Ruta al pickle, calculada desde BASE_DIR de Django para ser robusta
    independientemente de desde qué directorio se corra el comando.
    BASE_DIR = .../proyec_imprenta/imprenta_tucan/
    modelo   = .../proyec_imprenta/core/ai_ml/modelo_valor_cliente.pkl
    """
    from django.conf import settings
    return os.path.normpath(
        os.path.join(settings.BASE_DIR, '..', 'core', 'ai_ml', 'modelo_valor_cliente.pkl')
    )


FEATURES = ['total_compras', 'frecuencia', 'margen', 'ofertas_aceptadas']


class Command(BaseCommand):
    help = 'Entrena el modelo ML de valor de cliente y lo guarda como pickle.'

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
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_squared_error, r2_score
        except ImportError as e:
            self.stderr.write(self.style.ERROR(
                f'scikit-learn / numpy no disponible: {e}\n'
                'Instala: pip install scikit-learn numpy'
            ))
            return

        self.stdout.write('Recolectando datos de entrenamiento...')
        X, y = self._recolectar_datos()

        min_muestras = options['min_muestras']
        MODEL_PATH = _model_path()
        if len(y) < min_muestras:
            self.stdout.write(
                self.style.WARNING(
                    f'Solo {len(y)} muestras reales. Completando hasta {min_muestras * 3} con datos sintéticos...'
                )
            )
            X_syn, y_syn = self._generar_sinteticos(n=min_muestras * 3 - len(y))
            X = np.vstack([X, X_syn]) if len(X) else X_syn
            y = np.concatenate([y, y_syn]) if len(y) else y_syn

        self.stdout.write(f'Entrenando con {len(y)} muestras ({len(FEATURES)} features)...')

        if len(y) >= 4:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        else:
            X_train, X_test, y_train, y_test = X, X, y, y

        model = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )
        model.fit(X_train, y_train)

        if len(y_test) > 0:
            y_pred = model.predict(X_test)
            rmse = mean_squared_error(y_test, y_pred) ** 0.5
            r2 = r2_score(y_test, y_pred)
            self.stdout.write(f'  RMSE (hold-out): {rmse:.2f}   R²: {r2:.4f}')

        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(model, f)

        self.stdout.write(self.style.SUCCESS(f'Modelo guardado en: {MODEL_PATH}'))

        # Invalidar caché en memoria del módulo valor_cliente
        try:
            from core.ai_ml import valor_cliente as vc
            vc._model = None
            vc._warned_missing = False
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Recolección de datos reales
    # ------------------------------------------------------------------

    def _recolectar_datos(self):
        """
        Para cada cliente, empareja (features del período N) → (score del período N+1).
        Features: total_compras, frecuencia, margen (norm), ofertas_aceptadas.
        """
        try:
            import numpy as np
            from automatizacion.models import RankingHistorico, AccionCliente
            from django.db.models import Count
        except Exception as e:
            self.stderr.write(f'Error al importar modelos: {e}')
            return _empty_arrays()

        # Todas las entradas de historial, ordenadas
        historicos = list(
            RankingHistorico.objects.order_by('cliente_id', 'periodo')
            .values('cliente_id', 'periodo', 'score', 'metricas')
        )

        # Agrupar por cliente
        por_cliente: dict = {}
        for h in historicos:
            por_cliente.setdefault(h['cliente_id'], []).append(h)

        # Ofertas aceptadas por cliente (histórico total)
        aceptaciones: dict = dict(
            AccionCliente.objects
            .filter(tipo='aceptar')
            .values('cliente_id')
            .annotate(n=Count('id'))
            .values_list('cliente_id', 'n')
        )

        rows_X = []
        rows_y = []

        for cid, periodos in por_cliente.items():
            for i in range(len(periodos) - 1):
                curr = periodos[i]
                nxt = periodos[i + 1]
                m = curr.get('metricas') or {}
                # Features del período actual
                total_norm = float(m.get('total_norm', 0))
                freq_norm = float(m.get('freq_norm', 0))
                margen_norm = float(m.get('margen_norm', 0))
                ofertas = float(aceptaciones.get(cid, 0))
                # Escalar total_norm y freq_norm a valores aproximados
                # (la arquitectura de ranking.py usa raw para total y freq, norm para margen)
                # Aproximamos: total ≈ total_norm * 1_000_000, freq ≈ freq_norm * 30
                row = [
                    total_norm * 1_000_000,   # total_compras proxy
                    freq_norm * 30,           # frecuencia proxy
                    margen_norm,              # margen normalizado
                    ofertas,                  # ofertas_aceptadas
                ]
                rows_X.append(row)
                rows_y.append(float(nxt['score']))

        if not rows_X:
            import numpy as np
            return np.empty((0, len(FEATURES))), np.empty(0)

        import numpy as np
        return np.array(rows_X, dtype=float), np.array(rows_y, dtype=float)

    # ------------------------------------------------------------------
    # Generación de datos sintéticos
    # ------------------------------------------------------------------

    def _generar_sinteticos(self, n: int):
        """
        Genera n muestras sintéticas con distribución realista y scores
        calculados con la fórmula de reglas (pesos default).
        Esto permite que el modelo aprenda la misma función que las reglas
        y estará listo para incorporar señal adicional cuando haya más datos.
        """
        import numpy as np

        rng = np.random.default_rng(seed=0)

        # Rangos realistas por feature
        total = rng.exponential(scale=200_000, size=n).clip(0, 5_000_000)
        freq = rng.exponential(scale=4, size=n).clip(0, 30)
        margen = rng.uniform(0.0, 1.0, size=n)
        ofertas = rng.poisson(lam=1, size=n).astype(float)

        X = np.column_stack([total, freq, margen, ofertas])

        # Score sintético: misma fórmula de ranking.py (pesos default)
        # Normalizar sobre sus propios máximos
        def norm(arr):
            mx = arr.max() or 1
            return arr / mx

        t_n = norm(total)
        f_n = norm(freq)
        m_n = margen
        o_n = norm(ofertas + 0.01)

        # pesos: valor=30, margen=25, cantidad=20, freq=15, critico=10
        # freq aproxima cantidad+freq; margen=margen; resto en total y ofertas
        score = (0.30 * t_n + 0.25 * m_n + 0.20 * f_n + 0.15 * f_n + 0.10 * o_n) * 100
        score = score.clip(0, 100)

        return X, score


def _empty_arrays():
    import numpy as np
    return np.empty((0, len(FEATURES))), np.empty(0)
