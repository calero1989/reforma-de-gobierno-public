"""Parsea los textos consolidados en markdown del BOE en artículos estructurados."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BOE_ID_RE = re.compile(r"^[A-Z]{2,5}(?:-[a-zA-Z])?-\d+-\d+$")
FILENAME_ID_RE = re.compile(r"^([A-Z]{2,5}(?:-[a-zA-Z])?-\d+-\d+)")

# Formatos encontrados en el BOE:
#   ### Artículo 1        ### Art 1        ### Art. 1
#   ### Artículo primero  ### Artículo único
ARTICULO_RE = re.compile(
    r"^###\s+((?:Artículos?|Art\.?)\s+(.+?))\s*$", re.I
)
METADATA_RE = re.compile(r"^-\s+Identificador BOE:\s+`([^`]+)`")

_ORDINAL_A_NUM: dict[str, str] = {}
_ORDINALES = [
    ("primero", "1"), ("segundo", "2"), ("tercero", "3"), ("cuarto", "4"),
    ("quinto", "5"), ("sexto", "6"), ("séptimo", "7"), ("octavo", "8"),
    ("noveno", "9"), ("diez", "10"), ("décimo", "10"), ("once", "11"),
    ("undécimo", "11"), ("doce", "12"), ("duodécimo", "12"), ("trece", "13"),
    ("catorce", "14"), ("quince", "15"), ("dieciséis", "16"), ("diecisiete", "17"),
    ("dieciocho", "18"), ("diecinueve", "19"), ("veinte", "20"),
    ("veintiuno", "21"), ("veintidós", "22"), ("veintitrés", "23"),
    ("veinticuatro", "24"), ("veinticinco", "25"), ("veintiséis", "26"),
    ("veintisiete", "27"), ("veintiocho", "28"), ("veintinueve", "29"),
    ("treinta", "30"), ("treinta y uno", "31"), ("treinta y dos", "32"),
    ("treinta y tres", "33"), ("treinta y cuatro", "34"), ("treinta y cinco", "35"),
    ("treinta y seis", "36"), ("treinta y siete", "37"), ("treinta y ocho", "38"),
    ("treinta y nueve", "39"), ("cuarenta", "40"), ("cuarenta y uno", "41"),
    ("cuarenta y dos", "42"), ("cuarenta y tres", "43"), ("cuarenta y cuatro", "44"),
    ("cuarenta y cinco", "45"), ("cuarenta y seis", "46"), ("cuarenta y siete", "47"),
    ("cuarenta y ocho", "48"), ("cuarenta y nueve", "49"), ("cincuenta", "50"),
    ("único", "u"),
]
for _texto, _num in _ORDINALES:
    _ORDINAL_A_NUM[_texto] = _num


def _normalizar_numero(raw: str) -> str:
    """Convierte '3', 'primero', 'Art. 12 bis', etc. en un id razonable."""
    limpio = raw.strip().rstrip(".")
    if re.match(r"\d+[a-z]?(\s+bis|\s+ter|\s+quater)?$", limpio, re.I):
        return limpio
    clave = limpio.lower()
    if clave in _ORDINAL_A_NUM:
        return _ORDINAL_A_NUM[clave]
    # "treinta y nueve" etc. puede tener variantes con/sin tilde
    for texto, num in _ORDINALES:
        if clave == texto:
            return num
    return limpio


@dataclass
class Articulo:
    id: str
    titulo: str
    numero: str
    texto: str
    seccion: str


@dataclass
class Ley:
    id: str
    titulo: str
    ruta: Path
    articulos: list[Articulo]


def raiz_datos() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def _indice_leyes() -> dict[str, Path]:
    base = raiz_datos()
    indice: dict[str, Path] = {}
    for sub in ("leyes", "constitucion"):
        carpeta = base / sub
        if not carpeta.is_dir():
            continue
        for ruta in carpeta.rglob("*.md"):
            if ruta.name == "catalogo.md":
                continue
            m = FILENAME_ID_RE.match(ruta.name)
            if m:
                indice.setdefault(m.group(1), ruta)
    return indice


def resolver_ruta_ley(identificador: str) -> Path | None:
    if not identificador or not BOE_ID_RE.match(identificador):
        return None
    return _indice_leyes().get(identificador)


def parsear_markdown(contenido: str, identificador: str = "") -> Ley:
    lineas = contenido.splitlines()
    titulo = "Norma sin título"
    for linea in lineas:
        if linea.startswith("# "):
            titulo = linea[2:].strip()
            break
    for linea in lineas:
        m = METADATA_RE.match(linea.strip())
        if m:
            identificador = m.group(1)
            break

    articulos: list[Articulo] = []
    seccion_actual = ""
    articulo_actual: Articulo | None = None
    buffer: list[str] = []

    def cerrar_articulo() -> None:
        nonlocal articulo_actual, buffer
        if articulo_actual is None:
            return
        articulo_actual.texto = "\n".join(buffer).strip()
        if articulo_actual.texto:
            articulos.append(articulo_actual)
        articulo_actual = None
        buffer = []

    for linea in lineas:
        if linea.startswith("## ") and not linea.startswith("### "):
            cerrar_articulo()
            seccion_actual = linea[3:].strip()
            continue
        m = ARTICULO_RE.match(linea)
        if m:
            cerrar_articulo()
            titulo_art = m.group(1).strip()
            numero_raw = m.group(2).strip()
            numero = _normalizar_numero(numero_raw)
            articulo_actual = Articulo(
                id=f"art-{numero}",
                titulo=titulo_art,
                numero=numero,
                texto="",
                seccion=seccion_actual,
            )
            continue
        if articulo_actual is not None:
            buffer.append(linea)

    cerrar_articulo()
    return Ley(id=identificador or titulo, titulo=titulo, ruta=Path(), articulos=articulos)


@lru_cache(maxsize=512)
def cargar_ley(identificador: str) -> Ley | None:
    ruta = resolver_ruta_ley(identificador)
    if ruta is None or not ruta.exists():
        return None
    ley = parsear_markdown(ruta.read_text(encoding="utf-8"), identificador)
    ley.ruta = ruta
    return ley
