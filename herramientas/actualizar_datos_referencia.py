#!/usr/bin/env python3
"""Actualiza datos/ referencia.json desde INE (y mantiene cifras PGE oficiales)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.datos_referencia import actualizar_desde_fuentes


def main() -> int:
    resultado = actualizar_desde_fuentes()
    print(f"Actualizado: {resultado['actualizado']}")
    for linea in resultado["log"]:
        print(f"  - {linea}")
    if not resultado["log"]:
        print("  (Sin cambios desde INE; se conservan valores locales.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
