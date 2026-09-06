"""Univers de collecte analyst — configurable, avec repli active-tradable (RESEARCH ONLY).

L'univers ``analyst_research`` = liste du fichier dont le CHEMIN est configuré
dans ``config.yaml`` (``analyst_snapshot_collection.symbols_file``,
ex. ``config/univers_batch/univers_filtred_tradable.txt`` → 2255 symboles),
le même fichier que celui du batch ``earnings_calendar_sync``.

Règle (commune aux 2 batchs) :
- ``symbols_file`` renseigné ET fichier lisible → univers fichier (2255) ;
- ``symbols_file`` NON renseigné OU fichier introuvable → AVERTISSEMENT
  (remonté dans le log, l'email et Telegram par le launcher) + repli sur
  l'univers dynamique ``active-tradable`` (~13 600, table ``stock_metadata``
  filtres éligibles).

``--symbols AAPL,MSFT`` surcharge temporairement l'univers configuré.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from common.config_loader import load_config

LOGGER = logging.getLogger(__name__)

DEFAULT_UNIVERSE_NAME = "analyst_research"


@dataclass(frozen=True, slots=True)
class UniverseResolution:
    """Résolution d'univers : symboles + source effective + avertissements."""

    symbols: list[str]
    source: str          # "file:<chemin>" | "active-tradable" | "cli-override"
    warnings: list[str]  # messages si repli (symbols_file absent/introuvable)


def _split_symbols(raw: str | Iterable[str]) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for chunk in raw:
        for tok in re.split(r"[\s,;]+", str(chunk)):
            tok = tok.strip().upper()
            if tok:
                out.append(tok)
    return sorted(set(out))  # déterministe : trié + dédupliqué


def read_symbols_file(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Fichier d'univers introuvable: {p}")
    return _split_symbols(p.read_text(encoding="utf-8"))


def _active_tradable_resolution(warning: str) -> UniverseResolution:
    """Repli sur l'univers dynamique active-tradable (DB ``stock_metadata``)."""
    from database.selector_reference import list_active_tradable_symbols

    symbols = list_active_tradable_symbols()
    return UniverseResolution(
        symbols=symbols,
        source="active-tradable",
        warnings=[warning],
    )


def resolve_universe(
    name: str | None = None,
    symbols_override: str | None = None,
    *,
    symbols_file: str | None = None,
) -> UniverseResolution:
    """Résout l'univers de collecte.

    Priorité :
    1. ``symbols_override`` (--symbols) s'il est fourni.
    2. ``name == analyst_research`` (ou None) → fichier configuré dans
       ``config.yaml`` (``analyst_snapshot_collection.symbols_file``).
       Si ce chemin est absent/vide OU le fichier est introuvable → repli
       ``active-tradable`` avec un avertissement.
    """
    if symbols_override:
        return UniverseResolution(
            symbols=_split_symbols(symbols_override),
            source="cli-override",
            warnings=[],
        )
    name = name or DEFAULT_UNIVERSE_NAME
    if name != DEFAULT_UNIVERSE_NAME:
        raise ValueError(f"Univers inconnu: {name!r} (attendu: {DEFAULT_UNIVERSE_NAME!r})")
    cfg = load_config()
    section = cfg.get("analyst_snapshot_collection") or {}
    configured = (
        symbols_file if symbols_file is not None else section.get("symbols_file")
    )
    path = str(configured or "").strip()
    if not path:
        warning = (
            "analyst_snapshot_collection.symbols_file non renseigné (config.yaml) "
            "=> repli univers active-tradable (~13 600)"
        )
        LOGGER.warning(warning)
        return _active_tradable_resolution(warning)
    try:
        symbols = read_symbols_file(path)
    except OSError as exc:  # FileNotFoundError est un OSError.
        warning = (
            f"analyst_snapshot_collection.symbols_file introuvable/inaccessible : "
            f"{path} ({exc}) => repli univers active-tradable (~13 600)"
        )
        LOGGER.warning(warning)
        return _active_tradable_resolution(warning)
    return UniverseResolution(
        symbols=symbols,
        source=f"file:{path}",
        warnings=[],
    )
