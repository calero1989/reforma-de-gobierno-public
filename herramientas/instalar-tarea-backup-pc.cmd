@echo off
REM Instala la tarea programada de descarga diaria del backup del VPS.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$Descarga='%~dp0descargar-backup-pc.ps1';" ^
  "$LogDir='%~dp0..\backups-vps';" ^
  "$Nombre='ReformaGobierno-BackupPC';" ^
  "$Hora='05:30';" ^
  "New-Item -ItemType Directory -Force -Path $LogDir | Out-Null;" ^
  "$p=$Hora.Split(':');" ^
  "$accion=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File \"{0}\" >> \"{1}\backup-pc.log\" 2>&1' -f $Descarga,$LogDir);" ^
  "$disparo=New-ScheduledTaskTrigger -Daily -At (Get-Date -Hour ([int]$p[0]) -Minute ([int]$p[1]) -Second 0);" ^
  "$ajustes=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1);" ^
  "Get-ScheduledTask -TaskName $Nombre -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false;" ^
  "Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparo -Settings $ajustes -Description 'Descarga diaria backup Reforma de gobierno desde VPS' | Out-Null;" ^
  "Write-Host ('Tarea creada: ' + $Nombre);" ^
  "Write-Host ('Horario: todos los dias a las ' + $Hora);" ^
  "Write-Host ('Carpeta: ' + (Resolve-Path $LogDir));"
