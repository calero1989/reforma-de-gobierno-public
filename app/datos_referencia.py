"""Carga y actualización de datos de referencia (INE, presupuestos)."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from datetime import date
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_REFERENCIA = RAIZ / "datos" / "referencia.json"

# Series INE verificadas (API wstempus / servicios.ine.es)
# EPA7532: Tasa de paro. Total Nacional. De 16 a 64 años. Ambos sexos.
SERIES_INE = {
    "ipc_variacion_anual_pct": "IPC251856",
    "tasa_paro_pct": "EPA7532",
}

# Presupuestos PGE 2025-P (millones €) — SEPG, estadísticas consolidadas
PGE_2025_P = {
    "total_consolidado": 578_183,
    "sanidad": 5_505,
    "educacion": 5_338,
    "pensiones": 190_687,
    "desempleo": 21_278,
    "servicios_sociales": 5_744,
    "fomento_empleo": 7_516,
    "cultura": 1_652,
    "vivienda": 3_483,
    "medio_ambiente_agricultura": 8_412,
    "industria_energia": 9_801,
}

MAPEO_DIMENSION_PRESUPUESTO = {
    "social": ["sanidad", "educacion", "servicios_sociales", "vivienda", "cultura"],
    "economico": ["fomento_empleo", "industria_energia", "medio_ambiente_agricultura"],
    "fiscal": ["total_consolidado"],
    "laboral": ["desempleo", "fomento_empleo", "pensiones"],
    "ambiental": ["medio_ambiente_agricultura"],
    "institucional": ["total_consolidado"],
}


def _contexto_ssl() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def _ultimo_valor_serie(codigo: str) -> tuple[float | None, int | None, str, dict | None]:
    url = f"https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/{codigo}?nult=1"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25, context=_contexto_ssl()) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None, None, codigo, None
    bloque = datos.get("Data") or []
    if not bloque:
        return None, None, datos.get("Nombre") or codigo, None
    ultimo = bloque[-1]
    return (
        float(ultimo.get("Valor")),
        int(ultimo.get("Anyo") or 0),
        datos.get("Nombre") or codigo,
        ultimo,
    )


@lru_cache(maxsize=1)
def cargar_referencia() -> dict:
    if not RUTA_REFERENCIA.exists():
        return _referencia_por_defecto()
    return json.loads(RUTA_REFERENCIA.read_text(encoding="utf-8"))


def _referencia_por_defecto() -> dict:
    return {
        "actualizado": date.today().isoformat(),
        "ine": {
            "ipc_variacion_anual_pct": 2.9,
            "poblacion_total": 48_619_695,
            "tasa_paro_pct": 10.61,
            "tasa_paro_serie": "EPA7532",
            "salario_bruto_anual_medio_eur": 27_002,
        },
        "presupuestos_pge_2025_p_millones_eur": PGE_2025_P,
        "macro": {"pib_millones_eur": 1_592_000},
    }


def peso_presupuestario_dimension(dimension: str) -> float:
    """Fracción del PGE total asociada a la dimensión (0-1)."""
    ref = cargar_referencia()
    pge = ref.get("presupuestos_pge_2025_p_millones_eur") or PGE_2025_P
    total = float(pge.get("total_consolidado") or PGE_2025_P["total_consolidado"])
    claves = MAPEO_DIMENSION_PRESUPUESTO.get(dimension, [])
    suma = sum(float(pge.get(k, 0)) for k in claves)
    return min(1.0, suma / total) if total else 0.0


def escala_nacional(dimension: str) -> float:
    """Multiplicador 0.5-1.5 según peso real del gasto público en esa materia."""
    peso = peso_presupuestario_dimension(dimension)
    return 0.55 + peso * 4.5


def escala_individual(perfil_ingresos: int, situacion: str) -> float:
    ref = cargar_referencia()
    ine = ref.get("ine") or {}
    mediana = float(ine.get("renta_mediana_equivalizada_eur") or 19_009)
    salario = float(ine.get("salario_bruto_anual_medio_eur") or 27_002)
    tasa_paro = float(ine.get("tasa_paro_pct") or 10.61) / 100.0

    ratio_renta = perfil_ingresos / mediana if mediana else 1.0
    factor_renta = min(1.45, max(0.65, 0.85 + ratio_renta * 0.25))

    ajuste_situacion = {
        "desempleado": 1.0 + tasa_paro * 2.2,
        "jubilado": 1.15,
        "autonomo": 1.08,
        "empresario": 0.95 + (perfil_ingresos / salario) * 0.08,
        "estudiante": 0.88,
        "empleado": 1.0,
    }.get(situacion, 1.0)

    return factor_renta * ajuste_situacion


def impacto_euros_estimado(intensidad: float, dimension: str) -> float | None:
    """Orden de magnitud del impacto presupuestario potencial (millones €)."""
    ref = cargar_referencia()
    pge = ref.get("presupuestos_pge_2025_p_millones_eur") or PGE_2025_P
    claves = MAPEO_DIMENSION_PRESUPUESTO.get(dimension, ["total_consolidado"])
    base = max(float(pge.get(k, 0)) for k in claves) if claves else float(pge.get("total_consolidado", 0))
    return round(base * (intensidad / 100.0) * 0.015, 1)


def actualizar_desde_fuentes() -> dict:
    ref = cargar_referencia()
    ref["actualizado"] = date.today().isoformat()
    ine = ref.setdefault("ine", {})
    log: list[str] = []

    for clave, codigo in SERIES_INE.items():
        valor, anyo, nombre, raw = _ultimo_valor_serie(codigo)
        if valor is not None:
            ine[clave] = valor
            ine[f"{clave}_serie"] = codigo
            ine[f"{clave}_nombre"] = nombre
            if anyo:
                base = clave.removesuffix("_pct")
                ine[f"{base}_anyo"] = anyo
            if raw and raw.get("FK_Periodo") is not None:
                ine[f"{clave.removesuffix('_pct')}_trimestre"] = int(raw["FK_Periodo"])
            log.append(f"INE {codigo}: {valor} ({nombre[:55]})")

    ref.setdefault("presupuestos_pge_2025_p_millones_eur", {}).update(PGE_2025_P)
    RUTA_REFERENCIA.parent.mkdir(parents=True, exist_ok=True)
    RUTA_REFERENCIA.write_text(json.dumps(ref, ensure_ascii=False, indent=2), encoding="utf-8")
    cargar_referencia.cache_clear()
    return {"actualizado": ref["actualizado"], "log": log, "referencia": ref}
