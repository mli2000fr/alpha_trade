"""Filtre de corrélation Pearson greedy pré-sizing V2."""
from __future__ import annotations

import logging
import math

import pandas as pd

from risk_management.models import CorrelationRejection, EnrichedCandidate

LOGGER = logging.getLogger(__name__)

CORRELATION_CONVENTION_PRICE_ONLY = "price_only_close_split_adjusted"
CORRELATION_CONVENTION_TOTAL_RETURN = "total_return_with_cash_dividends"


def build_return_matrix(
    close_prices: pd.DataFrame,
    *,
    cash_dividends: pd.DataFrame | None = None,
    convention: str = CORRELATION_CONVENTION_PRICE_ONLY,
) -> pd.DataFrame:
    """Construit une matrice de rendements selon une convention explicite.

    - ``price_only_close_split_adjusted`` : corrélation sur ``close.pct_change()``.
    - ``total_return_with_cash_dividends`` : ajoute les dividendes cash du jour
      au close avant calcul de rendement, afin de refléter le rendement total.
    """
    prepared_close = close_prices.apply(pd.to_numeric, errors="coerce") if not close_prices.empty else close_prices.copy()
    if prepared_close.empty:
        return prepared_close.copy()
    if convention == CORRELATION_CONVENTION_PRICE_ONLY:
        returns = prepared_close.pct_change()
    elif convention == CORRELATION_CONVENTION_TOTAL_RETURN:
        aligned_dividends = (
            cash_dividends.reindex(index=prepared_close.index, columns=prepared_close.columns, fill_value=0.0)
            if isinstance(cash_dividends, pd.DataFrame)
            else pd.DataFrame(0.0, index=prepared_close.index, columns=prepared_close.columns)
        )
        aligned_dividends = aligned_dividends.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        previous_close = prepared_close.shift(1)
        returns = ((prepared_close + aligned_dividends) / previous_close) - 1.0
    else:
        raise ValueError(f"Convention de corrélation inconnue: {convention}")
    return returns.replace([math.inf, -math.inf], pd.NA).astype(float)


def filter_correlated(
    candidates: list[EnrichedCandidate],
    return_matrix: pd.DataFrame,
    threshold: float,
    min_overlap: int,
) -> tuple[list[EnrichedCandidate], list[CorrelationRejection]]:
    """Filtre greedy déterministe.

    Les candidats DOIVENT être triés par conviction_score DESC avant l'appel.
    """
    retained: list[EnrichedCandidate] = []
    rejections: list[CorrelationRejection] = []

    matrix_cols = set(return_matrix.columns) if not return_matrix.empty else set()

    for candidate in candidates:
        sym = candidate.symbol
        if sym not in matrix_cols:
            retained.append(candidate)
            continue

        correlated_with_retained = False
        for kept in retained:
            kept_sym = kept.symbol
            if kept_sym not in matrix_cols:
                continue
            pair = return_matrix[[sym, kept_sym]].dropna()
            if len(pair) < min_overlap:
                continue
            corr = pair[sym].corr(pair[kept_sym])
            if math.isnan(corr):
                continue
            if corr > threshold:
                rejections.append(CorrelationRejection(
                    rejected_symbol=sym,
                    blocker_symbol=kept_sym,
                    correlation_value=round(corr, 4),
                    threshold=threshold,
                ))
                correlated_with_retained = True
                break

        if not correlated_with_retained:
            retained.append(candidate)

    return retained, rejections

