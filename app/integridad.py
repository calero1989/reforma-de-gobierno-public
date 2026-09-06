"""Comprobaciones de integridad del corpus legal al arrancar."""

from __future__ import annotations

import json
import re
from pathlib import Path

BOE_ID_RE = re.compile(r"^[A-Z]{2,5}(?:-[a-zA-Z])?-\d+-\d+$")
FILENAME_ID_RE = re.compile(r"^([A-Z]{2,5}(?:-[a-zA-Z])?-\d+-\d+)")
RAIZ = Path(__file__).resolve().parents[1]


def _indice_archivos() -> dict[str, Path]:
    indice: dict[str, Path] = {}
    for sub in ("leyes", "constitucion"):
        carpeta = RAIZ / sub
        if not carpeta.is_dir():
            continue
        for ruta in carpeta.rglob("*.md"):
            if ruta.name == "catalogo.md":
                continue
            m = FILENAME_ID_RE.match(ruta.name)
            if m:
                indice.setdefault(m.group(1), ruta)
    return indice


def verificar_corpus() -> dict:
    catalogo_path = RAIZ / "leyes" / "catalogo.json"
    if not catalogo_path.exists():
        return {"ok": False, "error": "Falta leyes/catalogo.json"}

    catalogo = json.loads(catalogo_path.read_text(encoding="utf-8"))
    indice = _indice_archivos()
    faltantes = [
        item.get("identificador", "")
        for item in catalogo
        if item.get("identificador") and item["identificador"] not in indice
    ]

    ce_path = indice.get("BOE-A-1978-31229")
    articulos_ce = 0
    if ce_path and ce_path.exists():
        texto = ce_path.read_text(encoding="utf-8")
        articulos_ce = len(re.findall(r"^###\s+(?:Artículos?|Art\.?)", texto, re.M | re.I))

    return {
        "ok": not faltantes,
        "catalogo": len(catalogo),
        "archivos_indexados": len(indice),
        "faltantes": len(faltantes),
        "constitucion_articulos": articulos_ce,
    }
