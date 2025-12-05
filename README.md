# Proyecto Imprenta Tucán

## Descripción
Sistema de gestión para imprenta con automatización inteligente, predicción de demanda, ranking de clientes y proveedores, y generación automática de órdenes y ofertas.

## Instalación
1. Clona el repositorio.
2. Activa el entorno virtual:
   ```powershell
   & "imprenta_tuc/Scripts/Activate.ps1"
   ```
3. Instala las dependencias (si tienes requirements.txt):
   ```powershell
   pip install -r requirements.txt
   ```
4. Aplica migraciones:
   ```powershell
   python proyec_imprenta/imprenta_tucan/manage.py migrate
   ```
5. Inicia el servidor:
   ```powershell
   python run.py
   ```

## Estructura del Proyecto
- `core/ai_ml/`: Módulos de inteligencia artificial y machine learning
- `core/ai_rules/`: Motor de reglas de negocio
- `core/automation/`: Automatizaciones y tareas periódicas
- `core/notifications/`: Motor de notificaciones
- `proyec_imprenta/imprenta_tucan/`: Apps Django principales

## Uso
- Accede a la API REST para CRUD de modelos inteligentes.
- Usa el panel de administración de Django para gestionar datos.

## Pruebas y Calidad
- Ejecuta flake8 para revisar estilo:
  ```powershell
  python -m flake8 . --max-line-length=120
  ```
- Ejecuta tests (si tienes tests):
  ```powershell
  pytest
  ```

## Documentación adicional
Consulta `DOCUMENTACION_INTELIGENCIA.md` para detalles de automatización y módulos inteligentes.

## Contribución
1. Crea un branch para tu feature o fix.
2. Asegúrate de pasar flake8 y los tests.
3. Haz un Pull Request.

## Autor
- [Tu Nombre]

---
Este README es una base. Personalízalo según las necesidades de tu proyecto.
