"""modelFactory/features.py — Feature engineering à partir de stock_bars_daily."""
from __future__ import annotations

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


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les features dérivées à un DataFrame de bars trié par date.

    Le DataFrame d'entrée doit avoir : open, high, low, close, volume, adj_close, vwap, daily_return, is_filled.
    Retourne une copie avec les colonnes FEATURE_COLUMNS ajoutées (certaines existantes mises à jour).
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

    # Drop warm-up NaN rows (rolling windows need ~60 rows)
    df = df.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)
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

