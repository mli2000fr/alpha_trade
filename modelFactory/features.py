"""modelFactory/features.py — Feature engineering à partir de stock_bars_daily."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

# -------------------------------------------------------------------------
# Liste ordonnée des features V1 (dérivées de OHLCV uniquement)
# -------------------------------------------------------------------------
FEATURE_COLUMNS: list[str] = [
    "daily_return",
    "log_return",
    "intraday_range",
    "overnight_gap",
    "close_to_vwap",
    "volume_ratio_20",
    "rolling_volatility_20",
    "rolling_volatility_60",
    "rolling_mean_return_5",
    "rolling_mean_return_20",
    "rsi_14",
    "atr_14_norm",
    "is_filled",
]

# Features sentiment auxiliaires (depuis ticker_daily_sentiment_features)
SENTIMENT_FEATURE_COLUMNS: list[str] = [
    "sentiment_net_mean_1d",
    "sentiment_confidence_mean_1d",
    "news_count_log",
    "major_event_flag",
]


def get_feature_columns(include_sentiment: bool = False) -> list[str]:
    """Retourne la liste complète des colonnes features (OHLCV + optionnel sentiment)."""
    cols = list(FEATURE_COLUMNS)
    if include_sentiment:
        cols.extend(SENTIMENT_FEATURE_COLUMNS)
    return cols


def compute_features(
    df: pd.DataFrame,
    sentiment_df: Optional[pd.DataFrame] = None,
    include_sentiment: bool = False,
) -> pd.DataFrame:
    """Ajoute les features dérivées à un DataFrame de bars trié par date.

    Le DataFrame d'entrée doit avoir : open, high, low, close, volume, adj_close, vwap, daily_return, is_filled.
    Si include_sentiment=True et sentiment_df fourni, merge les colonnes sentiment sur (symbol, date).
    Retourne une copie avec les colonnes features ajoutées.
    Les premières lignes avec NaN rolling sont supprimées.
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    opn = df["open"].astype(float)
    volume = df["volume"].astype(float)
    vwap = df["vwap"].astype(float)

    # --- daily_return : utilise la colonne existante, forward-fill NaN ---
    df["daily_return"] = df["daily_return"].astype(float).fillna(0.0)

    # --- log return ---
    df["log_return"] = np.log(close / close.shift(1))

    # --- intraday range ---
    df["intraday_range"] = (high - low) / close.clip(lower=1e-8)

    # --- overnight gap ---
    df["overnight_gap"] = (opn - close.shift(1)) / close.shift(1).clip(lower=1e-8)

    # --- close to vwap ---
    df["close_to_vwap"] = (close - vwap) / vwap.clip(lower=1e-8)
    df["close_to_vwap"] = df["close_to_vwap"].fillna(0.0)

    # --- volume ratio 20d ---
    vol_ma20 = volume.rolling(20).mean()
    df["volume_ratio_20"] = volume / vol_ma20.clip(lower=1.0)

    # --- rolling volatility ---
    df["rolling_volatility_20"] = df["daily_return"].rolling(20).std()
    df["rolling_volatility_60"] = df["daily_return"].rolling(60).std()

    # --- rolling mean return ---
    df["rolling_mean_return_5"] = df["daily_return"].rolling(5).mean()
    df["rolling_mean_return_20"] = df["daily_return"].rolling(20).mean()

    # --- RSI 14 ---
    df["rsi_14"] = _rsi(close, 14)

    # --- ATR 14 normalized ---
    df["atr_14_norm"] = _atr_norm(high, low, close, 14)

    # --- is_filled as float ---
    df["is_filled"] = df["is_filled"].astype(float)

    # --- Sentiment features (optional) ---
    if include_sentiment:
        if sentiment_df is not None and not sentiment_df.empty:
            sent = sentiment_df.copy()
            # Normaliser la colonne date pour le merge
            if "trade_date" in sent.columns:
                sent = sent.rename(columns={"trade_date": "date"})
            sent["date"] = pd.to_datetime(sent["date"])
            sent["news_count_log"] = np.log1p(sent.get("news_count_1d", pd.Series(dtype=float)).fillna(0))
            merge_cols = ["date", "sentiment_net_mean_1d", "sentiment_confidence_mean_1d", "news_count_log", "major_event_flag"]
            if "symbol" in sent.columns and "symbol" in df.columns:
                merge_cols.insert(0, "symbol")
            sent = sent[[c for c in merge_cols if c in sent.columns]]
            df = df.merge(sent, on=[c for c in ["symbol", "date"] if c in sent.columns and c in df.columns], how="left")
        # Remplir les jours sans news par des valeurs neutres
        for col in SENTIMENT_FEATURE_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0
            else:
                df[col] = df[col].fillna(0.0).astype(float)

    # Determine active feature columns
    active_features = get_feature_columns(include_sentiment)

    # Drop warm-up NaN rows (rolling windows need ~60 rows)
    df = df.dropna(subset=active_features).reset_index(drop=True)
    return df


def build_target(df: pd.DataFrame, horizon: int = 5) -> pd.Series:
    """Construit la target binaire : 1 si future_Xd_return > 0.

    Retourne une Series alignée sur l'index de df.
    Les dernières `horizon` lignes seront NaN.
    """
    close = df["close"].astype(float)
    future_return = close.shift(-horizon) / close - 1.0
    return (future_return > 0).astype(float).where(future_return.notna())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.clip(lower=1e-10)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr_norm(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr / close.clip(lower=1e-8)

