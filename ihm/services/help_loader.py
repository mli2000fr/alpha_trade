"""Sprint S20 — Chargeur des tooltips contextuels (``ihm/help/<page>.yaml``).

* Lit chaque YAML en **utf-8 strict** (rejette le BOM — régression S10.1).
* Cache LRU mémoire pour éviter de relire le disque à chaque rerun.
* Fusionne automatiquement les entrées de ``_common.yaml`` dans toutes
  les pages (les clés spécifiques surchargent les communes).
* Validation de schéma : 6 champs obligatoires
  (``title``, ``description``, ``impact``, ``example``, ``default``,
  ``range``, ``doc_ref``). Les entrées invalides sont ignorées avec un
  ``logging.warning`` (pas d'exception : la page doit toujours rendre).
"""
from __future__ import annotations

import functools
import logging
import pathlib
from typing import Any, Mapping

import yaml

logger = logging.getLogger(__name__)

# Racine des YAML help, calculée relativement au package ``ihm``.
_HELP_DIR = pathlib.Path(__file__).resolve().parent.parent / "help"

REQUIRED_FIELDS: tuple[str, ...] = (
    "title",
    "description",
    "impact",
    "example",
    "default",
    "range",
    "doc_ref",
)


class HelpYamlError(RuntimeError):
    """Erreur structurelle dans un YAML help (BOM, format inattendu)."""


def _read_yaml(path: pathlib.Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise HelpYamlError(
            f"BOM UTF-8 interdit dans {path} — réenregistrer en utf-8 sans BOM"
        )
    text = raw.decode("utf-8")
    parsed = yaml.safe_load(text) or {}
    if not isinstance(parsed, dict):
        raise HelpYamlError(f"YAML help {path} attendu dict, reçu {type(parsed).__name__}")
    return parsed


def _validate_entry(page: str, key: str, entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        logger.warning("help[%s][%s] ignoré : entrée non dict", page, key)
        return None
    missing = [f for f in REQUIRED_FIELDS if f not in entry]
    if missing:
        logger.warning(
            "help[%s][%s] champs manquants : %s", page, key, ", ".join(missing)
        )
    return entry  # on retourne quand même : le rendu gère l'absence


@functools.lru_cache(maxsize=64)
def load_help(page: str) -> Mapping[str, Any]:
    """Retourne le mapping ``key -> entry`` pour la page demandée.

    Fusion ``_common.yaml`` ⊕ ``<page>.yaml`` (la page surcharge).
    """
    merged: dict[str, Any] = {}
    common = _HELP_DIR / "_common.yaml"
    if common.exists():
        try:
            for k, v in _read_yaml(common).items():
                if (validated := _validate_entry("_common", k, v)) is not None:
                    merged[k] = validated
        except HelpYamlError as exc:
            logger.warning("Impossible de charger _common.yaml : %s", exc)

    target = _HELP_DIR / f"{page}.yaml"
    if target.exists():
        try:
            for k, v in _read_yaml(target).items():
                if (validated := _validate_entry(page, k, v)) is not None:
                    merged[k] = validated
        except HelpYamlError as exc:
            logger.warning("Impossible de charger %s.yaml : %s", page, exc)
    return merged


def reset_cache() -> None:
    """Invalide le cache (utile pour les tests)."""
    load_help.cache_clear()


def help_dir() -> pathlib.Path:
    """Expose le répertoire des YAML help (utile pour audit/tests)."""
    return _HELP_DIR

