#!/bin/bash
# Instala copias periódicas en el VPS (cron diario + rclone opcional)
set -euo pipefail

APP_DIR=/opt/reforma-gobierno
SCRIPT="$APP_DIR/herramientas/backup-datos-vps.sh"

chmod +x "$SCRIPT" "$APP_DIR/herramientas/restaurar-backup-vps.sh" 2>/dev/null || true

if ! command -v rclone >/dev/null 2>&1; then
  curl -fsSL https://rclone.org/install.sh | bash
fi

CRON_LINE="15 3 * * * root $SCRIPT >> $APP_DIR/backups/cron.log 2>&1"
CRON_FILE=/etc/cron.d/reforma-gobierno-backup
echo "$CRON_LINE" > "$CRON_FILE"
chmod 644 "$CRON_FILE"

# Actualizar URL del túnel cada 10 min (por si cloudflared reinicia)
TUNEL_CRON="*/10 * * * * root /usr/local/bin/reforma-actualizar-url-tunel >/dev/null 2>&1"
echo "$TUNEL_CRON" > /etc/cron.d/reforma-gobierno-tunnel-url
chmod 644 /etc/cron.d/reforma-gobierno-tunnel-url

echo "Copias programadas: todos los días a las 03:15 UTC"
echo "Logs: $APP_DIR/backups/"
echo ""
echo "Para activar Google Drive (una sola vez):"
echo "  rclone config"
echo "  → n) New remote → name: gdrive → Google Drive → sigue el asistente"
echo "  Luego prueba: rclone lsd gdrive:"
echo ""
"$SCRIPT" || true
