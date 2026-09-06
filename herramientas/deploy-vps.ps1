# Despliega Reforma de gobierno en el VPS (junto al bot VCT, sin interferir)
#
# Tunel HTTPS:
#   - Sin .tunnel.env  -> túnel RÁPIDO (trycloudflare.com, URL temporal)
#   - Con .tunnel.env  -> túnel NOMBRADO (dominio permanente)
#   Guia dominio futuro: herramientas/CUANDO_TENGAS_DOMINIO.md
#
# Parametros:
#   -SkipLeyes         No sube la carpeta leyes (~380 MB); util para actualizar solo la app
#   -UploadComunidad  Sube datos/comunidad (PELIGROSO: puede sobrescribir comentarios del VPS)
param(
    [string]$VpsHost = "usuario@TU-VPS.ejemplo",
    [string]$Remoto = "/opt/reforma-gobierno",
    [switch]$SkipLeyes,
    # Por defecto NO se sube datos/comunidad: un scp desde el PC puede borrar
    # comentarios/usuarios del VPS si la copia local esta vacia o desfasada.
    [switch]$UploadComunidad
)

$ErrorActionPreference = "Stop"
$LocalRoot = Split-Path $PSScriptRoot -Parent

Write-Host "=== Despliegue Reforma de gobierno -> $VpsHost ===" -ForegroundColor Cyan

ssh -o BatchMode=yes $VpsHost "mkdir -p $Remoto"

Write-Host "Subiendo aplicacion (app, leyes, herramientas)..." -ForegroundColor Yellow
ssh -o BatchMode=yes $VpsHost "mkdir -p $Remoto/app $Remoto/herramientas $Remoto/datos/comunidad $Remoto/leyes"
scp -o BatchMode=yes -r "$LocalRoot\app" "${VpsHost}:${Remoto}/"
Get-ChildItem "$LocalRoot\herramientas" -File | Where-Object { $_.Name -ne 'programar-backup-pc.ps1' } | ForEach-Object {
    scp -o BatchMode=yes $_.FullName "${VpsHost}:${Remoto}/herramientas/"
}
scp -o BatchMode=yes "$LocalRoot\requirements.txt" "$LocalRoot\iniciar.sh" "$LocalRoot\README.md" "${VpsHost}:${Remoto}/"

if (-not $SkipLeyes -and (Test-Path "$LocalRoot\leyes")) {
    Write-Host "Subiendo leyes (~380 MB, puede tardar varios minutos)..." -ForegroundColor Yellow
    scp -o BatchMode=yes -r "$LocalRoot\leyes" "${VpsHost}:${Remoto}/"
} elseif ($SkipLeyes) {
    Write-Host "Omitiendo leyes (-SkipLeyes)." -ForegroundColor DarkGray
}

if (Test-Path "$LocalRoot\constitucion") {
    Write-Host "Subiendo constitucion..." -ForegroundColor Yellow
    ssh -o BatchMode=yes $VpsHost "mkdir -p $Remoto/constitucion"
    scp -o BatchMode=yes -r "$LocalRoot\constitucion\*" "${VpsHost}:${Remoto}/constitucion/"
}

$datosLocal = Join-Path $LocalRoot "datos\comunidad"
if ($UploadComunidad -and (Test-Path $datosLocal)) {
    Write-Host "Subiendo datos/comunidad (SOBRESCRIBE el VPS)..." -ForegroundColor Yellow
    scp -o BatchMode=yes -r "$datosLocal\*" "${VpsHost}:${Remoto}/datos/comunidad/"
} elseif ($UploadComunidad) {
    Write-Host "UploadComunidad pedido pero no existe $datosLocal" -ForegroundColor Red
} else {
    Write-Host "Omitiendo datos/comunidad (protege comentarios del VPS). Usa -UploadComunidad solo a proposito." -ForegroundColor DarkGray
}

if (Test-Path "$LocalRoot\datos\referencia.json") {
    scp -o BatchMode=yes "$LocalRoot\datos\referencia.json" "${VpsHost}:${Remoto}/datos/"
}

Write-Host "Configurando SECRET_KEY..." -ForegroundColor Yellow
$secretCmd = 'bash -c "test -s {0}/.env || (umask 077; echo SECRET_KEY=$(openssl rand -hex 32) > {0}/.env); chmod 600 {0}/.env"' -f $Remoto
ssh -o BatchMode=yes $VpsHost $secretCmd

$unit = @"
[Unit]
Description=Reforma de gobierno (Flask + Waitress)
After=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$Remoto
EnvironmentFile=-$Remoto/.env
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=$Remoto
Environment=HOST=127.0.0.1
Environment=PORT=8765
Environment=MODO_VPS=1
ExecStart=$Remoto/.venv/bin/python -m app.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"@

$unitLf = $unit -replace "`r`n", "`n"
$unitB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($unitLf))
ssh -o BatchMode=yes $VpsHost "echo $unitB64 | base64 -d > /etc/systemd/system/reforma-gobierno.service"

$cmds = @(
    "cd $Remoto",
    "python3 -m venv .venv",
    ".venv/bin/pip install -q -r requirements.txt",
    ".venv/bin/python herramientas/generar_iconos.py 2>/dev/null || true",
    "chmod +x herramientas/*.sh",
    "systemctl daemon-reload",
    "systemctl enable reforma-gobierno",
    "systemctl restart reforma-gobierno",
    "sleep 3",
    "systemctl is-active reforma-gobierno"
)
foreach ($c in $cmds) {
    ssh -o BatchMode=yes $VpsHost $c
}

Write-Host "Instalando tunel HTTPS..." -ForegroundColor Cyan
$tunnelEnvLocal = Join-Path $LocalRoot ".tunnel.env"
if (Test-Path $tunnelEnvLocal) {
    scp -o BatchMode=yes $tunnelEnvLocal "${VpsHost}:${Remoto}/.tunnel.env"
    ssh -o BatchMode=yes $VpsHost "chmod 600 $Remoto/.tunnel.env"
    $tunnelOut = ssh -o BatchMode=yes $VpsHost "bash $Remoto/herramientas/install-tunnel-nombrado-vps.sh 2>&1"
} else {
    $hasNamed = ssh -o BatchMode=yes $VpsHost "test -f $Remoto/.tunnel.env && echo yes || echo no"
    if ($hasNamed -match "yes") {
        $tunnelOut = ssh -o BatchMode=yes $VpsHost "bash $Remoto/herramientas/install-tunnel-nombrado-vps.sh 2>&1"
    } else {
        $tunnelOut = ssh -o BatchMode=yes $VpsHost "bash $Remoto/herramientas/install-tunnel-vps.sh 2>&1"
    }
}
$tunnelOut
if ($tunnelOut -match "PUBLIC_URL=(https://[^\s]+)") {
    Write-Host "`nApp publica: $($Matches[1])" -ForegroundColor Green
} elseif ($tunnelOut -match "(https://[a-zA-Z0-9.-]+\.trycloudflare\.com)") {
    Write-Host "`nApp publica: $($Matches[1])" -ForegroundColor Green
} else {
    $urlGuardada = ssh -o BatchMode=yes $VpsHost "cat $Remoto/datos/tunel_url.txt 2>/dev/null || true"
    if ($urlGuardada) { Write-Host "`nApp publica: $urlGuardada" -ForegroundColor Green }
}

Write-Host "Instalando copias de seguridad..." -ForegroundColor Cyan
ssh -o BatchMode=yes $VpsHost "bash $Remoto/herramientas/install-backup-vps.sh"

Write-Host "`n=== Despliegue completado ===" -ForegroundColor Green
Write-Host "Servicios: reforma-gobierno, reforma-gobierno-tunnel"
Write-Host "Backup PC:  .\herramientas\descargar-backup-pc.ps1"
Write-Host "Dominio permanente (cuando lo tengas): herramientas\CUANDO_TENGAS_DOMINIO.md" -ForegroundColor DarkGray
