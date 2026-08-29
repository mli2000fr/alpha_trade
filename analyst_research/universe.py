"""Univers de collecte analyst — explicite, configurable, déterministe (RESEARCH ONLY).

L'univers ``analyst_research`` = liste FIGÉE de ~400 symboles, lue depuis un
fichier dont le CHEMIN est configuré dans ``config.yaml``
(``analyst_snapshot_collection.symbols_file``). Ce n'est NI
``get_active_tradable_symbols()`` (13 608) NI le pool Oracle TOP20% — la liste
est la source authoritative du chantier ; un symbole sans données Yahoo reste
dans le suivi de couverture (jamais remplacé automatiquement).

``--symbols AAPL,MSFT`` surcharge temporairement l'univers configuré.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

from common.config_loader import load_config

LOGGER = logging.getLogger(__name__)

DEFAULT_SYMBOLS_FILE = "config/ticket_mid_cap_400.txt"
DEFAULT_UNIVERSE_NAME = "analyst_research"


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


def resolve_universe(name: str | None = None, symbols_override: str | None = None) -> list[str]:
    """Résout l'univers de collecte.

    Priorité :
    1. ``symbols_override`` (--symbols) s'il est fourni.
    2. ``name == analyst_research`` (ou None) → fichier configuré dans config.yaml
       (``analyst_snapshot_collection.symbols_file``), défaut
       ``config/ticket_mid_cap_400.txt``.
    """
    if symbols_override:
        return _split_symbols(symbols_override)
    name = name or DEFAULT_UNIVERSE_NAME
    if name != DEFAULT_UNIVERSE_NAME:
        raise ValueError(f"Univers inconnu: {name!r} (attendu: {DEFAULT_UNIVERSE_NAME!r})")
    cfg = load_config()
    section = cfg.get("analyst_snapshot_collection") or {}
    path = section.get("symbols_file", DEFAULT_SYMBOLS_FILE)
    return read_symbols_file(path)
