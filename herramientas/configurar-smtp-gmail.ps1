# Configura SMTP Gmail en el VPS sin dejar la contraseña en el historial del chat.
# Uso: .\herramientas\configurar-smtp-gmail.ps1

param(
    [string]$VpsHost = "usuario@TU-VPS.ejemplo",
    [string]$EnvPath = "/opt/reforma-gobierno/.env"
)

$ErrorActionPreference = "Stop"

Write-Host "Configurar correo Gmail para el Simulador" -ForegroundColor Cyan
Write-Host "La contraseña de aplicacion NO se muestra ni se guarda en este chat." -ForegroundColor DarkGray
Write-Host ""

$email = Read-Host "Tu Gmail (ej. tu@gmail.com)"
if (-not $email -or $email -notmatch "@") {
    Write-Host "Correo no valido." -ForegroundColor Red
    exit 1
}

$secure = Read-Host "Contraseña de aplicacion (16 caracteres)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $pass = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
$pass = ($pass -replace "\s", "")
if ($pass.Length -lt 16) {
    Write-Host "La contraseña de aplicacion suele tener 16 caracteres." -ForegroundColor Red
    exit 1
}

$tunel = (ssh -o BatchMode=yes $VpsHost "cat /opt/reforma-gobierno/datos/tunel_url.txt 2>/dev/null").Trim()
if (-not $tunel) {
    $tunel = Read-Host "PUBLIC_URL (enlace https de la app)"
}

$tmp = [IO.Path]::GetTempFileName()
try {
    scp -o BatchMode=yes "${VpsHost}:${EnvPath}" $tmp | Out-Null
    $lines = Get-Content $tmp -ErrorAction SilentlyContinue
    if (-not $lines) { $lines = @() }

    function Set-EnvLine([string[]]$src, [string]$key, [string]$value) {
        $found = $false
        $out = foreach ($line in $src) {
            if ($line -match "^\s*#?\s*$key=") {
                if (-not $found) {
                    $found = $true
                    "$key=$value"
                }
            } else {
                $line
            }
        }
        if (-not $found) { $out += "$key=$value" }
        return $out
    }

    $lines = Set-EnvLine $lines "SMTP_HOST" "smtp.gmail.com"
    $lines = Set-EnvLine $lines "SMTP_PORT" "587"
    $lines = Set-EnvLine $lines "SMTP_USER" $email
    $lines = Set-EnvLine $lines "SMTP_PASSWORD" $pass
    $lines = Set-EnvLine $lines "SMTP_FROM" $email
    if ($tunel) { $lines = Set-EnvLine $lines "PUBLIC_URL" $tunel }

    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($tmp, [string[]]$lines, $utf8)
    scp -o BatchMode=yes $tmp "${VpsHost}:${EnvPath}"
    ssh -o BatchMode=yes $VpsHost "chmod 600 $EnvPath; systemctl restart reforma-gobierno; systemctl is-active reforma-gobierno"
} finally {
    if (Test-Path $tmp) { Remove-Item -Force $tmp }
    $pass = $null
}

Write-Host ""
Write-Host "Listo. SMTP configurado y servicio reiniciado." -ForegroundColor Green
Write-Host "Prueba en la app: Comunidad -> Olvide mi contraseña (con un correo registrado)." -ForegroundColor DarkGray
