"""Helpers communs aux importeurs de barres Alpaca/EODHD."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def resolve_bars_provider(config: Mapping[str, Any] | None = None, *, fallback: str = "alpaca") -> str:
    """Résout le provider des barres depuis ``config.market_data.bars_provider``.

    Le ``fallback`` reste volontairement ``alpaca`` pour préserver la rétrocompat
    en environnement sans configuration exploitable.
    """
    cfg = config or {}
    market_data = cfg.get("market_data") if isinstance(cfg, Mapping) else {}
    if not isinstance(market_data, Mapping):
        market_data = {}
    provider = market_data.get("bars_provider", fallback)
    return str(provider or fallback).strip().lower()


def normalize_symbols(symbols: list[str] | None) -> list[str] | None:
    """Normalise une liste de symboles (trim/upper/dedup) en conservant l'ordre."""
    if symbols is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        cleaned = str(symbol or "").strip().upper()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)

    if not normalized:
        raise ValueError("symbols doit contenir au moins un symbole non vide.")
    return normalized

