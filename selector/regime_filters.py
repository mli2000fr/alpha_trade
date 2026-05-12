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
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from service.market import MarketRegimeSnapshot

LOGGER = logging.getLogger(__name__)


def apply_earnings_shield_to_candidates(
    df: pd.DataFrame,
    snapshot: "MarketRegimeSnapshot | None",
    *,
    score_column: str = "score",
    symbol_column: str = "symbol",
) -> pd.DataFrame:
    """Filtre / pénalise les candidats touchés par l'earnings shield."""
    if df is None or df.empty or snapshot is None or not snapshot.earnings_shielded_symbols:
        return df
    out = df.copy()
    syms = out[symbol_column].astype(str).str.upper()
    blocked_mask = syms.isin(
        {s for s, m in snapshot.earnings_shielded_symbols.items() if m == "strict_block"}
    )
    if blocked_mask.any():
        LOGGER.info("earnings_shield strict_block: %d candidats exclus", int(blocked_mask.sum()))
        out = out.loc[~blocked_mask].copy()
        syms = out[symbol_column].astype(str).str.upper()
    neg_set = {s for s, m in snapshot.earnings_shielded_symbols.items() if m == "negative_score"}
    if neg_set and score_column in out.columns:
        neg_mask = syms.isin(neg_set)
        if neg_mask.any():
            out.loc[neg_mask, score_column] = float(snapshot.earnings_negative_score_value)
            LOGGER.info("earnings_shield negative_score: %d candidats pénalisés", int(neg_mask.sum()))
    return out


def apply_buyback_blackout_to_candidates(
    df: pd.DataFrame,
    snapshot: "MarketRegimeSnapshot | None",
    *,
    score_column: str = "score",
    symbol_column: str = "symbol",
) -> pd.DataFrame:
    """Applique le multiplicateur ML buyback blackout sur la colonne ``score``."""
    if df is None or df.empty or snapshot is None or not snapshot.buyback_blackout_symbols:
        return df
    if score_column not in df.columns:
        return df
    out = df.copy()
    syms = out[symbol_column].astype(str).str.upper()
    affected = 0
    for symbol, mult in snapshot.buyback_blackout_symbols.items():
        mask = syms == str(symbol).upper()
        if mask.any():
            out.loc[mask, score_column] = out.loc[mask, score_column].astype(float) * float(mult)
            affected += int(mask.sum())
    if affected:
        LOGGER.info("buyback_blackout: %d candidats pénalisés (mult x%.2f)", affected, mult)
    return out


def apply_yield_filter_to_candidates(
    df: pd.DataFrame,
    snapshot: "MarketRegimeSnapshot | None",
    *,
    sector_column: str = "sector",
    symbol_column: str = "symbol",
) -> pd.DataFrame:
    """Exclut les secteurs blacklistés et les symboles bloqués (high beta géré ailleurs)."""
    if df is None or df.empty or snapshot is None:
        return df
    if not snapshot.blocked_sectors and not snapshot.blocked_symbols:
        return df
    out = df.copy()
    if snapshot.blocked_sectors and sector_column in out.columns:
        out = out.loc[~out[sector_column].astype(str).isin(snapshot.blocked_sectors)].copy()
    if snapshot.blocked_symbols and symbol_column in out.columns:
        out = out.loc[
            ~out[symbol_column].astype(str).str.upper().isin(
                {s.upper() for s in snapshot.blocked_symbols}
            )
        ].copy()
    return out


def apply_full_regime_to_candidates(
    df: pd.DataFrame,
    snapshot: "MarketRegimeSnapshot | None",
    *,
    score_column: str = "score",
    sector_column: str = "sector",
    symbol_column: str = "symbol",
) -> pd.DataFrame:
    """Pipeline complet : yield filter + earnings shield + buyback blackout."""
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

