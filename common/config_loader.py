"""Chargement de configuration YAML avec overrides Vault (Sprint S21.2).

Comportement :

- ``load_config(path)`` charge le YAML comme avant (rétrocompat 100 %).
- Si ``ALPHA_TRADE_VAULT_ADDR`` est défini dans l'environnement, toute
  valeur ``"${vault:KEY}"`` (string) est résolue via
  :func:`common.config_vault.build_vault_from_env`.
- Si le vault retourne ``None``, le placeholder est conservé et un
  warning est loggué.
"""
from __future__ import annotations

from contextlib import contextmanager
import logging
import os
import re
from pathlib import Path
from typing import Any, Iterator, Optional

import yaml

LOGGER = logging.getLogger(__name__)

_VAULT_PLACEHOLDER = re.compile(r"^\$\{vault:([A-Za-z0-9_./-]+)\}$")
CONFIG_PATH_ENV = "ALPHA_TRADE_CONFIG_PATH"
BATCH_CONFIG_PATH_ENV = "ALPHA_TRADE_BATCH_CONFIG_PATH"
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
_DEFAULT_BATCH_CONFIG_PATH = Path(__file__).resolve().parent.parent / "batch.yaml"
MARKETS_CONFIG_DIR_ENV = "ALPHA_TRADE_MARKETS_CONFIG_DIR"
_DEFAULT_MARKETS_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "markets"


def resolve_config_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Résout le chemin YAML effectif en tenant compte d'un override global.

    Si ``ALPHA_TRADE_CONFIG_PATH`` est défini, il remplace le chemin par défaut
    et tout appel qui pointe explicitement vers le ``config.yaml`` racine du
    dépôt. Un chemin alternatif explicite non standard reste prioritaire.
    """
    requested_path = Path(path) if path is not None else None
    env_path = os.getenv(CONFIG_PATH_ENV)
    if env_path:
        env_config_path = Path(env_path)
        if requested_path is None:
            return env_config_path
        try:
            if requested_path.resolve() == _DEFAULT_CONFIG_PATH.resolve():
                return env_config_path
        except OSError:
            if str(requested_path) == str(_DEFAULT_CONFIG_PATH):
                return env_config_path
    return requested_path if requested_path is not None else _DEFAULT_CONFIG_PATH


def resolve_batch_config_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Résout le chemin de ``batch.yaml`` et son override de déploiement."""
    requested_path = Path(path) if path is not None else None
    env_path = os.getenv(BATCH_CONFIG_PATH_ENV)
    if env_path:
        env_config_path = Path(env_path)
        if requested_path is None:
            return env_config_path
        try:
            if requested_path.resolve() == _DEFAULT_BATCH_CONFIG_PATH.resolve():
                return env_config_path
        except OSError:
            if str(requested_path) == str(_DEFAULT_BATCH_CONFIG_PATH):
                return env_config_path
    return requested_path if requested_path is not None else _DEFAULT_BATCH_CONFIG_PATH


@contextmanager
def override_config_path(path: str | os.PathLike[str] | None) -> Iterator[None]:
    """Applique temporairement un override global de chemin de config YAML."""
    if path is None:
        yield
        return
    previous = os.environ.get(CONFIG_PATH_ENV)
    os.environ[CONFIG_PATH_ENV] = str(Path(path))
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(CONFIG_PATH_ENV, None)
        else:
            os.environ[CONFIG_PATH_ENV] = previous


def resolve_markets_config_dir(
    path: str | os.PathLike[str] | None = None,
) -> Path:
    """Résout le répertoire contenant les contextes de marché."""
    if path is not None:
        return Path(path)
    env_path = os.getenv(MARKETS_CONFIG_DIR_ENV)
    return Path(env_path) if env_path else _DEFAULT_MARKETS_CONFIG_DIR


def load_market_registry(
    path: str | os.PathLike[str] | None = None,
):
    """Charge un registre immuable depuis config/markets par défaut."""
    from common.market_context import MarketRegistry

    return MarketRegistry.from_directory(resolve_markets_config_dir(path))


def resolve_market_context(
    market_code: str | None = None,
    *,
    path: str | os.PathLike[str] | None = None,
    require_enabled: bool = False,
):
    """Résout un contexte ; l'absence de code conserve le fallback US legacy."""
    return load_market_registry(path).resolve(
        market_code,
        require_enabled=require_enabled,
    )

def _walk_substitute(node: Any, vault: Any) -> Any:
    if isinstance(node, dict):
        return {k: _walk_substitute(v, vault) for k, v in node.items()}
    if isinstance(node, list):
        return [_walk_substitute(v, vault) for v in node]
    if isinstance(node, str):
        m = _VAULT_PLACEHOLDER.match(node)
        if m:
            key = m.group(1)
            try:
                resolved = vault.get(key)
            except Exception:  # noqa: BLE001
                LOGGER.warning("vault.get(%s) a échoué — placeholder conservé.",
                               key, exc_info=True)
                return node
            if resolved is None:
                LOGGER.warning("vault.get(%s) → None — placeholder conservé.", key)
                return node
            return resolved
    return node


def _apply_vault_overrides(cfg: dict, vault: Any) -> dict:
    """Substitue tous les placeholders ``${vault:KEY}`` du dict ``cfg``."""
    return _walk_substitute(cfg, vault)


def load_config(
    path: Optional[str] = None,
    *,
    vault: Any = None,
) -> dict:
    """Charge la configuration centralisée YAML (par défaut ``config.yaml``).

    Parameters
    ----------
    path:
        Chemin alternatif vers le fichier YAML.
    vault:
        Instance :class:`~common.config_vault.ConfigVault` explicite. Si
        ``None`` et que ``ALPHA_TRADE_VAULT_ADDR`` est défini, le vault
        est construit via
        :func:`~common.config_vault.build_vault_from_env`.
    """
    config_path = resolve_config_path(path)
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if vault is None and os.getenv("ALPHA_TRADE_VAULT_ADDR"):
        try:
            from common.config_vault import build_vault_from_env

            vault = build_vault_from_env()
        except Exception:  # noqa: BLE001
            LOGGER.warning("build_vault_from_env() a échoué — overrides ignorés.",
                           exc_info=True)
            vault = None

    if vault is not None and isinstance(cfg, dict):
        cfg = _apply_vault_overrides(cfg, vault)
    return cfg


def load_batch_config(
    path: Optional[str] = None,
    *,
    vault: Any = None,
) -> dict:
    """Charge la configuration dédiée aux traitements planifiés."""
    config_path = resolve_batch_config_path(path)
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if vault is None and os.getenv("ALPHA_TRADE_VAULT_ADDR"):
        try:
            from common.config_vault import build_vault_from_env

            vault = build_vault_from_env()
        except Exception:  # noqa: BLE001
            LOGGER.warning("build_vault_from_env() a échoué — overrides ignorés.",
                           exc_info=True)
            vault = None

    if vault is not None and isinstance(cfg, dict):
        cfg = _apply_vault_overrides(cfg, vault)
    return cfg


__all__ = [
    "BATCH_CONFIG_PATH_ENV",
    "CONFIG_PATH_ENV",
    "MARKETS_CONFIG_DIR_ENV",
    "load_batch_config",
    "load_market_registry",
    "load_config",
    "override_config_path",
    "resolve_batch_config_path",
    "resolve_config_path",
    "resolve_market_context",
    "resolve_markets_config_dir",
]

