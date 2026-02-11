
# Script PowerShell para activar entorno, iniciar sesión SSO y enviar email automáticamente
# Guarda este archivo como setup_ses_sso.ps1 y ejecútalo desde la raíz del proyecto

# Activar entorno virtual
Write-Host "Activando entorno virtual..."
& "imprenta_tuc/Scripts/Activate.ps1"

# Iniciar sesión SSO
Write-Host "Iniciando sesión AWS SSO..."
aws sso login --profile default

# Pedir destinatario
$destinatario = Read-Host "Ingresa el correo destinatario (verificado en SES)"

# Opcional: pedir asunto y cuerpo
$asunto = Read-Host "Asunto del email (opcional, Enter para predeterminado)"
$cuerpo = Read-Host "Cuerpo del email (opcional, Enter para predeterminado)"

# Construir comando
$cmd = "python proyec_imprenta/imprenta_tucan/manage.py test_email --to $destinatario"
if ($asunto -ne "") { $cmd += " --subject `"$asunto`"" }
if ($cuerpo -ne "") { $cmd += " --body `"$cuerpo`"" }

Write-Host "Ejecutando envío de email..."
Invoke-Expression $cmd

Write-Host "Proceso finalizado. Revisa la salida para confirmar el envío."
