"""Sprint S9 — Module d'alerting externe (Slack / SMTP / log).

Fournit une interface uniforme :class:`Notifier` consommée par les jobs de
supervision (parité backtest ↔ live, watchers, etc.).

Design :

- Aucun import réseau au top-level (lazy ``import requests`` / ``smtplib``).
- ``LogNotifier`` toujours disponible, sert de fallback.
- ``SlackNotifier`` : POST JSON sur webhook (env ``ALPHA_TRADE_SLACK_WEBHOOK``).
- ``EmailNotifier`` : SMTP stdlib (env ``ALPHA_TRADE_SMTP_*``).
- :func:`build_notifier_from_env` choisit l'implémentation selon l'env.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable, Literal, Optional, Protocol, runtime_checkable

LOGGER = logging.getLogger("service.alerting")

Severity = Literal["info", "warning", "critical"]

ENV_SLACK_WEBHOOK = "ALPHA_TRADE_SLACK_WEBHOOK"
ENV_SMTP_HOST = "ALPHA_TRADE_SMTP_HOST"
ENV_SMTP_PORT = "ALPHA_TRADE_SMTP_PORT"
ENV_SMTP_FROM = "ALPHA_TRADE_SMTP_FROM"
ENV_SMTP_TO = "ALPHA_TRADE_SMTP_TO"
ENV_SMTP_USER = "ALPHA_TRADE_SMTP_USER"
ENV_SMTP_PASSWORD = "ALPHA_TRADE_SMTP_PASSWORD"


@runtime_checkable
class Notifier(Protocol):
    """Contrat minimal d'un canal d'alerting."""

    def send(self, subject: str, body: str, *, severity: Severity = "warning") -> None:
        ...


# ---------------------------------------------------------------------------
# Implémentations
# ---------------------------------------------------------------------------


@dataclass
class LogNotifier:
    """Fallback : log dans le logger ``service.alerting``."""

    logger: logging.Logger = LOGGER

    def send(self, subject: str, body: str, *, severity: Severity = "warning") -> None:
        log_fn = {
            "info": self.logger.info,
            "warning": self.logger.warning,
            "critical": self.logger.error,
        }.get(severity, self.logger.warning)
        log_fn("[alerting] %s | %s", subject, body)


@dataclass
class SlackNotifier:
    """Envoie un message Slack via webhook incoming.

    En cas d'échec réseau, fallback automatique sur :class:`LogNotifier`
    (jamais bloquant pour le job appelant).
    """

    webhook_url: str
    timeout_seconds: float = 5.0
    fallback: Optional["Notifier"] = None

    def __post_init__(self) -> None:
        if self.fallback is None:
            self.fallback = LogNotifier()

    def send(self, subject: str, body: str, *, severity: Severity = "warning") -> None:
        emoji = {"info": ":information_source:", "warning": ":warning:", "critical": ":rotating_light:"}.get(
            severity, ":warning:"
        )
        text = f"{emoji} *{subject}*\n```\n{body}\n```"
        try:
            import requests  # type: ignore[import-untyped]

            resp = requests.post(
                self.webhook_url,
                json={"text": text},
                timeout=self.timeout_seconds,
            )
            if resp.status_code >= 300:
                raise RuntimeError(f"Slack HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:  # noqa: BLE001 — never raise to caller
            LOGGER.warning("[alerting] Slack send failed: %s -> fallback log", exc)
            assert self.fallback is not None  # for mypy
            self.fallback.send(subject, body, severity=severity)


@dataclass
class EmailNotifier:
    """Envoie un mail via SMTP (stdlib).

    En cas d'échec, fallback log (jamais bloquant).
    """

    host: str
    port: int
    from_addr: str
    to_addrs: tuple[str, ...]
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = True
    timeout_seconds: float = 10.0
    fallback: Optional["Notifier"] = None

    def __post_init__(self) -> None:
        if self.fallback is None:
            self.fallback = LogNotifier()

    def send(self, subject: str, body: str, *, severity: Severity = "warning") -> None:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = f"[{severity.upper()}] {subject}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.send_message(msg)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("[alerting] SMTP send failed: %s -> fallback log", exc)
            assert self.fallback is not None
            self.fallback.send(subject, body, severity=severity)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _split_recipients(value: str) -> tuple[str, ...]:
    return tuple(addr.strip() for addr in value.split(",") if addr.strip())


def build_notifiers_from_env(env: Optional[dict] = None) -> tuple[Notifier, ...]:
    """Construit tous les canaux disponibles depuis l'environnement.

    Contrairement à ``build_notifier_from_env`` (historique), cette fonction
    retourne potentiellement plusieurs notifiers (ex. Slack + SMTP).
    """
    source = env if env is not None else os.environ
    channels: list[Notifier] = []

    webhook = (source.get(ENV_SLACK_WEBHOOK) or "").strip()
    if webhook:
        channels.append(SlackNotifier(webhook_url=webhook))

    smtp_host = (source.get(ENV_SMTP_HOST) or "").strip()
    smtp_to_raw = (source.get(ENV_SMTP_TO) or "").strip()
    smtp_from = (source.get(ENV_SMTP_FROM) or "").strip()
    if smtp_host and smtp_to_raw and smtp_from:
        port_raw = (source.get(ENV_SMTP_PORT) or "587").strip()
        try:
            port = int(port_raw)
        except ValueError:
            port = 587
        channels.append(
            EmailNotifier(
                host=smtp_host,
                port=port,
                from_addr=smtp_from,
                to_addrs=_split_recipients(smtp_to_raw),
                username=(source.get(ENV_SMTP_USER) or None),
                password=(source.get(ENV_SMTP_PASSWORD) or None),
            )
        )

    if not channels:
        channels.append(LogNotifier())
    return tuple(channels)


def build_notifier_from_env(env: Optional[dict] = None) -> Notifier:
    """Construit le notifier le plus adapté à l'environnement courant.

    Ordre de priorité :
    1. ``ALPHA_TRADE_SLACK_WEBHOOK`` set non vide → :class:`SlackNotifier`.
    2. ``ALPHA_TRADE_SMTP_HOST`` + ``ALPHA_TRADE_SMTP_TO`` set → :class:`EmailNotifier`.
    3. Sinon → :class:`LogNotifier`.
    """
    return build_notifiers_from_env(env=env)[0]


def send_system_alert(
    event: str,
    payload: Optional[dict] = None,
    *,
    severity: Severity = "warning",
    env: Optional[dict] = None,
) -> None:
    """Diffuse une alerte système sur tous les canaux configurés.

    Jamais bloquant : chaque canal est best-effort.
    """
    subject = f"Alpha Trade | {event}"
    body = str(payload or {})
    for notifier in build_notifiers_from_env(env=env):
        try:
            notifier.send(subject=subject, body=body, severity=severity)
        except Exception:  # pragma: no cover - les notifiers gèrent déjà leurs erreurs
            LOGGER.debug("[alerting] notifier failure for event=%s", event, exc_info=True)


__all__ = [
    "ENV_SLACK_WEBHOOK",
    "ENV_SMTP_HOST",
    "ENV_SMTP_TO",
    "ENV_SMTP_FROM",
    "Notifier",
    "Severity",
    "LogNotifier",
    "SlackNotifier",
    "EmailNotifier",
    "build_notifiers_from_env",
    "build_notifier_from_env",
    "send_system_alert",
]

