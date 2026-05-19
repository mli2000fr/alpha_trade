"""Helpers selector consommant ``MarketRegimeSnapshot`` (Axes B, E).

Fournit deux fonctions pures applicables sur un DataFrame de candidats
(colonnes minimales attendues : ``symbol``, ``sector``, ``score``) :

* :func:`apply_earnings_shield_to_candidates` — élimine ou pénalise les
  symboles dans la fenêtre J-2 / J+2 selon le mode du snapshot.
* :func:`apply_buyback_blackout_to_candidates` — applique le multiplicateur
  ML (par défaut 0.70) aux symboles en blackout pré-earnings.
* :func:`apply_yield_filter_to_candidates` — exclut les secteurs blacklistés
  par le yield monitor.

Ces helpers sont volontairement découplés de ``selector/alpha_scanner.py``
pour permettre une intégration progressive (live + backtest + tests).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from service.market import MarketRegimeSnapshot

LOGGER = logging.getLogger(__name__)


def _normalize_symbol_set(values: Iterable[object] | None) -> set[str]:
    return {
        str(value).strip().upper()
        for value in (values or [])
        if str(value).strip()
    }


def _normalize_sector_set(values: Iterable[object] | None) -> set[str]:
    return {
        str(value).strip().casefold()
        for value in (values or [])
        if str(value).strip()
    }


def apply_earnings_shield_to_candidates(
    df: pd.DataFrame | None,
    snapshot: MarketRegimeSnapshot | None,
    *,
    score_column: str = "score",
    symbol_column: str = "symbol",
) -> pd.DataFrame:
    """Filtre / pénalise les candidats touchés par l'earnings shield."""
    if df is None:
        return pd.DataFrame()
    frame = df
    if (
        frame.empty
        or snapshot is None
        or not snapshot.earnings_shielded_symbols
        or symbol_column not in frame.columns
    ):
        return frame
    out = frame.copy()
    syms = out[symbol_column].astype(str).str.upper()
    blocked_symbols = _normalize_symbol_set(
        s for s, mode in snapshot.earnings_shielded_symbols.items() if mode == "strict_block"
    )
    blocked_mask = syms.isin(blocked_symbols)
    if blocked_mask.any():
        LOGGER.info("earnings_shield strict_block: %d candidats exclus", int(blocked_mask.sum()))
        out = out.loc[~blocked_mask].copy()
        syms = out[symbol_column].astype(str).str.upper()
    neg_set = _normalize_symbol_set(
        s for s, mode in snapshot.earnings_shielded_symbols.items() if mode == "negative_score"
    )
    if neg_set and score_column in out.columns:
        neg_mask = syms.isin(neg_set)
        if neg_mask.any():
            out.loc[neg_mask, score_column] = float(snapshot.earnings_negative_score_value)
            LOGGER.info("earnings_shield negative_score: %d candidats pénalisés", int(neg_mask.sum()))
    return out


def apply_buyback_blackout_to_candidates(
    df: pd.DataFrame | None,
    snapshot: MarketRegimeSnapshot | None,
    *,
    score_column: str = "score",
    symbol_column: str = "symbol",
) -> pd.DataFrame:
    """Applique le multiplicateur ML buyback blackout sur la colonne ``score``."""
    if df is None:
        return pd.DataFrame()
    frame = df
    if (
        frame.empty
        or snapshot is None
        or not snapshot.buyback_blackout_symbols
        or score_column not in frame.columns
        or symbol_column not in frame.columns
    ):
        return frame
    out = frame.copy()
    syms = out[symbol_column].astype(str).str.upper()
    normalized_multipliers = {
        str(symbol).strip().upper(): float(mult)
        for symbol, mult in snapshot.buyback_blackout_symbols.items()
        if str(symbol).strip()
    }
    affected = 0
    for symbol, mult in normalized_multipliers.items():
        mask = syms == symbol
        if mask.any():
            out.loc[mask, score_column] = out.loc[mask, score_column].astype(float) * float(mult)
            affected += int(mask.sum())
    if affected:
        LOGGER.info("buyback_blackout: %d candidats pénalisés", affected)
    return out


def apply_yield_filter_to_candidates(
    df: pd.DataFrame | None,
    snapshot: MarketRegimeSnapshot | None,
    *,
    sector_column: str = "sector",
    symbol_column: str = "symbol",
) -> pd.DataFrame:
    """Exclut les secteurs blacklistés et les symboles bloqués (high beta géré ailleurs)."""
    if df is None:
        return pd.DataFrame()
    frame = df
    if frame.empty or snapshot is None:
        return frame
    if not snapshot.blocked_sectors and not snapshot.blocked_symbols:
        return frame
    out = frame.copy()
    if snapshot.blocked_sectors and sector_column in out.columns:
        blocked_sectors = _normalize_sector_set(snapshot.blocked_sectors)
        normalized_sectors = out[sector_column].astype(str).str.strip().str.casefold()
        out = out.loc[~normalized_sectors.isin(blocked_sectors)].copy()
    if snapshot.blocked_symbols and symbol_column in out.columns:
        blocked_symbols = _normalize_symbol_set(snapshot.blocked_symbols)
        out = out.loc[
            ~out[symbol_column].astype(str).str.strip().str.upper().isin(blocked_symbols)
        ].copy()
    return out


def apply_full_regime_to_candidates(
    df: pd.DataFrame | None,
    snapshot: MarketRegimeSnapshot | None,
    *,
    score_column: str = "score",
    sector_column: str = "sector",
    symbol_column: str = "symbol",
) -> pd.DataFrame:
    """Pipeline complet : yield filter + earnings shield + buyback blackout."""
    if df is None:
        return pd.DataFrame()
    out = apply_yield_filter_to_candidates(
        df, snapshot, sector_column=sector_column, symbol_column=symbol_column
    )
    out = apply_earnings_shield_to_candidates(
        out, snapshot, score_column=score_column, symbol_column=symbol_column
    )
    out = apply_buyback_blackout_to_candidates(
        out, snapshot, score_column=score_column, symbol_column=symbol_column
    )
    return out


__all__ = [
    "apply_earnings_shield_to_candidates",
    "apply_buyback_blackout_to_candidates",
    "apply_yield_filter_to_candidates",
    "apply_full_regime_to_candidates",
]

