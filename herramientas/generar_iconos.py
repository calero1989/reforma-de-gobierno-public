"""Genera iconos PNG para instalar la PWA en Android e iOS."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

SALIDA = Path(__file__).resolve().parents[1] / "app" / "static"

FONDO = (26, 35, 50, 255)
TARJETA = (36, 48, 68, 255)
BORDE = (59, 130, 246, 255)
LINEA = (148, 163, 184, 255)
PUNTO = (34, 197, 94, 255)


def _chunk(etiqueta: bytes, datos: bytes) -> bytes:
    crc = zlib.crc32(etiqueta + datos) & 0xFFFFFFFF
    return struct.pack(">I", len(datos)) + etiqueta + datos + struct.pack(">I", crc)


def escribir_png(ruta: Path, ancho: int, alto: int, pixel) -> None:
    filas = bytearray()
    for y in range(alto):
        filas.append(0)
        for x in range(ancho):
            filas.extend(pixel(x, y))
    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(filas), 9)
    png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    ruta.write_bytes(png)


def _en_rect(x: float, y: float, izq: float, arr: float, der: float, aba: float, radio: float) -> bool:
    if x < izq or x > der or y < arr or y > aba:
        return False
    cx = min(max(x, izq + radio), der - radio)
    cy = min(max(y, arr + radio), aba - radio)
    if abs(x - cx) <= radio and abs(y - cy) <= radio:
        return (x - cx) ** 2 + (y - cy) ** 2 <= radio**2
    return True


def _en_circulo(x: float, y: float, cx: float, cy: float, r: float) -> bool:
    return (x - cx) ** 2 + (y - cy) ** 2 <= r**2


def pintar(tamano: int, margen: float = 0.0):
    escala = tamano / 192
    pad = tamano * margen

    def pixel(px: int, py: int) -> tuple[int, int, int, int]:
        x = (px - pad) * 192 / max(tamano - 2 * pad, 1)
        y = (py - pad) * 192 / max(tamano - 2 * pad, 1)
        if margen and (px < pad or py < pad or px >= tamano - pad or py >= tamano - pad):
            return FONDO
        if not _en_rect(x, y, 0, 0, 192, 192, 40):
            return (0, 0, 0, 0)
        color = FONDO
        if _en_rect(x, y, 28, 36, 164, 156, 12):
            color = TARJETA
        grosor = 6
        if (
            _en_rect(x, y, 28 - grosor / 2, 36 - grosor / 2, 164 + grosor / 2, 156 + grosor / 2, 14)
            and not _en_rect(x, y, 28 + grosor / 2, 36 + grosor / 2, 164 - grosor / 2, 156 - grosor / 2, 10)
        ):
            color = BORDE
        for cy in (72, 96, 120):
            ancho = 88 if cy < 120 else 56
            if abs(y - cy) <= 4 and 52 <= x <= 52 + ancho:
                color = LINEA
        if _en_circulo(x, y, 140, 132, 18):
            color = PUNTO
        return color

    return pixel


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    escribir_png(SALIDA / "icon-192.png", 192, 192, pintar(192))
    escribir_png(SALIDA / "icon-512.png", 512, 512, pintar(512))
    escribir_png(SALIDA / "icon-maskable-192.png", 192, 192, pintar(192, 0.12))
    escribir_png(SALIDA / "icon-maskable-512.png", 512, 512, pintar(512, 0.12))
    escribir_png(SALIDA / "apple-touch-icon.png", 180, 180, pintar(180))
    print(f"Iconos PNG en {SALIDA}")


if __name__ == "__main__":
    main()
