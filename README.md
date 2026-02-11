## Email con Amazon SES y AWS SSO (sin contraseñas)

Este proyecto está preparado para enviar correos reales usando Amazon SES mediante AWS SSO, sin almacenar contraseñas ni claves estáticas.

- Requisitos:
   - AWS CLI v2 instalado (Windows): `winget install Amazon.AWSCLI`
   - Una identidad verificada en SES (dominio o email) y, si estás en sandbox, acceso de producción o envío a destinatarios verificados.

- Configuración en entorno (no se guardan secretos):
   1) Inicia la configuración SSO
       ```powershell
       aws configure sso
       aws sso login --profile your-sso-profile
       $env:AWS_PROFILE = 'your-sso-profile'
       $env:AWS_REGION = 'us-east-1'   # Ajusta a tu región SES
       $env:ANYMAIL_PROVIDER = 'ses'
       $env:DEFAULT_FROM_EMAIL = 'no-reply@tu-dominio-verificado.com'
       ```

   2) Verifica que el dominio o email de `DEFAULT_FROM_EMAIL` esté verificado en SES.

- Probar envío real (sin credenciales persistidas):
   ```powershell
   & "C:\Users\Public\Documents\facultad\3er Año\Trabajo Final\proyecto_imprenta\imprenta_tuc\Scripts\python.exe" "C:\Users\Public\Documents\facultad\3er Año\Trabajo Final\proyecto_imprenta\proyec_imprenta\imprenta_tucan\manage.py" test_email --to "destinatario@tu-dominio-verificado.com" --subject "Prueba SES" --body "Entrega real vía SES + SSO"
   ```

- Alternativa rápida (script):
   ```powershell
   ./proyec_imprenta/imprenta_tucan/scripts/setup_ses_sso.ps1 -ProbarEnvio -DestinoPrueba "destinatario@tu-dominio-verificado.com"
   ```

- En producción (también sin secretos):
   - Ejecuta en AWS (EC2/ECS/EKS/Lambda) con un rol IAM que permita `ses:SendEmail` en tu región; boto3 usará el rol automáticamente.

- Plantillas y servicios relacionados:
   - Ajustes: ver [proyec_imprenta/imprenta_tucan/impre_tucan/settings.py](proyec_imprenta/imprenta_tucan/impre_tucan/settings.py)
   - Servicio de envío: ver [proyec_imprenta/imprenta_tucan/automatizacion/services.py](proyec_imprenta/imprenta_tucan/automatizacion/services.py)
   - Comando de prueba: ver [proyec_imprenta/imprenta_tucan/automatizacion/management/commands/test_email.py](proyec_imprenta/imprenta_tucan/automatizacion/management/commands/test_email.py)
   - Estado de credenciales: ver [proyec_imprenta/imprenta_tucan/automatizacion/management/commands/ses_status.py](proyec_imprenta/imprenta_tucan/automatizacion/management/commands/ses_status.py)

Solución de problemas:
- `Unable to locate credentials`: inicia sesión con `aws sso login` y exporta `AWS_PROFILE`.
- Sandbox SES: sólo puedes enviar a emails verificados hasta que solicites producción.
- Remitente no verificado: verifica el email o dominio en SES y usa ese remitente en `DEFAULT_FROM_EMAIL`.

## Cómo quedó la configuración
- Backend de email: Anymail con Amazon SES (sin contraseñas ni claves persistidas). SendGrid/Mailgun quedan desactivados salvo que definas explícitamente `ANYMAIL_PROVIDER` y su `ANYMAIL_API_KEY`.
- Credenciales: efímeras vía AWS SSO en desarrollo; roles IAM en producción.
- Variables de entorno de sesión: `AWS_PROFILE`, `AWS_REGION`, `ANYMAIL_PROVIDER=ses`, `DEFAULT_FROM_EMAIL`.
- Comandos útiles:
   - `manage.py ses_status` para validar credenciales activas.
   - `manage.py test_email` para probar entrega real.
   - Script de setup: `scripts/setup_ses_sso.ps1` para configurar y probar rápido.

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
