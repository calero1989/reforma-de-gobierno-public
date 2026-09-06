"""Envío de correo (Gmail / SMTP genérico; IONOS cuando haya dominio)."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

_log = logging.getLogger(__name__)


def smtp_configurado() -> bool:
    return bool(os.environ.get("SMTP_USER", "").strip() and os.environ.get("SMTP_PASSWORD", "").strip())


def enviar_correo(destino: str, asunto: str, cuerpo_texto: str) -> bool:
    """Envía correo. Si no hay SMTP, registra el cuerpo en el log y devuelve False."""
    destino = (destino or "").strip()
    if not destino:
        return False

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT", "587") or 587)
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    remitente = os.environ.get("SMTP_FROM", "").strip() or user

    if not user or not password:
        _log.warning(
            "SMTP no configurado. Correo a %s — %s\n%s",
            destino,
            asunto,
            cuerpo_texto,
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = destino
    msg.set_content(cuerpo_texto)

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)
        _log.info("Correo enviado a %s (%s)", destino, asunto)
        return True
    except Exception:
        _log.exception("Error enviando correo a %s", destino)
        return False


def enviar_recuperacion(destino: str, enlace: str, username: str) -> bool:
    cuerpo = (
        f"Hola{(' ' + username) if username else ''},\n\n"
        "Has solicitado restablecer la contraseña del Simulador de Reforma Legislativa.\n\n"
        f"Abre este enlace (válido 1 hora):\n{enlace}\n\n"
        "Si no has sido tú, ignora este mensaje.\n"
    )
    return enviar_correo(destino, "Restablecer contraseña — Simulador de Reforma Legislativa", cuerpo)
