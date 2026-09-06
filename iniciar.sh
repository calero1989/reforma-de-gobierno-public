#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PUBLICO=0
PUERTO=8765
while [[ $# -gt 0 ]]; do
  case "$1" in
    --publico|-p) PUBLICO=1; shift ;;
    --puerto) PUERTO="$2"; shift 2 ;;
    *) shift ;;
  esac
done

python3 -m venv .venv
./.venv/bin/python -m pip install -q -r requirements.txt
export PYTHONPATH="$PWD"
export HOST="0.0.0.0"
export PORT="$PUERTO"
export PUBLICO="$PUBLICO"
exec ./.venv/bin/python -m app.server
