# Descarga la última copia de seguridad del VPS a tu PC
param(
    [string]$VpsHost = "usuario@TU-VPS.ejemplo",
    [string]$Remoto = "/opt/reforma-gobierno/backups/latest.tar.gz",
    [string]$Destino = ""
)

$ErrorActionPreference = "Stop"
$LocalRoot = Split-Path $PSScriptRoot -Parent
if (-not $Destino) {
    $Destino = Join-Path $LocalRoot "backups-vps"
}
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$archivo = Join-Path $Destino "comunidad-$stamp.tar.gz"

Write-Host "Descargando backup del VPS..." -ForegroundColor Cyan
scp -o BatchMode=yes "${VpsHost}:${Remoto}" $archivo

Copy-Item -Force $archivo (Join-Path $Destino "latest.tar.gz")
Write-Host "Guardado en: $archivo" -ForegroundColor Green
Write-Host "Copia reciente: $(Join-Path $Destino 'latest.tar.gz')" -ForegroundColor Green
