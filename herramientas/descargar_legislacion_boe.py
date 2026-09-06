#!/usr/bin/env python3
"""Descarga la Constitución y las leyes vigentes de España desde la API del BOE."""

from __future__ import annotations

import argparse
import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path


def contexto_ssl() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        contexto = ssl.create_default_context()
        try:
            contexto.load_default_certs()
        except Exception:
            pass
        if sys.platform == "win32":
            contexto.check_hostname = False
            contexto.verify_mode = ssl.CERT_NONE
        return contexto

API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
USER_AGENT = "ReformaDeGobierno/1.0 (proyecto ciudadano; fuente oficial BOE)"

RANGOS_LEYES = {
    "1070": "Constitución",
    "1290": "Ley Orgánica",
    "1300": "Ley",
    "1310": "Real Decreto Legislativo",
    "1320": "Real Decreto-ley",
    "1450": "Ley Foral",
}

CARPETAS = {
    "1070": "constitucion",
    "1290": "leyes/organicas",
    "1300": "leyes/ordinarias",
    "1310": "leyes/reales_decretos_legislativos",
    "1320": "leyes/reales_decretos_ley",
    "1450": "leyes/forales",
}

# Códigos vigentes que no son "ley" en sentido formal, pero son Derecho común de España.
CODIGOS_ESENCIALES = [
    "BOE-A-1889-4763",  # Código Civil
    "BOE-A-1885-6627",  # Código de Comercio
    "BOE-A-1882-6036",  # Ley de Enjuiciamiento Criminal
    "BOE-A-1946-2453",  # Ley Hipotecaria
]

QUERY_VIGENTES = (
    "estatus_derogacion:N AND vigencia_agotada:N AND ("
    + " OR ".join(f"rango@codigo:{codigo}" for codigo in RANGOS_LEYES)
    + ")"
)


def raiz_proyecto() -> Path:
    return Path(__file__).resolve().parents[1]


def pedir(url: str, accept: str, reintentos: int = 5) -> bytes:
    ultimo: Exception | None = None
    for intento in range(1, reintentos + 1):
        req = urllib.request.Request(
            url,
            headers={"Accept": accept, "User-Agent": USER_AGENT},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=90, context=contexto_ssl()) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            ultimo = exc
            if exc.code in {404, 400}:
                raise
            time.sleep(min(2 ** intento, 20))
        except urllib.error.URLError as exc:
            ultimo = exc
            time.sleep(min(2 ** intento, 20))
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo}") from ultimo


def consulta_catalogo() -> list[dict]:
    payload = {
        "query": {"query_string": {"query": QUERY_VIGENTES}},
        "sort": [{"rango": "asc"}, {"fecha_publicacion": "desc"}],
    }
    qs = urllib.parse.urlencode(
        {"limit": "-1", "query": json.dumps(payload, ensure_ascii=False)}
    )
    bruto = pedir(f"{API}?{qs}", "application/json")
    datos = json.loads(bruto.decode("utf-8"))
    if str(datos.get("status", {}).get("code")) != "200":
        raise RuntimeError(f"La API del BOE devolvió: {datos.get('status')}")
    items = datos.get("data") or []
    if isinstance(items, dict):
        return []
    return items


def texto_de_nodo(nodo: ET.Element) -> str:
    partes: list[str] = []
    if nodo.text:
        partes.append(nodo.text)
    for hijo in list(nodo):
        partes.append(texto_de_nodo(hijo))
        if hijo.tail:
            partes.append(hijo.tail)
    texto = html.unescape("".join(partes))
    texto = texto.replace("\\.", ".")
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


def ultima_version(bloque: ET.Element) -> ET.Element | None:
    versiones = [hijo for hijo in bloque if hijo.tag.split("}")[-1] == "version"]
    if not versiones:
        return None

    def clave(version: ET.Element) -> str:
        return version.get("fecha_vigencia") or version.get("fecha_publicacion") or ""

    return max(versiones, key=clave)


def xml_a_markdown(xml_bytes: bytes, titulo: str, identificador: str, url: str) -> str:
    raiz = ET.fromstring(xml_bytes)
    texto = raiz.find(".//texto")
    if texto is None:
        raise ValueError(f"La norma {identificador} no trae nodo de texto")

    lineas = [
        f"# {titulo.strip()}",
        "",
        f"- Identificador BOE: `{identificador}`",
        f"- Texto consolidado (informativo, sin valor jurídico oficial): {url}",
        f"- Descargado: {date.today().isoformat()}",
        "",
        "> Fuente: Agencia Estatal Boletín Oficial del Estado. La consolidación facilita la consulta del Derecho vigente, pero para efectos jurídicos hay que acudir a la publicación oficial.",
        "",
    ]

    for bloque in texto.findall("bloque"):
        tipo = bloque.get("tipo", "")
        version = ultima_version(bloque)
        if version is None:
            continue
        titulo_bloque = bloque.get("titulo") or ""
        parrafos = [texto_de_nodo(p) for p in version if texto_de_nodo(p)]
        if not parrafos and not titulo_bloque:
            continue
        if tipo == "encabezado":
            cabecera = titulo_bloque or (parrafos[0] if parrafos else "")
            lineas.extend([f"## {cabecera}", ""])
            resto = parrafos[1:] if parrafos and parrafos[0] == cabecera else parrafos
            if resto and resto != [cabecera]:
                lineas.extend(resto + [""])
            continue
        if tipo == "precepto":
            cabecera = titulo_bloque or (parrafos[0] if parrafos else "Precepto")
            lineas.extend([f"### {cabecera}", ""])
            cuerpo = parrafos[1:] if parrafos and parrafos[0].lower() == cabecera.lower() else parrafos
            lineas.extend(cuerpo + [""])
            continue
        if tipo == "preambulo":
            lineas.extend(["## Preámbulo", ""])
            lineas.extend(parrafos + [""])
            continue
        if titulo_bloque:
            lineas.extend([f"### {titulo_bloque}", ""])
        lineas.extend(parrafos + [""])

    return "\n".join(lineas).rstrip() + "\n"


def nombre_archivo(identificador: str, titulo: str) -> str:
    limpio = re.sub(r'[<>:"/\\\\|?*]', " ", titulo)
    limpio = re.sub(r"\s+", " ", limpio).strip().rstrip(".")
    if len(limpio) > 120:
        limpio = limpio[:117].rstrip() + "..."
    return f"{identificador} - {limpio}.md"


def codigo_rango(item: dict) -> str:
    rango = item.get("rango") or {}
    if isinstance(rango, dict):
        return str(rango.get("codigo") or "")
    return ""


def texto_rango(item: dict) -> str:
    rango = item.get("rango") or {}
    if isinstance(rango, dict):
        return str(rango.get("texto") or RANGOS_LEYES.get(codigo_rango(item), ""))
    return str(rango)


def ambito(item: dict) -> str:
    valor = item.get("ambito") or {}
    if isinstance(valor, dict):
        return str(valor.get("texto") or "")
    return str(valor)


def guardar_catalogo(items: list[dict], destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    compacto = []
    for item in items:
        compacto.append(
            {
                "identificador": item.get("identificador"),
                "rango": texto_rango(item),
                "rango_codigo": codigo_rango(item),
                "ambito": ambito(item),
                "numero_oficial": item.get("numero_oficial"),
                "titulo": item.get("titulo"),
                "fecha_publicacion": item.get("fecha_publicacion"),
                "fecha_vigencia": item.get("fecha_vigencia"),
                "url": item.get("url_html_consolidada"),
                "eli": item.get("url_eli"),
            }
        )
    (destino / "catalogo.json").write_text(
        json.dumps(compacto, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lineas = [
        "# Catálogo de leyes vigentes de España",
        "",
        f"Actualizado: {date.today().isoformat()}.",
        f"Total de normas incluidas: **{len(compacto)}**.",
        "",
        "Incluye Constitución, leyes orgánicas, leyes, reales decretos legislativos, reales decretos-ley y leyes forales que el BOE marca como no derogadas y con vigencia no agotada.",
        "",
        "| Identificador | Rango | Ámbito | Título | Publicación | BOE |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in compacto:
        titulo = (item.get("titulo") or "").replace("|", "/")
        url = item.get("url") or ""
        lineas.append(
            f"| `{item.get('identificador')}` | {item.get('rango')} | {item.get('ambito')} | {titulo} | {item.get('fecha_publicacion')} | [consultar]({url}) |"
        )
    (destino / "catalogo.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def metadatos_norma(identificador: str) -> dict:
    bruto = pedir(f"{API}/id/{identificador}/metadatos", "application/json")
    datos = json.loads(bruto.decode("utf-8"))
    bloque = datos.get("data") or datos
    if isinstance(bloque, dict) and "metadatos" in bloque:
        return bloque["metadatos"]
    return bloque


def descargar_codigos_esenciales(base: Path, forzar: bool) -> list[dict]:
    extras: list[dict] = []
    for identificador in CODIGOS_ESENCIALES:
        meta = metadatos_norma(identificador)
        titulo = meta.get("titulo") or identificador
        url_html = meta.get("url_html_consolidada") or f"https://www.boe.es/buscar/act.php?id={identificador}"
        item = {
            "identificador": identificador,
            "titulo": titulo,
            "url_html_consolidada": url_html,
            "rango": {"codigo": "codigos", "texto": "Código histórico"},
            "ambito": {"texto": "Estatal"},
            "fecha_publicacion": meta.get("fecha_publicacion"),
            "fecha_vigencia": meta.get("fecha_vigencia"),
            "url_eli": meta.get("url_eli"),
            "numero_oficial": meta.get("numero_oficial"),
        }
        carpeta = base / "leyes" / "codigos"
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / nombre_archivo(identificador, titulo)
        if not destino.exists() or forzar:
            xml_bytes = pedir(f"{API}/id/{identificador}/texto", "application/xml")
            destino.write_text(
                xml_a_markdown(xml_bytes, titulo, identificador, url_html),
                encoding="utf-8",
            )
        extras.append(item)
        print(f"[código] {identificador} {titulo}")
    return extras


def descargar_norma(item: dict, base: Path, forzar: bool) -> Path:
    identificador = item["identificador"]
    titulo = item.get("titulo") or identificador
    url_html = item.get("url_html_consolidada") or f"https://www.boe.es/buscar/act.php?id={identificador}"
    carpeta = base / CARPETAS.get(codigo_rango(item), "leyes/otras")
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / nombre_archivo(identificador, titulo)
    if destino.exists() and not forzar:
        return destino
    xml_bytes = pedir(f"{API}/id/{identificador}/texto", "application/xml")
    markdown = xml_a_markdown(xml_bytes, titulo, identificador, url_html)
    destino.write_text(markdown, encoding="utf-8")
    return destino


def escribir_portada(base: Path, items: list[dict]) -> None:
    constitucion = next(
        (item for item in items if codigo_rango(item) == "1070"),
        None,
    )
    conteo: dict[str, int] = {}
    for item in items:
        clave = texto_rango(item) or "Otros"
        conteo[clave] = conteo.get(clave, 0) + 1

    lineas = [
        "# Reforma de gobierno",
        "",
        "Proyecto de consulta del ordenamiento jurídico español vigente: **Constitución Española** y **leyes** según la legislación consolidada del Boletín Oficial del Estado.",
        "",
        f"Fecha de esta copia local: **{date.today().isoformat()}**.",
        "",
        "## Cómo está organizado",
        "",
        "- `constitucion/`: texto consolidado de la Constitución Española.",
        "- `leyes/organicas/`: leyes orgánicas vigentes.",
        "- `leyes/ordinarias/`: leyes vigentes.",
        "- `leyes/reales_decretos_legislativos/`: textos refundidos y códigos.",
        "- `leyes/reales_decretos_ley/`: reales decretos-ley vigentes.",
        "- `leyes/forales/`: leyes forales vigentes.",
        "- `leyes/catalogo.md`: índice completo con enlace al BOE.",
        "",
        "## Resumen",
        "",
        f"- Normas descargadas o indexadas: **{len(items)}**",
    ]
    for nombre, total in sorted(conteo.items()):
        lineas.append(f"- {nombre}: **{total}**")
    lineas.extend(
        [
            "",
            "## Constitución Española",
            "",
        ]
    )
    if constitucion:
        ruta = base / CARPETAS["1070"] / nombre_archivo(
            constitucion["identificador"], constitucion.get("titulo") or "Constitución Española"
        )
        if ruta.exists():
            cuerpo = ruta.read_text(encoding="utf-8")
            cuerpo = re.sub(r"^# .*\n+", "", cuerpo, count=1)
            lineas.append(cuerpo)
        else:
            lineas.append(
                f"Texto consolidado: {constitucion.get('url_html_consolidada')}"
            )
    lineas.extend(
        [
            "",
            "## Índice de leyes",
            "",
            "El listado completo está en [`leyes/catalogo.md`](leyes/catalogo.md). Cada norma tiene su propio archivo con el texto consolidado vigente.",
            "",
            "Para actualizar esta copia local:",
            "",
            "```powershell",
            "python .\\herramientas\\descargar_legislacion_boe.py",
            "```",
            "",
        ]
    )
    (base / "Reforma de gobierno.md").write_text("\n".join(lineas), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solo-catalogo", action="store_true")
    parser.add_argument("--solo-codigos", action="store_true", help="Solo descarga códigos históricos esenciales")
    parser.add_argument("--forzar", action="store_true", help="Vuelve a descargar normas ya guardadas")
    parser.add_argument("--max", type=int, default=0, help="Limita el número de normas (0 = todas)")
    parser.add_argument("--pausa", type=float, default=0.25, help="Segundos de espera entre descargas")
    args = parser.parse_args()

    base = raiz_proyecto()
    print(f"Proyecto: {base}")
    print("Descargando catálogo del BOE...")
    items = consulta_catalogo()
    items.sort(
        key=lambda item: (
            codigo_rango(item),
            ambito(item),
            item.get("fecha_publicacion") or "",
            item.get("identificador") or "",
        )
    )
    guardar_catalogo(items, base / "leyes")
    print(f"Catálogo: {len(items)} normas vigentes")

    if args.solo_catalogo:
        escribir_portada(base, items)
        return 0

    errores: list[str] = []
    if not args.solo_codigos:
        seleccion = items if args.max <= 0 else items[: args.max]
        for i, item in enumerate(seleccion, start=1):
            ident = item.get("identificador")
            print(f"[{i}/{len(seleccion)}] {ident} {item.get('titulo')}")
            try:
                descargar_norma(item, base, args.forzar)
            except Exception as exc:  # noqa: BLE001
                errores.append(f"{ident}: {exc}")
                print(f"  ERROR: {exc}", file=sys.stderr)
            time.sleep(args.pausa)

    try:
        descargar_codigos_esenciales(base, args.forzar)
    except Exception as exc:  # noqa: BLE001
        errores.append(f"codigos: {exc}")
        print(f"  ERROR códigos: {exc}", file=sys.stderr)

    escribir_portada(base, items)
    (base / "leyes" / "errores_descarga.txt").write_text(
        "\n".join(errores) + ("\n" if errores else ""),
        encoding="utf-8",
    )
    print(f"Terminado. Errores: {len(errores)}")
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
