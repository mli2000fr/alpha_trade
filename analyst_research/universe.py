"""Univers stable de collecte analyst (RESEARCH ONLY).

L'univers ``analyst_research`` = liste du fichier dont le CHEMIN est configuré
dans ``batch.yaml`` (``analyst_snapshot_collection.symbols_file``,
``config/univers_batch/univers_filtred_tradable.txt``),
le même fichier que celui du batch ``earnings_calendar_sync``.

Le fichier est obligatoire. Une configuration absente, un fichier introuvable ou
un fichier vide bloque la collecte avant tout appel fournisseur. Il n'existe pas
de repli silencieux vers un univers dynamique plus large.

``--symbols AAPL,MSFT`` surcharge temporairement l'univers configuré.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from common.config_loader import load_batch_config

LOGGER = logging.getLogger(__name__)

DEFAULT_UNIVERSE_NAME = "analyst_research"


@dataclass(frozen=True, slots=True)
class UniverseResolution:
    """Résolution d'univers : symboles + source effective + avertissements."""

    symbols: list[str]
    source: str          # "file:<chemin>" | "cli-override"
    warnings: list[str]


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
       ``batch.yaml`` (``analyst_snapshot_collection.symbols_file``).
       Ce chemin doit être renseigné, lisible et non vide.
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
    cfg = load_batch_config()
    section = cfg.get("analyst_snapshot_collection") or {}
    configured = (
        symbols_file if symbols_file is not None else section.get("symbols_file")
    )
    path = str(configured or "").strip()
    if not path:
        raise ValueError(
            "analyst_snapshot_collection.symbols_file est obligatoire dans batch.yaml"
        )
    symbols = read_symbols_file(path)
    if not symbols:
        raise ValueError(f"Fichier d'univers vide: {path}")
    return UniverseResolution(
        symbols=symbols,
        source=f"file:{path}",
        warnings=[],
    )
