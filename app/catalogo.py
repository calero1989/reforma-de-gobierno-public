"""Acceso al catálogo de leyes descargadas del BOE."""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

ORDEN_RANGOS = [
    "Constitución",
    "Ley Orgánica",
    "Ley",
    "Ley Foral",
    "Real Decreto Legislativo",
    "Real Decreto-ley",
]

INFO_RANGOS: dict[str, dict] = {
    "Constitución": {
        "como": "Fue elaborada por una Asamblea Constituyente formada por diputados y senadores elegidos en las elecciones generales de junio de 1977, conocidos como los 'Padres de la Constitución'. El texto fue redactado por una ponencia de siete miembros (Gabriel Cisneros, José Pedro Pérez-Llorca, Miguel Herrero de Miñón, Miquel Roca, Manuel Fraga, Gregorio Peces-Barba y Jordi Solé Tura) que representaban a las principales fuerzas políticas. Tras intensos debates y negociaciones de consenso en las Cortes, fue sometida a referéndum nacional.",
        "quien": "Las Cortes Generales constituyentes (Congreso y Senado), con la participación de representantes de todos los partidos políticos con representación parlamentaria. Fue ratificada directamente por el pueblo español mediante referéndum el 6 de diciembre de 1978, con un 87,78% de votos a favor.",
        "porque": "España necesitaba un marco jurídico democrático tras casi 40 años de dictadura franquista (1939-1975). La Transición española requería una norma suprema que garantizara los derechos fundamentales, estableciera la monarquía parlamentaria, organizara el Estado de las Autonomías y sentara las bases de un Estado social y democrático de Derecho, integrando a España en el marco europeo de democracias.",
    },
    "Ley Orgánica": {
        "como": "Se aprueban mediante un procedimiento legislativo reforzado que exige mayoría absoluta del Congreso de los Diputados (al menos 176 votos de 350) en una votación final sobre el conjunto del proyecto. Pueden ser iniciadas por el Gobierno, el Congreso, el Senado, las Asambleas de las Comunidades Autónomas o por iniciativa popular (500.000 firmas). El proceso incluye debate en comisión, enmiendas y debate en pleno, con intervención del Senado.",
        "quien": "Las Cortes Generales (Congreso y Senado), a iniciativa del Gobierno o de los propios parlamentarios. La mayoría absoluta requerida garantiza un amplio consenso político, ya que normalmente necesita el acuerdo de más de un partido.",
        "porque": "La Constitución reserva esta categoría especial para las materias más sensibles del ordenamiento jurídico: desarrollo de los derechos fundamentales y libertades públicas (Título I CE), aprobación de los Estatutos de Autonomía, régimen electoral general, y otras materias expresamente previstas en la Constitución (art. 81 CE). Su exigencia de mayoría absoluta busca proteger estas materias de cambios impulsivos o con mayorías simples.",
    },
    "Ley": {
        "como": "Se aprueban por el procedimiento legislativo ordinario: iniciativa (del Gobierno como proyecto de ley, o del Congreso/Senado/CC.AA./ciudadanos como proposición de ley), toma en consideración, debate en comisión con enmiendas, debate y votación en el Pleno del Congreso por mayoría simple, remisión al Senado (que puede enmendar o vetar), y en su caso, resolución de discrepancias. Finalmente, el Rey sanciona y ordena su publicación en el BOE.",
        "quien": "Las Cortes Generales, siendo el Congreso de los Diputados la cámara con prevalencia legislativa. El Gobierno tiene iniciativa prioritaria mediante proyectos de ley. Los ciudadanos pueden presentar proposiciones de ley con 500.000 firmas (iniciativa legislativa popular), aunque con materias excluidas.",
        "porque": "Son el instrumento ordinario para regular la convivencia social, económica y política del país. Desarrollan la Constitución en materias no reservadas a Ley Orgánica, regulan derechos y obligaciones, establecen impuestos, organizan servicios públicos, y en general, cualquier materia que requiera una norma con rango de ley aprobada por el Parlamento con plenas garantías democráticas.",
    },
    "Ley Foral": {
        "como": "Se aprueban por el Parlamento de Navarra (Parlamento Foral) siguiendo un procedimiento legislativo propio establecido en la Ley Orgánica de Reintegración y Amejoramiento del Régimen Foral de Navarra (LORAFNA, 1982). El procedimiento incluye iniciativa legislativa, debate en comisión, enmiendas y votación en pleno del Parlamento Foral.",
        "quien": "El Parlamento de Navarra, compuesto por 50 parlamentarios elegidos por los ciudadanos navarros. La iniciativa puede ser del Gobierno de Navarra, de los propios parlamentarios, de los ayuntamientos navarros o de los ciudadanos navarros mediante iniciativa popular.",
        "porque": "Navarra tiene un régimen foral histórico especial, reconocido en la Disposición Adicional Primera de la Constitución, que le otorga competencias legislativas propias. Las Leyes Forales regulan materias de competencia exclusiva o compartida de la Comunidad Foral: régimen tributario propio (Convenio Económico), administración local, ordenación del territorio, sanidad, educación, y las demás competencias asumidas. Este sistema foral tiene raíces históricas anteriores a la Constitución de 1978.",
    },
    "Real Decreto Legislativo": {
        "como": "El Parlamento (Cortes Generales) aprueba una ley de delegación (ley de bases o ley ordinaria autorizante) que fija con precisión el objeto, alcance, principios y plazo de la delegación. El Gobierno, dentro de ese mandato y plazo, elabora el Real Decreto Legislativo, que tiene rango de ley. Puede ser un texto articulado (desarrollando unas bases) o un texto refundido (reuniendo en un solo texto varias leyes dispersas sobre la misma materia).",
        "quien": "El Gobierno de España (Consejo de Ministros), por delegación expresa de las Cortes Generales según el artículo 82 de la Constitución. La delegación debe ser precisa: no cabe en materia de Ley Orgánica, y se agota con su uso.",
        "porque": "Responden a necesidades técnicas que el Parlamento delega al Gobierno: (1) Textos refundidos: cuando una materia está regulada por múltiples leyes dispersas y modificadas sucesivamente, se encarga al Gobierno reunirlas en un texto único, claro y coherente, facilitando su conocimiento y aplicación. (2) Textos articulados: cuando una materia requiere una regulación muy técnica y detallada, el Parlamento fija los principios y el Gobierno los desarrolla con mayor agilidad técnica.",
    },
    "Real Decreto-ley": {
        "como": "El Gobierno los aprueba directamente en Consejo de Ministros ante una situación de extraordinaria y urgente necesidad, sin debate parlamentario previo. Entran en vigor inmediatamente tras su publicación en el BOE. En un plazo de 30 días hábiles, el Congreso debe debatirlo y votarlo: puede convalidarlo (ratificarlo), derogarlo, o tramitarlo como proyecto de ley por el procedimiento de urgencia para introducir modificaciones.",
        "quien": "El Gobierno de España (Consejo de Ministros) en uso de la potestad que le confiere el artículo 86 de la Constitución. No requiere autorización previa del Parlamento, aunque sí su convalidación posterior por el Congreso de los Diputados.",
        "porque": "Son el instrumento legislativo de emergencia para situaciones de extraordinaria y urgente necesidad donde el procedimiento legislativo ordinario sería demasiado lento. Se han utilizado para crisis económicas, sanitarias (COVID-19), catástrofes naturales, situaciones sociales urgentes o adaptaciones normativas europeas con plazos inaplazables. No pueden afectar al ordenamiento de las instituciones básicas del Estado, derechos fundamentales del Título I CE, régimen de las CC.AA. ni al derecho electoral general.",
    },
}

INFO_COLECCIONES: dict[str, dict] = {
    "derechos-humanos": {
        "como": "Los derechos humanos se han codificado a través de declaraciones, tratados y convenciones internacionales negociadas en organismos multilaterales, principalmente la ONU. En España, se incorporan al ordenamiento a través de la Constitución (Título I), leyes orgánicas que desarrollan derechos fundamentales, y la ratificación de tratados internacionales que, una vez publicados en el BOE, forman parte del derecho interno (art. 96 CE).",
        "quien": "A nivel internacional: la Asamblea General de la ONU adoptó la Declaración Universal de Derechos Humanos (1948), impulsada por Eleanor Roosevelt y una comisión de representantes de 18 países. A nivel europeo: el Consejo de Europa adoptó el Convenio Europeo de Derechos Humanos (1950). En España: las Cortes Generales desarrollan estos derechos mediante leyes orgánicas, supervisadas por el Tribunal Constitucional y el Defensor del Pueblo.",
        "porque": "Tras las atrocidades de la Segunda Guerra Mundial y los totalitarismos del siglo XX, la comunidad internacional reconoció la necesidad de establecer un catálogo universal de derechos inherentes a toda persona, por el mero hecho de serlo, que ningún Estado pudiera vulnerar. En España, tras la dictadura, la Constitución de 1978 incorporó un amplio catálogo de derechos fundamentales alineado con los estándares europeos e internacionales.",
    },
    "carta-magna": {
        "como": "La “Carta Magna” (Magna Carta) es un documento histórico del Reino de Inglaterra. Su versión de referencia se emitió en 1215 por el rey Juan, con el objetivo de fijar garantías y límites al poder real y reconocer derechos y procedimientos frente a abusos. En el lenguaje moderno, “carta magna” se usa como sinónimo de “carta fundamental” o base de un orden jurídico.",
        "quien": "Fue impulsada por la Corona inglesa, pero nació de la presión de los barones y del conflicto político con el rey Juan (1215). En aquel contexto también influyeron sectores eclesiásticos y de la administración que reclamaban estabilidad, legalidad y respeto a los procedimientos.",
        "porque": "Se redactó para poner freno al poder arbitrario del monarca y asegurar garantías legales (como límites a detenciones o procedimientos sin causa, y reglas de proceso). Con el tiempo, la Magna Carta se reeditó y su influencia se extendió como antecedente de principios como el “due process” y el gobierno sometido a la ley.\n\nNota en esta app: cuando eliges “Carta Magna”, el contenido enlaza a la **Constitución Española de 1978** como equivalencia práctica de “carta fundamental” en España.",
    },
    "extranjeria": {
        "como": "La legislación de extranjería se elabora mediante leyes orgánicas (por afectar a derechos fundamentales) y reglamentos de desarrollo. El proceso incluye consulta a organizaciones sociales, informes del Consejo de Estado, debate parlamentario y, frecuentemente, adaptación a directivas europeas sobre migración y asilo. Las sucesivas reformas responden a cambios en los flujos migratorios y compromisos internacionales.",
        "quien": "Las Cortes Generales aprueban las leyes orgánicas de extranjería. El Gobierno elabora los reglamentos de desarrollo. Intervienen también: la Unión Europea (directivas de migración y asilo), organismos internacionales (ACNUR, OIM) mediante recomendaciones, y el Tribunal Constitucional verificando que la regulación respete los derechos fundamentales de los extranjeros en España.",
        "porque": "España pasó de ser un país de emigración a uno de inmigración a partir de los años 1990. Fue necesario crear un marco legal que regulara la entrada, estancia, trabajo y derechos de los extranjeros en España, respetando los compromisos internacionales (Convención de Ginebra sobre refugiados), las directivas europeas y los derechos constitucionales. La ley busca equilibrar el control de flujos migratorios con la protección de derechos humanos.",
    },
    "tratados-internacionales": {
        "como": "El Gobierno negocia los tratados a través del Ministerio de Asuntos Exteriores. Según su contenido, requieren autorización previa de las Cortes Generales (art. 94 CE) o por ley orgánica si implican cesión de soberanía (art. 93 CE). Tras la autorización parlamentaria, el Rey ratifica el tratado. Una vez publicado en el BOE, el tratado se integra en el ordenamiento interno y sus disposiciones solo pueden ser modificadas conforme al propio tratado.",
        "quien": "El Gobierno de España negocia y firma los tratados. Las Cortes Generales los autorizan o aprueban. El Rey los ratifica formalmente. Las otras partes son Estados soberanos u organizaciones internacionales (ONU, UE, Consejo de Europa, OTAN, etc.). El Tribunal Constitucional puede ser consultado sobre la compatibilidad del tratado con la Constitución antes de su ratificación.",
        "porque": "España, como miembro de la comunidad internacional, necesita formalizar sus relaciones con otros Estados y organizaciones mediante acuerdos vinculantes. Los tratados regulan comercio, defensa, cooperación judicial, protección del medio ambiente, derechos humanos, extradición, doble imposición fiscal y muchas otras materias que trascienden las fronteras nacionales. Son esenciales para la integración europea y la participación en el orden internacional.",
    },
    "normativa-europea": {
        "como": "La normativa europea se genera mediante un proceso legislativo propio de la UE: la Comisión Europea propone, el Parlamento Europeo y el Consejo de la UE (representantes de los gobiernos) debaten y aprueban. Los Reglamentos son directamente aplicables en todos los Estados. Las Directivas deben ser transpuestas al derecho nacional (en España, generalmente mediante ley o real decreto-ley). España incorpora esta normativa a través de leyes de transposición, reales decretos o reales decretos-ley.",
        "quien": "Las instituciones de la Unión Europea: la Comisión Europea (iniciativa), el Parlamento Europeo (ciudadanos, elegidos por sufragio directo) y el Consejo de la UE (gobiernos de los 27 Estados miembros). España participa en todas estas instituciones: eurodiputados en el Parlamento, ministros en el Consejo, y un comisario en la Comisión. El Tribunal de Justicia de la UE garantiza la correcta aplicación.",
        "porque": "Desde la adhesión de España a las Comunidades Europeas en 1986, el derecho europeo forma parte del ordenamiento español con primacía sobre el derecho interno. La normativa europea busca crear un mercado único, garantizar las cuatro libertades fundamentales (personas, mercancías, servicios y capitales), armonizar estándares de protección al consumidor, medio ambiente, competencia, y construir un espacio común de libertad, seguridad y justicia.",
    },
    "derecho-publico": {
        "como": "Se genera mediante leyes aprobadas por las Cortes Generales o los Parlamentos autonómicos, reglamentos del Gobierno, y normativa de las Administraciones Públicas. El proceso legislativo incluye informes técnicos, dictámenes del Consejo de Estado, consulta pública, debate parlamentario y publicación en el BOE. Cada rama (administrativo, tributario, penal) tiene sus procedimientos específicos y órganos especializados.",
        "quien": "Las Cortes Generales (legislación estatal), los Parlamentos autonómicos (legislación autonómica), el Gobierno (reglamentos), y las Administraciones Públicas en sus distintos niveles (estatal, autonómico, local). El Tribunal Constitucional, el Tribunal Supremo y los tribunales contencioso-administrativos controlan que la actuación pública se ajuste a Derecho.",
        "porque": "El Derecho Público regula la organización y funcionamiento del Estado y sus relaciones con los ciudadanos. Es necesario para: organizar la Administración Pública y garantizar su funcionamiento eficaz, establecer el sistema tributario y la Hacienda Pública, regular la contratación pública, proteger la seguridad ciudadana, garantizar el acceso a servicios públicos (sanidad, educación, justicia), y establecer las reglas del proceso electoral democrático.",
    },
    "derecho-privado": {
        "como": "Se genera principalmente mediante leyes aprobadas por las Cortes Generales, codificaciones históricas (Código Civil de 1889, Código de Comercio de 1885) y sus sucesivas reformas modernizadoras. También interviene la jurisprudencia del Tribunal Supremo unificando criterios interpretativos, y cada vez más, la armonización europea mediante directivas que España transpone. Los derechos forales de algunas CC.AA. añaden regulaciones civiles propias.",
        "quien": "Las Cortes Generales como legislador principal. El Gobierno desarrolla reglamentariamente ciertas materias. Los Parlamentos autonómicos con competencias en derecho civil foral o especial (Cataluña, Aragón, Navarra, País Vasco, Galicia, Baleares, Valencia). Los notarios y registradores dan fe pública y seguridad jurídica a las relaciones privadas. Los jueces de lo civil resuelven los conflictos entre particulares.",
        "porque": "El Derecho Privado regula las relaciones entre personas (físicas y jurídicas) en condiciones de igualdad. Es imprescindible para: garantizar la propiedad y su transmisión (compraventa, herencia), regular los contratos y obligaciones, organizar el matrimonio y las relaciones familiares, proteger a los consumidores frente a las empresas, regular las sociedades mercantiles y el comercio, y proteger la propiedad intelectual e industrial.",
    },
    "mixtas": {
        "como": "Las categorías mixtas combinan elementos de Derecho Público y Privado. Se generan mediante leyes estatales y autonómicas, reglamentos, convenios colectivos (en lo laboral), y cada vez más, por transposición de normativa europea. Su elaboración implica consulta a agentes sociales (sindicatos, patronal), organismos técnicos especializados, y procesos de participación ciudadana. Son materias donde el interés público y los derechos individuales se entrelazan.",
        "quien": "Las Cortes Generales y los Parlamentos autonómicos para las leyes. El Gobierno y los gobiernos autonómicos para los reglamentos. Los agentes sociales (sindicatos y organizaciones empresariales) negocian convenios colectivos en materia laboral. Organismos especializados (AEPD en protección de datos, Agencia Estatal de Meteorología en medio ambiente) aplican y supervisan la normativa. La UE tiene competencias crecientes en estas materias.",
        "porque": "Estas materias —trabajo, seguridad social, medio ambiente, educación, sanidad, vivienda, igualdad, protección de datos, telecomunicaciones— son esenciales para el bienestar de los ciudadanos y requieren una regulación que combine la intervención pública (garantizar derechos, establecer mínimos, controlar riesgos) con el respeto a la autonomía privada. Reflejan el modelo de Estado social y democrático de Derecho que establece la Constitución (art. 1.1 CE).",
    },
}


def raiz_datos() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def cargar_catalogo() -> list[dict]:
    ruta = raiz_datos() / "leyes" / "catalogo.json"
    if not ruta.exists():
        return []
    return json.loads(ruta.read_text(encoding="utf-8"))


COLECCIONES_TEMATICAS = [
    {
        "id": "derechos-humanos",
        "nombre": "Derechos Humanos",
        "icono": "✊",
        "palabras": ["derechos humanos", "derechos fundamentales", "libertades públicas",
                     "habeas corpus", "asilo", "refugio", "tutela", "amparo",
                     "víctimas", "tortura", "discriminación"],
        "tipo": "tematica",
    },
    {
        "id": "carta-magna",
        "nombre": "Carta Magna",
        "icono": "📜",
        "palabras": ["constitución"],
        "rangos": ["Constitución"],
        "tipo": "tematica",
    },
    {
        "id": "extranjeria",
        "nombre": "Ley de Extranjería",
        "icono": "🌍",
        "palabras": ["extranjería", "extranjeria", "extranjeros", "inmigración",
                     "inmigracion", "asilo", "refugiados", "nacionalidad",
                     "residencia", "fronteras"],
        "tipo": "tematica",
    },
    {
        "id": "tratados-internacionales",
        "nombre": "Tratados Internacionales",
        "icono": "🌐",
        "palabras": ["tratado", "convenio internacional", "acuerdo internacional",
                     "protocolo internacional", "naciones unidas", "pacto internacional",
                     "convención", "convencion"],
        "tipo": "tematica",
    },
    {
        "id": "normativa-europea",
        "nombre": "Normativa Europea",
        "icono": "🇪🇺",
        "palabras": ["unión europea", "union europea", "europea", "comunitario",
                     "comunitaria", "directiva", "reglamento europeo", "tratado de"],
        "tipo": "tematica",
    },
    {
        "id": "derecho-publico",
        "nombre": "Derecho Público",
        "icono": "🏛️",
        "palabras": ["administración pública", "administracion publica", "procedimiento administrativo",
                     "función pública", "funcion publica", "régimen jurídico",
                     "hacienda", "tributar", "fiscal", "impuesto", "presupuest",
                     "seguridad ciudadana", "defensa", "electoral", "contratación pública",
                     "contratacion publica", "patrimonio del estado"],
        "tipo": "tematica",
    },
    {
        "id": "derecho-privado",
        "nombre": "Derecho Privado",
        "icono": "📝",
        "palabras": ["civil", "mercantil", "hipotecari", "propiedad", "arrendamiento",
                     "sociedades", "consumidor", "competencia desleal", "patentes",
                     "marcas", "herencia", "sucesiones", "contrato", "obligaciones"],
        "tipo": "tematica",
    },
    {
        "id": "mixtas",
        "nombre": "Categorías Mixtas",
        "icono": "⚖️",
        "palabras": ["seguridad social", "laboral", "trabajo", "prevención de riesgos",
                     "prevencion de riesgos", "medio ambiente", "urbanismo",
                     "educación", "educacion", "sanidad", "salud", "vivienda",
                     "igualdad", "violencia de género", "violencia de genero",
                     "protección de datos", "proteccion de datos", "telecomunicaciones"],
        "tipo": "tematica",
    },
]


def _buscar_tematica(col: dict) -> list[dict]:
    items = cargar_catalogo()
    rangos = col.get("rangos")
    if rangos:
        return [i for i in items if i.get("rango") in rangos]
    palabras = col["palabras"]
    resultado = []
    for item in items:
        titulo = (item.get("titulo") or "").lower()
        if any(p in titulo for p in palabras):
            resultado.append(item)
    return resultado


def categorias() -> list[dict]:
    conteo = Counter(item.get("rango", "Otro") for item in cargar_catalogo())
    resultado = []
    for rango in ORDEN_RANGOS:
        if conteo.get(rango):
            entry: dict = {"rango": rango, "total": conteo[rango], "tipo": "rango"}
            if rango in INFO_RANGOS:
                entry["info"] = INFO_RANGOS[rango]
            resultado.append(entry)
    for rango, total in sorted(conteo.items(), key=lambda x: -x[1]):
        if rango not in ORDEN_RANGOS:
            resultado.append({"rango": rango, "total": total, "tipo": "rango"})
    return resultado


def colecciones() -> list[dict]:
    result = []
    for col in COLECCIONES_TEMATICAS:
        total = len(_buscar_tematica(col))
        entry = {
            "id": col["id"],
            "nombre": col["nombre"],
            "icono": col["icono"],
            "total": total,
            "tipo": "tematica",
        }
        if col["id"] in INFO_COLECCIONES:
            entry["info"] = INFO_COLECCIONES[col["id"]]
        result.append(entry)
    return result


def buscar_coleccion(col_id: str, q: str = "", limite: int = 200) -> list[dict]:
    col = next((c for c in COLECCIONES_TEMATICAS if c["id"] == col_id), None)
    if not col:
        return []
    items = _buscar_tematica(col)
    if q:
        palabras = q.lower().split()
        items = [i for i in items if all(
            p in " ".join(str(i.get(k, "")) for k in ("titulo", "identificador", "rango")).lower()
            for p in palabras
        )]
    return items[:limite]


def buscar(q: str = "", rango: str = "", limite: int = 80,
           titulo: str = "", materia: str = "") -> list[dict]:
    items = cargar_catalogo()
    qn = q.strip().lower()
    rn = rango.strip().lower()
    tn = titulo.strip().lower()
    mn = materia.strip().lower()
    palabras = qn.split() if qn else []
    palabras_titulo = tn.split() if tn else []
    palabras_materia = mn.split() if mn else []
    filtrados = []
    for item in items:
        if rn and rn != (item.get("rango") or "").lower():
            continue
        tit = (item.get("titulo") or "").lower()
        if palabras_titulo and not all(p in tit for p in palabras_titulo):
            continue
        if palabras_materia:
            blob = " ".join(str(item.get(k, "")) for k in ("titulo", "rango")).lower()
            if not all(p in blob for p in palabras_materia):
                continue
        if palabras:
            blob = " ".join(
                str(item.get(k, "")) for k in ("titulo", "identificador", "numero_oficial", "rango")
            ).lower()
            if not all(p in blob for p in palabras):
                continue
        filtrados.append(item)
        if len(filtrados) >= limite:
            break
    return filtrados


def obtener(identificador: str) -> dict | None:
    for item in cargar_catalogo():
        if item.get("identificador") == identificador:
            return item
    return None


# ─── Áreas de materia (mapa normativo; sin gasto PGE) ───

CE = "BOE-A-1978-31229"

AREAS_MATERIA = [
    {
        "id": "vivienda",
        "nombre": "Vivienda y urbanismo",
        "icono": "🏠",
        "descripcion": "Normas y artículos sobre acceso a la vivienda, alquiler y ordenación del suelo.",
        "palabras": ["vivienda", "alquiler", "arrendamiento urbano", "urbanismo", "suelo"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-47",
                "titulo": "Artículo 47 CE — derecho a la vivienda",
            },
        ],
    },
    {
        "id": "sanidad",
        "nombre": "Sanidad",
        "icono": "🏥",
        "descripcion": "Normativa sobre salud pública, asistencia sanitaria y farmacia.",
        "palabras": ["sanidad", "salud", "farmacéutic", "farmacia", "sistema nacional de salud"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-43",
                "titulo": "Artículo 43 CE — protección de la salud",
            },
        ],
    },
    {
        "id": "educacion",
        "nombre": "Educación",
        "icono": "📚",
        "descripcion": "Educación reglada, universidades, formación profesional y becas.",
        "palabras": ["educación", "educacion", "universidad", "enseñanza", "formacion profesional", "formación profesional"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-27",
                "titulo": "Artículo 27 CE — derecho a la educación",
            },
        ],
    },
    {
        "id": "empleo",
        "nombre": "Empleo y seguridad social",
        "icono": "💼",
        "descripcion": "Trabajo, relaciones laborales, desempleo y seguridad social.",
        "palabras": ["trabajo", "laboral", "empleo", "seguridad social", "desempleo", "estatuto de los trabajadores"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-35",
                "titulo": "Artículo 35 CE — derecho al trabajo",
            },
        ],
    },
    {
        "id": "personal-publico",
        "nombre": "Personal del sector público",
        "icono": "👤",
        "descripcion": "Función pública, empleo público y régimen del personal al servicio de las administraciones.",
        "palabras": ["función pública", "funcion publica", "empleo público", "empleo publico", "estatuto básico del empleado"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-103",
                "titulo": "Artículo 103 CE — Administración Pública",
            },
        ],
    },
    {
        "id": "defensa-seguridad",
        "nombre": "Defensa y seguridad",
        "icono": "🛡️",
        "descripcion": "Defensa, fuerzas armadas y seguridad ciudadana a nivel normativo.",
        "palabras": ["defensa", "fuerzas armadas", "seguridad ciudadana", "guardia civil", "policía", "policia"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-8",
                "titulo": "Artículo 8 CE — Fuerzas Armadas",
            },
        ],
    },
    {
        "id": "justicia",
        "nombre": "Justicia y derechos",
        "icono": "⚖️",
        "descripcion": "Derechos fundamentales, garantías procesales y organización de la justicia.",
        "palabras": ["justicia", "poder judicial", "tutela judicial", "derechos fundamentales", "enjuiciamiento"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-24",
                "titulo": "Artículo 24 CE — tutela judicial efectiva",
            },
            {
                "ley_id": CE,
                "articulo_id": "art-14",
                "titulo": "Artículo 14 CE — igualdad ante la ley",
            },
        ],
    },
    {
        "id": "economia-fiscal",
        "nombre": "Economía y fiscalidad",
        "icono": "💶",
        "descripcion": "Tributos, hacienda pública, consumo y marco económico general.",
        "palabras": ["tribut", "impuesto", "hacienda", "fiscal", "presupuesto", "consumo"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-31",
                "titulo": "Artículo 31 CE — sistema tributario",
            },
        ],
    },
    {
        "id": "medio-ambiente",
        "nombre": "Medio ambiente y energía",
        "icono": "🌿",
        "descripcion": "Protección ambiental, energía, agua y residuos.",
        "palabras": ["medio ambiente", "ambiental", "energía", "energia", "residuos", "cambio climático", "cambio climatico"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-45",
                "titulo": "Artículo 45 CE — medio ambiente",
            },
        ],
    },
    {
        "id": "igualdad-inclusion",
        "nombre": "Igualdad e inclusión",
        "icono": "🤝",
        "descripcion": "Igualdad de trato, discapacidad y prevención de la discriminación.",
        "palabras": ["igualdad", "discriminación", "discriminacion", "discapacidad", "violencia de género", "violencia de genero"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-14",
                "titulo": "Artículo 14 CE — igualdad ante la ley",
            },
        ],
    },
    {
        "id": "migracion",
        "nombre": "Migración y extranjería",
        "icono": "🌍",
        "descripcion": "Extranjería, asilo, nacionalidad y régimen de residencia.",
        "palabras": ["extranjería", "extranjeria", "extranjeros", "inmigración", "inmigracion", "asilo", "nacionalidad"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-13",
                "titulo": "Artículo 13 CE — extranjeros en España",
            },
        ],
    },
    {
        "id": "cooperacion",
        "nombre": "Cooperación internacional",
        "icono": "🌐",
        "descripcion": "Acción exterior, tratados y cooperación al desarrollo.",
        "palabras": ["cooperación", "cooperacion", "acción exterior", "accion exterior", "tratado internacional", "desarrollo internacional"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-93",
                "titulo": "Artículo 93 CE — tratados de atribución de competencias",
            },
        ],
    },
    {
        "id": "entidades-sociales",
        "nombre": "Entidades sociales y tercer sector",
        "icono": "🏛️",
        "descripcion": "Asociaciones, fundaciones y régimen de entidades sin ánimo de lucro.",
        "palabras": ["asociacion", "asociación", "fundacion", "fundación", "tercer sector", "voluntariado"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-22",
                "titulo": "Artículo 22 CE — derecho de asociación",
            },
        ],
    },
    {
        "id": "administracion",
        "nombre": "Administración y procedimiento",
        "icono": "📋",
        "descripcion": "Procedimiento administrativo, transparencia y buen gobierno.",
        "palabras": ["procedimiento administrativo", "transparencia", "buen gobierno", "administración pública", "administracion publica"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-105",
                "titulo": "Artículo 105 CE — audiencia y acceso a archivos",
            },
        ],
    },
    {
        "id": "autonomias-local",
        "nombre": "Autonomías y administración local",
        "icono": "🗺️",
        "descripcion": "Comunidades autónomas, régimen foral y entidades locales.",
        "palabras": ["autonomía", "autonomia", "comunidad autónoma", "comunidad autonoma", "régimen local", "regimen local", "ayuntamiento", "foral"],
        "ejemplos": [
            {
                "ley_id": CE,
                "articulo_id": "art-137",
                "titulo": "Artículo 137 CE — organización territorial",
            },
        ],
    },
]


def _normas_de_area(area: dict) -> list[dict]:
    items = cargar_catalogo()
    palabras = [p.lower() for p in area.get("palabras") or []]
    resultado = []
    for item in items:
        titulo = (item.get("titulo") or "").lower()
        if any(p in titulo for p in palabras):
            resultado.append(item)
    return resultado


def areas() -> list[dict]:
    result = []
    for area in AREAS_MATERIA:
        total = len(_normas_de_area(area))
        result.append(
            {
                "id": area["id"],
                "nombre": area["nombre"],
                "icono": area["icono"],
                "descripcion": area["descripcion"],
                "total": total,
                "ejemplos": len(area.get("ejemplos") or []),
            }
        )
    return result


def obtener_area(area_id: str) -> dict | None:
    return next((a for a in AREAS_MATERIA if a["id"] == area_id), None)


def buscar_area(area_id: str, q: str = "", limite: int = 200) -> dict | None:
    area = obtener_area(area_id)
    if not area:
        return None
    items = _normas_de_area(area)
    if q:
        palabras = q.lower().split()
        items = [
            i
            for i in items
            if all(
                p in " ".join(str(i.get(k, "")) for k in ("titulo", "identificador", "rango")).lower()
                for p in palabras
            )
        ]
    return {
        "id": area["id"],
        "nombre": area["nombre"],
        "icono": area["icono"],
        "descripcion": area["descripcion"],
        "ejemplos": area.get("ejemplos") or [],
        "items": items[:limite],
        "total": len(items),
    }
