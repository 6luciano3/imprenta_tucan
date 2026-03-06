"""
Comando de gestión: entrenar modelo ML de score de proveedor.

Uso:
    python manage.py entrenar_modelo_score_proveedor [--min-muestras 5]

Proceso:
    1. Para cada proveedor activo, calcula sus 5 métricas con ProveedorInteligenteEngine
       y las empareja con el ScoreProveedor.score ya persistido en BD como target.
    2. Si hay < --min-muestras muestras reales, genera datos sintéticos.
    3. Entrena un GradientBoostingRegressor (scikit-learn).
    4. Evalúa con RMSE y R² en hold-out 20%.
    5. Guarda el modelo en core/ai_ml/modelo_score_proveedor.pkl.
"""
import os
import pickle
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

FEATURES = ['precio_relativo', 'cumplimiento', 'incidencias', 'disponibilidad', 'latencia']


def _model_path():
    from django.conf import settings
    return os.path.normpath(
        os.path.join(settings.BASE_DIR, '..', 'core', 'ai_ml', 'modelo_score_proveedor.pkl')
    )


class Command(BaseCommand):
    help = 'Entrena el modelo ML de score de proveedor y lo guarda como pickle.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-muestras',
            type=int,
            default=5,
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

        min_muestras = options['min_muestras']
        self.stdout.write('Recolectando métricas de proveedores desde BD...')

        X_real, y_real = self._recolectar_datos_reales()
        self.stdout.write(f'  Muestras reales encontradas: {len(y_real)}')

        if len(y_real) < min_muestras:
            faltantes = min_muestras - len(y_real)
            self.stdout.write(
                self.style.WARNING(
                    f'  Insuficientes muestras ({len(y_real)} < {min_muestras}). '
                    f'Generando {faltantes + 25} muestras sintéticas...'
                )
            )
            X_sint, y_sint = self._generar_sinteticos(faltantes + 25)
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

        # Split hold-out
        test_size = 0.2 if len(y_all) >= 10 else 1
        X_train, X_test, y_train, y_test = train_test_split(
            X_all, y_all, test_size=test_size, random_state=42
        )

        model = GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42
        )
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
            from core.ai_ml import score_proveedor as sp
            sp._model = None
        except Exception:
            pass

    def _recolectar_datos_reales(self):
        """
        Para cada proveedor activo con ScoreProveedor en BD,
        calcula sus 5 métricas y las usa como features.
        El score guardado en ScoreProveedor es el target.
        """
        import numpy as np
        try:
            from proveedores.models import Proveedor
            from automatizacion.models import ScoreProveedor
            from core.motor.proveedor_engine import ProveedorInteligenteEngine
        except ImportError:
            return np.empty((0, len(FEATURES))), np.array([])

        engine = ProveedorInteligenteEngine()
        X, y = [], []
        for sp_obj in ScoreProveedor.objects.select_related('proveedor').filter(proveedor__activo=True):
            p = sp_obj.proveedor
            try:
                feats = {
                    'precio_relativo':  engine._precio_relativo(p),
                    'cumplimiento':     engine._cumplimiento(p),
                    'incidencias':      engine._incidencias(p),
                    'disponibilidad':   engine._disponibilidad(p),
                    'latencia':         engine._latencia_promedio_dias(p),
                }
                X.append([feats[f] for f in FEATURES])
                y.append(float(sp_obj.score))
            except Exception:
                continue

        if not X:
            return np.empty((0, len(FEATURES))), np.array([])
        return np.array(X), np.array(y)

    def _generar_sinteticos(self, n: int):
        """
        Genera n muestras sintéticas variando las 5 features con distribuciones
        realistas y calculando el score con la fórmula de reglas (verdad de tierra).
        """
        import numpy as np
        rng = np.random.default_rng(42)

        precio        = rng.uniform(0.0, 1.0, n)
        cumplimiento  = rng.beta(8, 2, n)          # sesgo a valores altos
        incidencias   = rng.beta(2, 8, n)          # sesgo a valores bajos
        disponibilidad = rng.beta(7, 3, n)
        latencia      = rng.beta(2, 6, n)          # sesgo a latencia baja

        # Score con pesos fijos (misma fórmula del motor de reglas)
        w = {'precio': 0.25, 'cumplimiento': 0.30, 'incidencias': 0.25,
             'disponibilidad': 0.10, 'latencia': 0.10}
        score = (
            w['precio'] * (1 - precio) +
            w['cumplimiento'] * cumplimiento +
            w['incidencias'] * (1 - incidencias) +
            w['disponibilidad'] * disponibilidad +
            w['latencia'] * (1 - latencia)
        ) * 100

        X = np.column_stack([precio, cumplimiento, incidencias, disponibilidad, latencia])
        return X, score
