"""Filtre de corrélation Pearson greedy pré-sizing V2.

Sprint Maître 6 — corrélation signée :
- ``filter_correlated_signed()`` traite la corrélation de PnL signée.
  Corrélation positive long/short → hedge (PnL se compensent).
  Corrélation négative long/short → concentration (PnL amplifiée).
"""
from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from risk_management.models import CorrelationRejection, EnrichedSelection

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
    candidates: list[EnrichedSelection],
    return_matrix: pd.DataFrame,
    threshold: float,
    min_overlap: int,
) -> tuple[list[EnrichedSelection], list[CorrelationRejection]]:
    """Filtre greedy déterministe.

    Les candidats DOIVENT être triés par conviction_score DESC avant l'appel.
    """
    retained: list[EnrichedSelection] = []
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
                LOGGER.debug(
                    "correlation_filter | %s REJETÉ (corr=%.4f > seuil=%.2f avec %s, overlap=%s jours)",
                    sym, corr, threshold, kept_sym, len(pair),
                )
                correlated_with_retained = True
                break

        if not correlated_with_retained:
            retained.append(candidate)

    return retained, rejections


# ── Sprint Maître 6 : corrélation PnL signée ──────────────────────────────

def filter_correlated_signed(
    candidates: list[EnrichedSelection],
    return_matrix: pd.DataFrame,
    threshold: float,
    min_overlap: int,
) -> tuple[list[EnrichedSelection], list[CorrelationRejection]]:
    """Filtre greedy avec corrélation de PnL signée (Sprint Maître 6).

    Contrairement à ``filter_correlated`` qui utilise les rendements bruts,
    cette fonction utilise les rendements SIGNÉS (×1 pour long, ×(-1)
    pour short) pour mesurer la corrélation de PnL.

    - Corrélation **positive** entre un long et un short = HEDGE
      (les PnL se compensent) → le filtre PEUT ignorer le seuil.
    - Corrélation **négative** entre un long et un short = CONCENTRATION
      (les PnL s'amplifient mutuellement) → rejet si |corr| > threshold.
    - Même side : comportement identique à ``filter_correlated``.

    Parameters
    ----------
    candidates : list[EnrichedSelection]
        Triés par conviction_score DESC. Doivent avoir ``.side`` renseigné.
    return_matrix : pd.DataFrame
        Matrice de rendements bruts (price returns).
    threshold : float
        Seuil de corrélation au-delà duquel on rejette.
    min_overlap : int
        Nombre minimum d'observations communes.

    Returns
    -------
    (retained, rejections)
    """
    retained: list[EnrichedSelection] = []
    rejections: list[CorrelationRejection] = []

    matrix_cols = set(return_matrix.columns) if not return_matrix.empty else set()

    for candidate in candidates:
        sym = candidate.symbol
        if sym not in matrix_cols:
            retained.append(candidate)
            continue

        c_side = str(getattr(candidate, "side", "buy") or "buy").strip().lower()
        c_is_short = c_side in ("short", "sell")
        c_sign = -1 if c_is_short else 1

        correlated_with_retained = False
        for kept in retained:
            kept_sym = kept.symbol
            if kept_sym not in matrix_cols:
                continue

            k_side = str(getattr(kept, "side", "buy") or "buy").strip().lower()
            k_is_short = k_side in ("short", "sell")
            k_sign = -1 if k_is_short else 1

            pair = return_matrix[[sym, kept_sym]].dropna()
            if len(pair) < min_overlap:
                continue

            # Rendements bruts
            ret_c = pair[sym].to_numpy(float)
            ret_k = pair[kept_sym].to_numpy(float)

            # ── PnL signée ──────────────────────────────────────────
            pnl_c = ret_c * c_sign
            pnl_k = ret_k * k_sign
            signed_corr = float(np.corrcoef(pnl_c, pnl_k)[0, 1]) if len(pnl_c) > 1 else 0.0

            if math.isnan(signed_corr):
                continue

            # Même side : seuil positif normal
            same_side = (c_is_short == k_is_short)
            if same_side and signed_corr > threshold:
                rejections.append(CorrelationRejection(
                    rejected_symbol=sym,
                    blocker_symbol=kept_sym,
                    correlation_value=round(signed_corr, 4),
                    threshold=threshold,
                ))
                LOGGER.debug(
                    "correlation_filter_signed | %s REJETÉ same_side (corr=%.4f > %.2f avec %s)",
                    sym, signed_corr, threshold, kept_sym,
                )
                correlated_with_retained = True
                break

            # Sides opposés : corrélation positive = hedge (OK),
            # corrélation négative = concentration (rejet)
            if not same_side:
                if signed_corr < -threshold:
                    # Concentration long/short → rejet
                    rejections.append(CorrelationRejection(
                        rejected_symbol=sym,
                        blocker_symbol=kept_sym,
                        correlation_value=round(signed_corr, 4),
                        threshold=threshold,
                    ))
                    LOGGER.debug(
                        "correlation_filter_signed | %s REJETÉ cross_side_concentration "
                        "(signed_corr=%.4f < -%.2f avec %s)",
                        sym, signed_corr, threshold, kept_sym,
                    )
                    correlated_with_retained = True
                    break
                # signed_corr >= 0 ou dans [-threshold, 0] → hedge acceptable
                continue

        if not correlated_with_retained:
            retained.append(candidate)

    return retained, rejections

