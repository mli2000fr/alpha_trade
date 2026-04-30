"""
Phase 3.3.a — Calcul des facteurs techniques (pur, sans I/O).

Extrait de ``selector.alpha_scanner`` pour clarifier les responsabilités :
- Ce module **ne touche pas** à la base de données.
- Il transforme un DataFrame de prix journaliers + un DataFrame de retours benchmark
  (SPY) en un DataFrame de facteurs (MA50/150/200, ATR, beta_126, trend_score
  Minervini, weekly_trend_score, vcp_score, etc.).
- Les valeurs/fenêtres sont fournies via ``config`` (``AlphaScannerConfig``).

Le wrapper rétro-compatible ``AlphaScanner.compute_factors(market_data)`` reste
exposé dans ``selector.alpha_scanner`` ; il pré-charge ``benchmark_returns`` puis
appelle ``compute_factor_frame`` ici.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd

if TYPE_CHECKING:  # pragma: no cover - import circulaire évité
    from selector.alpha_scanner import AlphaScannerConfig

LOGGER = logging.getLogger(__name__)

FACTOR_COLUMNS = [
    "symbol",
    "date",
    "latest_close",
    "avg_dollar_volume_20d",
    "history_days",
    "atr_20",
    "atr_pct_20",
    "beta_126",
    "ma50",
    "ma150",
    "ma200",
    "high_52w",
    "low_52w",
    "high_52w_proximity",
    "weekly_close",
    "weekly_ma10",
    "weekly_ma30",
    "weekly_trend_score",
    "volatility_ratio",
    "trend_score",
    "vcp_score",
]


def winsorize_and_normalize(
    series: Optional[pd.Series],
    lower_pct: float = 0.01,
    upper_pct: float = 0.99,
) -> pd.Series:
    """
    Winsorise [lower_pct, upper_pct] puis normalise en [0, 1] (min-max).

    Remplace le min-max pur (sensible aux outliers) : 1 seule valeur extrême
    compressait tous les autres scores vers 0 ou 1.
    """
    if series is None:
        return pd.Series(dtype=float)

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.empty:
        return pd.Series(dtype=float)

    non_null = numeric.dropna()
    if non_null.empty:
        return pd.Series(np.nan, index=numeric.index, dtype=float)

    lo = float(non_null.quantile(lower_pct))
    hi = float(non_null.quantile(upper_pct))
    winsorized = numeric.clip(lo, hi)

    if np.isclose(hi, lo):
        result = pd.Series(np.nan, index=numeric.index, dtype=float)
        result.loc[non_null.index] = 0.5
        return result

    return ((winsorized - lo) / (hi - lo)).clip(0.0, 1.0)


def compute_factor_frame(
    market_data: pd.DataFrame,
    benchmark_returns: pd.DataFrame,
    config: "AlphaScannerConfig",
) -> pd.DataFrame:
    """
    Calcule MA, range 52 semaines, trend_score Minervini et VCP score.

    Fonction PURE : ne lit ni n'écrit en base. ``benchmark_returns`` doit être
    un DataFrame avec colonnes ``date`` et ``spy_return`` (cf.
    ``AlphaScanner._load_benchmark_returns``).
    """
    if market_data.empty:
        return pd.DataFrame(columns=FACTOR_COLUMNS)

    LOGGER.debug(
        "Calcul facteurs | lignes_marche=%s symboles=%s",
        len(market_data),
        market_data["symbol"].nunique(),
    )

    required = {"symbol", "date", "close", "volume"}
    missing = required.difference(market_data.columns)
    if missing:
        raise ValueError(f"Colonnes marché manquantes: {sorted(missing)}")

    prices = market_data.copy()
    prices["date"] = pd.to_datetime(prices["date"], utc=False)
    prices = prices.sort_values(["symbol", "date"]).reset_index(drop=True)
    prices["close"] = prices["close"].astype(float)
    prices["volume"] = prices["volume"].astype(float)
    prices["high"] = prices["high"].astype(float) if "high" in prices.columns else prices["close"]
    prices["low"] = prices["low"].astype(float) if "low" in prices.columns else prices["close"]
    prices["dollar_volume"] = prices["close"] * prices["volume"]
    grouped = prices.groupby("symbol", group_keys=False)
    prices["prev_close"] = grouped["close"].shift(1)
    prices["true_range"] = np.maximum.reduce(
        [
            (prices["high"] - prices["low"]).to_numpy(dtype=float),
            (prices["high"] - prices["prev_close"]).abs().fillna(0.0).to_numpy(dtype=float),
            (prices["low"] - prices["prev_close"]).abs().fillna(0.0).to_numpy(dtype=float),
        ]
    )
    prices["daily_return"] = (
        prices.groupby("symbol")["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    )

    beta_rows: list[dict[str, float | str]] = []
    for symbol, symbol_prices in prices.groupby("symbol", sort=False):
        if benchmark_returns.empty:
            beta_rows.append({"symbol": str(symbol), "beta_126": np.nan})
            continue
        merged_returns = symbol_prices[["date", "daily_return"]].merge(
            benchmark_returns, on="date", how="inner"
        )
        merged_returns = merged_returns.dropna(subset=["daily_return", "spy_return"])
        if len(merged_returns) < 30:
            beta_rows.append({"symbol": str(symbol), "beta_126": np.nan})
            continue
        tail = merged_returns.tail(126)
        variance = float(tail["spy_return"].var(ddof=0))
        if variance <= 1e-12:
            beta_rows.append({"symbol": str(symbol), "beta_126": np.nan})
            continue
        covariance = float(np.cov(tail["daily_return"], tail["spy_return"], ddof=0)[0, 1])
        beta_rows.append({"symbol": str(symbol), "beta_126": covariance / variance})

    prices["ma50"] = grouped["close"].rolling(config.ma_short_window, min_periods=config.ma_short_window).mean().reset_index(level=0, drop=True)
    prices["ma150"] = grouped["close"].rolling(config.ma_mid_window, min_periods=config.ma_mid_window).mean().reset_index(level=0, drop=True)
    prices["ma200"] = grouped["close"].rolling(config.ma_long_window, min_periods=config.ma_long_window).mean().reset_index(level=0, drop=True)
    prices["ma200_lag_20"] = prices.groupby("symbol")["ma200"].shift(20)
    prices["high_52w"] = grouped["high"].rolling(config.trailing_range_window, min_periods=config.trailing_range_window).max().reset_index(level=0, drop=True)
    prices["low_52w"] = grouped["low"].rolling(config.trailing_range_window, min_periods=config.trailing_range_window).min().reset_index(level=0, drop=True)
    prices["avg_dollar_volume_20d"] = grouped["dollar_volume"].rolling(config.liquidity_lookback_days, min_periods=config.liquidity_lookback_days).mean().reset_index(level=0, drop=True)
    prices["atr_20"] = grouped["true_range"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
    prices["atr_pct_20"] = np.where(prices["close"] > 0, prices["atr_20"] / prices["close"], np.nan)
    prices["vol_10"] = grouped["daily_return"].rolling(config.volatility_short_window, min_periods=config.volatility_short_window).std(ddof=0).reset_index(level=0, drop=True)
    prices["vol_60"] = grouped["daily_return"].rolling(config.volatility_long_window, min_periods=config.volatility_long_window).std(ddof=0).reset_index(level=0, drop=True)
    prices["volatility_ratio"] = np.where(prices["vol_60"] > 0, prices["vol_10"] / prices["vol_60"], np.nan)

    latest = grouped.tail(1).copy()
    history_days = prices.groupby("symbol")["date"].size().reset_index(name="history_days")
    latest = latest.merge(history_days, on="symbol", how="left")
    latest = latest.merge(pd.DataFrame(beta_rows), on="symbol", how="left")
    latest["high_52w_proximity"] = np.where(
        latest["high_52w"] > 0,
        latest["close"] / latest["high_52w"],
        np.nan,
    )

    weekly_feature_rows: list[dict[str, float | str]] = []
    for symbol, symbol_prices in prices.groupby("symbol", sort=False):
        weekly_close = (
            symbol_prices.set_index("date")["close"]
            .resample("W-FRI")
            .last()
            .dropna()
        )
        if weekly_close.empty:
            weekly_feature_rows.append(
                {
                    "symbol": str(symbol),
                    "weekly_close": np.nan,
                    "weekly_ma10": np.nan,
                    "weekly_ma30": np.nan,
                }
            )
            continue

        weekly_df = weekly_close.to_frame(name="weekly_close")
        weekly_df["weekly_ma10"] = weekly_df["weekly_close"].rolling(10, min_periods=10).mean()
        weekly_df["weekly_ma30"] = weekly_df["weekly_close"].rolling(30, min_periods=30).mean()
        latest_week = weekly_df.iloc[-1]
        weekly_feature_rows.append(
            {
                "symbol": str(symbol),
                "weekly_close": float(latest_week["weekly_close"]),
                "weekly_ma10": float(latest_week["weekly_ma10"]) if pd.notna(latest_week["weekly_ma10"]) else np.nan,
                "weekly_ma30": float(latest_week["weekly_ma30"]) if pd.notna(latest_week["weekly_ma30"]) else np.nan,
            }
        )

    latest = latest.merge(pd.DataFrame(weekly_feature_rows), on="symbol", how="left")

    criteria = pd.DataFrame(
        {
            "close_gt_ma150": latest["close"] > latest["ma150"],
            "close_gt_ma200": latest["close"] > latest["ma200"],
            "ma150_gt_ma200": latest["ma150"] > latest["ma200"],
            "ma200_uptrend": latest["ma200"] > latest["ma200_lag_20"],
            "close_gt_ma50": latest["close"] > latest["ma50"],
            "close_25pct_above_low52": latest["close"] >= (1.25 * latest["low_52w"]),
            "close_within_25pct_high52": latest["close"] >= (0.75 * latest["high_52w"]),
        }
    )
    latest["trend_score"] = criteria.fillna(False).astype(float).mean(axis=1)
    weekly_criteria = pd.DataFrame(
        {
            "weekly_close_gt_ma10": latest["weekly_close"] > latest["weekly_ma10"],
            "weekly_ma10_gt_ma30": latest["weekly_ma10"] > latest["weekly_ma30"],
        }
    )
    latest["weekly_trend_score"] = weekly_criteria.fillna(False).astype(float).mean(axis=1)
    latest["vcp_score"] = (
        (config.vcp_ratio_threshold - latest["volatility_ratio"]) / config.vcp_ratio_threshold
    ).clip(lower=0.0, upper=1.0)
    latest["vcp_score"] = latest["vcp_score"].fillna(0.0)

    factor_frame = latest[
        [
            "symbol",
            "date",
            "close",
            "avg_dollar_volume_20d",
            "history_days",
            "atr_20",
            "atr_pct_20",
            "beta_126",
            "ma50",
            "ma150",
            "ma200",
            "high_52w",
            "low_52w",
            "high_52w_proximity",
            "weekly_close",
            "weekly_ma10",
            "weekly_ma30",
            "weekly_trend_score",
            "volatility_ratio",
            "trend_score",
            "vcp_score",
        ]
    ].rename(columns={"close": "latest_close"})

    factor_frame["volatility_ratio"] = factor_frame["volatility_ratio"].replace([np.inf, -np.inf], np.nan)
    factor_frame["atr_pct_20"] = factor_frame["atr_pct_20"].replace([np.inf, -np.inf], np.nan)
    factor_frame["beta_126"] = factor_frame["beta_126"].replace([np.inf, -np.inf], np.nan)
    factor_frame["high_52w_proximity"] = factor_frame["high_52w_proximity"].clip(lower=0.0)
    factor_frame["trend_score"] = factor_frame["trend_score"].clip(0.0, 1.0)
    factor_frame["weekly_trend_score"] = factor_frame["weekly_trend_score"].clip(0.0, 1.0)
    factor_frame["vcp_score"] = factor_frame["vcp_score"].clip(0.0, 1.0)
    return factor_frame.reset_index(drop=True)

