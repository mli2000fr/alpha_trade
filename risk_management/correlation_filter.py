"""Filtre de corrélation Pearson greedy pré-sizing V2."""
from __future__ import annotations

import logging
import math

import pandas as pd

from risk_management.models import CorrelationRejection, EnrichedCandidate

LOGGER = logging.getLogger(__name__)


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

