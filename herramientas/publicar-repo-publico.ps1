# Publica una copia SANITIZADA en el repo público.
# Uso (desde la raíz del proyecto privado):
#   .\herramientas\publicar-repo-publico.ps1
#   .\herramientas\publicar-repo-publico.ps1 -Mensaje "Actualización foro"
#
# Repo privado (completo):  https://github.com/calero1989/reforma-de-gobierno
# Repo público (sanitizado): https://github.com/calero1989/reforma-de-gobierno-public
#
# NUNCA copia: .env, datos/comunidad, tuneles, backups, venv, secretos.

param(
    [string]$Mensaje = "Actualización pública sanitizada",
    [string]$RepoPublicoUrl = "https://github.com/calero1989/reforma-de-gobierno-public.git",
    [string]$Destino = ""
)

$ErrorActionPreference = "Stop"
$LocalRoot = Split-Path $PSScriptRoot -Parent
if (-not $Destino) {
    $Destino = Join-Path (Split-Path $LocalRoot -Parent) "reforma-de-gobierno-public"
}

Write-Host "=== Publicar copia pública sanitizada ===" -ForegroundColor Cyan
Write-Host "Origen : $LocalRoot"
Write-Host "Destino: $Destino"

# Exclusiones (robocopy)
$excluirDirs = @(
    ".git", ".venv", "__pycache__", "datos\comunidad", "backups-vps", "backups",
    "node_modules", ".cursor"
)
$excluirArchivos = @(
    ".env", ".env.*", ".tunnel.env", "tunel_url.txt", "smtp.env",
    "*.pyc", "*.pyo", "*.log", "Thumbs.db", ".DS_Store"
)

if (-not (Test-Path $Destino)) {
    New-Item -ItemType Directory -Force -Path $Destino | Out-Null
    git -C $Destino init -b main | Out-Null
    git -C $Destino remote add origin $RepoPublicoUrl
    Write-Host "Repo público local inicializado." -ForegroundColor DarkGray
} elseif (-not (Test-Path (Join-Path $Destino ".git"))) {
    git -C $Destino init -b main | Out-Null
    git -C $Destino remote add origin $RepoPublicoUrl 2>$null
}

# Limpiar destino (salvo .git) para evitar restos
Get-ChildItem $Destino -Force | Where-Object { $_.Name -ne ".git" } | Remove-Item -Recurse -Force

$xd = ($excluirDirs | ForEach-Object { "/XD"; $_ })
$xf = ($excluirArchivos | ForEach-Object { "/XF"; $_ })
$argsRobo = @($LocalRoot, $Destino, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np") + $xd + $xf
& robocopy @argsRobo | Out-Null
# robocopy exit codes 0-7 = success-ish
if ($LASTEXITCODE -ge 8) {
    throw "robocopy falló con código $LASTEXITCODE"
}

# Sanitizar infra / secretos en la copia pública
$reemplazos = @(
    @{ De = "usuario@TU-VPS.ejemplo"; A = "usuario@TU-VPS.ejemplo" },
    @{ De = "TU-VPS.ejemplo"; A = "TU-VPS.ejemplo" }
)

$extensiones = "*.md", "*.ps1", "*.sh", "*.cmd", "*.py", "*.txt", "*.example", "*.env.example"
Get-ChildItem $Destino -Recurse -File -Include $extensiones -ErrorAction SilentlyContinue | ForEach-Object {
    $raw = [System.IO.File]::ReadAllText($_.FullName)
    $nuevo = $raw
    foreach ($r in $reemplazos) {
        $nuevo = $nuevo.Replace($r.De, $r.A)
    }
    if ($nuevo -ne $raw) {
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($_.FullName, $nuevo, $utf8)
        Write-Host "Sanitizado: $($_.FullName.Substring($Destino.Length + 1))" -ForegroundColor DarkGray
    }
}

# Aviso público
$aviso = @"
# Simulador de Reforma Legislativa (repo público)

Esta es la **copia pública sanitizada** del proyecto.

| Repo | Uso |
|------|-----|
| [reforma-de-gobierno](https://github.com/calero1989/reforma-de-gobierno) | Privado / completo (desarrollo propio) |
| **Este repo** | Público, sin secretos ni datos de usuarios |

## Qué NO incluye a propósito
- Contraseñas, `.env`, tokens de túnel
- Datos de comunidad (usuarios, correos, comentarios reales del servidor)
- IP / credenciales reales del VPS (sustituidas por placeholders)

## Arranque rápido
1. Instala Python 3
2. Crea un `.env` local a partir de `herramientas/smtp.env.example` (opcional)
3. Descarga leyes: ``python herramientas/descargar_legislacion_boe.py``
4. Arranca: ``.\iniciar.ps1``

Los textos legales se obtienen del BOE (legislación consolidada). Las simulaciones son orientativas.

Última sincronización pública: $(Get-Date -Format "yyyy-MM-dd HH:mm")
"@
$avisoPath = Join-Path $Destino "AVISO_REPO_PUBLICO.md"
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($avisoPath, $aviso, $utf8)

# .gitignore público reforzado
$gi = @"
.venv/
__pycache__/
*.pyc
*.pyo
.env
.env.*
!.env.example
.tunnel.env
herramientas/smtp.env
datos/comunidad/
datos/tunel_url.txt
backups-vps/
backups/
*.tar.gz
*.log
.DS_Store
Thumbs.db
"@
[System.IO.File]::WriteAllText((Join-Path $Destino ".gitignore"), $gi, $utf8)

# Asegurar que no hay restos sensibles
$prohibidos = @(
    (Join-Path $Destino "datos\comunidad"),
    (Join-Path $Destino ".env"),
    (Join-Path $Destino ".tunnel.env"),
    (Join-Path $Destino "datos\tunel_url.txt")
)
foreach ($p in $prohibidos) {
    if (Test-Path $p) {
        Remove-Item -Recurse -Force $p
        Write-Host "Eliminado del público: $p" -ForegroundColor Yellow
    }
}

# Commit + push
Push-Location $Destino
try {
    git add -A
    $pendiente = git status --porcelain
    if (-not $pendiente) {
        Write-Host "Sin cambios nuevos en el repo público." -ForegroundColor DarkGray
    } else {
        git -c user.name="calero1989" -c user.email="vidagaming.89@gmail.com" commit -m $Mensaje
    }
    git push -u origin main
    Write-Host "Push público OK → $RepoPublicoUrl" -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Privado: https://github.com/calero1989/reforma-de-gobierno" -ForegroundColor Cyan
Write-Host "Público: https://github.com/calero1989/reforma-de-gobierno-public" -ForegroundColor Cyan
