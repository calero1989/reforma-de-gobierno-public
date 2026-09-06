"""Sesiones firmadas, control de acceso, CAPTCHA y limitación de peticiones."""

from __future__ import annotations

import os
import random
import secrets
import time
from collections import defaultdict
from datetime import timedelta
from functools import wraps
from typing import Callable

from flask import jsonify, request, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_buckets: dict[str, list[float]] = defaultdict(list)
_lockouts: dict[str, float] = {}
_version_checker: Callable[[str], int] | None = None

CAPTCHA_MAX_AGE = 600
LOGIN_FALLAS_MAX = 5
LOGIN_BLOQUEO_SEG = 900


def _modo_vps() -> bool:
    return os.environ.get("MODO_VPS", "").strip().lower() in {"1", "true", "yes", "si", "sí"}


def init_app(app) -> None:
    secret = os.environ.get("SECRET_KEY", "").strip()
    if not secret:
        if _modo_vps():
            raise SystemExit(
                "FATAL: SECRET_KEY no definido. Configúralo en /opt/reforma-gobierno/.env"
            )
        secret = secrets.token_hex(32)
        print("AVISO: SECRET_KEY temporal (solo desarrollo local).")
    app.config["SECRET_KEY"] = secret
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = _modo_vps()
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    app.config["SESSION_COOKIE_NAME"] = "rg_session"
    app.config["PROPAGATE_EXCEPTIONS"] = False

    try:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    except Exception:
        pass


def set_version_checker(fn: Callable[[str], int]) -> None:
    global _version_checker
    _version_checker = fn


def _serializer() -> URLSafeTimedSerializer:
    from flask import current_app

    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="rg-captcha")


def crear_captcha() -> dict:
    a = random.randint(2, 12)
    b = random.randint(1, 9)
    if random.choice((True, False)):
        pregunta = f"¿Cuánto es {a} + {b}?"
        respuesta = str(a + b)
    else:
        if a < b:
            a, b = b, a
        pregunta = f"¿Cuánto es {a} − {b}?"
        respuesta = str(a - b)
    token = _serializer().dumps({"r": respuesta})
    return {"token": token, "pregunta": pregunta}


def verificar_captcha(token: str | None, respuesta: str | None) -> bool:
    if not token or respuesta is None:
        return False
    try:
        data = _serializer().loads(token, max_age=CAPTCHA_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    esperada = str(data.get("r", "")).strip()
    dada = str(respuesta).strip()
    return bool(esperada) and secrets.compare_digest(esperada, dada)


def ip_cliente() -> str:
    return (request.remote_addr or "?").strip() or "?"


def _es_local(remote: str) -> bool:
    return remote in {"127.0.0.1", "::1"} or remote.startswith("127.")


def iniciar_sesion(usuario_id: str, session_version: int = 0) -> None:
    session.clear()
    session["usuario_id"] = usuario_id
    session["session_version"] = int(session_version or 0)
    session.permanent = True


def cerrar_sesion() -> None:
    session.clear()


def usuario_actual() -> str | None:
    uid = session.get("usuario_id")
    if not uid:
        return None
    if _version_checker is not None:
        try:
            actual = int(_version_checker(uid))
        except Exception:
            session.clear()
            return None
        if int(session.get("session_version") or 0) != actual:
            session.clear()
            return None
    return uid


def requiere_sesion(f: Callable):
    @wraps(f)
    def envuelto(*args, **kwargs):
        uid = usuario_actual()
        if not uid:
            return jsonify({"error": "Debes iniciar sesión."}), 401
        kwargs["usuario_id"] = uid
        return f(*args, **kwargs)

    return envuelto


def rate_limit(max_calls: int, window: float, por_usuario: bool = False):
    def decorador(f: Callable):
        @wraps(f)
        def envuelto(*args, **kwargs):
            ip = ip_cliente()
            clave = f"{f.__name__}:{ip}"
            if por_usuario:
                data = request.get_json(silent=True) or {}
                extra = (
                    str(data.get("username") or data.get("email") or "").strip().lower()
                )
                if extra:
                    clave = f"{clave}:{extra}"
            ahora = time.time()
            ventana = [t for t in _buckets[clave] if ahora - t < window]
            if len(ventana) >= max_calls:
                return jsonify({"error": "Demasiadas peticiones. Espera un momento."}), 429
            ventana.append(ahora)
            _buckets[clave] = ventana
            return f(*args, **kwargs)

        return envuelto

    return decorador


def clave_lockout(username: str) -> str:
    return f"{ip_cliente()}:{(username or '').strip().lower()}"


def esta_bloqueado(username: str) -> bool:
    hasta = _lockouts.get(clave_lockout(username), 0)
    return time.time() < hasta


def registrar_fallo_login(username: str) -> None:
    clave = clave_lockout(username)
    ahora = time.time()
    fallos = [t for t in _buckets[f"fail:{clave}"] if ahora - t < LOGIN_BLOQUEO_SEG]
    fallos.append(ahora)
    _buckets[f"fail:{clave}"] = fallos
    if len(fallos) >= LOGIN_FALLAS_MAX:
        _lockouts[clave] = ahora + LOGIN_BLOQUEO_SEG


def limpiar_fallos_login(username: str) -> None:
    clave = clave_lockout(username)
    _buckets.pop(f"fail:{clave}", None)
    _lockouts.pop(clave, None)


def cookie_flags(app) -> dict:
    return {
        "samesite": "Lax",
        "httponly": True,
        "secure": bool(app.config.get("SESSION_COOKIE_SECURE", False)),
        "path": "/",
    }


def cookie_visitante(app, response, vid: str):
    response.set_cookie(
        "rg_vid",
        vid,
        max_age=365 * 24 * 3600,
        **cookie_flags(app),
    )
    return response


def cookie_segura(app, response, uid: str):
    """Compatibilidad: marca identidad autenticada (no sustituye la sesión)."""
    response.set_cookie(
        "rg_uid",
        uid,
        max_age=30 * 24 * 3600,
        **cookie_flags(app),
    )
    return response


def expirar_cookies_auth(app, response):
    flags = cookie_flags(app)
    response.set_cookie("rg_uid", "", max_age=0, **flags)
    return response
