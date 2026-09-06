# Crea una tarea programada en Windows para descargar el backup del VPS cada dia.
param(
    [string]$Hora = "05:30",
    [string]$NombreTarea = "ReformaGobierno-BackupPC"
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
$Descarga = Join-Path $ScriptDir "descargar-backup-pc.ps1"
$LogDir = Join-Path (Split-Path $ScriptDir -Parent) "backups-vps"

if (-not (Test-Path $Descarga)) {
    Write-Error "No se encuentra: $Descarga"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$partes = $Hora.Split(":")
if ($partes.Count -ne 2) {
    Write-Error "Hora invalida. Usa formato HH:mm (ejemplo: 05:30)."
}
$hh = [int]$partes[0]
$mm = [int]$partes[1]

$wrapper = Join-Path $LogDir "ejecutar-descarga-backup.ps1"
@"
`$ErrorActionPreference = 'Stop'
`$log = Join-Path '$LogDir' 'backup-pc.log'
`$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
try {
    & '$Descarga' *>> `$log
    "`$stamp OK" | Add-Content `$log
} catch {
    "`$stamp ERROR: `$_" | Add-Content `$log
    exit 1
}
"@ | Set-Content -Path $wrapper -Encoding UTF8

$accion = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$wrapper`""

$disparo = New-ScheduledTaskTrigger -Daily -At (Get-Date -Hour $hh -Minute $mm -Second 0)

$ajustes = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$existente = Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
if ($existente) {
    Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $NombreTarea `
    -Action $accion `
    -Trigger $disparo `
    -Settings $ajustes `
    -Description "Descarga diaria del backup de Reforma de gobierno desde el VPS." `
    -RunLevel Highest | Out-Null

Write-Host "Tarea creada: $NombreTarea" -ForegroundColor Green
Write-Host "Horario: todos los dias a las $Hora (hora local de Windows)" -ForegroundColor Green
Write-Host "Destino: $LogDir" -ForegroundColor Green
Write-Host "Log: $(Join-Path $LogDir 'backup-pc.log')" -ForegroundColor Green
Write-Host ""
Write-Host "Para desactivar: Unregister-ScheduledTask -TaskName '$NombreTarea' -Confirm:`$false"
Write-Host "Para ejecutar ahora: Start-ScheduledTask -TaskName '$NombreTarea'"
