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
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


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


__all__ = ["CONFIG_PATH_ENV", "load_config", "override_config_path", "resolve_config_path"]

