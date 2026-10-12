"""Chronological daily OHLC first touches. Never invent intrabar ordering/fills."""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from modelFactory.config import OracleBarrierConfig
from modelFactory.oracle_path.labels import PRICE_COLUMNS, LINEAGE_COLUMNS, load_bars
from . import TARGETS, ANY_TARGET


def _side_events(opens, highs, lows, entry, expiry, config, side):
    """Gap open precedes intrabar extremes; a resolved trade never resurrects."""
    long = side == "long"
    tp = entry * (1 + config.take_profit_pct if long else 1 - config.take_profit_pct)
    sl = entry * (1 - config.stop_loss_pct if long else 1 + config.stop_loss_pct)
    # Include mathematical equality despite one-ULP multiplication rounding.
    def reaches(prices, level, above):
        boundary = np.nextafter(level, -np.inf if above else np.inf)[:, None]
        return prices >= boundary if above else prices <= boundary
    gap_tp = reaches(opens, tp, long)
    gap_sl = reaches(opens, sl, not long)
    touch_tp = reaches(highs if long else lows, tp, long)
    touch_sl = reaches(lows if long else highs, sl, not long)
    events = np.where(gap_tp, 1, np.where(gap_sl, 2,
             np.where(touch_tp & touch_sl, 3, np.where(touch_tp, 1, np.where(touch_sl, 2, 0)))))
    touched = (events != 0).any(axis=1)
    first = np.argmax(events != 0, axis=1)
    rows = np.arange(len(entry))
    kind = np.where(touched, events[rows, first], 0)
    at_open = touched & (gap_tp[rows, first] | gap_sl[rows, first])
    price = np.where(kind == 0, expiry, np.where(at_open, opens[rows, first],
                      np.where(kind == 1, tp, np.where(kind == 2, sl, np.nan))))
    returns = (price / entry - 1) * (1 if long else -1)
    target = np.where(kind == 3, np.nan, (kind == 1).astype(float))
    return target, np.array(["EXPIRED", "TP", "SL", "AMBIGUOUS"])[kind], first, at_open, price, returns


def symbol_barriers(bars, sessions, *, start, end, registry, config: OracleBarrierConfig):
    """Decision J; entry J+1 open; monitor J+1..J+H; time exit J+H+1 open.

    Conservative label availability J+H+2 for ALL outcomes, even early TP/SL.
    Full path + expiry bar qualification is required. Adjusted OHLC preserves
    splits, but current adjusted prices are not a historical revision/PIT proof.
    """
    symbol = str(bars.symbol.iloc[0])
    bars = bars.copy()
    bars["date"] = pd.to_datetime(bars.date).dt.normalize()
    if bars.duplicated("date").any():
        raise ValueError(f"Duplicate barrier price dates: {symbol}")
    sessions = pd.DatetimeIndex(sessions).normalize()
    if sessions.has_duplicates or not sessions.is_monotonic_increasing:
        raise ValueError("Barrier calendar must be unique and increasing")
    h = config.max_sessions
    width = h + 2  # J, entry..last holding session, expiry open
    if len(sessions) < width:
        raise ValueError("Calendar too short for barrier window")
    grid = bars.set_index("date").reindex(sessions)
    raw = grid[PRICE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    factor = raw.adj_close.where(raw.adj_close.notna(), raw.close) / raw.close
    good = (np.isfinite(raw[["open", "high", "low", "close"]]).all(axis=1)
        & raw[["open", "high", "low", "close"]].gt(0).all(axis=1)
        & raw.high.ge(raw[["open", "close", "low"]].max(axis=1))
        & raw.low.le(raw[["open", "close", "high"]].min(axis=1))
        & np.isfinite(factor) & factor.gt(0) & np.isfinite(raw.volume) & raw.volume.gt(0) & raw.is_filled.eq(0))
    membership = pd.DataFrame({"date": sessions[good], "symbol": symbol})
    membership = membership[membership.date.between(pd.Timestamp(start), pd.Timestamp(end))]
    n = len(sessions) - width + 1
    dates = sessions[:n]
    windows = {col: sliding_window_view((raw[col] * factor).to_numpy(float), width)
               for col in ("open", "high", "low", "close")}
    entry = windows["open"][:, 1]
    reasons = np.full(n, "", dtype=object)
    def reject(mask, reason):
        reasons[(reasons == "") & mask] = reason
    reject(~sliding_window_view(good.to_numpy(), width).all(axis=1), "INVALID_OR_MISSING_PATH")
    for col in LINEAGE_COLUMNS:
        codes = pd.factorize(grid[col])[0]
        lineage = sliding_window_view(codes, width)
        stable = (lineage == lineage[:, :1]).all(axis=1) & (lineage[:, 0] >= 0)
        if col != "instrument_id":
            stable &= ~grid[col].iloc[:n].astype(str).str.upper().isin(["UNKNOWN", ""]).to_numpy()
        else:
            stable &= pd.to_numeric(grid[col].iloc[:n], errors="coerce").gt(0).to_numpy()
        reject(~stable, f"UNKNOWN_OR_CHANGED_{col.upper()}")
    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = windows["close"][:, 1:] / windows["close"][:, :-1]
    reject(((ratios >= 20) | (ratios <= .05)).any(axis=1), "UNEXPLAINED_20X_PRICE_BREAK")
    for event in registry.get(symbol, ()):
        reject((dates <= event.last_predecessor_date) & (sessions[h + 1:] >= event.first_successor_date),
               "KNOWN_IDENTITY_BREAK")
    available = pd.Series(sessions).shift(-(h + 2)).iloc[:n].to_numpy()
    reject(pd.isna(available) | (available > np.datetime64(pd.Timestamp(end))), "IMMATURE_WINDOW")
    result = pd.DataFrame({"date": dates, "symbol": symbol, "path_qualified": reasons == "",
        "path_quality_reason": reasons, "entry_date": sessions[1:n + 1], "entry_price": entry,
        "expiry_date": sessions[h + 1:], "oracle_available_date": available})
    for side, target in TARGETS.items():
        values, outcomes, first, at_open, prices, returns = _side_events(
            windows["open"][:, 1:h + 1], windows["high"][:, 1:h + 1],
            windows["low"][:, 1:h + 1], entry, windows["open"][:, -1], config, side)
        qualified = (reasons == "") & (outcomes != "AMBIGUOUS")
        result[target] = np.where(qualified, values, np.nan)
        result[f"{side}_outcome"] = np.where(reasons == "", outcomes, "UNQUALIFIED")
        result[f"{side}_exit_date"] = sessions[np.where(outcomes == "EXPIRED", np.arange(n) + h + 1,
                                                       np.arange(n) + first + 1)].to_numpy()
        result[f"{side}_exit_at_open"] = at_open | (outcomes == "EXPIRED")
        result[f"{side}_exit_price"] = np.where(qualified, prices, np.nan)
        result[f"{side}_gross_return"] = np.where(qualified, returns, np.nan)
        result.loc[~qualified, f"{side}_exit_date"] = pd.NaT
        result[f"{side}_exit_at_open"] = result[f"{side}_exit_at_open"].where(qualified).astype("boolean")
    both = result[list(TARGETS.values())].notna().all(axis=1)
    result[ANY_TARGET] = result[list(TARGETS.values())].max(axis=1).where(both)
    result = result[result.date.between(pd.Timestamp(start), pd.Timestamp(end)) & good.iloc[:n].to_numpy()]
    return result.reset_index(drop=True), membership.reset_index(drop=True)
