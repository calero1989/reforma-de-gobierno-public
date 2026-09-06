"""Genera un ZIP descargable de la aplicación (sin secretos ni entorno virtual)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EXCLUIR_DIR = {".venv", "__pycache__", ".git", "node_modules", "backups"}
EXCLUIR_NOMBRES = {
    "tunel_url.txt",
    "usuarios.jsonl",
    "visitas.jsonl",
    "valoraciones.jsonl",
    "foro_hilos.jsonl",
    "foro_respuestas.jsonl",
    "foro_votos.jsonl",
    "comentarios.jsonl",
    "reacciones.jsonl",
    "guardados.jsonl",
    "reset_tokens.jsonl",
    ".env",
    "rclone.conf",
    "tunnel.log",
}
EXCLUIR_SUFIJOS = {".pyc", ".pyo", ".pem", ".key"}


def _excluir_ruta(ruta: Path) -> bool:
    if any(parte in EXCLUIR_DIR for parte in ruta.parts):
        return True
    if ruta.name in EXCLUIR_NOMBRES:
        return True
    if ruta.suffix.lower() in EXCLUIR_SUFIJOS:
        return True
    if "comunidad" in ruta.parts and "datos" in ruta.parts:
        return True
    if "leyes" in ruta.parts and ruta.suffix == ".md" and ruta.name != "catalogo.md":
        return True
    return False


def construir_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for ruta in RAIZ.rglob("*"):
            if not ruta.is_file():
                continue
            if _excluir_ruta(ruta):
                continue
            relativo = ruta.relative_to(RAIZ).as_posix()
            zf.write(ruta, f"Simulador de Reforma Legislativa/{relativo}")
        zf.writestr(
            "Simulador de Reforma Legislativa/LEEME_INSTALACION.txt",
            "Simulador de Reforma Legislativa\n"
            "================================\n\n"
            "En el movil o tablet: instala desde el navegador (Añadir a pantalla de inicio).\n"
            "En un ordenador con Python 3:\n"
            "  Windows:  iniciar.ps1\n"
            "  Linux/macOS:  ./iniciar.sh\n\n"
            "Luego descarga las leyes vigentes:\n"
            "  python herramientas/descargar_legislacion_boe.py\n",
        )
    return buffer.getvalue()
