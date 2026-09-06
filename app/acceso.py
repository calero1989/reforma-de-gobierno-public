"""Direcciones de acceso local, LAN y túnel público."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

PUERTO_DEFECTO = 8765
TUNEL_ARCHIVO = Path(__file__).resolve().parents[1] / "datos" / "tunel_url.txt"
_tunel_proc: subprocess.Popen | None = None
_tunel_url_sesion: str = ""


def puerto() -> int:
    return int(os.environ.get("PORT", str(PUERTO_DEFECTO)))


def ips_lan() -> list[str]:
    ips: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            principal = sock.getsockname()[0]
            if principal and not principal.startswith("127."):
                ips.append(principal)
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


def _es_host_publico(host: str) -> bool:
    host = (host or "").split(":")[0].lower().strip()
    if not host or host.startswith("127.") or host in {"localhost"}:
        return False
    if host.endswith((".trycloudflare.com", ".loca.lt", ".lhr.life", ".cfargotunnel.com")):
        return True
    if TUNEL_ARCHIVO.exists():
        guardada = TUNEL_ARCHIVO.read_text(encoding="utf-8").strip().lower()
        if guardada:
            guardada_host = guardada.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
            if host == guardada_host:
                return True
    return False


def _tunel_en_ejecucion() -> bool:
    global _tunel_proc
    return _tunel_proc is not None and _tunel_proc.poll() is None


def limpiar_tunel_guardado() -> None:
    global _tunel_url_sesion
    _tunel_url_sesion = ""
    os.environ.pop("TUNNEL_URL", None)
    if TUNEL_ARCHIVO.exists():
        TUNEL_ARCHIVO.unlink()


def url_publica_actual(host_peticion: str = "") -> str | None:
    """Devuelve el enlace público válido en esta sesión (no URLs caducadas)."""
    if _es_host_publico(host_peticion):
        return f"https://{host_peticion.split(':')[0]}"
    if _tunel_url_sesion:
        return _tunel_url_sesion
    tunel = os.environ.get("TUNNEL_URL", "").strip()
    if tunel:
        return tunel
    if _tunel_en_ejecucion() and TUNEL_ARCHIVO.exists():
        guardada = TUNEL_ARCHIVO.read_text(encoding="utf-8").strip()
        if guardada:
            return guardada
    if os.environ.get("MODO_VPS", "").strip().lower() in {"1", "true", "yes", "si", "sí"}:
        if TUNEL_ARCHIVO.exists():
            guardada = TUNEL_ARCHIVO.read_text(encoding="utf-8").strip()
            if guardada:
                return guardada
    return None


def urls_acceso(host_bind: str, port: int, host_peticion: str = "") -> dict:
    locales = [f"http://127.0.0.1:{port}"]
    lan = [f"http://{ip}:{port}" for ip in ips_lan()]
    tunel = url_publica_actual(host_peticion)
    return {
        "bind": host_bind,
        "puerto": port,
        "este_equipo": locales,
        "red_local": lan,
        "publico": tunel,
        "tunel_activo": _tunel_en_ejecucion() or bool(_es_host_publico(host_peticion)),
        "compartido": host_bind in {"0.0.0.0", "::"},
    }


def guardar_tunel(url: str) -> None:
    global _tunel_url_sesion
    url = url.strip()
    _tunel_url_sesion = url
    TUNEL_ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    TUNEL_ARCHIVO.write_text(url, encoding="utf-8")
    os.environ["TUNNEL_URL"] = url


def _buscar_url(texto: str) -> str | None:
    m = re.search(r"https://[a-z0-9.-]+\.(trycloudflare\.com|loca\.lt)", texto, re.I)
    if m:
        return m.group(0).rstrip("./")
    m = re.search(r"https://[^\s]+\.lhr\.life", texto, re.I)
    if m:
        return m.group(0).rstrip("./")
    return None


def iniciar_tunel(port: int) -> subprocess.Popen | None:
    """Arranca Cloudflare Tunnel si está instalado y guarda la URL pública."""
    global _tunel_proc
    exe = _which("cloudflared") or _which("cloudflared.exe")
    if not exe:
        print("Túnel público: instala cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) y vuelve a usar -Publico.")
        return None

    if _tunel_proc and _tunel_proc.poll() is None:
        _tunel_proc.terminate()
    limpiar_tunel_guardado()

    proc = subprocess.Popen(
        [exe, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def leer() -> None:
        assert proc.stdout is not None
        for linea in proc.stdout:
            url = _buscar_url(linea)
            if url:
                guardar_tunel(url)
                print(f"Enlace público: {url}")

    threading.Thread(target=leer, daemon=True).start()

    for _ in range(40):
        if TUNEL_ARCHIVO.exists() and TUNEL_ARCHIVO.read_text(encoding="utf-8").strip():
            break
        if proc.poll() is not None:
            print("Túnel público: cloudflared se detuvo antes de publicar una URL.")
            break
        time.sleep(0.25)
    _tunel_proc = proc
    return proc


def _which(nombre: str) -> str | None:
    from shutil import which

    return which(nombre)


def imprimir_accesos(host: str, port: int) -> None:
    datos = urls_acceso(host, port)
    print("")
    print("Abre la app en cualquier navegador (Windows, macOS, Linux, Android, iOS):")
    for url in datos["este_equipo"]:
        print(f"  Este equipo:  {url}")
    if datos["red_local"]:
        print("  Misma Wi-Fi / red:")
        for url in datos["red_local"]:
            print(f"    {url}")
    else:
        print("  Red local: no se detectó IP LAN. Usa -Red y revisa el firewall.")
    if datos["publico"]:
        print(f"  Fuera de casa: {datos['publico']}")
    print("")
    print("En el movil: abre el enlace o escanea el codigo QR de la cabecera.")
    if sys.platform == "win32" and datos["compartido"]:
        print("Si el teléfono no entra, permite el puerto en el Firewall de Windows.")
    print("")
