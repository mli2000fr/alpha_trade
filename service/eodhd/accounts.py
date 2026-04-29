"""Registre du token API EODHD (mono-compte).

Charge le token depuis :
1. ``config.yaml`` -> ``eodhd.api_token`` (peut être un placeholder ``${VAR}``).
2. variable d environnement ``EODHD_API_TOKEN`` (par défaut, cf. plan §4.3).
3. variable d environnement personnalisée si ``eodhd.api_token_env`` est défini.

Calque simplifié de ``service/alpaca/accounts.py`` : EODHD est mono-compte
(pas de notion ``paper`` / ``live``, pas de credentials multiples).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"
DEFAULT_TOKEN_ENV = "EODHD_API_TOKEN"


class EodhdAuthError(RuntimeError):
    """Token EODHD manquant ou invalide."""


@dataclass(frozen=True, slots=True)
class EodhdAccount:
    """Identité du compte EODHD (mono-token)."""

    api_token: str
    exchange: str = "US"
    base_url: str = "https://eodhd.com/api"

    def __post_init__(self) -> None:
        if not self.api_token:
            raise EodhdAuthError("EODHD_API_TOKEN manquant.")


class EodhdAccountRegistry:
    """Singleton-like — résout le token une seule fois par process."""

    _instance: "EodhdAccountRegistry | None" = None
    _account: EodhdAccount | None

    def __init__(self) -> None:
        self._account = None
        self._load()

    @classmethod
    def get(cls) -> "EodhdAccountRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Réinitialise le singleton (utile pour les tests)."""
        cls._instance = None

    reset_for_tests = reset

    # ------------------------------------------------------------------
    def resolve(self) -> EodhdAccount:
        if self._account is None:
            raise EodhdAuthError(
                "Aucun token EODHD configuré. Définir EODHD_API_TOKEN ou "
                "config.yaml::eodhd.api_token."
            )
        return self._account

    def get_token(self) -> str:
        return self.resolve().api_token

    # ------------------------------------------------------------------
    def _load(self) -> None:
        cfg = self._read_yaml().get("eodhd", {}) or {}
        token_env = str(cfg.get("api_token_env", DEFAULT_TOKEN_ENV)).strip() or DEFAULT_TOKEN_ENV
        exchange = str(cfg.get("exchange", "US")).strip() or "US"
        base_url = str(cfg.get("base_url", "https://eodhd.com/api")).strip() or "https://eodhd.com/api"

        # 1) Champ explicite api_token (avec résolution ${VAR})
        api_token = str(cfg.get("api_token", "")).strip()
        if api_token.startswith("${") and api_token.endswith("}"):
            api_token = os.getenv(api_token[2:-1], "").strip()
        # 2) Fallback variable d environnement
        if not api_token:
            api_token = os.getenv(token_env, "").strip()

        if not api_token:
            LOGGER.warning(
                "Aucun token EODHD trouvé (config.yaml::eodhd.api_token / env=%s).",
                token_env,
            )
            return

        try:
            self._account = EodhdAccount(api_token=api_token, exchange=exchange, base_url=base_url)
        except EodhdAuthError as exc:
            LOGGER.warning("Compte EODHD invalide : %s", exc)

    def _read_yaml(self) -> dict[str, Any]:
        try:
            import yaml  # type: ignore
        except ImportError:
            return {}
        if not _CONFIG_PATH.exists():
            return {}
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        except Exception:
            return {}


def get_eodhd_token() -> str:
    """Raccourci public — équivalent à ``get_alpaca_credentials()``."""
    return EodhdAccountRegistry.get().get_token()


__all__ = [
    "DEFAULT_TOKEN_ENV",
    "EodhdAccount",
    "EodhdAccountRegistry",
    "EodhdAuthError",
    "get_eodhd_token",
]

