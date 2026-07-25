"""modelFactory/factor_features.py — Factor exposures from OHLCV data.

Computes CAPM-style factor loadings via rolling regression of stock
returns against benchmark (SPY) returns.  No external data required.

Features produced
-----------------
- ``beta_252``        : rolling CAPM beta (252 days)
- ``alpha_252``       : rolling CAPM alpha, annualised (252 days)
- ``r_squared_252``   : regression R², quality of fit
- ``momentum_252_vs_market`` : stock 252d return minus market 252d return
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

FACTOR_FEATURE_COLUMNS: list[str] = [
    "beta_252",
    "alpha_252",
    "r_squared_252",
    "momentum_252_vs_market",
]

FACTOR_DEFAULTS: dict[str, float] = {
    "beta_252": 1.0,
    "alpha_252": 0.0,
    "r_squared_252": 0.0,
    "momentum_252_vs_market": 0.0,
}


def compute_factor_features(
    df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute CAPM factor exposures and append to ``df``.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: date, daily_return.  Already sorted by date.
    benchmark_df : pd.DataFrame or None
        Benchmark bars (SPY).  Must have date, daily_return.
        If None, beta defaults to 1.0, alpha to 0.0.

    Returns
    -------
    pd.DataFrame
        ``df`` with ``FACTOR_FEATURE_COLUMNS`` appended.
    """
    df = df.copy()
    window = 252
    min_periods = 126  # ~6 months minimum

    if benchmark_df is None or benchmark_df.empty:
        LOGGER.info("compute_factor_features: no benchmark, using defaults")
        for col, default in FACTOR_DEFAULTS.items():
            df[col] = default
        return df

    # ── Align benchmark returns on stock dates ──
    bench = benchmark_df.copy().sort_values("date").reset_index(drop=True)
    bench["date"] = pd.to_datetime(bench["date"])
    bench_returns = (
        bench.set_index("date")
        .reindex(pd.to_datetime(df["date"]), method="ffill")
        .reset_index()
    )
    bench_daily = bench_returns.get("daily_return", pd.Series(0.0, index=df.index))
    if isinstance(bench_daily, pd.DataFrame):
        bench_daily = bench_daily.iloc[:, 0] if bench_daily.shape[1] > 0 else pd.Series(0.0, index=df.index)
    bench_daily = pd.Series(bench_daily).fillna(0.0).astype(float).values

    stock_daily = df["daily_return"].fillna(0.0).astype(float).values
    n = len(stock_daily)

    beta_arr = np.full(n, 1.0)
    alpha_arr = np.full(n, 0.0)
    rsq_arr = np.full(n, 0.0)

    for i in range(n):
        start = max(0, i - window + 1)
        length = i - start + 1
        if length < min_periods:
            continue
        x = bench_daily[start : i + 1]
        y = stock_daily[start : i + 1]

        # Simple OLS: beta = cov(x,y)/var(x), alpha = mean(y) - beta*mean(x)
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        x_demean = x - x_mean
        y_demean = y - y_mean
        cov_xy = np.dot(x_demean, y_demean) / length
        var_x = np.dot(x_demean, x_demean) / length
        var_y = np.dot(y_demean, y_demean) / length

        if var_x > 1e-12:
            beta = cov_xy / var_x
            alpha_daily = y_mean - beta * x_mean
            beta_arr[i] = beta
            alpha_arr[i] = alpha_daily * 252  # annualised
            if var_y > 1e-12:
                rsq_arr[i] = (cov_xy ** 2) / (var_x * var_y)

    df["beta_252"] = beta_arr
    df["alpha_252"] = alpha_arr
    df["r_squared_252"] = rsq_arr

    # ── Momentum 252d vs market ──
    stock_mom_252 = df["daily_return"].rolling(window=window, min_periods=min_periods).sum()
    market_mom_252 = pd.Series(bench_daily, index=df.index).rolling(
        window=window, min_periods=min_periods
    ).sum()
    df["momentum_252_vs_market"] = stock_mom_252 - market_mom_252
    df["momentum_252_vs_market"] = df["momentum_252_vs_market"].fillna(0.0)

    return df


def fill_factor_defaults(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all factor columns exist with sensible defaults."""
    for col, default in FACTOR_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
        else:
            df[col] = df[col].fillna(default).astype(float)
            df[col] = df[col].replace([np.inf, -np.inf], default)
    return df


__all__ = [
    "FACTOR_FEATURE_COLUMNS",
    "FACTOR_DEFAULTS",
    "compute_factor_features",
    "fill_factor_defaults",
]
