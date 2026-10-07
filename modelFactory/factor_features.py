"""modelFactory/factor_features.py — Factor exposures from OHLCV data.

Computes CAPM-style factor loadings via rolling regression of stock
returns against benchmark (SPY) returns.  No external data required.

Features produced
-----------------
- ``beta_252``        : rolling CAPM beta (252 days)
- ``alpha_252``       : rolling CAPM alpha, annualised (252 days)
- ``r_squared_252``   : regression R², quality of fit
- ``momentum_252_vs_market`` : difference of rolling sums of paired daily returns
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
        Benchmark bars (SPY). Returns are derived from adjusted prices when
        ``close`` is present, independently of the persisted daily_return field.
        Returns-only frames remain supported. Missing dates are NOT forward-filled.
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
    dates = pd.to_datetime(df["date"])
    if bench["date"].isna().any() or bench["date"].duplicated().any():
        raise ValueError("Factor benchmark dates must be non-null and unique")
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Factor stock dates must be sorted, non-null and unique")
    if "close" in bench:
        # Local import avoids the features -> factor_features import cycle.
        from modelFactory.features import _build_adjusted_price_frame
        prices = _build_adjusted_price_frame(bench)["close"]
        prices = prices.where(np.isfinite(prices) & prices.gt(0))
        # Insert stock-observed dates missing from the benchmark BEFORE differencing:
        # otherwise the next benchmark return would silently span several sessions.
        price_dates = pd.DatetimeIndex(bench["date"]).union(pd.DatetimeIndex(dates)).sort_values()
        dated_prices = pd.Series(prices.to_numpy(), index=bench["date"]).reindex(price_dates)
        benchmark_returns = dated_prices.pct_change(fill_method=None).reindex(bench["date"])
    else:
        benchmark_returns = pd.to_numeric(
            bench.get("daily_return", pd.Series(np.nan, index=bench.index)), errors="coerce"
        )
    benchmark_returns = pd.Series(benchmark_returns.to_numpy(dtype=float), index=bench["date"])
    bench_daily = pd.Series(benchmark_returns.reindex(dates).to_numpy(), index=df.index, dtype=float)
    stock_daily = pd.to_numeric(df["daily_return"], errors="coerce").astype(float)
    paired = np.isfinite(bench_daily) & np.isfinite(stock_daily)
    missing_pairs = int((~paired).sum())
    if missing_pairs:
        LOGGER.debug("compute_factor_features: excluded %d missing/non-finite return pairs", missing_pairs)
    x = bench_daily.where(paired)
    y = stock_daily.where(paired)
    # Both rolling series use precisely the same observed pairs. Preserve the
    # historical 252-row window and 126-pair minimum; never fabricate zero returns.
    xr = x.rolling(window, min_periods=min_periods)
    yr = y.rolling(window, min_periods=min_periods)
    var_x = xr.var(ddof=0)
    var_y = yr.var(ddof=0)
    cov_xy = xr.cov(y, ddof=0)
    estimable = var_x.gt(1e-12)
    beta = (cov_xy / var_x.where(estimable)).where(estimable)
    alpha = ((yr.mean() - beta * xr.mean()) * 252).where(estimable)
    rsq = (cov_xy.pow(2) / (var_x * var_y).where(estimable & var_y.gt(1e-12))).clip(0, 1)
    df["beta_252"] = beta.replace([np.inf, -np.inf], np.nan).fillna(FACTOR_DEFAULTS["beta_252"])
    df["alpha_252"] = alpha.replace([np.inf, -np.inf], np.nan).fillna(FACTOR_DEFAULTS["alpha_252"])
    df["r_squared_252"] = rsq.replace([np.inf, -np.inf], np.nan).fillna(FACTOR_DEFAULTS["r_squared_252"])

    # ── Momentum 252d vs market ──
    stock_mom_252 = yr.sum()
    market_mom_252 = xr.sum()
    df["momentum_252_vs_market"] = stock_mom_252 - market_mom_252
    df["momentum_252_vs_market"] = pd.to_numeric(df["momentum_252_vs_market"], errors="coerce").fillna(0.0).astype(float)

    return df


def fill_factor_defaults(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all factor columns exist with sensible defaults."""
    for col, default in FACTOR_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default).astype(float)
            df[col] = df[col].replace([np.inf, -np.inf], default)
    return df


__all__ = [
    "FACTOR_FEATURE_COLUMNS",
    "FACTOR_DEFAULTS",
    "compute_factor_features",
    "fill_factor_defaults",
]
