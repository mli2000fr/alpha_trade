from datetime import date, datetime, timezone
from typing import Optional

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
CANDIDATE_COLUMNS = [
    "symbol",
    "liquidity_val",
    "relative_strength_index",
    "latest_close",
]
HISTORICAL_RANGE_COLUMNS = ["symbol", "hist_low", "hist_high"]


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(columns=RESULT_COLUMNS)


def _empty_candidates() -> pd.DataFrame:
    return pd.DataFrame(columns=CANDIDATE_COLUMNS)


def _empty_historical_range() -> pd.DataFrame:
    return pd.DataFrame(columns=HISTORICAL_RANGE_COLUMNS)


def _percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.empty:
        return pd.Series(dtype=float)
    if numeric.notna().sum() == 0:
        return pd.Series(np.nan, index=numeric.index, dtype=float)
    return numeric.rank(method="average", pct=True) * 100.0


def _prepare_prices(prices_df: pd.DataFrame, as_of_date: Optional[date] = None) -> pd.DataFrame:
    if prices_df.empty:
        return pd.DataFrame()

    prices = prices_df.copy()
    prices["timestamp"] = pd.to_datetime(prices["timestamp"], utc=False)
    prices = prices.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    if as_of_date is not None:
        cutoff_ts = pd.Timestamp(as_of_date)
        prices = prices[prices["timestamp"] <= cutoff_ts].copy()
        if prices.empty:
            return pd.DataFrame()

    return prices


def screen_recent_prices(
    prices_df: pd.DataFrame,
    spy_return_6m: float,
    config: ScreenerConfig,
    as_of_date: Optional[date] = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Passe 1 du screener: historique minimal, prix minimal, liquidité, force relative."""
    prices = _prepare_prices(prices_df, as_of_date=as_of_date)
    metrics = {
        "input_symbols": int(prices["symbol"].nunique()) if not prices.empty else 0,
        "symbols_pass_history": 0,
        "symbols_pass_liquidity": 0,
        "symbols_pass_relative_strength": 0,
    }
    if prices.empty:
        return _empty_candidates(), metrics

    history_agg = (
        prices.groupby("symbol", as_index=False)
        .agg(
            history_days=("timestamp", "size"),
            latest_close=("close_price", "last"),
        )
    )
    history_eligible = history_agg[
        (history_agg["history_days"] >= config.min_history_days)
        & (pd.to_numeric(history_agg["latest_close"], errors="coerce") >= config.min_close_price)
    ].copy()
    metrics["symbols_pass_history"] = len(history_eligible)
    if history_eligible.empty:
        return _empty_candidates(), metrics

    prices = prices[prices["symbol"].isin(history_eligible["symbol"])].copy()
    prices["dollar_volume"] = prices["volume"].astype(float) * prices["close_price"].astype(float)

    recent_liquidity = prices.groupby("symbol", group_keys=False).tail(config.lookback_liquidity_bars)
    liquidity = (
        recent_liquidity.groupby("symbol", as_index=False)["dollar_volume"]
        .mean()
        .rename(columns={"dollar_volume": "liquidity_val"})
    )
    p1 = liquidity[liquidity["liquidity_val"] >= config.liquidity_threshold_usd].copy()
    metrics["symbols_pass_liquidity"] = len(p1)
    if p1.empty:
        return _empty_candidates(), metrics

    if spy_return_6m <= -0.9999:
        return _empty_candidates(), metrics

    prices_p1 = prices[prices["symbol"].isin(p1["symbol"])].copy()
    latest_ts = prices_p1["timestamp"].max()
    rel_cutoff = latest_ts - pd.Timedelta(days=config.lookback_relative_days)
    rel_window = prices_p1[prices_p1["timestamp"] >= rel_cutoff].copy()
    if rel_window.empty:
        return _empty_candidates(), metrics

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
        return _empty_candidates(), metrics

    rel_agg["stock_return"] = (rel_agg["end_close"] / rel_agg["start_close"]) - 1.0
    rel_agg["relative_strength_index"] = (
        ((1.0 + rel_agg["stock_return"]) / (1.0 + spy_return_6m)) * 100.0
    )
    rel_agg = rel_agg.replace([np.inf, -np.inf], np.nan).dropna(subset=["relative_strength_index"])
    p2 = p1.merge(rel_agg[["symbol", "relative_strength_index"]], on="symbol", how="inner")
    metrics["symbols_pass_relative_strength"] = len(p2)
    if p2.empty:
        return _empty_candidates(), metrics

    last_close = (
        prices_p1.groupby("symbol", group_keys=False)
        .tail(1)[["symbol", "close_price"]]
        .rename(columns={"close_price": "latest_close"})
    )
    candidates = p2.merge(last_close, on="symbol", how="inner")
    return candidates.loc[:, CANDIDATE_COLUMNS].copy(), metrics


def compute_historical_range_stats_from_prices(
    prices_df: pd.DataFrame,
    symbols: list[str],
    as_of_date: Optional[date] = None,
) -> pd.DataFrame:
    prices = _prepare_prices(prices_df, as_of_date=as_of_date)
    if prices.empty or not symbols:
        return _empty_historical_range()

    hist_agg = (
        prices[prices["symbol"].isin(symbols)]
        .groupby("symbol", as_index=False)
        .agg(
            hist_low=("low_price", "min"),
            hist_high=("high_price", "max"),
        )
    )
    return hist_agg.loc[:, HISTORICAL_RANGE_COLUMNS].copy() if not hist_agg.empty else _empty_historical_range()


def finalize_scores_with_historical_range(
    candidate_df: pd.DataFrame,
    historical_range_df: pd.DataFrame,
    config: ScreenerConfig,
) -> pd.DataFrame:
    if candidate_df.empty or historical_range_df.empty:
        return _empty_result()

    hist = historical_range_df.merge(candidate_df[["symbol", "latest_close"]], on="symbol", how="inner")
    if hist.empty:
        return _empty_result()

    span = hist["hist_high"] - hist["hist_low"]
    hist["historical_range_score"] = np.where(
        span > 0,
        ((hist["latest_close"] - hist["hist_low"]) / span) * 100.0,
        50.0,
    )
    hist["historical_range_score"] = hist["historical_range_score"].clip(0.0, 100.0)

    scored = candidate_df.merge(hist[["symbol", "historical_range_score"]], on="symbol", how="inner")
    if scored.empty:
        return _empty_result()

    scored["liquidity_score"] = _percentile_score(scored["liquidity_val"])
    scored["relative_strength_score"] = _percentile_score(scored["relative_strength_index"])
    scored["historical_range_percentile"] = _percentile_score(scored["historical_range_score"])
    weight_sum = (
        config.weight_liquidity
        + config.weight_relative_strength
        + config.weight_historical_range
    )
    scored["total_score"] = (
        scored["liquidity_score"] * config.weight_liquidity
        + scored["relative_strength_score"] * config.weight_relative_strength
        + scored["historical_range_percentile"] * config.weight_historical_range
    ) / weight_sum
    calculated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    scored["last_updated_score"] = calculated_at
    scored["is_candidate"] = 0
    scored["sector"] = None
    scored["last_updated_scan"] = calculated_at

    result = scored[RESULT_COLUMNS].copy()
    return result.sort_values("total_score", ascending=False).reset_index(drop=True)


def compute_scores_from_prices(
    prices_df: pd.DataFrame,
    spy_return_6m: float,
    config: ScreenerConfig,
    as_of_date: Optional[date] = None,
) -> pd.DataFrame:
    """
    Calcule les scores screener à partir des données de prix.

    :param prices_df: DataFrame multi-symboles avec colonnes [symbol, timestamp, close_price, …]
    :param spy_return_6m: Rendement SPY sur la fenêtre relative (précalculé, borné à as_of_date)
    :param config: Paramètres screener
    :param as_of_date: Date de référence pour l'évaluation (point-in-time).
        Toutes les données postérieures à cette date sont EXCLUES afin d'éviter
        tout look-ahead bias en backtest. Si None, on utilise le timestamp max disponible.
    """
    if prices_df.empty:
        return _empty_result()

    candidates, _ = screen_recent_prices(
        prices_df,
        spy_return_6m=spy_return_6m,
        config=config,
        as_of_date=as_of_date,
    )
    if candidates.empty:
        return _empty_result()

    historical_range_df = compute_historical_range_stats_from_prices(
        prices_df,
        symbols=candidates["symbol"].astype(str).tolist(),
        as_of_date=as_of_date,
    )
    return finalize_scores_with_historical_range(candidates, historical_range_df, config)
