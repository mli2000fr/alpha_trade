from datetime import datetime, timezone

import numpy as np
import pandas as pd

from screener.models import ScreenerConfig


RESULT_COLUMNS = [
    "symbol",
    "liquidity_val",
    "relative_strength_index",
    "historical_range_score",
    "total_score",
    "last_updated_score",
    "is_candidate",
    "sector",
    "last_updated_scan",
]


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(columns=RESULT_COLUMNS)


def compute_scores_from_prices(
    prices_df: pd.DataFrame,
    spy_return_6m: float,
    config: ScreenerConfig,
) -> pd.DataFrame:
    if prices_df.empty:
        return _empty_result()

    prices = prices_df.copy()
    prices["timestamp"] = pd.to_datetime(prices["timestamp"], utc=False)
    prices = prices.sort_values(["symbol", "timestamp"])
    prices["dollar_volume"] = prices["volume"].astype(float) * prices["close_price"].astype(float)

    # Passage 1 - Liquidite moyenne sur les N dernieres barres.
    recent_liquidity = prices.groupby("symbol", group_keys=False).tail(config.lookback_liquidity_bars)
    liquidity = (
        recent_liquidity.groupby("symbol", as_index=False)["dollar_volume"]
        .mean()
        .rename(columns={"dollar_volume": "liquidity_val"})
    )
    p1 = liquidity[liquidity["liquidity_val"] >= config.liquidity_threshold_usd].copy()
    if p1.empty:
        return _empty_result()

    prices_p1 = prices[prices["symbol"].isin(p1["symbol"])].copy()

    # Passage 2 - Relative strength versus SPY sur 6 mois.
    latest_ts = prices_p1["timestamp"].max()
    rel_cutoff = latest_ts - pd.Timedelta(days=config.lookback_relative_days)
    rel_window = prices_p1[prices_p1["timestamp"] >= rel_cutoff].copy()
    if rel_window.empty:
        return _empty_result()

    rel_agg = (
        rel_window.groupby("symbol", as_index=False)
        .agg(
            start_close=("close_price", "first"),
            end_close=("close_price", "last"),
            bars=("close_price", "size"),
        )
    )
    rel_agg = rel_agg[rel_agg["bars"] >= 2].copy()
    if rel_agg.empty:
        return _empty_result()

    rel_agg["stock_return"] = (rel_agg["end_close"] / rel_agg["start_close"]) - 1.0
    if spy_return_6m <= -0.9999:
        return _empty_result()

    rel_agg["relative_strength_index"] = (
        ((1.0 + rel_agg["stock_return"]) / (1.0 + spy_return_6m)) * 100.0
    )
    rel_agg = rel_agg.replace([np.inf, -np.inf], np.nan).dropna(subset=["relative_strength_index"])
    p2 = p1.merge(rel_agg[["symbol", "relative_strength_index"]], on="symbol", how="inner")
    if p2.empty:
        return _empty_result()

    # Passage 3 - Position dans le range historique 10 ans.
    prices_p2 = prices[prices["symbol"].isin(p2["symbol"])].copy()
    hist_agg = prices_p2.groupby("symbol", as_index=False).agg(
        hist_low=("low_price", "min"),
        hist_high=("high_price", "max"),
    )
    last_close = prices_p2.groupby("symbol", group_keys=False).tail(1)[["symbol", "close_price"]]
    hist = hist_agg.merge(last_close, on="symbol", how="inner")

    span = hist["hist_high"] - hist["hist_low"]
    hist["historical_range_score"] = np.where(
        span > 0,
        ((hist["close_price"] - hist["hist_low"]) / span) * 100.0,
        50.0,
    )
    hist["historical_range_score"] = hist["historical_range_score"].clip(0.0, 100.0)

    scored = p2.merge(hist[["symbol", "historical_range_score"]], on="symbol", how="inner")
    if scored.empty:
        return _empty_result()

    scored["liquidity_score"] = scored["liquidity_val"].rank(pct=True) * 100.0
    scored["total_score"] = (
        scored["liquidity_score"] * config.weight_liquidity
        + scored["relative_strength_index"] * config.weight_relative_strength
        + scored["historical_range_score"] * config.weight_historical_range
    )
    calculated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    scored["last_updated_score"] = calculated_at
    scored["is_candidate"] = 0
    scored["sector"] = None
    scored["last_updated_scan"] = calculated_at

    result = scored[RESULT_COLUMNS].copy()
    result = result.sort_values("total_score", ascending=False).reset_index(drop=True)
    return result

