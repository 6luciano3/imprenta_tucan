<#
Script de configuración rápida para Amazon SES con AWS SSO en Windows.

Uso:
  1) Ejecuta este script en PowerShell:
     PS> ./scripts/setup_ses_sso.ps1
  2) Sigue las indicaciones para seleccionar perfil SSO, región y remitente.
  3) Inicia sesión SSO cuando se te solicite.
  4) Ejecuta el comando de prueba de email (opcional).

Este script NO guarda credenciales ni claves. Solo establece variables de entorno
para la sesión actual y usa credenciales efímeras de SSO/IAM.
#>

param(
    [string]$PerfilSSO,
    [string]$Region = "us-east-1",
    [string]$Remitente,
    [string]$DestinoPrueba,
    [switch]$ProbarEnvio
)

Write-Host "Configuración de SES + SSO (sin contraseñas)" -ForegroundColor Cyan

# Verificar AWS CLI
try {
    $awsVersion = & "$env:ProgramFiles\Amazon\AWSCLIV2\aws.exe" --version 2>$null
} catch {
    $awsVersion = $null
}
if (-not $awsVersion) {
    Write-Host "AWS CLI no encontrado. Instala con:" -ForegroundColor Red
    Write-Host "   winget install Amazon.AWSCLI" -ForegroundColor Yellow
    exit 1
}
Write-Host "AWS CLI detectado: $awsVersion" -ForegroundColor Green

# Solicitar datos si no se pasan por parámetro
if (-not $PerfilSSO) { $PerfilSSO = Read-Host "Perfil SSO (por ejemplo, 'default' o 'empresa')" }
if (-not $Region) { $Region = Read-Host "Región AWS (por ejemplo, us-east-1)" }
if (-not $Remitente) { $Remitente = Read-Host "Email remitente verificado en SES (no-reply@tu-dominio.com)" }

# Exportar variables de entorno (solo sesión actual)
$env:AWS_PROFILE = $PerfilSSO
$env:AWS_REGION = $Region
$env:ANYMAIL_PROVIDER = "ses"
$env:DEFAULT_FROM_EMAIL = $Remitente

Write-Host "Entorno configurado:" -ForegroundColor Green
Write-Host "   AWS_PROFILE=$env:AWS_PROFILE"
Write-Host "   AWS_REGION=$env:AWS_REGION"
Write-Host "   ANYMAIL_PROVIDER=$env:ANYMAIL_PROVIDER"
Write-Host "   DEFAULT_FROM_EMAIL=$env:DEFAULT_FROM_EMAIL"

# Configurar perfil SSO
Write-Host "Configurando perfil SSO..." -ForegroundColor Cyan
aws configure sso --profile $env:AWS_PROFILE

# Iniciar sesión SSO
Write-Host "Iniciando sesión con AWS SSO..." -ForegroundColor Cyan
aws sso login --profile $env:AWS_PROFILE

# Comprobar identidad
Write-Host "Verificando identidad STS..." -ForegroundColor Cyan
try {
    $identity = aws sts get-caller-identity | ConvertFrom-Json
    Write-Host "Identidad activa: $($identity.Arn)" -ForegroundColor Green
} catch {
    Write-Host "No se pudieron obtener credenciales. Asegúrate de completar el login SSO." -ForegroundColor Red
    exit 1
}

if ($ProbarEnvio) {
    if (-not $DestinoPrueba) {
        $DestinoPrueba = Read-Host "Email destino de prueba (debe estar permitido en SES)"
    }
    Write-Host "Enviando email de prueba via manage.py test_email..." -ForegroundColor Cyan
    & "$PSScriptRoot\..\..\imprenta_tuc\Scripts\python.exe" "$PSScriptRoot\..\imprenta_tucan\manage.py" test_email --to $DestinoPrueba --subject "Prueba SES" --body "Entrega real vía SES + SSO"
}

Write-Host "Validando estado de SES y credenciales..." -ForegroundColor Cyan
& "$PSScriptRoot\..\..\imprenta_tuc\Scripts\python.exe" "$PSScriptRoot\..\imprenta_tucan\manage.py" ses_status

Write-Host "Listo. Configuración completada." -ForegroundColor Green
