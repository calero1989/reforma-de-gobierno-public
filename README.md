# Simulador de Reforma Legislativa

Proyecto **independiente** del Auditor Bancario VCT.

Carpeta del proyecto: `C:\Users\judit\Documents\Reforma de gobierno`

Aplicación web para consultar leyes y simular el impacto de una reforma. Funciona en **ordenador, tablet y teléfono**, con Windows, macOS, Linux, Android o iOS: solo hace falta un navegador.

## Arrancar y enviar a otros dispositivos

En tu PC (el que hace de servidor):

```powershell
cd "C:\Users\judit\Documents\Reforma de gobierno"
.\iniciar.ps1
```

La terminal mostrará las URLs. En otro dispositivo:

1. **Misma Wi‑Fi:** abre `http://IP-DE-TU-PC:8765` (la IP aparece al arrancar).
2. **Código QR:** pulsa **Compartir** en la app y escanea con el móvil.
3. **Fuera de casa / otra red:**

```powershell
.\iniciar.ps1 -Publico
```

Eso publica un enlace `https://….trycloudflare.com` si tienes [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) instalado. Envía ese enlace por WhatsApp, correo, etc.

## Correo (Gmail) para «olvidé mi contraseña»

En el VPS, añade a `/opt/reforma-gobierno/.env` (ver `herramientas/smtp.env.example`):

- `SMTP_USER` / `SMTP_PASSWORD` (contraseña de aplicación de Gmail)
- `PUBLIC_URL` (URL pública actual del túnel o dominio)

Sin SMTP, el enlace de recuperación se escribe en el log del servidor.

En el teléfono o tablet pulsa **Instalar en el teléfono** y sigue los pasos (no uses el ZIP: en el móvil solo se guarda como documento). En Android, Chrome pedirá «Añadir a pantalla de inicio». En iPhone hay que abrirla en Safari → Compartir → Añadir a pantalla de inicio. En el ordenador, **Código (ZIP)** es el código fuente, no un instalador.

## Comunidad

En el apartado **Comunidad** la gente puede:

- Registrarse (para contar cuántas personas usan la app)
- Valorar de 1 a 5 y dejar sugerencias

Los datos se guardan en `datos/comunidad/` en este PC (no se publican correos).

### Linux / macOS

```bash
chmod +x iniciar.sh
./iniciar.sh
./iniciar.sh --publico
```

## Firewall (Windows)

Si el móvil no entra estando en la misma red, permite el puerto 8765 en el Firewall de Windows (regla de entrada TCP).

## Actualizar datos

```powershell
python .\herramientas\descargar_legislacion_boe.py
python .\herramientas\actualizar_datos_referencia.py
```

## Modelo de impacto

Calibrado con PGE 2025-P e INE (IPC `IPC251856`, tasa de paro `EPA7532`). Simulación orientativa: no sustituye informes oficiales.

## Repositorios GitHub

| Repo | Visibilidad | Contenido |
|------|-------------|-----------|
| [reforma-de-gobierno](https://github.com/calero1989/reforma-de-gobierno) | **Privado** | Completo (desarrollo propio) |
| [reforma-de-gobierno-public](https://github.com/calero1989/reforma-de-gobierno-public) | **Público** | Copia sanitizada (sin secretos ni datos de usuarios) |

Para actualizar el público tras cambios locales:

```powershell
.\herramientas\publicar-repo-publico.ps1
```

## VPS (servidor permanente)

Puede convivir con el bot del Auditor Bancario en el mismo VPS (`TU-VPS.ejemplo`), en el puerto **8765**, sin interferir (bot Discord + staff en 8090).

### Enlace público

| Ahora | Más adelante (con dominio) |
|-------|----------------------------|
| Túnel **rápido** Cloudflare (`*.trycloudflare.com`) | Túnel **nombrado** (`https://app.tudominio.com`) |
| La URL **cambia** al reiniciar el túnel | URL **fija** |
| No requiere dominio | Dominio en IONOS (u otro) + DNS en Cloudflare |

**Cuando tengas nombre y dominio:** sigue la guía [`herramientas/CUANDO_TENGAS_DOMINIO.md`](herramientas/CUANDO_TENGAS_DOMINIO.md) o ejecuta `.\herramientas\activar-dominio.ps1`.

### Desplegar / actualizar

```powershell
cd "C:\Users\judit\Documents\Reforma de gobierno"
.\herramientas\deploy-vps.ps1
```

Eso actualiza `/opt/reforma-gobierno/`, arranca `reforma-gobierno` + túnel HTTPS y programa copias diarias.

Solo app (sin re-subir ~380 MB de leyes):

```powershell
.\herramientas\deploy-vps.ps1 -SkipLeyes
```

Si en el futuro existe `.tunnel.env` (local o en el VPS), el despliegue usará el túnel nombrado en lugar del rápido.

### Copias de seguridad

| Dónde | Cuándo | Qué |
|-------|--------|-----|
| VPS local | 03:15 UTC | `backups/comunidad-*.tar.gz` |
| Google Drive | 03:15 UTC | `gdrive:reforma-gobierno-backups/` (tras configurar rclone) |
| Tu PC | 05:30 (hora local) | `backups-vps/` (tarea programada) |

**Programar copia diaria en tu PC** (una sola vez):

```powershell
cd "C:\Users\judit\Documents\Reforma de gobierno"
.\herramientas\instalar-tarea-backup-pc.cmd
```

La tarea se llama `ReformaGobierno-BackupPC` y corre a las **05:30** (hora local), después del backup del VPS (03:15 UTC ≈ 05:15 en verano en España).

**Descarga manual:**

```powershell
.\herramientas\descargar-backup-pc.ps1
```

**Gestionar la tarea:**

```powershell
Start-ScheduledTask -TaskName "ReformaGobierno-BackupPC"   # ejecutar ahora
Unregister-ScheduledTask -TaskName "ReformaGobierno-BackupPC" -Confirm:$false   # desactivar
Get-Content ".\backups-vps\backup-pc.log" -Tail 20   # ver log
```

**Activar nube (una vez en el VPS):**

```bash
ssh usuario@TU-VPS.ejemplo
rclone config   # crea remoto "gdrive" → Google Drive
rclone lsd gdrive:
```

**Restaurar en el VPS:**

```bash
bash /opt/reforma-gobierno/herramientas/restaurar-backup-vps.sh
# o desde Google Drive:
rclone copy gdrive:reforma-gobierno-backups/comunidad-YYYYMMDD-HHMM.tar.gz /tmp/
bash /opt/reforma-gobierno/herramientas/restaurar-backup-vps.sh /tmp/comunidad-....tar.gz
```

