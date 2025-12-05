# Guía para Desarrolladores - Proyecto Imprenta Tucán

## Requisitos
- Python 3.13+
- Entorno virtual (recomendado)
- pip

## Instalación y configuración
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

## Estructura del proyecto
- `core/ai_ml/`: Lógica de IA y ML
- `core/ai_rules/`: Motor de reglas
- `core/automation/`: Automatizaciones
- `core/notifications/`: Notificaciones
- `proyec_imprenta/imprenta_tucan/`: Apps Django

## Buenas prácticas
- Usa flake8 para revisar el estilo:
  ```powershell
  python -m flake8 . --max-line-length=120
  ```
- Usa autopep8 para formateo automático:
  ```powershell
  python -m autopep8 --in-place --recursive .
  ```
- Escribe y ejecuta tests (pytest recomendado):
  ```powershell
  pytest
  ```

## Contribución
1. Crea un branch para tu feature o fix.
2. Asegúrate de pasar flake8 y los tests.
3. Haz un Pull Request.

## Notas adicionales
- Consulta `DOCUMENTACION_INTELIGENCIA.md` para detalles de automatización y módulos inteligentes.
- El archivo `README.md` contiene instrucciones generales y de despliegue.

---
Personaliza esta guía según las necesidades de tu equipo y proyecto.
