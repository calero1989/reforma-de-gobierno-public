# Cuando tengas nombre y dominio

Guía para pasar de la URL temporal (`trycloudflare.com`) a una **URL permanente** con tu propio dominio.

**Ahora (sin dominio):** el VPS usa túnel rápido Cloudflare. La URL cambia si reinicias el túnel.  
**Después (con dominio):** un túnel nombrado con `https://app.TUDOMINIO.com` (o el subdominio que elijas).

---

## Requisitos previos

- [ ] Nombre definitivo de la aplicación (para elegir dominio y subdominio)
- [ ] Dominio comprado (p. ej. en **IONOS**, donde tienes el VPS)
- [ ] Cuenta gratuita en [Cloudflare](https://dash.cloudflare.com/)
- [ ] Dominio añadido a Cloudflare (cambiar nameservers en IONOS → los de Cloudflare)

---

## Paso 1 — Elegir subdominios

En el **mismo VPS** (`TU-VPS.ejemplo`) puedes tener varios servicios:

| Servicio              | Subdominio sugerido     | Puerto local   |
|-----------------------|-------------------------|----------------|
| Reforma de gobierno   | `app.TUDOMINIO.com`     | `8765`         |
| Bot VCT (staff)       | `vct.TUDOMINIO.com`     | `8090`         |

Sustituye `TUDOMINIO.com` por tu dominio real (p. ej. `micomunidad.es` → `app.micomunidad.es`).

---

## Paso 2 — Crear túnel en Cloudflare

1. Entra en [Zero Trust → Networks → Tunnels](https://one.dash.cloudflare.com/)
2. **Create a tunnel** → tipo **Cloudflared**
3. Nombre del túnel: `reforma-gobierno` (o el que prefieras)
4. En **Public Hostname** (ruta publicada):
   - **Subdomain:** `app` (o `reforma`, según tu gusto)
   - **Domain:** `TUDOMINIO.com`
   - **Service type:** HTTP
   - **URL:** `127.0.0.1:8765`
5. Copia el **token** de instalación (cadena larga que empieza por `eyJ...`)

*(Opcional)* Añade otra ruta en el mismo túnel o un segundo túnel para VCT → `127.0.0.1:8090`.

---

## Paso 3 — Activar desde tu PC (Windows)

Opción **A** — asistente con preguntas:

```powershell
cd "C:\Users\judit\Documents\Reforma de gobierno"
.\herramientas\activar-dominio.ps1
```

Opción **B** — parámetros directos:

```powershell
.\herramientas\configurar-tunnel-nombrado.ps1 `
  -TunnelToken "eyJ..." `
  -PublicHostname "app.TUDOMINIO.com"
```

Eso sube `.tunnel.env` al VPS, instala el túnel nombrado y guarda la URL en `datos/tunel_url.txt`.

---

## Paso 4 — Comprobar

1. Abre `https://app.TUDOMINIO.com` en el navegador
2. En el VPS:

```bash
ssh usuario@TU-VPS.ejemplo
systemctl status reforma-gobierno-tunnel
cat /opt/reforma-gobierno/datos/tunel_url.txt
```

3. En la app, pulsa **Compartir** — debe mostrar tu dominio, no `trycloudflare.com`

---

## Archivos implicados

| Archivo | Uso |
|---------|-----|
| `herramientas/install-tunnel-vps.sh` | Túnel **rápido** (actual, URL temporal) |
| `herramientas/install-tunnel-nombrado-vps.sh` | Túnel **nombrado** (URL permanente) |
| `herramientas/tunnel.env.example` | Plantilla de `.tunnel.env` (no commitear el real) |
| `herramientas/configurar-tunnel-nombrado.ps1` | Sube config y activa túnel nombrado |
| `herramientas/activar-dominio.ps1` | Asistente interactivo |
| `/opt/reforma-gobierno/.tunnel.env` | En el VPS; contiene token y hostname |

---

## Despliegues futuros

- **Sin dominio aún:** `.\herramientas\deploy-vps.ps1 -SkipLeyes` → sigue usando túnel rápido
- **Con dominio ya configurado:** si existe `.tunnel.env` en el VPS (o copias `.tunnel.env` en la raíz del proyecto antes de desplegar), `deploy-vps.ps1` activará el túnel nombrado automáticamente

---

## Cambiar de nombre / subdominio más adelante

1. En Cloudflare, edita el **Public Hostname** del túnel (nuevo subdominio)
2. Actualiza `PUBLIC_HOSTNAME` en `/opt/reforma-gobierno/.tunnel.env`
3. Ejecuta de nuevo `configurar-tunnel-nombrado.ps1` o `activar-dominio.ps1`
4. (Opcional) Renombra textos en la app, PWA y README cuando fijes el nombre comercial

---

## Volver al túnel temporal (solo pruebas)

```bash
ssh usuario@TU-VPS.ejemplo
rm /opt/reforma-gobierno/.tunnel.env
bash /opt/reforma-gobierno/herramientas/install-tunnel-vps.sh
```

La URL volverá a ser `*.trycloudflare.com` (cambia al reiniciar).
