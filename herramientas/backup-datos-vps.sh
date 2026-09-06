#!/bin/bash
# Copia de seguridad de datos/comunidad en el VPS (local + nube opcional)
set -euo pipefail

APP_DIR=/opt/reforma-gobierno
DATOS="$APP_DIR/datos/comunidad"
BACKUP_DIR="$APP_DIR/backups"
STAMP=$(date +%Y%m%d-%H%M)
ARCHIVO="$BACKUP_DIR/comunidad-$STAMP.tar.gz"
LOG="$BACKUP_DIR/backup.log"

mkdir -p "$BACKUP_DIR" "$DATOS"

if [ ! -d "$DATOS" ] || [ -z "$(ls -A "$DATOS" 2>/dev/null)" ]; then
  echo "$(date -Is) Sin datos en $DATOS" >> "$LOG"
  exit 0
fi

tar czf "$ARCHIVO" -C "$APP_DIR/datos" comunidad
ln -sfn "$(basename "$ARCHIVO")" "$BACKUP_DIR/latest.tar.gz"
echo "$(date -Is) Backup local: $ARCHIVO ($(du -h "$ARCHIVO" | cut -f1))" >> "$LOG"

# Conservar solo los últimos 14 backups locales
ls -1t "$BACKUP_DIR"/comunidad-*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm -f

# Nube (Google Drive u otro remoto rclone) si está configurado
if command -v rclone >/dev/null 2>&1; then
  if rclone listremotes 2>/dev/null | grep -q '^gdrive:'; then
    if rclone copy "$ARCHIVO" "gdrive:reforma-gobierno-backups/" --log-file "$LOG" --log-level INFO; then
      echo "$(date -Is) Subido a gdrive:reforma-gobierno-backups/" >> "$LOG"
    else
      echo "$(date -Is) ERROR subiendo a Google Drive" >> "$LOG"
    fi
  else
    echo "$(date -Is) rclone sin remoto gdrive: (ejecuta install-backup-vps.sh)" >> "$LOG"
  fi
fi
