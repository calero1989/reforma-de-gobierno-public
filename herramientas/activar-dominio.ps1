# Asistente para activar URL permanente cuando ya tengas dominio y token Cloudflare
param(
    [string]$VpsHost = "usuario@TU-VPS.ejemplo"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path $PSScriptRoot -Leaf
$Root = Split-Path $PSScriptRoot -Parent

Write-Host ""
Write-Host "=== Activar dominio permanente (Reforma de gobierno) ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Necesitas haber creado el tunel en Cloudflare y copiado el token." -ForegroundColor DarkGray
Write-Host "Guia completa: herramientas\CUANDO_TENGAS_DOMINIO.md" -ForegroundColor DarkGray
Write-Host ""

$dominio = Read-Host "Dominio (ej: micomunidad.es, sin https://)"
$sub = Read-Host "Subdominio para la app (ej: app o reforma; Enter = app)"
if ([string]::IsNullOrWhiteSpace($sub)) { $sub = "app" }
$hostname = "$sub.$($dominio.Trim().TrimEnd('.'))"

Write-Host ""
Write-Host "La URL sera: https://$hostname" -ForegroundColor Yellow
Write-Host ""
Write-Host "Pega el TUNNEL_TOKEN de Cloudflare (eyJ...):" -ForegroundColor White
$token = Read-Host

if ([string]::IsNullOrWhiteSpace($token) -or $token.Length -lt 20) {
    Write-Host "Token invalido o vacio." -ForegroundColor Red
    exit 1
}

$confirm = Read-Host "Continuar? (s/N)"
if ($confirm -notmatch '^[sS]') {
    Write-Host "Cancelado."
    exit 0
}

& "$PSScriptRoot\configurar-tunnel-nombrado.ps1" `
    -VpsHost $VpsHost `
    -TunnelToken $token.Trim() `
    -PublicHostname $hostname

Write-Host ""
Write-Host "Listo. Comparte: https://$hostname" -ForegroundColor Green
Write-Host "Si cambias el nombre de la app, edita el hostname en Cloudflare y vuelve a ejecutar este script." -ForegroundColor DarkGray
