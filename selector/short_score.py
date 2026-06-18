"""
selector/short_score.py
=======================
Option B — short_score dédié pour sélectionner les candidats short.

Calcule un score baissier composite (0-1, plus c'est élevé, plus le titre
est baissier) basé sur :
- trend_score faible (< 0.3)
- RSI bas (< 40)
- prix sous SMA50
- prix sous SMA200

Utilisé en remplacement du bottom-N final_score pour taguer les shorts.
"""

from __future__ import annotations

import pandas as pd


def compute_short_score(
    day_df: pd.DataFrame,
    close_df: pd.DataFrame | None = None,
    trade_day: pd.Timestamp | None = None,
    *,
    sma_50_col: str = "sma_50",
    sma_200_col: str = "sma_200",
) -> pd.Series:
    """Calcule un score baissier composite (0-1).

    Parameters
    ----------
    day_df : pd.DataFrame
        Candidats du jour (doit contenir trend_score, relative_strength_index).
    close_df : pd.DataFrame or None
        OHLCV close (index=dates, columns=symbols). Si None, les facteurs SMA
        sont ignorés.
    trade_day : pd.Timestamp or None
        Date de trading pour chercher les prix dans close_df.
    sma_50_col, sma_200_col : str
        Noms des colonnes SMA si déjà présentes dans day_df.

    Returns
    -------
    pd.Series
        Score baissier entre 0.0 (pas baissier) et 1.0 (très baissier).
        Index aligné sur day_df.
    """
    n = len(day_df)
    if n == 0:
        return pd.Series(dtype=float)

    scores = pd.Series(0.0, index=day_df.index, dtype=float)

    # ── Facteur 1 : trend_score faible (< 0.3) → bearish ──────────
    if "trend_score" in day_df.columns:
        trend = day_df["trend_score"].astype(float).fillna(1.0)
        # trend_score ∈ [0, 1], on veut les valeurs faibles
        trend_bearish = (1.0 - trend.clip(0.0, 1.0)).clip(0.0, 1.0)
        scores += 0.30 * trend_bearish

    # ── Facteur 2 : RSI bas (< 40) → bearish ──────────────────────
    rsi_col = "relative_strength_index"
    if rsi_col in day_df.columns:
        rsi = day_df[rsi_col].astype(float).fillna(50.0)
        # RSI ∈ [0, 100], on veut RSI < 40 → bearish
        # Transforme : RSI=0 → 1.0, RSI=40 → 0.5, RSI=100 → 0.0
        rsi_bearish = (1.0 - rsi.clip(0.0, 100.0) / 100.0).clip(0.0, 1.0)
        scores += 0.25 * rsi_bearish

    # ── Facteur 3 : prix sous SMA50 ───────────────────────────────
    if sma_50_col in day_df.columns:
        sma50 = day_df[sma_50_col].astype(float)
        # Récupérer le prix (depuis close_df ou colonne last_close)
        price_col = None
        if "last_close" in day_df.columns:
            price_col = "last_close"
        elif close_df is not None and trade_day is not None:
            # On n'a pas de prix dans day_df, on laisse tomber ce facteur
            pass

        if price_col and price_col in day_df.columns:
            close_price = day_df[price_col].astype(float)
            below_sma50 = (close_price < sma50) & (sma50 > 0)
            scores += 0.25 * below_sma50.astype(float)

    # ── Facteur 4 : prix sous SMA200 ──────────────────────────────
    if sma_200_col in day_df.columns:
        sma200 = day_df[sma_200_col].astype(float)
        price_col = "last_close" if "last_close" in day_df.columns else None
        if price_col and price_col in day_df.columns:
            close_price = day_df[price_col].astype(float)
            below_sma200 = (close_price < sma200) & (sma200 > 0)
            scores += 0.20 * below_sma200.astype(float)

    return scores.clip(0.0, 1.0)


def enrich_with_short_score(
    day_df: pd.DataFrame,
    close_df: pd.DataFrame | None = None,
    trade_day: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Ajoute la colonne ``short_score`` au DataFrame des candidats.

    Si ``close_df`` est fourni, les SMA sont calculés à la volée.
    Sinon, seuls les facteurs trend_score et RSI sont utilisés.
    """
    result = day_df.copy()
    result["short_score"] = compute_short_score(result, close_df, trade_day)
    return result


def compute_sma_column(
    close_df: pd.DataFrame,
    symbol: str,
    trade_day: pd.Timestamp,
    window: int = 50,
) -> float | None:
    """Calcule la SMA(window) pour un symbole à une date donnée.

    Parameters
    ----------
    close_df : pd.DataFrame
        OHLCV close (index=dates, columns=symbols).
    symbol : str
        Symbole à analyser.
    trade_day : pd.Timestamp
        Date de référence.
    window : int
        Fenêtre de la SMA (50 ou 200).

    Returns
    -------
    float or None
        Valeur de la SMA, ou None si pas assez de données.
    """
    if close_df is None or symbol not in close_df.columns:
        return None
    try:
        # Trouver la position du trade_day dans l'index
        loc = close_df.index.get_loc(trade_day)
        if isinstance(loc, slice):
            return None
        # Prendre les window jours avant trade_day (inclus)
        start_loc = max(0, loc - window + 1)
        prices = close_df.iloc[start_loc:loc + 1][symbol].dropna()
        if len(prices) < min(window // 2, 20):
            return None
        return float(prices.mean())
    except (KeyError, IndexError):
        return None
