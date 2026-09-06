#!/bin/bash
# Túnel HTTPS RÁPIDO (URL temporal *.trycloudflare.com)
# Usar mientras no haya dominio. Para URL permanente: install-tunnel-nombrado-vps.sh
# Ver: herramientas/CUANDO_TENGAS_DOMINIO.md
set -euo pipefail
REMOTE_DIR=/opt/reforma-gobierno
URL_FILE="$REMOTE_DIR/datos/tunel_url.txt"
LOG_FILE="$REMOTE_DIR/tunnel.log"

if ! command -v cloudflared >/dev/null 2>&1; then
  curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
  dpkg -i /tmp/cloudflared.deb || apt-get install -f -y
fi

mkdir -p "$REMOTE_DIR/datos"
touch "$LOG_FILE"

cat > /etc/systemd/system/reforma-gobierno-tunnel.service <<UNIT
[Unit]
Description=Cloudflare Tunnel -> Reforma de gobierno :8765
After=network-online.target reforma-gobierno.service
Wants=reforma-gobierno.service

[Service]
Type=simple
ExecStart=/usr/bin/cloudflared tunnel --url http://127.0.0.1:8765 --no-autoupdate
Restart=always
RestartSec=10
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=multi-user.target
UNIT

cat > /usr/local/bin/reforma-actualizar-url-tunel <<'SCRIPT'
#!/bin/bash
REMOTE_DIR=/opt/reforma-gobierno
LOG_FILE="$REMOTE_DIR/tunnel.log"
URL_FILE="$REMOTE_DIR/datos/tunel_url.txt"
URL=$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$LOG_FILE" 2>/dev/null | tail -1)
if [ -n "$URL" ]; then
  mkdir -p "$(dirname "$URL_FILE")"
  echo "$URL" > "$URL_FILE"
  echo "$URL"
fi
SCRIPT
chmod +x /usr/local/bin/reforma-actualizar-url-tunel

systemctl daemon-reload
systemctl enable reforma-gobierno-tunnel
systemctl restart reforma-gobierno-tunnel

echo "Esperando URL del túnel..."
for _ in $(seq 1 30); do
  URL=$(reforma-actualizar-url-tunel || true)
  if [ -n "$URL" ]; then
    echo "PUBLIC_URL=$URL"
    exit 0
  fi
  sleep 2
done
echo "No se pudo leer la URL del túnel. Revisa: journalctl -u reforma-gobierno-tunnel -n 50" >&2
exit 1
