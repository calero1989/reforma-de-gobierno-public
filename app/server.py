"""Servidor de la aplicación Simulador de Reforma Legislativa."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, make_response, request, send_from_directory

from app.auth import (
    cerrar_sesion,
    cookie_segura,
    cookie_visitante,
    crear_captcha,
    esta_bloqueado,
    expirar_cookies_auth,
    iniciar_sesion,
    init_app,
    limpiar_fallos_login,
    rate_limit,
    registrar_fallo_login,
    requiere_sesion,
    set_version_checker,
    usuario_actual,
    verificar_captcha,
    _es_local,
)
from app.acceso import imprimir_accesos, iniciar_tunel, puerto, urls_acceso
from app.catalogo import areas, buscar, buscar_area, buscar_coleccion, categorias, colecciones, obtener
from app.comunidad import (
    CATEGORIAS_FORO,
    EMOJIS_REACCION,
    crear_comentario,
    crear_hilo,
    eliminar_guardado,
    estadisticas,
    guardar_item,
    guardar_valoracion,
    actualizar_usuario,
    cambiar_contrasena,
    listar_comentarios,
    listar_hilos,
    login_usuario,
    obtener_hilo,
    obtener_perfil,
    obtener_usuario_publico,
    reaccionar_comentario,
    registrar_usuario,
    registrar_visita,
    responder_hilo,
    restablecer_password,
    solicitar_reset_password,
    version_sesion,
    votar,
)
from app.correo import enviar_recuperacion, smtp_configurado
from app.datos_referencia import cargar_referencia
from app.descarga import construir_zip
from app.integridad import verificar_corpus
from app.parser import cargar_ley
from app.simulator import PerfilCiudadano, evaluar_impacto, impacto_a_dict, simular_reforma

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"

app = Flask(__name__, static_folder=str(STATIC), static_url_path="")
init_app(app)
set_version_checker(version_sesion)


def _exigir_captcha(data: dict):
    if not verificar_captcha(data.get("captcha_token"), data.get("captcha_respuesta")):
        return jsonify({"error": "Captcha incorrecto o caducado. Inténtalo de nuevo."}), 400
    return None


def _url_publica() -> str:
    base = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    if base:
        return base
    return (request.url_root or "").rstrip("/")


def _iniciar_y_responder(resultado: dict, codigo: int = 200):
    iniciar_sesion(resultado["id"], resultado.get("session_version", 0))
    resp = make_response(jsonify({**resultado, **estadisticas()}), codigo)
    cookie_segura(app, resp, resultado["id"])
    return resp


def _entero(valor: str | None, defecto: int, maximo: int) -> int:
    try:
        return min(int(valor or defecto), maximo)
    except (TypeError, ValueError):
        return defecto


def perfil_desde_request(data: dict | None = None) -> PerfilCiudadano:
    data = data or {}
    return PerfilCiudadano(
        situacion=str(data.get("situacion") or "empleado"),
        ingresos_anuales=int(data.get("ingresos_anuales") or 28000),
        tamano_hogar=int(data.get("tamano_hogar") or 2),
        region=str(data.get("region") or "España"),
    )


@app.get("/")
def index():
    respuesta = send_from_directory(STATIC, "index.html")
    respuesta.headers["Cache-Control"] = "no-cache"
    return respuesta


@app.after_request
def add_cache_headers(response):
    if request.path.endswith((".js", ".css")) and request.path != "/sw.js":
        response.headers["Cache-Control"] = "no-cache"
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if os.environ.get("MODO_VPS", "").strip().lower() in {"1", "true", "yes", "si", "sí"}:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    csp = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers.setdefault("Content-Security-Policy", csp)
    return response


@app.get("/limpiar")
def limpiar_cache():
    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Limpiando…</title></head>
<body style="font-family:system-ui;text-align:center;padding:2rem;background:#0f1419;color:#e7e9ea">
<h2>Limpiando caché…</h2><p id="msg">Espera un momento.</p>
<script>
(async()=>{
  const m=document.getElementById("msg");
  if("serviceWorker"in navigator){
    const regs=await navigator.serviceWorker.getRegistrations();
    for(const r of regs) await r.unregister();
    m.textContent="Service worker eliminado.";
  }
  const keys=await caches.keys();
  for(const k of keys) await caches.delete(k);
  m.textContent="Caché limpia. Redirigiendo…";
  setTimeout(()=>location.href="/",1500);
})();
</script></body></html>"""
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@app.get("/manifest.webmanifest")
def manifest():
    respuesta = send_from_directory(STATIC, "manifest.webmanifest", mimetype="application/manifest+json")
    respuesta.headers["Cache-Control"] = "no-cache"
    return respuesta


@app.get("/sw.js")
def service_worker():
    respuesta = send_from_directory(STATIC, "sw.js")
    respuesta.headers["Service-Worker-Allowed"] = "/"
    respuesta.headers["Cache-Control"] = "no-cache"
    return respuesta


@app.get("/api/acceso")
def api_acceso():
    host = os.environ.get("HOST", "0.0.0.0")
    datos = urls_acceso(host, puerto(), request.host)
    remoto = request.remote_addr or ""
    if os.environ.get("MODO_VPS", "").strip().lower() in {"1", "true", "yes", "si", "sí"} or not _es_local(remoto):
        return jsonify(
            {
                "puerto": datos["puerto"],
                "publico": datos["publico"],
                "tunel_activo": datos["tunel_activo"],
            }
        )
    return jsonify(datos)


@app.get("/api/referencia")
def api_referencia():
    return jsonify(cargar_referencia())


@app.get("/api/categorias")
def api_categorias():
    return jsonify(categorias())


@app.get("/api/colecciones")
def api_colecciones():
    return jsonify(colecciones())


@app.get("/api/areas")
def api_areas():
    return jsonify(areas())


@app.get("/api/area/<area_id>")
def api_area(area_id: str):
    q = request.args.get("q", "")
    limite = _entero(request.args.get("limit"), 200, 500)
    data = buscar_area(area_id, q, limite)
    if not data:
        return jsonify({"error": "Área no encontrada"}), 404
    return jsonify(data)


@app.get("/api/coleccion/<col_id>")
def api_coleccion(col_id: str):
    q = request.args.get("q", "")
    limite = _entero(request.args.get("limit"), 200, 500)
    items = buscar_coleccion(col_id, q, limite)
    return jsonify({"items": items, "total": len(buscar_coleccion(col_id, "", 10000))})


@app.get("/api/catalogo")
def api_catalogo():
    q = request.args.get("q", "")
    rango = request.args.get("rango", "")
    titulo = request.args.get("titulo", "")
    materia = request.args.get("materia", "")
    articulo = request.args.get("articulo", "")
    limite = _entero(request.args.get("limit"), 80, 200)
    items = buscar(q, rango, limite, titulo=titulo, materia=materia)
    total = len(buscar(q, rango, 10000, titulo=titulo, materia=materia))
    if articulo.strip():
        art_num = articulo.strip().lower()
        items_con_art = []
        for item in items:
            ley = cargar_ley(item.get("identificador", ""))
            if ley and any(a.numero.lower() == art_num for a in ley.articulos):
                items_con_art.append(item)
        items = items_con_art[:limite]
        total = len(items)
    return jsonify({"items": items, "total": total})


@app.get("/api/ley/<identificador>")
def api_ley(identificador: str):
    meta = obtener(identificador)
    ley = cargar_ley(identificador)
    if ley is None:
        return jsonify({"error": "Ley no encontrada"}), 404
    return jsonify(
        {
            "meta": meta,
            "id": ley.id,
            "titulo": ley.titulo,
            "articulos": [
                {
                    "id": a.id,
                    "titulo": a.titulo,
                    "numero": a.numero,
                    "seccion": a.seccion,
                    "extracto": a.texto[:220] + ("…" if len(a.texto) > 220 else ""),
                }
                for a in ley.articulos
            ],
        }
    )


@app.get("/api/ley/<identificador>/articulo/<articulo_id>")
def api_articulo(identificador: str, articulo_id: str):
    ley = cargar_ley(identificador)
    if ley is None:
        return jsonify({"error": "Ley no encontrada"}), 404
    articulo = next((a for a in ley.articulos if a.id == articulo_id), None)
    if articulo is None:
        return jsonify({"error": "Artículo no encontrado"}), 404
    perfil = perfil_desde_request(request.args)
    impacto = evaluar_impacto(articulo.texto, perfil)
    return jsonify(
        {
            "ley_id": identificador,
            "ley_titulo": ley.titulo,
            "articulo": {
                "id": articulo.id,
                "titulo": articulo.titulo,
                "numero": articulo.numero,
                "seccion": articulo.seccion,
                "texto": articulo.texto,
            },
            "impacto": impacto_a_dict(impacto),
        }
    )


@app.post("/api/simular")
def api_simular():
    data = request.get_json(force=True, silent=True) or {}
    identificador = data.get("ley_id", "")
    articulo_id = data.get("articulo_id", "")
    texto_propuesto = data.get("texto_propuesto", "")
    ley = cargar_ley(identificador)
    if ley is None:
        return jsonify({"error": "Ley no encontrada"}), 404
    articulo = next((a for a in ley.articulos if a.id == articulo_id), None)
    if articulo is None:
        return jsonify({"error": "Artículo no encontrado"}), 404
    perfil = perfil_desde_request(data.get("perfil"))
    resultado = simular_reforma(articulo.texto, texto_propuesto or articulo.texto, perfil)
    return jsonify(
        {
            "ley_id": identificador,
            "articulo_id": articulo_id,
            "articulo_titulo": articulo.titulo,
            **resultado,
        }
    )


@app.post("/api/visita")
@rate_limit(30, 60)
def api_visita():
    data = request.get_json(force=True, silent=True) or {}
    uid = usuario_actual() or request.cookies.get("rg_vid") or request.cookies.get("rg_uid")
    nuevo_visitante = False
    if not uid:
        uid = str(uuid.uuid4())
        nuevo_visitante = True
    registrar_visita(uid, data.get("dispositivo") or request.headers.get("User-Agent", "")[:80])
    resp = make_response(jsonify({"ok": True, "visitante_id": uid, **estadisticas()}))
    if nuevo_visitante and not usuario_actual():
        cookie_visitante(app, resp, uid)
    return resp


@app.get("/api/sesion")
def api_sesion():
    uid = usuario_actual()
    if not uid:
        return jsonify({"autenticado": False})
    pub = obtener_usuario_publico(uid)
    if not pub:
        cerrar_sesion()
        return jsonify({"autenticado": False})
    return jsonify(
        {
            "autenticado": True,
            "id": pub["id"],
            "nombre": pub["nombre"],
            "username": pub["username"],
            "email": pub.get("email", ""),
            **estadisticas(),
        }
    )


@app.get("/api/captcha")
@rate_limit(60, 60)
def api_captcha():
    return jsonify(crear_captcha())


@app.post("/api/registro")
@rate_limit(10, 300, por_usuario=True)
def api_registro():
    data = request.get_json(force=True, silent=True) or {}
    fallo = _exigir_captcha(data)
    if fallo:
        return fallo
    sesion_uid = usuario_actual()
    resultado = registrar_usuario(
        data.get("nombre", ""),
        data.get("email", ""),
        data.get("dispositivo") or request.headers.get("User-Agent", "")[:80],
        None,
        data.get("username", ""),
        data.get("password", ""),
        sesion_uid=sesion_uid,
    )
    if resultado.get("error"):
        return jsonify(resultado), 400
    return _iniciar_y_responder(resultado)


@app.post("/api/login")
@rate_limit(15, 300, por_usuario=True)
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    fallo = _exigir_captcha(data)
    if fallo:
        return fallo
    username = data.get("username", "")
    if esta_bloqueado(username):
        return jsonify({"error": "Demasiados intentos fallidos. Espera 15 minutos."}), 429
    resultado = login_usuario(username, data.get("password", ""))
    if resultado.get("error"):
        registrar_fallo_login(username)
        return jsonify(resultado), 400
    limpiar_fallos_login(username)
    return _iniciar_y_responder(resultado)


@app.post("/api/logout")
def api_logout():
    cerrar_sesion()
    resp = make_response(jsonify({"ok": True}))
    expirar_cookies_auth(app, resp)
    return resp


@app.post("/api/cambiar-contrasena")
@rate_limit(10, 300, por_usuario=True)
def api_cambiar_contrasena():
    data = request.get_json(force=True, silent=True) or {}
    fallo = _exigir_captcha(data)
    if fallo:
        return fallo
    resultado = cambiar_contrasena(
        data.get("username", ""),
        data.get("password_actual", ""),
        data.get("password_nuevo", ""),
    )
    if resultado.get("error"):
        return jsonify(resultado), 400
    return _iniciar_y_responder(resultado)


@app.post("/api/recuperar-password")
@rate_limit(5, 300, por_usuario=True)
def api_recuperar_password():
    data = request.get_json(force=True, silent=True) or {}
    fallo = _exigir_captcha(data)
    if fallo:
        return fallo
    resultado = solicitar_reset_password(data.get("email", ""))
    if resultado.get("error"):
        return jsonify(resultado), 400
    token = resultado.pop("token", None)
    email = resultado.pop("email", None)
    username = resultado.pop("username", "")
    if token and email:
        enlace = f"{_url_publica()}/?reset={token}"
        enviado = enviar_recuperacion(email, enlace, username)
        if not enviado:
            logging.getLogger(__name__).warning(
                "Reset password sin SMTP. Enlace para %s: %s", email, enlace
            )
            if not smtp_configurado():
                resultado["aviso"] = (
                    "Correo SMTP no configurado en el servidor; "
                    "revisa el log del VPS o configura SMTP_USER/SMTP_PASSWORD."
                )
    return jsonify(resultado)


@app.post("/api/restablecer-password")
@rate_limit(10, 300)
def api_restablecer_password():
    data = request.get_json(force=True, silent=True) or {}
    fallo = _exigir_captcha(data)
    if fallo:
        return fallo
    resultado = restablecer_password(data.get("token", ""), data.get("password_nuevo", ""))
    if resultado.get("error"):
        return jsonify(resultado), 400
    return _iniciar_y_responder(resultado)


@app.get("/api/comunidad")
def api_comunidad():
    return jsonify(estadisticas())


@app.post("/api/valoracion")
@requiere_sesion
@rate_limit(20, 300)
def api_valoracion(usuario_id: str):
    data = request.get_json(force=True, silent=True) or {}
    resultado = guardar_valoracion(
        usuario_id,
        data.get("puntuacion"),
        data.get("sugerencia", ""),
        data.get("nombre", ""),
    )
    if resultado.get("error"):
        return jsonify(resultado), 400
    return jsonify(resultado)


# ─── Foro ───

@app.get("/api/foro/categorias")
def api_foro_categorias():
    return jsonify(CATEGORIAS_FORO)


@app.get("/api/foro/hilos")
def api_foro_hilos():
    cat = request.args.get("categoria", "")
    return jsonify(listar_hilos(cat))


@app.get("/api/foro/hilo/<hilo_id>")
def api_foro_hilo(hilo_id: str):
    hilo = obtener_hilo(hilo_id)
    if not hilo:
        return jsonify({"error": "Hilo no encontrado"}), 404
    return jsonify(hilo)


@app.post("/api/foro/hilo")
@requiere_sesion
@rate_limit(20, 300)
def api_foro_crear(usuario_id: str):
    data = request.get_json(force=True, silent=True) or {}
    res = crear_hilo(
        usuario_id,
        data.get("titulo", ""),
        data.get("cuerpo", ""),
        data.get("categoria", "General"),
    )
    if res.get("error"):
        return jsonify(res), 400
    return jsonify(res)


@app.post("/api/foro/respuesta")
@requiere_sesion
@rate_limit(30, 300)
def api_foro_responder(usuario_id: str):
    data = request.get_json(force=True, silent=True) or {}
    res = responder_hilo(
        usuario_id,
        data.get("hilo_id", ""),
        data.get("cuerpo", ""),
    )
    if res.get("error"):
        return jsonify(res), 400
    return jsonify(res)


@app.post("/api/foro/votar")
@requiere_sesion
@rate_limit(60, 300)
def api_foro_votar(usuario_id: str):
    data = request.get_json(force=True, silent=True) or {}
    res = votar(
        usuario_id,
        data.get("target_id", ""),
        data.get("tipo", ""),
    )
    if res.get("error"):
        return jsonify(res), 400
    return jsonify(res)


# ─── Comentarios en leyes y artículos ───

@app.get("/api/comentarios")
def api_listar_comentarios():
    ley_id = request.args.get("ley_id", "")
    articulo_id = request.args.get("articulo_id", "")
    uid_req = usuario_actual()
    return jsonify(
        {
            "comentarios": listar_comentarios(ley_id, articulo_id, uid_req),
            "emojis": list(EMOJIS_REACCION),
        }
    )


@app.post("/api/comentarios")
@requiere_sesion
@rate_limit(30, 300)
def api_crear_comentario(usuario_id: str):
    data = request.get_json(force=True, silent=True) or {}
    res = crear_comentario(
        usuario_id,
        data.get("ley_id", ""),
        data.get("cuerpo", ""),
        data.get("articulo_id", ""),
        data.get("ley_titulo", ""),
        data.get("articulo_titulo", ""),
    )
    if res.get("error"):
        return jsonify(res), 400
    return jsonify(res)


@app.post("/api/comentarios/reaccion")
@requiere_sesion
@rate_limit(60, 300)
def api_reaccionar_comentario(usuario_id: str):
    data = request.get_json(force=True, silent=True) or {}
    res = reaccionar_comentario(
        usuario_id,
        data.get("comentario_id", ""),
        data.get("emoji", ""),
    )
    if res.get("error"):
        return jsonify(res), 400
    return jsonify(res)


# ─── Perfil y guardados ───

@app.get("/api/perfil")
@requiere_sesion
def api_perfil(usuario_id: str):
    res = obtener_perfil(usuario_id)
    if res.get("error"):
        return jsonify(res), 400
    return jsonify(res)


@app.post("/api/guardar")
@requiere_sesion
@rate_limit(40, 300)
def api_guardar(usuario_id: str):
    data = request.get_json(force=True, silent=True) or {}
    res = guardar_item(
        usuario_id,
        data.get("tipo", ""),
        data.get("datos", {}),
    )
    if res.get("error"):
        return jsonify(res), 400
    return jsonify(res)


@app.post("/api/guardar/eliminar")
@requiere_sesion
def api_eliminar_guardado(usuario_id: str):
    data = request.get_json(force=True, silent=True) or {}
    res = eliminar_guardado(usuario_id, data.get("id", ""))
    if res.get("error"):
        return jsonify(res), 400
    return jsonify(res)


@app.post("/api/perfil/actualizar")
@requiere_sesion
@rate_limit(15, 300)
def api_perfil_actualizar(usuario_id: str):
    data = request.get_json(force=True, silent=True) or {}
    res = actualizar_usuario(
        usuario_id,
        nombre=data.get("nombre", ""),
        email=data.get("email", ""),
        username=data.get("username", ""),
        password_actual=data.get("password_actual", ""),
        password_nuevo=data.get("password_nuevo", ""),
    )
    if res.get("error"):
        return jsonify(res), 400
    if "session_version" in res:
        iniciar_sesion(usuario_id, res.get("session_version", 0))
    return jsonify(res)


@app.get("/descargar/Simulador-de-Reforma-Legislativa.zip")
@app.get("/descargar/Reforma-de-gobierno.zip")
@rate_limit(5, 3600)
def descargar_app():
    bruto = construir_zip()
    resp = make_response(bruto)
    resp.headers["Content-Type"] = "application/zip"
    resp.headers["Content-Disposition"] = "attachment; filename=Simulador-de-Reforma-Legislativa.zip"
    return resp


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = puerto()
    informe = verificar_corpus()
    if informe.get("ok"):
        print(
            f"Corpus legal: {informe['catalogo']} normas indexadas, "
            f"Constitución con {informe['constitucion_articulos']} artículos."
        )
    else:
        print(f"AVISO integridad corpus: faltan {informe.get('faltantes', '?')} archivos de ley.")
    print(f"Simulador de Reforma Legislativa — http://127.0.0.1:{port}")
    imprimir_accesos(host, port)
    if os.environ.get("PUBLICO", "").strip().lower() in {"1", "true", "si", "sí", "yes"}:
        threading.Thread(target=lambda: (time.sleep(1.2), iniciar_tunel(port)), daemon=True).start()
    try:
        from waitress import serve

        serve(app, host=host, port=port, threads=8, ident="simulador-reforma-legislativa")
    except ImportError:
        app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
