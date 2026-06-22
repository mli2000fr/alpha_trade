"""Sprint S9 — Module d'alerting externe (Slack / SMTP / log / Telegram / SMS / Discord).

Fournit une interface uniforme :class:`Notifier` consommée par les jobs de
supervision (parité backtest ↔ live, watchers, etc.).

Design :

- Aucun import réseau au top-level (lazy ``import requests`` / ``smtplib``).
- ``LogNotifier`` toujours disponible, sert de fallback.
- ``SlackNotifier`` : POST JSON sur webhook (env ``ALPHA_TRADE_SLACK_WEBHOOK``).
- ``EmailNotifier`` : SMTP stdlib (env ``ALPHA_TRADE_SMTP_*``).
- ``TelegramNotifier`` : Bot Telegram API (env ``ALPHA_TRADE_TELEGRAM_BOT_TOKEN``,
  ``ALPHA_TRADE_TELEGRAM_CHAT_ID``).
- ``SMSNotifier`` : SMS via Twilio (env ``TWILIO_ACCOUNT_SID``,
  ``TWILIO_AUTH_TOKEN``, ``TWILIO_PHONE_NUMBER``, ``NUM_SMS_ALERT``).
- ``DiscordNotifier`` : Discord webhook (env ``ALPHA_TRADE_DISCORD_WEBHOOK``).
- :func:`build_notifiers_from_env` choisit les implémentations selon l'env.
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
ENV_TELEGRAM_BOT_TOKEN = "ALPHA_TRADE_TELEGRAM_BOT_TOKEN"
ENV_TELEGRAM_CHAT_ID = "ALPHA_TRADE_TELEGRAM_CHAT_ID"
ENV_DISCORD_WEBHOOK = "ALPHA_TRADE_DISCORD_WEBHOOK"
ENV_TWILIO_ACCOUNT_SID = "TWILIO_ACCOUNT_SID"
ENV_TWILIO_AUTH_TOKEN = "TWILIO_AUTH_TOKEN"
ENV_TWILIO_PHONE_NUMBER = "TWILIO_PHONE_NUMBER"
ENV_NUM_SMS_ALERT = "NUM_SMS_ALERT"


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


@dataclass
class TelegramNotifier:
    """Envoie un message via Telegram Bot API.

    Configuration via variables d'environnement :
    - ``ALPHA_TRADE_TELEGRAM_BOT_TOKEN`` : token du bot Telegram
    - ``ALPHA_TRADE_TELEGRAM_CHAT_ID`` : ID du chat/canal cible

    En cas d'échec réseau, fallback automatique sur :class:`LogNotifier`
    (jamais bloquant pour le job appelant).
    """

    bot_token: str
    chat_id: str
    timeout_seconds: float = 5.0
    fallback: Optional["Notifier"] = None

    def __post_init__(self) -> None:
        if self.fallback is None:
            self.fallback = LogNotifier()

    def send(self, subject: str, body: str, *, severity: Severity = "warning") -> None:
        emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(severity, "⚠️")
        text = f"{emoji} *{subject}*\n```\n{body}\n```"
        try:
            import requests  # type: ignore[import-untyped]

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = requests.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=self.timeout_seconds,
            )
            if resp.status_code >= 300:
                raise RuntimeError(f"Telegram HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:  # noqa: BLE001 — never raise to caller
            LOGGER.warning("[alerting] Telegram send failed: %s -> fallback log", exc)
            assert self.fallback is not None  # for mypy
            self.fallback.send(subject, body, severity=severity)


@dataclass
class DiscordNotifier:
    """Envoie un message via Discord webhook.

    Configuration via variable d'environnement :
    - ``ALPHA_TRADE_DISCORD_WEBHOOK`` : URL du webhook Discord

    En cas d'échec réseau, fallback automatique sur :class:`LogNotifier`.
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
        # Discord limite les messages à 2000 caractères ; on tronque le body si nécessaire.
        max_body_len = 1800
        truncated_body = body if len(body) <= max_body_len else body[:max_body_len] + "\n[...truncated]"
        text = f"{emoji} **{subject}**\n```\n{truncated_body}\n```"
        try:
            import requests  # type: ignore[import-untyped]

            resp = requests.post(
                self.webhook_url,
                json={"content": text},
                timeout=self.timeout_seconds,
            )
            if resp.status_code >= 300:
                raise RuntimeError(f"Discord HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:  # noqa: BLE001 — never raise to caller
            LOGGER.warning("[alerting] Discord send failed: %s -> fallback log", exc)
            assert self.fallback is not None  # for mypy
            self.fallback.send(subject, body, severity=severity)


@dataclass
class SMSNotifier:
    """Envoie un SMS via l'API Twilio.

    Configuration via variables d'environnement :
    - ``TWILIO_ACCOUNT_SID`` : Account SID Twilio
    - ``TWILIO_AUTH_TOKEN`` : Auth Token Twilio
    - ``TWILIO_PHONE_NUMBER`` : Numéro de téléphone Twilio (expéditeur)
    - ``NUM_SMS_ALERT`` : Numéro de téléphone destinataire des alertes

    En cas d'échec, fallback automatique sur :class:`LogNotifier`
    (jamais bloquant pour le job appelant).
    """

    account_sid: str
    auth_token: str
    from_number: str
    to_number: str
    timeout_seconds: float = 10.0
    fallback: Optional["Notifier"] = None

    def __post_init__(self) -> None:
        if self.fallback is None:
            self.fallback = LogNotifier()

    def send(self, subject: str, body: str, *, severity: Severity = "warning") -> None:
        emoji = {"info": "[INFO]", "warning": "[WARN]", "critical": "[CRITICAL]"}.get(severity, "[WARN]")
        # SMS limité à ~160 caractères ; on condense.
        sms_body = f"{emoji} {subject}: {body}"
        if len(sms_body) > 320:
            sms_body = sms_body[:315] + "..."
        try:
            import requests  # type: ignore[import-untyped]

            from requests.auth import HTTPBasicAuth

            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            resp = requests.post(
                url,
                data={
                    "From": self.from_number,
                    "To": self.to_number,
                    "Body": sms_body,
                },
                auth=HTTPBasicAuth(self.account_sid, self.auth_token),
                timeout=self.timeout_seconds,
            )
            if resp.status_code >= 300:
                raise RuntimeError(f"Twilio HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:  # noqa: BLE001 — never raise to caller
            LOGGER.warning("[alerting] SMS send failed: %s -> fallback log", exc)
            assert self.fallback is not None  # for mypy
            self.fallback.send(subject, body, severity=severity)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _split_recipients(value: str) -> tuple[str, ...]:
    return tuple(addr.strip() for addr in value.split(",") if addr.strip())


def build_notifiers_from_env(env: Optional[dict] = None) -> tuple[Notifier, ...]:
    """Construit tous les canaux disponibles depuis l'environnement.

    Retourne potentiellement plusieurs notifiers (ex. Slack + Telegram + Discord + SMS + SMTP).
    Chaque canal est indépendant et best-effort.
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

    # Telegram Bot
    tg_bot_token = (source.get(ENV_TELEGRAM_BOT_TOKEN) or "").strip()
    tg_chat_id = (source.get(ENV_TELEGRAM_CHAT_ID) or "").strip()
    if tg_bot_token and tg_chat_id:
        channels.append(TelegramNotifier(bot_token=tg_bot_token, chat_id=tg_chat_id))

    # Discord webhook
    discord_webhook = (source.get(ENV_DISCORD_WEBHOOK) or "").strip()
    if discord_webhook:
        channels.append(DiscordNotifier(webhook_url=discord_webhook))

    # SMS via Twilio
    twilio_sid = (source.get(ENV_TWILIO_ACCOUNT_SID) or "").strip()
    twilio_token = (source.get(ENV_TWILIO_AUTH_TOKEN) or "").strip()
    twilio_from = (source.get(ENV_TWILIO_PHONE_NUMBER) or "").strip()
    sms_to = (source.get(ENV_NUM_SMS_ALERT) or "").strip()
    if twilio_sid and twilio_token and twilio_from and sms_to:
        channels.append(
            SMSNotifier(
                account_sid=twilio_sid,
                auth_token=twilio_token,
                from_number=twilio_from,
                to_number=sms_to,
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
    cooldown_seconds: float = 300.0,
) -> None:
    """Diffuse une alerte système sur tous les canaux configurés.

    Jamais bloquant : chaque canal est best-effort.

    Anti-doublon : une même signature d'alerte (event + payload) n'est pas
    renvoyée avant l'expiration du cooldown (défaut 5 minutes). Le cache
    de signatures est stocké dans ``_ALERT_SIGNATURE_CACHE`` (module-level).
    """
    import hashlib
    import time

    payload_str = str(payload or {})
    signature = hashlib.sha256(f"{event}:{payload_str}".encode()).hexdigest()

    now = time.monotonic()
    last_sent = _ALERT_SIGNATURE_CACHE.get(signature)
    if last_sent is not None and (now - last_sent) < cooldown_seconds:
        LOGGER.debug("[alerting] dedup — alerte %s ignorée (cooldown=%.0fs)", event, now - last_sent)
        return
    _ALERT_SIGNATURE_CACHE[signature] = now

    # Nettoyage périodique du cache (limite à 1000 entrées)
    if len(_ALERT_SIGNATURE_CACHE) > 1000:
        cutoff = now - max(cooldown_seconds * 2, 3600.0)
        expired = [sig for sig, ts in _ALERT_SIGNATURE_CACHE.items() if ts < cutoff]
        for sig in expired:
            del _ALERT_SIGNATURE_CACHE[sig]

    subject = f"Alpha Trade | {event}"
    body = payload_str
    for notifier in build_notifiers_from_env(env=env):
        try:
            notifier.send(subject=subject, body=body, severity=severity)
        except Exception:  # pragma: no cover - les notifiers gèrent déjà leurs erreurs
            LOGGER.debug("[alerting] notifier failure for event=%s", event, exc_info=True)

    # Métriques Prometheus : incrémente le compteur d'alertes
    try:
        from service.prometheus_metrics import bump_alert
        bump_alert(severity)
    except Exception:
        pass


# Cache global anti-doublon : signature -> timestamp monotonic
_ALERT_SIGNATURE_CACHE: dict[str, float] = {}


__all__ = [
    "ENV_SLACK_WEBHOOK",
    "ENV_SMTP_HOST",
    "ENV_SMTP_TO",
    "ENV_SMTP_FROM",
    "ENV_TELEGRAM_BOT_TOKEN",
    "ENV_TELEGRAM_CHAT_ID",
    "ENV_DISCORD_WEBHOOK",
    "ENV_TWILIO_ACCOUNT_SID",
    "ENV_TWILIO_AUTH_TOKEN",
    "ENV_TWILIO_PHONE_NUMBER",
    "ENV_NUM_SMS_ALERT",
    "Notifier",
    "Severity",
    "LogNotifier",
    "SlackNotifier",
    "EmailNotifier",
    "TelegramNotifier",
    "DiscordNotifier",
    "SMSNotifier",
    "build_notifiers_from_env",
    "build_notifier_from_env",
    "send_system_alert",
]

