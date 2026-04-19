"""Registre multi-comptes Alpaca.

Charge les comptes broker depuis :
1. ``config.yaml`` → clé ``alpaca.accounts`` (liste)
2. Variables d'environnement préfixées : ``ALPACA_<ID>_API_KEY`` / ``ALPACA_<ID>_SECRET_KEY``
3. Fallback mono-compte classique : ``ALPACA_API_KEY`` / ``ALPACA_SECRET_KEY``

Chaque compte est identifié par un ``account_id`` unique (chaîne courte).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"

DEFAULT_ACCOUNT_ID = "default"


@dataclass(frozen=True, slots=True)
class BrokerAccount:
    """Identité d'un compte broker Alpaca."""

    account_id: str
    label: str
    api_key: str
    secret_key: str
    mode: str = "paper"  # paper | live

    def __post_init__(self) -> None:
        if not self.api_key or not self.secret_key:
            raise ValueError(f"Credentials manquantes pour le compte '{self.account_id}'")
        if self.mode not in ("paper", "live"):
            raise ValueError(f"mode invalide pour le compte '{self.account_id}': {self.mode}")


class AccountRegistry:
    """Singleton-like registry — charge les comptes une seule fois."""

    _instance: AccountRegistry | None = None
    _accounts: dict[str, BrokerAccount]

    def __init__(self) -> None:
        self._accounts = {}
        self._load()

    @classmethod
    def get(cls) -> AccountRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Réinitialise le singleton (utile pour les tests)."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_accounts(self) -> list[BrokerAccount]:
        return list(self._accounts.values())

    def list_account_ids(self) -> list[str]:
        return list(self._accounts.keys())

    def resolve(self, account_id: str | None = None) -> BrokerAccount:
        """Résout un compte par ID. Si None, retourne le premier (rétrocompat)."""
        if account_id is None:
            if not self._accounts:
                raise RuntimeError("Aucun compte Alpaca configuré.")
            return next(iter(self._accounts.values()))
        if account_id not in self._accounts:
            raise KeyError(
                f"Compte Alpaca '{account_id}' introuvable. "
                f"Comptes disponibles : {list(self._accounts.keys())}"
            )
        return self._accounts[account_id]

    def get_credentials(self, account_id: str | None = None) -> tuple[str, str]:
        """Raccourci → (api_key, secret_key)."""
        acct = self.resolve(account_id)
        return acct.api_key, acct.secret_key

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Charge dans l'ordre : config.yaml → env vars préfixées → fallback classique."""
        self._load_from_yaml()
        self._load_from_env_prefixed()
        self._load_fallback_env()

        if not self._accounts:
            LOGGER.warning("Aucun compte Alpaca trouvé (ni config.yaml, ni variables d'environnement).")
        else:
            LOGGER.info(
                "AccountRegistry chargé | %d compte(s) : %s",
                len(self._accounts),
                list(self._accounts.keys()),
            )

    def _load_from_yaml(self) -> None:
        """Charge depuis config.yaml → alpaca.accounts (liste de dicts)."""
        try:
            import yaml
        except ImportError:
            return

        if not _CONFIG_PATH.exists():
            return

        try:
            with open(_CONFIG_PATH, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
        except Exception:
            return

        alpaca_cfg = cfg.get("alpaca", {})
        accounts_list: list[dict[str, Any]] = alpaca_cfg.get("accounts", [])
        if not isinstance(accounts_list, list):
            return

        for entry in accounts_list:
            if not isinstance(entry, dict):
                continue
            aid = str(entry.get("id", entry.get("account_id", ""))).strip()
            if not aid:
                continue
            if aid in self._accounts:
                continue
            api_key = str(entry.get("api_key", "")).strip()
            secret_key = str(entry.get("secret_key", "")).strip()
            # Permettre la résolution depuis env vars si la valeur est un placeholder
            if api_key.startswith("${"):
                env_var = api_key.strip("${}")
                api_key = os.getenv(env_var, "")
            if secret_key.startswith("${"):
                env_var = secret_key.strip("${}")
                secret_key = os.getenv(env_var, "")
            if not api_key or not secret_key:
                continue
            try:
                self._accounts[aid] = BrokerAccount(
                    account_id=aid,
                    label=str(entry.get("label", aid)),
                    api_key=api_key,
                    secret_key=secret_key,
                    mode=str(entry.get("mode", "paper")),
                )
            except ValueError as exc:
                LOGGER.warning("Compte Alpaca invalide dans config.yaml : %s", exc)

    def _load_from_env_prefixed(self) -> None:
        """Détecte les paires ALPACA_<ID>_API_KEY / ALPACA_<ID>_SECRET_KEY."""
        seen_ids: set[str] = set()
        suffix = "_API_KEY"
        prefix = "ALPACA_"
        for key in os.environ:
            if key.startswith(prefix) and key.endswith(suffix) and key != "ALPACA_API_KEY":
                mid = key[len(prefix):-len(suffix)]
                if not mid:
                    continue
                account_id = mid.lower()
                if account_id in self._accounts or account_id in seen_ids:
                    continue
                seen_ids.add(account_id)
                api_key = os.getenv(key, "")
                secret_key = os.getenv(f"ALPACA_{mid}_SECRET_KEY", "")
                if not api_key or not secret_key:
                    continue
                mode = os.getenv(f"ALPACA_{mid}_MODE", "paper").lower()
                label = os.getenv(f"ALPACA_{mid}_LABEL", account_id)
                try:
                    self._accounts[account_id] = BrokerAccount(
                        account_id=account_id,
                        label=label,
                        api_key=api_key,
                        secret_key=secret_key,
                        mode=mode,
                    )
                except ValueError:
                    pass

    def _load_fallback_env(self) -> None:
        """Fallback : variables classiques ALPACA_API_KEY / ALPACA_SECRET_KEY → compte 'default'."""
        if DEFAULT_ACCOUNT_ID in self._accounts:
            return
        api_key = os.getenv("ALPACA_API_KEY", "")
        secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        if not api_key or not secret_key:
            return
        self._accounts[DEFAULT_ACCOUNT_ID] = BrokerAccount(
            account_id=DEFAULT_ACCOUNT_ID,
            label="Compte principal",
            api_key=api_key,
            secret_key=secret_key,
            mode="paper",
        )

