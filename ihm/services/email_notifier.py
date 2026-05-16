"""ihm/services/email_notifier.py — Notificateur email léger pour alertes opérationnelles.

Sprint S3 / A-013 : envoi d'emails configurables via SMTP (TLS/SSL) sur événements
critiques (circuit_breaker, kill_switch, réconciliation bloquée, …).

Configuration via variables d'environnement (aucun secret en code) :

    ALPHA_TRADE_EMAIL_ENABLED=1          # désactivé par défaut
    ALPHA_TRADE_SMTP_HOST=smtp.gmail.com
    ALPHA_TRADE_SMTP_PORT=587
    ALPHA_TRADE_SMTP_USER=alerts@example.com
    ALPHA_TRADE_SMTP_PASSWORD=secret
    ALPHA_TRADE_EMAIL_FROM=alerts@example.com
    ALPHA_TRADE_EMAIL_TO=operator@example.com   # virgule = multi-destinataires
    ALPHA_TRADE_EMAIL_SUBJECT_PREFIX=[AlphaTrade]

Usage :
    from ihm.services.email_notifier import send_notification
    send_notification(event="circuit_breaker_fired", payload={"dd_pct": 0.12})
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (env vars)
# ---------------------------------------------------------------------------

_ENV_ENABLED = "ALPHA_TRADE_EMAIL_ENABLED"
_ENV_HOST = "ALPHA_TRADE_SMTP_HOST"
_ENV_PORT = "ALPHA_TRADE_SMTP_PORT"
_ENV_USER = "ALPHA_TRADE_SMTP_USER"
_ENV_PASSWORD = "ALPHA_TRADE_SMTP_PASSWORD"
_ENV_FROM = "ALPHA_TRADE_EMAIL_FROM"
_ENV_TO = "ALPHA_TRADE_EMAIL_TO"
_ENV_PREFIX = "ALPHA_TRADE_EMAIL_SUBJECT_PREFIX"

_DEFAULT_PORT = 587
_DEFAULT_PREFIX = "[AlphaTrade]"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_enabled() -> bool:
    return os.environ.get(_ENV_ENABLED, "0").strip() in ("1", "true", "yes", "on")


def _build_subject(event: str) -> str:
    prefix = os.environ.get(_ENV_PREFIX, _DEFAULT_PREFIX).strip()
    return f"{prefix} {event.replace('_', ' ').title()}"


def _build_body(event: str, payload: dict[str, Any], *, ts: str) -> str:
    lines = [
        f"Événement : {event}",
        f"Timestamp : {ts}",
        "",
        "Détails :",
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
    ]
    return "\n".join(lines)


def _send_smtp(subject: str, body: str) -> None:
    host = os.environ.get(_ENV_HOST, "").strip()
    port = int(os.environ.get(_ENV_PORT, str(_DEFAULT_PORT)).strip())
    user = os.environ.get(_ENV_USER, "").strip()
    password = os.environ.get(_ENV_PASSWORD, "").strip()
    sender = os.environ.get(_ENV_FROM, user).strip()
    recipients_raw = os.environ.get(_ENV_TO, "").strip()

    if not host or not recipients_raw:
        LOGGER.warning(
            "send_notification : SMTP_HOST ou EMAIL_TO absent — alerte non envoyée."
        )
        return

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(sender, recipients, msg.as_string())
        LOGGER.info("Notification email envoyée : %s → %s", subject, recipients)
    except Exception as exc:  # noqa: BLE001 — alerting best-effort
        LOGGER.error("Échec envoi notification email : %s", exc)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def send_notification(
    event: str,
    payload: dict[str, Any] | None = None,
    *,
    raise_on_disabled: bool = False,
) -> bool:
    """Envoie une notification email pour l'événement ``event``.

    Returns:
        ``True`` si l'email a été tenté, ``False`` si le notificateur est
        désactivé (``ALPHA_TRADE_EMAIL_ENABLED != 1``).

    Args:
        event: Identifiant de l'événement (ex ``"circuit_breaker_fired"``).
        payload: Données supplémentaires à inclure dans le corps du mail.
        raise_on_disabled: Si ``True``, lève ``RuntimeError`` quand l'envoi
            est désactivé (utile pour les tests d'intégration).
    """
    if not _is_enabled():
        LOGGER.debug("Email notifier désactivé (ALPHA_TRADE_EMAIL_ENABLED != 1).")
        if raise_on_disabled:
            raise RuntimeError("Email notifier désactivé — ALPHA_TRADE_EMAIL_ENABLED != 1")
        return False

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    subject = _build_subject(event)
    body = _build_body(event, payload or {}, ts=ts)
    _send_smtp(subject, body)
    return True


__all__ = ["send_notification"]

