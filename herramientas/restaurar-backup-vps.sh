#!/bin/bash
# Restaura datos/comunidad desde un backup .tar.gz
set -euo pipefail

APP_DIR=/opt/reforma-gobierno
ARCHIVO="${1:-$APP_DIR/backups/latest.tar.gz}"

if [ ! -f "$ARCHIVO" ]; then
  echo "No existe: $ARCHIVO" >&2
  echo "Uso: $0 [ruta/al/comunidad-YYYYMMDD-HHMM.tar.gz]" >&2
  exit 1
fi

systemctl stop reforma-gobierno || true
mkdir -p "$APP_DIR/datos"
rm -rf "$APP_DIR/datos/comunidad"
tar xzf "$ARCHIVO" -C "$APP_DIR/datos"
systemctl start reforma-gobierno
echo "Restaurado desde $ARCHIVO"
