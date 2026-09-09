"""Univers Oracle quotidien PIT construit uniquement depuis les barres disponibles."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd
from sqlalchemy import bindparam, text


@dataclass(frozen=True, slots=True)
class DynamicUniverseThresholds:
    min_real_sessions: int = 504
    min_price: float = 10.0
    volume_window: int = 20
    min_avg_volume: float = 100_000.0
    min_avg_dollar_volume: float = 10_000_000.0
    filled_window: int = 252
    max_filled_ratio: float = 0.02


def compute_dynamic_membership(bars: pd.DataFrame, *, start_date: str, end_date: str,
                               thresholds: DynamicUniverseThresholds | None = None
                               ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Retourne les couples ``date/symbol`` admis par les gates P0b."""
    limits = thresholds or DynamicUniverseThresholds()
    required = {"symbol", "date", "close", "volume", "is_filled"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"Barres incompatibles avec l'univers dynamique: {sorted(missing)}")
    if bars.empty:
        return pd.DataFrame(columns=["date", "symbol"]), {
            "thresholds": asdict(limits), "rows": 0, "dates": 0, "symbols": 0,
            "daily_min": 0, "daily_median": 0, "daily_max": 0,
        }
    frame = bars.loc[:, ["symbol", "date", "close", "volume", "is_filled"]].copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ("close", "volume", "is_filled"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "symbol"]).sort_values(["symbol", "date"])
    frame = frame.drop_duplicates(["symbol", "date"], keep="last")
    frame["real_bar"] = frame["close"].notna() & frame["volume"].notna() & frame["is_filled"].fillna(0).ne(1)
    frame["real_sessions"] = frame.groupby("symbol", sort=False)["real_bar"].cumsum()
    frame["volume_real"] = frame["volume"].where(frame["real_bar"])
    frame["dollar_volume_real"] = (frame["close"] * frame["volume"]).where(frame["real_bar"])
    grouped = frame.groupby("symbol", sort=False)
    frame["avg_volume_20"] = grouped["volume_real"].transform(
        lambda values: values.rolling(limits.volume_window, min_periods=limits.volume_window).mean())
    frame["avg_dollar_volume_20"] = grouped["dollar_volume_real"].transform(
        lambda values: values.rolling(limits.volume_window, min_periods=limits.volume_window).mean())
    frame["filled_ratio_252"] = grouped["is_filled"].transform(
        lambda values: values.fillna(0).eq(1).rolling(
            limits.filled_window, min_periods=limits.filled_window).mean())
    admitted = (
        frame["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        & frame["real_bar"]
        & frame["real_sessions"].ge(limits.min_real_sessions)
        & frame["close"].ge(limits.min_price)
        & frame["avg_volume_20"].ge(limits.min_avg_volume)
        & frame["avg_dollar_volume_20"].ge(limits.min_avg_dollar_volume)
        & frame["filled_ratio_252"].le(limits.max_filled_ratio)
    )
    membership = frame.loc[admitted, ["date", "symbol"]].reset_index(drop=True)
    daily = membership.groupby("date").size() if not membership.empty else pd.Series(dtype=int)
    return membership, {
        "thresholds": asdict(limits), "rows": int(len(membership)),
        "dates": int(membership["date"].nunique()), "symbols": int(membership["symbol"].nunique()),
        "daily_min": int(daily.min()) if not daily.empty else 0,
        "daily_median": int(daily.median()) if not daily.empty else 0,
        "daily_max": int(daily.max()) if not daily.empty else 0,
    }


def load_dynamic_universe_from_bars(engine: Any, symbols: list[str], *, start_date: str,
                                    end_date: str,
                                    thresholds: DynamicUniverseThresholds | None = None
                                    ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Charge le warm-up nécessaire puis calcule l'admission quotidienne P0b."""
    normalized = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    if not normalized:
        return compute_dynamic_membership(
            pd.DataFrame(columns=["symbol", "date", "close", "volume", "is_filled"]),
            start_date=start_date, end_date=end_date, thresholds=thresholds)
    query = text(
        "SELECT symbol,`date`,COALESCE(adj_close,close) AS close,volume,is_filled "
        "FROM stock_bars_daily WHERE symbol IN :symbols AND `date` <= :end_date "
        "ORDER BY symbol,`date`"
    ).bindparams(bindparam("symbols", expanding=True))
    with engine.connect() as connection:
        bars = pd.read_sql(query, connection, params={"symbols": normalized, "end_date": end_date})
    return compute_dynamic_membership(
        bars, start_date=start_date, end_date=end_date, thresholds=thresholds)
