# Programa descarga diaria del backup VPS -> PC (03:30 hora local)
param(
    [string]$VpsHost = "usuario@TU-VPS.ejemplo"
)

$ErrorActionPreference = "Stop"
$Script = Join-Path $PSScriptRoot "descargar-backup-pc.ps1"
$TaskName = "ReformaGobierno-BackupVPS"

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`" -VpsHost $VpsHost"
$trigger = New-ScheduledTaskTrigger -Daily -At "03:30"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Tarea programada: $TaskName (todos los dÃ­as a las 03:30)" -ForegroundColor Green
Write-Host "Para probar ahora: powershell -File `"$Script`"" -ForegroundColor Cyan

