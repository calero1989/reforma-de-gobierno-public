"""Motor de impacto social y económico calibrado con datos INE y presupuestos PGE."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.datos_referencia import (
    cargar_referencia,
    escala_individual,
    escala_nacional,
    impacto_euros_estimado,
    peso_presupuestario_dimension,
)

DIMENSIONES = ("social", "economico", "fiscal", "laboral", "ambiental", "institucional")

PALABRAS = {
    "social": (
        "derecho derechos protección proteccion salud educación educacion vivienda familia "
        "discapacidad igualdad infancia juventud ancianos asilo refugio inclusión inclusion "
        "servicios sociales dependencia violencia género genero pension prestacion prestación"
    ).split(),
    "economico": (
        "economía economia empleo empresa empresas inversión inversion mercado consumo "
        "competitividad productividad crecimiento renta ingresos gasto presupuesto "
        "subvención subvencion ayuda financiación financiacion crédito credito pib"
    ).split(),
    "fiscal": (
        "impuesto tributo cotización cotizacion recaudación recaudacion exención exencion "
        "deducción deduccion arancel tasas contribución contribucion hacienda fiscal irpf iva"
    ).split(),
    "laboral": (
        "trabajo trabajador trabajadores salario despido contrato jornada sindicato "
        "convenio colectivo paro desempleo formación formacion profesional seguridad social "
        "prestación prestacion pension jubilación jubilacion ere ere"
    ).split(),
    "ambiental": (
        "medio ambiente sostenibilidad emisiones carbono energía energia renovable "
        "residuos reciclaje biodiversidad clima contaminación contaminacion agua suelo"
    ).split(),
    "institucional": (
        "gobierno administración administracion ministerio organismo competencia "
        "autoridad tribunal procedimiento sanción sancion inspección inspeccion "
        "transparencia participación participacion democracia constitución constitucion"
    ).split(),
}

PESOS_PERFIL = {
    "empleado": {"laboral": 1.4, "fiscal": 1.2, "social": 1.1},
    "autonomo": {"fiscal": 1.5, "economico": 1.3, "laboral": 1.1},
    "desempleado": {"social": 1.5, "laboral": 1.4, "economico": 1.2},
    "jubilado": {"social": 1.4, "fiscal": 1.2, "economico": 1.1},
    "estudiante": {"social": 1.3, "economico": 1.1},
    "empresario": {"economico": 1.5, "fiscal": 1.4, "laboral": 1.2},
}


@dataclass
class PerfilCiudadano:
    situacion: str = "empleado"
    ingresos_anuales: int = 28000
    tamano_hogar: int = 2
    region: str = "España"

    def pesos(self) -> dict[str, float]:
        ref = cargar_referencia()
        ine = ref.get("ine") or {}
        default_ingresos = int(ine.get("salario_bruto_anual_medio_eur") or 27_002)
        if self.ingresos_anuales <= 0:
            self.ingresos_anuales = default_ingresos
        base = {d: 1.0 for d in DIMENSIONES}
        for clave, ajustes in PESOS_PERFIL.items():
            if self.situacion == clave:
                base.update(ajustes)
        return base


PALABRAS_POSITIVAS = {
    "derecho", "derechos", "protección", "proteccion", "igualdad", "inclusión",
    "inclusion", "educación", "educacion", "salud", "ayuda", "prestación",
    "prestacion", "subvención", "subvencion", "inversión", "inversion",
    "crecimiento", "empleo", "formación", "formacion", "sostenibilidad",
    "renovable", "transparencia", "participación", "participacion",
    "exención", "exencion", "deducción", "deduccion", "biodiversidad",
    "pension", "jubilación", "jubilacion", "vivienda", "familia",
}

PALABRAS_NEGATIVAS = {
    "sanción", "sancion", "prohibición", "prohibicion", "restricción",
    "restriccion", "multa", "pena", "penalización", "penalizacion",
    "recorte", "reducción", "reduccion", "supresión", "supresion",
    "despido", "ere", "impuesto", "tributo", "cotización", "cotizacion",
    "arancel", "tasas", "contaminación", "contaminacion", "emisiones",
    "residuos", "inspección", "inspeccion", "embargo", "decomiso",
}


PALABRAS_PRO_CIUDADANO = {
    "derecho", "derechos", "libertad", "protección", "proteccion",
    "prestación", "prestacion", "ayuda", "subvención", "subvencion",
    "exención", "exencion", "deducción", "deduccion", "educación",
    "educacion", "salud", "vivienda", "pension", "jubilación", "jubilacion",
    "empleo", "formación", "formacion", "igualdad", "inclusión", "inclusion",
    "participación", "participacion", "transparencia", "acceso",
    "gratuito", "gratuita", "familia", "infancia", "dependencia",
    "asistencia", "beneficio", "rebaja", "bonificación", "bonificacion",
}

PALABRAS_PRO_GOBIERNO = {
    "impuesto", "tributo", "recaudación", "recaudacion", "cotización",
    "cotizacion", "arancel", "tasa", "tasas", "sanción", "sancion",
    "multa", "inspección", "inspeccion", "control", "vigilancia",
    "obligación", "obligacion", "prohibición", "prohibicion",
    "restricción", "restriccion", "autorización", "autorizacion",
    "licencia", "permiso", "registro", "declaración", "declaracion",
    "potestad", "competencia", "regulación", "regulacion",
    "intervención", "intervencion", "expediente", "procedimiento",
}


def _calcular_beneficiario(texto: str) -> dict:
    """Determina quién se beneficia más: ciudadanos, gobierno o ambos."""
    norm = set(_normalizar(texto).split())
    ciud = len(norm & {_normalizar(p) for p in PALABRAS_PRO_CIUDADANO})
    gob = len(norm & {_normalizar(p) for p in PALABRAS_PRO_GOBIERNO})
    total = ciud + gob
    if total == 0:
        return {"beneficiario": "ambos", "ciudadanos_pct": 50, "gobierno_pct": 50}
    c_pct = round(ciud / total * 100)
    g_pct = 100 - c_pct
    if c_pct >= 65:
        quien = "ciudadanos"
    elif g_pct >= 65:
        quien = "gobierno"
    else:
        quien = "ambos"
    return {"beneficiario": quien, "ciudadanos_pct": c_pct, "gobierno_pct": g_pct}


def _calcular_signo(texto: str) -> str:
    """Devuelve 'positivo', 'negativo' o 'mixto' según las palabras del texto."""
    norm = set(_normalizar(texto).split())
    pos = len(norm & {_normalizar(p) for p in PALABRAS_POSITIVAS})
    neg = len(norm & {_normalizar(p) for p in PALABRAS_NEGATIVAS})
    if pos > 0 and neg > 0:
        ratio = pos / (pos + neg)
        if ratio >= 0.65:
            return "positivo"
        if ratio <= 0.35:
            return "negativo"
        return "mixto"
    if pos > 0:
        return "positivo"
    if neg > 0:
        return "negativo"
    return "mixto"


@dataclass
class Impacto:
    dimensiones: dict[str, float] = field(default_factory=dict)
    social_nacional: float = 0.0
    economico_nacional: float = 0.0
    social_individual: float = 0.0
    economico_individual: float = 0.0
    intensidad: float = 0.0
    confianza: float = 0.0
    signo: str = "mixto"
    beneficiario: dict = field(default_factory=lambda: {"beneficiario": "ambos", "ciudadanos_pct": 50, "gobierno_pct": 50})
    etiquetas: list[str] = field(default_factory=list)
    explicacion: list[str] = field(default_factory=list)
    impacto_presupuestario_millones_eur: float | None = None
    afectados_estimados: int | None = None
    datos_referencia: dict = field(default_factory=dict)


def _normalizar(texto: str) -> str:
    t = texto.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        t = t.replace(a, b)
    return t


def _puntuar_dimensiones(texto: str) -> dict[str, float]:
    norm = _normalizar(texto)
    palabras = re.findall(r"[a-záéíóúñ]+", norm)
    total = max(len(palabras), 1)
    scores = {}
    for dim, claves in PALABRAS.items():
        hits = sum(
            1 for p in palabras if p in claves or any(p.startswith(c[:4]) for c in claves if len(c) >= 4)
        )
        base = min(100.0, (hits / total) * 420.0 + hits * 2.5)
        scores[dim] = min(100.0, base * escala_nacional(dim))
    return scores


def _etiquetas(scores: dict[str, float]) -> list[str]:
    orden = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [k for k, v in orden if v >= 18][:4]


def _personas_afectadas(intensidad: float, dimension: str) -> int:
    ref = cargar_referencia()
    pob = int((ref.get("ine") or {}).get("poblacion_total") or 48_619_695)
    peso = peso_presupuestario_dimension(dimension)
    return int(pob * peso * (intensidad / 100.0) * 0.12)


def evaluar_impacto(texto: str, perfil: PerfilCiudadano | None = None) -> Impacto:
    perfil = perfil or PerfilCiudadano()
    ref = cargar_referencia()
    ine = ref.get("ine") or {}
    scores = _puntuar_dimensiones(texto)
    pesos = perfil.pesos()

    social = scores["social"] * 0.55 + scores["institucional"] * 0.20 + scores["ambiental"] * 0.15 + scores["laboral"] * 0.10
    economico = scores["economico"] * 0.40 + scores["fiscal"] * 0.35 + scores["laboral"] * 0.25

    ipc = float(ine.get("ipc_variacion_anual_pct") or 2.9) / 100.0
    economico *= 1.0 + ipc * 0.15

    factor_ind = escala_individual(perfil.ingresos_anuales, perfil.situacion)
    factor_hogar = min(1.25, max(0.85, perfil.tamano_hogar / 2))

    social_ind = min(100.0, social * pesos.get("social", 1.0) * factor_hogar * (0.9 + factor_ind * 0.15))
    economico_ind = min(100.0, economico * pesos.get("economico", 1.0) * factor_ind)

    intensidad = min(100.0, (social + economico) / 2)
    palabras = len(texto.split())
    confianza = min(92.0, 42.0 + palabras * 0.07 + len(_etiquetas(scores)) * 7)

    etiquetas = _etiquetas(scores)
    dim_principal = etiquetas[0] if etiquetas else "institucional"
    euros = impacto_euros_estimado(intensidad, dim_principal)
    afectados = _personas_afectadas(intensidad, dim_principal)

    explicacion = [
        f"Calibrado con PGE 2025-P (total {ref.get('presupuestos_pge_2025_p_millones_eur', {}).get('total_consolidado', 578183):,.0f} M€).".replace(",", "."),
        f"Población de referencia: {int(ine.get('poblacion_total', 48619695)):,} hab.; paro {float(ine.get('tasa_paro_pct', 10.61)):.1f}%; IPC {float(ine.get('ipc_variacion_anual_pct', 2.9)):.1f}%.".replace(",", "."),
    ]
    for dim in etiquetas:
        peso = peso_presupuestario_dimension(dim) * 100
        explicacion.append(f"Materia {dim}: índice textual {scores[dim]:.0f}/100; peso presupuestario ~{peso:.1f}%.")
    if perfil.situacion != "empleado":
        explicacion.append(f"Perfil '{perfil.situacion}' ajustado con renta mediana INE ({int(ine.get('renta_mediana_equivalizada_eur', 19009)):,} €).".replace(",", "."))
    if euros is not None:
        explicacion.append(f"Orden de magnitud presupuestaria estimada: ~{euros:,.1f} M€/año (simulación).".replace(",", "."))

    signo = _calcular_signo(texto)
    beneficiario = _calcular_beneficiario(texto)

    return Impacto(
        dimensiones={k: round(v, 1) for k, v in scores.items()},
        social_nacional=round(social, 1),
        economico_nacional=round(economico, 1),
        social_individual=round(social_ind, 1),
        economico_individual=round(economico_ind, 1),
        intensidad=round(intensidad, 1),
        confianza=round(confianza, 1),
        signo=signo,
        beneficiario=beneficiario,
        etiquetas=etiquetas,
        explicacion=explicacion,
        impacto_presupuestario_millones_eur=euros,
        afectados_estimados=afectados,
        datos_referencia={
            "fuentes": ref.get("fuentes", []),
            "actualizado": ref.get("actualizado"),
        },
    )


def simular_reforma(texto_original: str, texto_propuesto: str, perfil: PerfilCiudadano | None = None) -> dict:
    antes = evaluar_impacto(texto_original, perfil)
    despues = evaluar_impacto(texto_propuesto, perfil)
    delta = {
        "social_nacional": round(despues.social_nacional - antes.social_nacional, 1),
        "economico_nacional": round(despues.economico_nacional - antes.economico_nacional, 1),
        "social_individual": round(despues.social_individual - antes.social_individual, 1),
        "economico_individual": round(despues.economico_individual - antes.economico_individual, 1),
        "intensidad": round(despues.intensidad - antes.intensidad, 1),
    }
    if antes.impacto_presupuestario_millones_eur is not None and despues.impacto_presupuestario_millones_eur is not None:
        delta["presupuesto_millones_eur"] = round(
            despues.impacto_presupuestario_millones_eur - antes.impacto_presupuestario_millones_eur, 1
        )
    if antes.afectados_estimados is not None and despues.afectados_estimados is not None:
        delta["personas_afectadas"] = despues.afectados_estimados - antes.afectados_estimados

    palabras_nuevas = set(_normalizar(texto_propuesto).split()) - set(_normalizar(texto_original).split())
    palabras_quitadas = set(_normalizar(texto_original).split()) - set(_normalizar(texto_propuesto).split())

    resumen = []
    if delta["social_nacional"] > 3:
        resumen.append("La reforma aumentaría el impacto social nacional respecto al texto vigente.")
    elif delta["social_nacional"] < -3:
        resumen.append("La reforma reduciría el impacto social nacional estimado.")
    if delta["economico_nacional"] > 3:
        resumen.append("El impacto económico agregado crecería según el modelo calibrado.")
    elif delta["economico_nacional"] < -3:
        resumen.append("El impacto económico nacional disminuiría.")
    if delta.get("presupuesto_millones_eur"):
        v = delta["presupuesto_millones_eur"]
        resumen.append(f"Cambio presupuestario orientativo: {v:+.1f} M€/año.")
    if delta.get("personas_afectadas"):
        resumen.append(f"Variación de personas potencialmente afectadas: {delta['personas_afectadas']:+,.0f}.".replace(",", "."))
    if abs(delta["intensidad"]) <= 3:
        resumen.append("Cambio global moderado en esta simulación.")
    if palabras_nuevas:
        resumen.append(f"Términos añadidos: {', '.join(list(palabras_nuevas)[:8])}.")
    if palabras_quitadas:
        resumen.append(f"Términos eliminados: {', '.join(list(palabras_quitadas)[:8])}.")

    d_total = delta["social_nacional"] + delta["economico_nacional"]
    signo_reforma = "positivo" if d_total > 3 else ("negativo" if d_total < -3 else "mixto")

    return {
        "antes": impacto_a_dict(antes),
        "despues": impacto_a_dict(despues),
        "delta": delta,
        "signo_reforma": signo_reforma,
        "beneficiario_antes": antes.beneficiario,
        "beneficiario_despues": despues.beneficiario,
        "resumen": resumen or ["Sin cambios significativos detectados."],
        "aviso": (
            "Simulación orientativa calibrada con INE y PGE 2025-P. No sustituye informes oficiales "
            "de impacto normativo ni memorias económicas del Gobierno."
        ),
    }


def impacto_a_dict(impacto: Impacto) -> dict:
    return {
        "dimensiones": impacto.dimensiones,
        "social_nacional": impacto.social_nacional,
        "economico_nacional": impacto.economico_nacional,
        "social_individual": impacto.social_individual,
        "economico_individual": impacto.economico_individual,
        "intensidad": impacto.intensidad,
        "confianza": impacto.confianza,
        "signo": impacto.signo,
        "beneficiario": impacto.beneficiario,
        "etiquetas": impacto.etiquetas,
        "explicacion": impacto.explicacion,
        "impacto_presupuestario_millones_eur": impacto.impacto_presupuestario_millones_eur,
        "afectados_estimados": impacto.afectados_estimados,
        "datos_referencia": impacto.datos_referencia,
    }
