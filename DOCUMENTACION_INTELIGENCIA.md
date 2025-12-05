# Cambios aplicados: Automatización Inteligente en Proyecto Django

## Carpetas y Motores creados
- `core/ai_rules/`: Motor de reglas de negocio (`rules_engine.py`)
- `core/ai_ml/`: Módulos de ML y lógica inteligente (`demand_prediction.py`, `anticipation.py`, `ranking.py`, `proveedor_recomendacion.py`, `ofertas.py`)
- `core/notifications/`: Motor de notificaciones multicanal (`engine.py`)
- `core/automation/`: Automatizaciones y tareas periódicas (`alertas.py`, `ordenes_sugeridas.py`, `confirmacion_disponibilidad.py`, `campanas.py`, `tasks.py`)

## Modelos Django agregados (en `core_models.py`)
- `RankingCliente`: Ranking dinámico de clientes
- `ScoreProveedor`: Score de proveedores
- `OrdenSugerida`: Orden de compra sugerida vinculada a pedido
- `OfertaAutomatica`: Generación automática de ofertas
- `AprobacionAutomatica`: Flujos de aprobación
- `AutomationLog`: Registro histórico de decisiones automáticas

## Endpoints API REST
- CRUD para todos los modelos inteligentes vía DRF (`api_inteligente.py`, `api_inteligente_urls.py`)

## Automatizaciones y procesos inteligentes
- Predicción de demanda de insumos
- Anticipación de compras de insumos críticos
- Ranking dinámico de clientes estratégicos
- Recomendación de proveedores óptimos
- Generación automática de ofertas
- Alertas de retraso
- Generación de órdenes sugeridas
- Confirmación de disponibilidad
- Activación de campañas
- Tareas periódicas (cron jobs) en `core/automation/tasks.py`

## Workflow automático de pedidos
- Automatización de estados de pedido (`pedidos/workflow.py`)

## Motor de notificaciones
- Envío de notificaciones por email, portal y app (`core/notifications/engine.py`)

## Registro histórico de decisiones
- Utilidad para registrar logs automáticos (`automationlog_utils.py`)

## Migraciones
- Ejecutadas correctamente (sin cambios pendientes)

---

**Todos los cambios siguen la lista oficial y no agregan nada fuera de lo solicitado.**
