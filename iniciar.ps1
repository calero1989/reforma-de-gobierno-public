param(
    [switch]$Red,
    [switch]$Publico,
    [int]$Puerto = 8765
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt

$env:PYTHONPATH = $PSScriptRoot
$env:PORT = "$Puerto"
if ($Red -or $Publico) {
    $env:HOST = "0.0.0.0"
} else {
    $env:HOST = "0.0.0.0"
}
if ($Publico) {
    $env:PUBLICO = "1"
} else {
    $env:PUBLICO = "0"
}

Write-Host "Simulador de Reforma Legislativa"
if ($Publico) {
    Write-Host "Modo: enlace publico (cualquier dispositivo con internet)"
} else {
    Write-Host "Modo: este PC y dispositivos en la misma Wi-Fi"
}

& .\.venv\Scripts\python.exe -m app.server
