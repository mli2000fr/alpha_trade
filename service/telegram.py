"""Service Telegram — envoi de notifications via Telegram Bot API.

Service autonome dédié aux notifications Telegram. Le token du bot est lu
depuis la variable d'environnement ``TOKEN_TELEGRAM_BOT`` (déclarée dans
``conf/var_env.json``). Le chat/canal destinataire peut être fourni
explicitement à l'appel (``chat_id=...``) ou lu depuis la variable
d'environnement ``TELEGRAM_CHAT_ID``.

Usage rapide ::

    from service.telegram import send_telegram_message

    ok = send_telegram_message("Backtest terminé avec succès")

Avec un chat/canal explicite (ex. un groupe) ::

    ok = send_telegram_message("🚨 Alerte drawdown", chat_id="-1001234567890")

Design :
- import réseau lazy (``requests`` importé seulement à l'envoi) ;
- best-effort : par défaut, une erreur réseau/HTTP est loggée et renvoie
  ``False`` (jamais d'exception) ; ``raise_on_error=True`` pour propager ;
- config invalide (token ou chat_id manquant) lève :class:`TelegramConfigError` ;
- limite Telegram de 4096 caractères par message respectée (troncature propre).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

LOGGER = logging.getLogger("service.telegram")

# Variable d'environnement contenant le token du bot (requis).
TOKEN_ENV = "TOKEN_TELEGRAM_BOT"
# Variable d'environnement optionnelle : chat/canal cible par défaut.
CHAT_ID_ENV = "TELEGRAM_CHAT_ID"

API_BASE_URL = "https://api.telegram.org"
# Limite officielle d'un message Telegram (caractères).
MAX_TEXT_LENGTH = 4096


class TelegramConfigError(RuntimeError):
    """Configuration Telegram invalide (token ou chat_id manquant)."""


# ---------------------------------------------------------------------------
# Helpers de configuration (lecture de l'environnement)
# ---------------------------------------------------------------------------


def get_bot_token() -> str:
    """Retourne le token du bot depuis l'env ``TOKEN_TELEGRAM_BOT``.

    Lève :class:`TelegramConfigError` si absent/vide.
    """
    token = (os.environ.get(TOKEN_ENV) or "").strip()
    if not token:
        raise TelegramConfigError(
            f"Token Telegram non configuré : variable d'environnement {TOKEN_ENV!r} absente."
        )
    return token


def get_default_chat_id() -> Optional[str]:
    """Retourne le chat_id par défaut depuis l'env ``TELEGRAM_CHAT_ID`` (si défini)."""
    chat_id = (os.environ.get(CHAT_ID_ENV) or "").strip()
    return chat_id or None


def is_telegram_configured() -> bool:
    """True si le token ``TOKEN_TELEGRAM_BOT`` est présent dans l'environnement."""
    return bool((os.environ.get(TOKEN_ENV) or "").strip())


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


@dataclass
class TelegramClient:
    """Client Telegram minimal (Bot API ``sendMessage``).

    Paramètres :
    - ``bot_token`` : token du bot. ``None`` (défaut) → lu depuis l'env
      ``TOKEN_TELEGRAM_BOT`` au premier envoi.
    - ``default_chat_id`` : chat/canal cible par défaut. ``None`` (défaut) →
      lu depuis l'env ``TELEGRAM_CHAT_ID``.
    - ``timeout_seconds`` : timeout HTTP (défaut 5 s).

    Le token et le chat_id ne sont résolus qu'au moment de l'envoi (résolution
    paresseuse), ce qui permet de construire un client sans variables d'env
    définies (pratique pour les tests).
    """

    bot_token: Optional[str] = None
    default_chat_id: Optional[str] = None
    timeout_seconds: float = 5.0

    def _resolve_token(self) -> str:
        if self.bot_token:
            return self.bot_token
        return get_bot_token()

    def _resolve_chat_id(self, chat_id: Optional[str]) -> str:
        resolved = chat_id or self.default_chat_id or get_default_chat_id()
        if not resolved:
            raise TelegramConfigError(
                "Aucun chat_id : passez chat_id=... ou définissez la variable "
                f"d'environnement {CHAT_ID_ENV!r}."
            )
        return resolved

    def send(
        self,
        text: str,
        *,
        chat_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> bool:
        """Envoie ``text`` au chat cible.

        Retourne ``True`` si le message est accepté par l'API (HTTP 2xx),
        ``False`` en cas d'erreur réseau/HTTP (message loggé).
        Lève une :class:`TelegramConfigError` si la config est invalide, ou
        l'exception d'envoi si ``raise_on_error=True``.
        """
        token = self._resolve_token()
        target = self._resolve_chat_id(chat_id)

        if len(text) > MAX_TEXT_LENGTH:
            text = text[: MAX_TEXT_LENGTH - 20] + "\n[… tronqué]"

        payload: dict = {"chat_id": target, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            import requests  # type: ignore[import-untyped]  # import réseau lazy

            url = f"{API_BASE_URL}/bot{token}/sendMessage"
            resp = requests.post(url, json=payload, timeout=self.timeout_seconds)
            if resp.status_code >= 300:
                raise RuntimeError(f"Telegram HTTP {resp.status_code}: {resp.text[:200]}")
            return True
        except Exception as exc:  # noqa: BLE001 — best-effort
            LOGGER.warning("[telegram] Échec envoi Telegram : %s", exc)
            if raise_on_error:
                raise
            return False


# ---------------------------------------------------------------------------
# Fonction one-shot
# ---------------------------------------------------------------------------


def send_telegram_message(
    text: str,
    *,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = None,
    bot_token: Optional[str] = None,
    timeout_seconds: float = 5.0,
    raise_on_error: bool = False,
) -> bool:
    """Envoi one-shot d'une notification Telegram.

    Le token est lu depuis ``TOKEN_TELEGRAM_BOT`` (ou ``bot_token``) ; le chat
    cible depuis ``chat_id`` sinon l'env ``TELEGRAM_CHAT_ID``.

    Exemple ::

        from service.telegram import send_telegram_message

        send_telegram_message("Backtest terminé ✅")
    """
    client = TelegramClient(
        bot_token=bot_token,
        default_chat_id=chat_id,
        timeout_seconds=timeout_seconds,
    )
    return client.send(
        text,
        chat_id=chat_id,
        parse_mode=parse_mode,
        raise_on_error=raise_on_error,
    )


__all__ = [
    "API_BASE_URL",
    "CHAT_ID_ENV",
    "MAX_TEXT_LENGTH",
    "TOKEN_ENV",
    "TelegramClient",
    "TelegramConfigError",
    "get_bot_token",
    "get_default_chat_id",
    "is_telegram_configured",
    "send_telegram_message",
]
