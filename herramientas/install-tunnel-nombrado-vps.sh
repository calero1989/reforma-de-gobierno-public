#!/bin/bash
# Túnel Cloudflare NOMBRADO (URL permanente con tu dominio)
# Requiere /opt/reforma-gobierno/.tunnel.env — ver herramientas/CUANDO_TENGAS_DOMINIO.md
#
# Requisitos:
#   - Cuenta Cloudflare + dominio gestionado en su DNS
#   - Archivo /opt/reforma-gobierno/.tunnel.env con:
#       TUNNEL_TOKEN=eyJ...        (desde Zero Trust > Networks > Tunnels)
#       PUBLIC_HOSTNAME=reforma.tudominio.com
#
# Crear el túnel en: https://one.dash.cloudflare.com/ → Networks → Tunnels
set -euo pipefail

REMOTE_DIR=/opt/reforma-gobierno
ENV_FILE="$REMOTE_DIR/.tunnel.env"
URL_FILE="$REMOTE_DIR/datos/tunel_url.txt"
LOG_FILE="$REMOTE_DIR/tunnel.log"
TUNNEL_NAME="reforma-gobierno"

if ! command -v cloudflared >/dev/null 2>&1; then
  curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
  dpkg -i /tmp/cloudflared.deb || apt-get install -f -y
fi

mkdir -p "$REMOTE_DIR/datos"
touch "$LOG_FILE"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

install_token_service() {
  if [[ -z "${TUNNEL_TOKEN:-}" ]]; then
    echo "ERROR: Falta TUNNEL_TOKEN en $ENV_FILE" >&2
    return 1
  fi
  systemctl stop reforma-gobierno-tunnel 2>/dev/null || true
  cat > /etc/systemd/system/reforma-gobierno-tunnel.service <<UNIT
[Unit]
Description=Cloudflare Named Tunnel -> Reforma de gobierno :8765
After=network-online.target reforma-gobierno.service
Wants=reforma-gobierno.service

[Service]
Type=simple
EnvironmentFile=-$ENV_FILE
ExecStart=/usr/bin/cloudflared tunnel run --token \${TUNNEL_TOKEN} --no-autoupdate
Restart=always
RestartSec=10
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=multi-user.target
UNIT
  if [[ -n "${PUBLIC_HOSTNAME:-}" ]]; then
    echo "https://${PUBLIC_HOSTNAME}" > "$URL_FILE"
    echo "PUBLIC_URL=https://${PUBLIC_HOSTNAME}"
  fi
  return 0
}

install_local_named_tunnel() {
  local hostname="$1"
  local cert="/root/.cloudflared/cert.pem"

  if [[ ! -f "$cert" ]]; then
    echo "ERROR: No existe $cert. Ejecuta: cloudflared tunnel login" >&2
    return 1
  fi

  if ! cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    cloudflared tunnel create "$TUNNEL_NAME"
  fi

  local tunnel_id
  tunnel_id=$(cloudflared tunnel list 2>/dev/null | awk -v n="$TUNNEL_NAME" '$0 ~ n {print $1; exit}')
  if [[ -z "$tunnel_id" ]]; then
    echo "ERROR: No se pudo obtener el ID del túnel $TUNNEL_NAME" >&2
    return 1
  fi

  mkdir -p /root/.cloudflared
  cat > /root/.cloudflared/config.yml <<YAML
tunnel: $tunnel_id
credentials-file: /root/.cloudflared/${tunnel_id}.json

ingress:
  - hostname: $hostname
    service: http://127.0.0.1:8765
  - service: http_status:404
YAML

  cloudflared tunnel route dns "$TUNNEL_NAME" "$hostname" || true

  cat > /etc/systemd/system/reforma-gobierno-tunnel.service <<UNIT
[Unit]
Description=Cloudflare Named Tunnel -> Reforma de gobierno :8765
After=network-online.target reforma-gobierno.service
Wants=reforma-gobierno.service

[Service]
Type=simple
ExecStart=/usr/bin/cloudflared tunnel --config /root/.cloudflared/config.yml run --no-autoupdate
Restart=always
RestartSec=10
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=multi-user.target
UNIT

  echo "https://${hostname}" > "$URL_FILE"
  echo "PUBLIC_URL=https://${hostname}"
}

if [[ -n "${TUNNEL_TOKEN:-}" ]]; then
  install_token_service
elif [[ -n "${PUBLIC_HOSTNAME:-}" ]] && [[ -f /root/.cloudflared/cert.pem ]]; then
  install_local_named_tunnel "$PUBLIC_HOSTNAME"
else
  cat >&2 <<'MSG'
ERROR: Túnel nombrado no configurado.

Opción A (recomendada) — desde el panel Cloudflare:
  1. https://one.dash.cloudflare.com/ → Networks → Tunnels → Create tunnel
  2. Nombre: reforma-gobierno
  3. Public Hostname: reforma.TUDOMINIO.com → http://127.0.0.1:8765
  4. Copia el token de instalación y créalo en el VPS:

     cat > /opt/reforma-gobierno/.tunnel.env <<EOF
     TUNNEL_TOKEN=eyJ...
     PUBLIC_HOSTNAME=reforma.tudominio.com
     EOF
     chmod 600 /opt/reforma-gobierno/.tunnel.env
     bash /opt/reforma-gobierno/herramientas/install-tunnel-nombrado-vps.sh

Opción B — certificado local:
  1. cloudflared tunnel login   (abre URL en el navegador)
  2. Añade PUBLIC_HOSTNAME=reforma.tudominio.com en .tunnel.env
  3. Vuelve a ejecutar este script
MSG
  exit 1
fi

cat > /usr/local/bin/reforma-actualizar-url-tunel <<'SCRIPT'
#!/bin/bash
REMOTE_DIR=/opt/reforma-gobierno
URL_FILE="$REMOTE_DIR/datos/tunel_url.txt"
ENV_FILE="$REMOTE_DIR/.tunnel.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  if [[ -n "${PUBLIC_HOSTNAME:-}" ]]; then
    echo "https://${PUBLIC_HOSTNAME}" > "$URL_FILE"
    echo "https://${PUBLIC_HOSTNAME}"
    exit 0
  fi
fi
LOG_FILE="$REMOTE_DIR/tunnel.log"
URL=$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$LOG_FILE" 2>/dev/null | tail -1)
if [[ -n "$URL" ]]; then
  echo "$URL" > "$URL_FILE"
  echo "$URL"
fi
SCRIPT
chmod +x /usr/local/bin/reforma-actualizar-url-tunel

systemctl daemon-reload
systemctl enable reforma-gobierno-tunnel
systemctl restart reforma-gobierno-tunnel

sleep 4
if systemctl is-active --quiet reforma-gobierno-tunnel; then
  reforma-actualizar-url-tunel || true
  echo "Túnel nombrado activo."
  exit 0
fi

echo "ERROR: El servicio reforma-gobierno-tunnel no arrancó. Revisa: journalctl -u reforma-gobierno-tunnel -n 40" >&2
exit 1
