"""Read-only, exchange-session aligned path targets. No legacy label persistence."""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from sqlalchemy import bindparam, text

from modelFactory.oracle_path import HORIZON, TARGET

PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume", "is_filled"]
LINEAGE_COLUMNS = ["instrument_id", "data_source", "data_adjustment"]


def load_bars(engine, symbols, start, end):
    """Archive actual source/identity columns, unlike the minimal feature loader."""
    query = text("SELECT symbol, `date`, `open`, high, low, `close`, adj_close, volume, "
                 "is_filled, instrument_id, data_source, data_adjustment FROM stock_bars_daily "
                 "WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end ORDER BY symbol, `date`"
                 ).bindparams(bindparam("symbols", expanding=True))
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"symbols": symbols, "start": start, "end": end},
                           parse_dates=["date"])


def symbol_paths(bars, sessions, *, start, end, registry):
    """J close adjusted baseline, future HIGH/LOW in exactly J+1..J+20.

    Prices are on the same adjustment basis. Even an early peak is not an early
    available label: the full window matures only at J+21. No forward filling.
    """
    symbol = str(bars.symbol.iloc[0])
    bars = bars.copy()
    bars["date"] = pd.to_datetime(bars.date).dt.normalize()
    if bars.duplicated("date").any():
        raise ValueError(f"Duplicate price dates: {symbol}")
    sessions = pd.DatetimeIndex(sessions).normalize()
    grid = bars.set_index("date").reindex(sessions)
    raw = grid[PRICE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    adjusted = raw.adj_close.where(raw.adj_close.notna(), raw.close)
    factor = adjusted / raw.close
    good = (np.isfinite(raw[["open", "high", "low", "close"]]).all(axis=1)
            & raw[["open", "high", "low", "close"]].gt(0).all(axis=1)
            & raw.high.ge(raw[["open", "close", "low"]].max(axis=1))
            & raw.low.le(raw[["open", "close", "high"]].min(axis=1))
            & np.isfinite(factor) & factor.gt(0) & raw.volume.gt(0) & raw.is_filled.eq(0))
    # Membership/ranks at J do NOT depend on future missing bars.
    membership = pd.DataFrame({"date": sessions[good], "symbol": symbol})
    membership = membership[membership.date.between(pd.Timestamp(start), pd.Timestamp(end))]
    n = len(sessions) - HORIZON
    if n <= 0:
        raise ValueError("Calendar too short for H20")
    dates = sessions[:n]
    with np.errstate(divide="ignore", invalid="ignore"):
        closes = sliding_window_view(adjusted.to_numpy(float), HORIZON + 1)
        highs = sliding_window_view((raw.high * factor).to_numpy(float), HORIZON + 1)[:, 1:]
        lows = sliding_window_view((raw.low * factor).to_numpy(float), HORIZON + 1)[:, 1:]
        up = np.maximum(0, highs.max(axis=1) / closes[:, 0] - 1)
        down = np.maximum(0, 1 - lows.min(axis=1) / closes[:, 0])
        ratios = closes[:, 1:] / closes[:, :-1]
        terminal = closes[:, -1] / closes[:, 0] - 1
    reasons = np.full(n, "", dtype=object)

    def reject(mask, reason):
        reasons[(reasons == "") & mask] = reason

    reject(~sliding_window_view(good.to_numpy(), HORIZON + 1).all(axis=1), "INVALID_OR_MISSING_PATH")
    for col in LINEAGE_COLUMNS:
        codes = pd.factorize(grid[col])[0]
        windows = sliding_window_view(codes, HORIZON + 1)
        stable = (windows == windows[:, :1]).all(axis=1) & (windows[:, 0] >= 0)
        if col != "instrument_id":
            stable &= ~grid[col].iloc[:n].astype(str).str.upper().isin(["UNKNOWN", ""]).to_numpy()
        reject(~stable, f"UNKNOWN_OR_CHANGED_{col.upper()}")
    reject(((ratios >= 20) | (ratios <= .05)).any(axis=1), "UNEXPLAINED_20X_PRICE_BREAK")
    for event in registry.get(symbol, ()):
        reject((dates <= event.last_predecessor_date) & (sessions[HORIZON:] >= event.first_successor_date),
               "KNOWN_IDENTITY_BREAK")
    available = pd.Series(sessions).shift(-(HORIZON + 1)).iloc[:n].to_numpy()
    reject(pd.isna(available) | (available > np.datetime64(pd.Timestamp(end))), "IMMATURE_WINDOW")
    result = pd.DataFrame({"date": dates, "symbol": symbol,
        "path_qualified": reasons == "", "path_quality_reason": reasons,
        "oracle_exit_date": sessions[HORIZON:], "oracle_available_date": available,
        "up_excursion": up, "down_excursion": down, "path_amplitude": np.maximum(up, down),
        "terminal_return": terminal})
    result = result[result.date.between(pd.Timestamp(start), pd.Timestamp(end)) & good.iloc[:n].to_numpy()]
    for col in ("up_excursion", "down_excursion", "path_amplitude", "terminal_return"):
        result.loc[~result.path_qualified, col] = np.nan
    return result.reset_index(drop=True), membership.reset_index(drop=True)


def classify(labels, min_universe=20, min_coverage=.95):
    """Daily TOP20% by absolute path amplitude; ties never get arbitrary symbol labels.

    Threshold ties are all included (prevalence can exceed 20%); a constant
    cross-section is uninformative and excluded. Rank denominators are frozen
    from valid observations at J, not from a future-selected feature population.
    """
    result = labels.copy()
    grouped = result.groupby("date")
    result["daily_count"] = grouped.symbol.transform("size")
    result["daily_coverage"] = grouped.path_qualified.transform("mean")
    rank = result.path_amplitude.groupby(result.date).rank(method="max", pct=True)
    distinct = grouped.path_amplitude.transform("nunique")
    eligible = (result.path_qualified & result.daily_count.ge(min_universe)
                & result.daily_coverage.ge(min_coverage) & distinct.gt(1))
    result[TARGET] = (rank > .8).astype(float).where(eligible)
    result["path_amplitude_rank"] = rank
    return result
