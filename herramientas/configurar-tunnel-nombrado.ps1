# Configura túnel Cloudflare NOMBRADO (URL permanente) para Reforma de gobierno
param(
    [string]$VpsHost = "usuario@TU-VPS.ejemplo",
    [string]$Remoto = "/opt/reforma-gobierno",
    [Parameter(Mandatory = $true)]
    [string]$TunnelToken,
    [Parameter(Mandatory = $true)]
    [string]$PublicHostname
)

$ErrorActionPreference = "Stop"
$hostname = $PublicHostname.Trim().TrimEnd("/")
if ($hostname -match "^https?://") {
    $hostname = ($hostname -replace "^https?://", "")
}

$envContent = @"
TUNNEL_TOKEN=$TunnelToken
PUBLIC_HOSTNAME=$hostname
"@

$localEnv = Join-Path $env:TEMP "reforma-tunnel.env"
Set-Content -Path $localEnv -Value $envContent -Encoding UTF8 -NoNewline

Write-Host "Subiendo configuracion del tunel nombrado..." -ForegroundColor Cyan
scp -o BatchMode=yes $localEnv "${VpsHost}:${Remoto}/.tunnel.env"
ssh -o BatchMode=yes $VpsHost "chmod 600 $Remoto/.tunnel.env"
Remove-Item $localEnv -Force

Write-Host "Instalando tunel nombrado en el VPS..." -ForegroundColor Cyan
$out = ssh -o BatchMode=yes $VpsHost "bash $Remoto/herramientas/install-tunnel-nombrado-vps.sh 2>&1"
$out
if ($out -match "PUBLIC_URL=(https://[^\s]+)") {
    Write-Host "`nURL permanente: $($Matches[1])" -ForegroundColor Green
} elseif ($out -match "(https://[^\s]+)") {
    Write-Host "`nURL permanente: $($Matches[1])" -ForegroundColor Green
}
