"""Registro de usuarios, visitas, valoraciones y sugerencias."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import threading
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "datos" / "comunidad"
USUARIOS = DATOS / "usuarios.jsonl"
VISITAS = DATOS / "visitas.jsonl"
VALORACIONES = DATOS / "valoraciones.jsonl"
FORO_HILOS = DATOS / "foro_hilos.jsonl"
FORO_RESPUESTAS = DATOS / "foro_respuestas.jsonl"
FORO_VOTOS = DATOS / "foro_votos.jsonl"
COMENTARIOS = DATOS / "comentarios.jsonl"
REACCIONES = DATOS / "reacciones.jsonl"
PERFIL_GUARDADOS = DATOS / "guardados.jsonl"
RESET_TOKENS = DATOS / "reset_tokens.jsonl"
_lock = threading.Lock()
_log = logging.getLogger(__name__)



EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8
MAX_PASSWORD = 128
CAMPOS_PRIVADOS = frozenset({"usuario_id", "password_hash", "session_version"})


def _hash_password(password: str) -> str:
    return generate_password_hash(password, method="scrypt")


def _verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    if stored.startswith(("pbkdf2:", "scrypt:", "argon2:")):
        return check_password_hash(stored, password)
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    try:
        return secrets.compare_digest(legacy, stored)
    except (TypeError, ValueError):
        return False


def _password_ok(password: str) -> str | None:
    if not password or len(password) < MIN_PASSWORD:
        return f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres."
    if len(password) > MAX_PASSWORD:
        return f"La contraseña no puede superar {MAX_PASSWORD} caracteres."
    return None


def version_sesion(usuario_id: str) -> int:
    if not usuario_id:
        return -1
    for u in _leer_jsonl(USUARIOS):
        if u.get("id") == usuario_id:
            return int(u.get("session_version") or 0)
    return -1


def _bump_session_version(usuario: dict) -> int:
    nueva = int(usuario.get("session_version") or 0) + 1
    usuario["session_version"] = nueva
    return nueva


def obtener_usuario_publico(usuario_id: str) -> dict | None:
    for u in _leer_jsonl(USUARIOS):
        if u.get("id") == usuario_id:
            return {
                "id": u["id"],
                "nombre": u.get("nombre", ""),
                "username": u.get("username", ""),
                "email": u.get("email", ""),
                "session_version": int(u.get("session_version") or 0),
            }
    return None


def _sin_campos_privados(registro: dict) -> dict:
    return {k: v for k, v in registro.items() if k not in CAMPOS_PRIVADOS}


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _quitar_caracteres_formato(texto: str) -> str:
    return "".join(c for c in texto if unicodedata.category(c) != "Cf")


def _sanear_texto_usuario(texto: str) -> str:
    return _quitar_caracteres_formato(texto)


def _leer_jsonl(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    filas = []
    for num, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        linea = linea.strip()
        if not linea:
            continue
        parseada = None
        for candidata in (linea, _quitar_caracteres_formato(linea)):
            try:
                parseada = json.loads(candidata)
                break
            except json.JSONDecodeError:
                continue
        if parseada is None:
            _log.warning(
                "No se pudo parsear la linea %s de %s (inicio: %.80r)",
                num,
                ruta.name,
                linea,
            )
            continue
        filas.append(parseada)
    return filas


def _append(ruta: Path, registro: dict) -> None:
    DATOS.mkdir(parents=True, exist_ok=True)
    with _lock:
        with ruta.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _write_jsonl(ruta: Path, registros: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        contenido = "\n".join(json.dumps(r, ensure_ascii=False) for r in registros)
        if contenido:
            contenido += "\n"
        ruta.write_text(contenido, encoding="utf-8")


def registrar_usuario(
    nombre: str,
    email: str,
    dispositivo: str,
    usuario_id: str | None,
    username: str = "",
    password: str = "",
    sesion_uid: str | None = None,
) -> dict:
    nombre = (nombre or "").strip()[:80]
    email = (email or "").strip().lower()[:120]
    username = (username or "").strip().lower()[:40]
    # No hacer strip() a la contraseña: los espacios pueden ser intencionados
    password = password or ""
    if len(nombre) < 2:
        return {"error": "Indica un nombre de al menos 2 caracteres."}
    if not email or not EMAIL_RE.match(email):
        return {"error": "El correo es obligatorio y debe ser válido."}
    if not username or len(username) < 3:
        return {"error": "El nombre de usuario debe tener al menos 3 caracteres."}
    if not re.match(r"^[a-z0-9._-]+$", username):
        return {"error": "El usuario solo puede contener letras, números, puntos, guiones y guiones bajos."}
    err_pass = _password_ok(password)
    if err_pass:
        return {"error": err_pass}

    existentes = _leer_jsonl(USUARIOS)

    # Completar credenciales solo en la misma sesión y sin contraseña previa.
    objetivo = None
    objetivo_id = None
    if usuario_id:
        objetivo = next((u for u in existentes if u.get("id") == usuario_id), None)
        if objetivo:
            objetivo_id = objetivo.get("id")
    if objetivo is None and email:
        objetivo = next((u for u in existentes if u.get("email") == email), None)
        if objetivo:
            objetivo_id = objetivo.get("id")

    if objetivo:
        if objetivo.get("password_hash"):
            return {"error": "No se pudo completar el registro. Prueba iniciar sesión."}
        if not sesion_uid or sesion_uid != objetivo_id:
            return {"error": "No autorizado para completar este registro."}
        usado_por_otro = next(
            (u for u in existentes if u.get("username") == username and u.get("id") != objetivo_id),
            None,
        )
        if usado_por_otro:
            return {"error": "No se pudo completar el registro. Prueba con otro nombre de usuario."}
        email_otro = next(
            (u for u in existentes if u.get("email") == email and u.get("id") != objetivo_id),
            None,
        )
        if email_otro:
            return {"error": "No se pudo completar el registro. Prueba con otro correo."}

        objetivo.update(
            {
                "nombre": nombre,
                "username": username,
                "password_hash": _hash_password(password),
                "email": email,
                "dispositivo": (dispositivo or objetivo.get("dispositivo", "") or "")[:80],
                "session_version": int(objetivo.get("session_version") or 0),
            }
        )
        _write_jsonl(USUARIOS, existentes)
        return {
            "ok": True,
            "id": objetivo_id,
            "nuevo": False,
            "nombre": objetivo.get("nombre"),
            "username": objetivo.get("username", ""),
            "session_version": int(objetivo.get("session_version") or 0),
        }

    ya_user = next((u for u in existentes if u.get("username") == username), None)
    if ya_user:
        return {"error": "No se pudo completar el registro. Prueba iniciar sesión u otro usuario."}

    ya_email = next((u for u in existentes if u.get("email") == email), None)
    if ya_email:
        return {"error": "No se pudo completar el registro. Prueba iniciar sesión u otro correo."}

    uid = str(uuid.uuid4())
    _append(
        USUARIOS,
        {
            "id": uid,
            "nombre": nombre,
            "username": username,
            "password_hash": _hash_password(password),
            "email": email,
            "dispositivo": (dispositivo or "")[:80],
            "alta": _ahora(),
            "session_version": 0,
        },
    )
    return {
        "ok": True,
        "id": uid,
        "nuevo": True,
        "nombre": nombre,
        "username": username,
        "session_version": 0,
    }


def login_usuario(username: str, password: str) -> dict:
    username = (username or "").strip().lower()
    password = password or ""
    if not username or not password:
        return {"error": "Introduce tu usuario y contraseña."}

    existentes = _leer_jsonl(USUARIOS)
    usuario = next((u for u in existentes if u.get("username") == username), None)
    if not usuario or not _verify_password(password, usuario.get("password_hash")):
        return {"error": "Usuario o contraseña incorrectos."}

    stored = usuario.get("password_hash") or ""
    if not stored.startswith("scrypt:"):
        usuario["password_hash"] = _hash_password(password)
        _write_jsonl(USUARIOS, existentes)

    return {
        "ok": True,
        "id": usuario["id"],
        "nombre": usuario.get("nombre", ""),
        "username": usuario.get("username", ""),
        "session_version": int(usuario.get("session_version") or 0),
    }


def cambiar_contrasena(username: str, password_actual: str, password_nuevo: str) -> dict:
    """Cambia la contraseña verificando la actual (sin sesión iniciada)."""
    username = (username or "").strip().lower()
    password_actual = password_actual or ""
    password_nuevo = password_nuevo or ""
    if not username or not password_actual or not password_nuevo:
        return {"error": "Completa usuario, contraseña actual y contraseña nueva."}
    err_pass = _password_ok(password_nuevo)
    if err_pass:
        return {"error": err_pass}
    if password_actual == password_nuevo:
        return {"error": "La contraseña nueva debe ser distinta a la actual."}

    registros = _leer_jsonl(USUARIOS)
    usuario = next((u for u in registros if u.get("username") == username), None)
    if not usuario or not _verify_password(password_actual, usuario.get("password_hash")):
        return {"error": "Usuario o contraseña actual incorrectos."}

    usuario["password_hash"] = _hash_password(password_nuevo)
    version = _bump_session_version(usuario)
    _write_jsonl(USUARIOS, registros)
    return {
        "ok": True,
        "id": usuario["id"],
        "nombre": usuario.get("nombre", ""),
        "username": usuario.get("username", ""),
        "session_version": version,
    }


def solicitar_reset_password(email: str) -> dict:
    """Crea token de reset. Siempre mensaje genérico (no enumerar cuentas)."""
    email = (email or "").strip().lower()[:120]
    msg_ok = {
        "ok": True,
        "mensaje": "Si el correo está registrado, recibirás un enlace para restablecer la contraseña.",
    }
    if not email or not EMAIL_RE.match(email):
        return {"error": "Indica un correo válido."}

    usuario = next((u for u in _leer_jsonl(USUARIOS) if u.get("email") == email), None)
    if not usuario or not usuario.get("password_hash"):
        return msg_ok

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expira = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds")
    _append(
        RESET_TOKENS,
        {
            "token_hash": token_hash,
            "usuario_id": usuario["id"],
            "email": email,
            "expira": expira,
            "usado": False,
            "creado": _ahora(),
        },
    )
    return {
        **msg_ok,
        "token": token,
        "username": usuario.get("username", ""),
        "email": email,
    }


def restablecer_password(token: str, password_nuevo: str) -> dict:
    token = (token or "").strip()
    password_nuevo = password_nuevo or ""
    if not token:
        return {"error": "Enlace no válido o caducado."}
    err_pass = _password_ok(password_nuevo)
    if err_pass:
        return {"error": err_pass}

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    tokens = _leer_jsonl(RESET_TOKENS)
    ahora = datetime.now(timezone.utc)
    entrada = None
    for t in tokens:
        if t.get("token_hash") == token_hash and not t.get("usado"):
            entrada = t
            break
    if not entrada:
        return {"error": "Enlace no válido o caducado."}
    try:
        expira = datetime.fromisoformat(entrada["expira"])
        if expira.tzinfo is None:
            expira = expira.replace(tzinfo=timezone.utc)
        if ahora > expira:
            return {"error": "Enlace no válido o caducado."}
    except Exception:
        return {"error": "Enlace no válido o caducado."}

    registros = _leer_jsonl(USUARIOS)
    usuario = next((u for u in registros if u.get("id") == entrada.get("usuario_id")), None)
    if not usuario:
        return {"error": "Enlace no válido o caducado."}

    usuario["password_hash"] = _hash_password(password_nuevo)
    version = _bump_session_version(usuario)
    entrada["usado"] = True
    _write_jsonl(USUARIOS, registros)
    _write_jsonl(RESET_TOKENS, tokens)
    return {
        "ok": True,
        "id": usuario["id"],
        "nombre": usuario.get("nombre", ""),
        "username": usuario.get("username", ""),
        "session_version": version,
    }


def registrar_visita(usuario_id: str | None, dispositivo: str) -> None:
    _append(
        VISITAS,
        {
            "usuario_id": usuario_id or "",
            "dispositivo": (dispositivo or "")[:80],
            "fecha": _ahora(),
            "dia": date.today().isoformat(),
        },
    )


def guardar_valoracion(usuario_id: str | None, puntuacion: int, sugerencia: str, nombre: str) -> dict:
    try:
        puntos = int(puntuacion)
    except (TypeError, ValueError):
        return {"error": "La puntuación debe ser un número de 1 a 5."}
    if puntos < 1 or puntos > 5:
        return {"error": "Valora entre 1 y 5 estrellas."}
    texto = (sugerencia or "").strip()[:800]
    if not texto:
        return {"error": "Escribe una sugerencia o un comentario."}

    nombre_final = "Anónimo"
    if usuario_id:
        u = next((x for x in _leer_jsonl(USUARIOS) if x.get("id") == usuario_id), None)
        if u and (u.get("email") or "").strip():
            nombre_final = (nombre or u.get("nombre") or "Anónimo").strip()[:80]

    _append(
        VALORACIONES,
        {
            "usuario_id": usuario_id or "",
            "nombre": nombre_final,
            "puntuacion": puntos,
            "sugerencia": texto,
            "fecha": _ahora(),
        },
    )
    return {"ok": True, **estadisticas()}


def estadisticas() -> dict:
    usuarios = _leer_jsonl(USUARIOS)
    visitas = _leer_jsonl(VISITAS)
    valoraciones = _leer_jsonl(VALORACIONES)
    media = 0.0
    if valoraciones:
        media = round(sum(int(v.get("puntuacion") or 0) for v in valoraciones) / len(valoraciones), 2)
    dias = {v.get("dia") for v in visitas if v.get("dia")}
    sugerencias = [
        {
            "nombre": v.get("nombre") or "Anónimo",
            "puntuacion": v.get("puntuacion"),
            "sugerencia": v.get("sugerencia"),
            "fecha": v.get("fecha"),
        }
        for v in reversed(valoraciones[-40:])
    ]
    return {
        "usuarios_registrados": len(usuarios),
        "visitas_totales": len(visitas),
        "dias_con_uso": len(dias),
        "valoraciones": len(valoraciones),
        "puntuacion_media": media,
        "sugerencias": sugerencias,
    }


# ─── Foro ───────────────────────────────────────────────

CATEGORIAS_FORO = ["Debate", "Simulación", "Opinión", "Propuesta", "General"]


def _nombre_usuario(uid: str) -> str:
    for u in _leer_jsonl(USUARIOS):
        if u.get("id") == uid:
            # Si no hay correo, se respeta el anonimato público.
            if not (u.get("email") or "").strip():
                return "Anónimo"
            return u.get("nombre", "Anónimo")
    return "Anónimo"


def crear_hilo(usuario_id: str, titulo: str, cuerpo: str, categoria: str = "General") -> dict:
    titulo = (titulo or "").strip()[:200]
    cuerpo = (cuerpo or "").strip()[:4000]
    if not usuario_id:
        return {"error": "Debes registrarte para publicar."}
    if len(titulo) < 3:
        return {"error": "El título debe tener al menos 3 caracteres."}
    if len(cuerpo) < 5:
        return {"error": "Escribe un mensaje de al menos 5 caracteres."}
    if categoria not in CATEGORIAS_FORO:
        categoria = "General"

    hilo_id = str(uuid.uuid4())[:8]
    hilo = {
        "id": hilo_id,
        "usuario_id": usuario_id,
        "autor": _nombre_usuario(usuario_id),
        "titulo": titulo,
        "cuerpo": cuerpo,
        "categoria": categoria,
        "fecha": _ahora(),
        "fijado": False,
    }
    _append(FORO_HILOS, hilo)
    return {"ok": True, "hilo": _sin_campos_privados(hilo)}


def responder_hilo(usuario_id: str, hilo_id: str, cuerpo: str) -> dict:
    cuerpo = (cuerpo or "").strip()[:4000]
    if not usuario_id:
        return {"error": "Debes registrarte para responder."}
    if len(cuerpo) < 2:
        return {"error": "Escribe un mensaje."}

    hilos = _leer_jsonl(FORO_HILOS)
    if not any(h.get("id") == hilo_id for h in hilos):
        return {"error": "Hilo no encontrado."}

    resp_id = str(uuid.uuid4())[:8]
    resp = {
        "id": resp_id,
        "hilo_id": hilo_id,
        "usuario_id": usuario_id,
        "autor": _nombre_usuario(usuario_id),
        "cuerpo": cuerpo,
        "fecha": _ahora(),
    }
    _append(FORO_RESPUESTAS, resp)
    return {"ok": True, "respuesta": _sin_campos_privados(resp)}


def votar(usuario_id: str, target_id: str, tipo: str) -> dict:
    """tipo: 'up' o 'down'. target_id puede ser hilo o respuesta."""
    if not usuario_id:
        return {"error": "Debes registrarte para votar."}
    if tipo not in ("up", "down"):
        return {"error": "Voto no válido."}

    votos = _leer_jsonl(FORO_VOTOS)
    existente = next(
        (v for v in votos if v.get("usuario_id") == usuario_id and v.get("target_id") == target_id),
        None,
    )
    if existente:
        return {"error": "Ya has votado este contenido."}

    voto = {
        "id": str(uuid.uuid4())[:8],
        "usuario_id": usuario_id,
        "target_id": target_id,
        "tipo": tipo,
        "fecha": _ahora(),
    }
    _append(FORO_VOTOS, voto)
    return {"ok": True}


def _contar_votos(target_id: str, votos: list[dict]) -> int:
    total = 0
    for v in votos:
        if v.get("target_id") == target_id:
            total += 1 if v.get("tipo") == "up" else -1
    return total


def listar_hilos(categoria: str = "", limite: int = 50) -> list[dict]:
    hilos = _leer_jsonl(FORO_HILOS)
    respuestas = _leer_jsonl(FORO_RESPUESTAS)
    votos = _leer_jsonl(FORO_VOTOS)

    if categoria and categoria in CATEGORIAS_FORO:
        hilos = [h for h in hilos if h.get("categoria") == categoria]

    resultado = []
    for h in reversed(hilos[-500:]):
        n_resp = sum(1 for r in respuestas if r.get("hilo_id") == h.get("id"))
        puntos = _contar_votos(h.get("id", ""), votos)
        resultado.append({
            **_sin_campos_privados(h),
            "respuestas": n_resp,
            "puntos": puntos,
        })

    resultado.sort(key=lambda x: (x.get("fijado", False), x.get("puntos", 0)), reverse=True)
    return resultado[:limite]


def obtener_hilo(hilo_id: str) -> dict | None:
    hilos = _leer_jsonl(FORO_HILOS)
    respuestas = _leer_jsonl(FORO_RESPUESTAS)
    votos = _leer_jsonl(FORO_VOTOS)

    hilo = next((h for h in hilos if h.get("id") == hilo_id), None)
    if not hilo:
        return None

    resps = [_sin_campos_privados(r) for r in respuestas if r.get("hilo_id") == hilo_id]
    for r in resps:
        r["puntos"] = _contar_votos(r.get("id", ""), votos)

    return {
        **_sin_campos_privados(hilo),
        "puntos": _contar_votos(hilo_id, votos),
        "respuestas_lista": resps,
    }


# ─── Comentarios en leyes y artículos ───────────────────

EMOJIS_REACCION = ("👍", "👎", "❤️", "💡", "😮", "😡", "🤔")


def _agregar_reacciones(comentarios: list[dict], usuario_id: str | None) -> list[dict]:
    reacciones = _leer_jsonl(REACCIONES)
    resultado = []
    for c in comentarios:
        cid = c.get("id", "")
        counts: dict[str, int] = {}
        mi_reaccion = None
        for r in reacciones:
            if r.get("comentario_id") != cid:
                continue
            emoji = r.get("emoji", "")
            if emoji:
                counts[emoji] = counts.get(emoji, 0) + 1
            if usuario_id and r.get("usuario_id") == usuario_id:
                mi_reaccion = emoji
        resultado.append({**c, "reacciones": counts, "mi_reaccion": mi_reaccion})
    return resultado


def crear_comentario(
    usuario_id: str,
    ley_id: str,
    cuerpo: str,
    articulo_id: str = "",
    ley_titulo: str = "",
    articulo_titulo: str = "",
) -> dict:
    ley_id = _sanear_texto_usuario((ley_id or "").strip())
    articulo_id = _sanear_texto_usuario((articulo_id or "").strip())
    cuerpo = _sanear_texto_usuario((cuerpo or "").strip())[:2000]
    if not usuario_id:
        return {"error": "Debes registrarte para comentar."}
    if not ley_id:
        return {"error": "Norma no identificada."}
    if len(cuerpo) < 3:
        return {"error": "Escribe al menos 3 caracteres."}

    comentario = {
        "id": str(uuid.uuid4())[:8],
        "ley_id": ley_id,
        "articulo_id": articulo_id,
        "ley_titulo": (ley_titulo or "")[:200],
        "articulo_titulo": (articulo_titulo or "")[:200],
        "usuario_id": usuario_id,
        "autor": _nombre_usuario(usuario_id),
        "cuerpo": cuerpo,
        "fecha": _ahora(),
    }
    _append(COMENTARIOS, comentario)
    publico = {**_sin_campos_privados(comentario), "reacciones": {}, "mi_reaccion": None}
    return {"ok": True, "comentario": publico}


def _norm_articulo_id(valor: str) -> str:
    v = _sanear_texto_usuario((valor or "").strip()).lower().replace("_", "-")
    if v.startswith("art-"):
        return v
    m = re.search(r"art[\W_]*(\d+[\w-]*)", v, re.I)
    if m:
        return f"art-{m.group(1)}"
    if v.isdigit() or (v and v[0].isdigit()):
        return f"art-{v}"
    return v

def listar_comentarios(ley_id: str, articulo_id: str = "", usuario_id: str | None = None) -> list[dict]:
    ley_id = (ley_id or "").strip()
    articulo_id = (articulo_id or "").strip()
    if not ley_id:
        return []

    objetivo = _norm_articulo_id(articulo_id)

    def coincide(c: dict) -> bool:
        if c.get("ley_id") != ley_id:
            return False
        guardado = (c.get("articulo_id") or "").strip()
        if not articulo_id:
            return not guardado
        return guardado == articulo_id or _norm_articulo_id(guardado) == objetivo

    comentarios = [c for c in _leer_jsonl(COMENTARIOS) if coincide(c)]
    comentarios.sort(key=lambda c: c.get("fecha", ""))
    return _agregar_reacciones([_sin_campos_privados(c) for c in comentarios], usuario_id)


def reaccionar_comentario(usuario_id: str, comentario_id: str, emoji: str) -> dict:
    if not usuario_id:
        return {"error": "Debes registrarte para reaccionar."}
    if emoji not in EMOJIS_REACCION:
        return {"error": "Reacción no válida."}

    comentarios = _leer_jsonl(COMENTARIOS)
    if not any(c.get("id") == comentario_id for c in comentarios):
        return {"error": "Comentario no encontrado."}

    reacciones = _leer_jsonl(REACCIONES)
    existente = next(
        (
            r
            for r in reacciones
            if r.get("usuario_id") == usuario_id and r.get("comentario_id") == comentario_id
        ),
        None,
    )

    if existente:
        if existente.get("emoji") == emoji:
            reacciones = [r for r in reacciones if r.get("id") != existente.get("id")]
            _write_jsonl(REACCIONES, reacciones)
            return {"ok": True, "accion": "eliminada"}
        existente["emoji"] = emoji
        existente["fecha"] = _ahora()
        _write_jsonl(REACCIONES, reacciones)
        return {"ok": True, "accion": "cambiada"}

    _append(
        REACCIONES,
        {
            "id": str(uuid.uuid4())[:8],
            "comentario_id": comentario_id,
            "usuario_id": usuario_id,
            "emoji": emoji,
            "fecha": _ahora(),
        },
    )
    return {"ok": True, "accion": "añadida"}


# ─── Perfil y guardados ────────────────────────────────

def guardar_item(usuario_id: str, tipo: str, datos: dict) -> dict:
    """Guarda un elemento en el perfil del usuario.
    tipo: 'simulacion', 'comentario', 'valoracion', 'articulo'
    """
    if not usuario_id:
        return {"error": "Debes registrarte para guardar."}
    tipos_validos = ("simulacion", "comentario", "valoracion", "articulo")
    if tipo not in tipos_validos:
        return {"error": f"Tipo no válido. Usa: {', '.join(tipos_validos)}"}

    item_id = str(uuid.uuid4())[:8]
    registro = {
        "id": item_id,
        "usuario_id": usuario_id,
        "tipo": tipo,
        "datos": datos,
        "fecha": _ahora(),
    }
    _append(PERFIL_GUARDADOS, registro)
    return {"ok": True, "id": item_id}


def eliminar_guardado(usuario_id: str, item_id: str) -> dict:
    if not usuario_id:
        return {"error": "No autorizado."}
    items = _leer_jsonl(PERFIL_GUARDADOS)
    nuevos = [i for i in items if not (i.get("id") == item_id and i.get("usuario_id") == usuario_id)]
    if len(nuevos) == len(items):
        return {"error": "Elemento no encontrado."}
    DATOS.mkdir(parents=True, exist_ok=True)
    with _lock:
        PERFIL_GUARDADOS.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in nuevos) + ("\n" if nuevos else ""),
            encoding="utf-8",
        )
    return {"ok": True}


def actualizar_usuario(
    usuario_id: str,
    nombre: str = "",
    email: str = "",
    username: str = "",
    password_actual: str = "",
    password_nuevo: str = "",
) -> dict:
    if not usuario_id:
        return {"error": "No autorizado."}

    registros = _leer_jsonl(USUARIOS)
    usuario = next((u for u in registros if u.get("id") == usuario_id), None)
    if not usuario:
        return {"error": "Usuario no encontrado."}

    nombre = (nombre or usuario.get("nombre") or "").strip()[:80]
    email_in = (email or "").strip().lower()[:120]
    email_final = email_in or (usuario.get("email") or "").strip().lower()
    username = (username or "").strip().lower()[:40]
    password_actual = password_actual or ""
    password_nuevo = password_nuevo or ""

    if len(nombre) < 2:
        return {"error": "El nombre visible debe tener al menos 2 caracteres."}
    if not email_final or not EMAIL_RE.match(email_final):
        return {"error": "El correo es obligatorio y debe ser válido."}
    if username:
        if len(username) < 3:
            return {"error": "El usuario debe tener al menos 3 caracteres."}
        if not re.match(r"^[a-z0-9._-]+$", username):
            return {"error": "El usuario solo puede contener letras, números, puntos, guiones y guiones bajos."}

    if username and username != usuario.get("username"):
        usado = next((u for u in registros if u.get("username") == username and u.get("id") != usuario_id), None)
        if usado:
            return {"error": "Ese nombre de usuario no está disponible."}

    if email_final != (usuario.get("email") or ""):
        usado = next((u for u in registros if u.get("email") == email_final and u.get("id") != usuario_id), None)
        if usado:
            return {"error": "Ese correo no está disponible."}

    stored_hash = usuario.get("password_hash")
    cambio_credenciales = bool(username or password_nuevo)
    cambio_datos = nombre != (usuario.get("nombre") or "") or email_final != (usuario.get("email") or "")
    if stored_hash and (cambio_credenciales or cambio_datos):
        if not password_actual:
            return {"error": "Introduce tu contraseña actual para modificar el perfil."}
        if not _verify_password(password_actual, stored_hash):
            return {"error": "Contraseña actual incorrecta."}

    if cambio_credenciales:
        if password_nuevo:
            err_pass = _password_ok(password_nuevo)
            if err_pass:
                return {"error": err_pass}
            usuario["password_hash"] = _hash_password(password_nuevo)
            _bump_session_version(usuario)

        if username:
            usuario["username"] = username

    usuario["nombre"] = nombre
    usuario["email"] = email_final

    _write_jsonl(USUARIOS, registros)
    return {
        "ok": True,
        "session_version": int(usuario.get("session_version") or 0),
        "username": usuario.get("username", ""),
        "nombre": usuario.get("nombre", ""),
    }


def obtener_perfil(usuario_id: str) -> dict:
    if not usuario_id:
        return {"error": "No autorizado."}

    usuarios = _leer_jsonl(USUARIOS)
    usuario = next((u for u in usuarios if u.get("id") == usuario_id), None)
    if not usuario:
        return {"error": "Usuario no encontrado."}

    guardados = [g for g in _leer_jsonl(PERFIL_GUARDADOS) if g.get("usuario_id") == usuario_id]
    valoraciones = [v for v in _leer_jsonl(VALORACIONES) if v.get("usuario_id") == usuario_id]
    hilos = [h for h in _leer_jsonl(FORO_HILOS) if h.get("usuario_id") == usuario_id]
    respuestas = [r for r in _leer_jsonl(FORO_RESPUESTAS) if r.get("usuario_id") == usuario_id]
    visitas = [v for v in _leer_jsonl(VISITAS) if v.get("usuario_id") == usuario_id]

    return {
        "usuario": {
            "id": usuario.get("id"),
            "nombre": usuario.get("nombre"),
            "username": usuario.get("username", ""),
            "email": usuario.get("email", ""),
            "alta": usuario.get("alta"),
        },
        "guardados": list(reversed(guardados[-100:])),
        "valoraciones": list(reversed(valoraciones[-50:])),
        "hilos": list(reversed(hilos[-50:])),
        "respuestas": list(reversed(respuestas[-50:])),
        "total_visitas": len(visitas),
        "resumen": {
            "guardados": len(guardados),
            "valoraciones": len(valoraciones),
            "hilos": len(hilos),
            "respuestas": len(respuestas),
        },
    }
