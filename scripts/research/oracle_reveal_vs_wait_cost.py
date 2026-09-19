"""Read-only Oracle TOP20 H20 revelation versus cost of delayed entry.

Descriptive research. The day-J Oracle OOF panel and labels are frozen inputs.
No tuning, model fitting, portfolio simulation, database write, or serving change.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars


DEFAULT_EVENTS = Path(
    "artifacts/research/oracle_opening_price_confirmation/"
    "e20b-opening-price-only-20260914051444/oracle_price_only_events.parquet"
)
DEFAULT_OUTPUT = Path("artifacts/research/oracle_reveal_vs_wait_cost/e20b-h20")
DAYS = tuple(range(1, 20))


def price_panel(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars[["symbol", "date", "open", "close", "adj_close"]].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ("open", "close", "adj_close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    factor = frame["adj_close"] / frame["close"].replace(0, np.nan)
    frame["px_close"] = frame["adj_close"].where(frame["adj_close"].gt(0), frame["close"])
    frame["px_open"] = (frame["open"] * factor).where(factor.gt(0), frame["open"])
    frame = frame.dropna(subset=["px_close", "px_open"])
    frame = frame[frame["px_close"].gt(0) & frame["px_open"].gt(0)]
    frame = frame.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"])
    grouped = frame.groupby("symbol", sort=False)
    frame["entry_open"] = grouped["px_open"].shift(-1)
    frame["exit_open"] = grouped["px_open"].shift(-21)
    for n in DAYS:
        frame[f"close_{n}"] = grouped["px_close"].shift(-n)
        frame[f"entry_open_{n}"] = grouped["px_open"].shift(-(n + 1))
    return frame


def policy_rows(events: pd.DataFrame, n: int, threshold: float, cost: float) -> pd.DataFrame:
    required = ["px_close", "entry_open", "exit_open", f"close_{n}", f"entry_open_{n}"]
    frame = events.dropna(subset=required).copy()
    frame = frame[(frame["entry_open"] > 0) & (frame[f"entry_open_{n}"] > 0)]
    frame["observed_return"] = frame[f"close_{n}"] / frame["px_close"] - 1.0
    frame["side"] = np.select(
        [frame["observed_return"] >= threshold, frame["observed_return"] <= -threshold],
        [1, -1], default=0,
    )
    frame["immediate_long_net"] = frame["exit_open"] / frame["entry_open"] - 1.0 - cost
    frame["delayed_long_net"] = frame["exit_open"] / frame[f"entry_open_{n}"] - 1.0 - cost
    frame["immediate_signed_net"] = np.where(
        frame["side"] == 1, frame["immediate_long_net"],
        np.where(frame["side"] == -1, -frame["immediate_long_net"] - 2 * cost, 0.0),
    )
    frame["delayed_signed_net"] = np.where(
        frame["side"] == 1, frame["delayed_long_net"],
        np.where(frame["side"] == -1, -frame["delayed_long_net"] - 2 * cost, 0.0),
    )
    return frame


def summarize(frame: pd.DataFrame, n: int, period: str, threshold: float, cost: float) -> dict:
    traded = frame[frame["side"] != 0]
    tails = traded[traded["oracle_decile"].isin([1, 10])]
    long = traded[traded["side"] == 1]
    short = traded[traded["side"] == -1]
    long_tails = tails[tails["side"] == 1]
    short_tails = tails[tails["side"] == -1]
    d1_short = short[short["oracle_decile"] == 1]

    def mean(group: pd.DataFrame, column: str) -> float | None:
        return float(group[column].mean()) if len(group) else None

    def fraction(group: pd.DataFrame, decile: int) -> float | None:
        return float(group["oracle_decile"].eq(decile).mean()) if len(group) else None

    def day_mean(group: pd.DataFrame, column: str) -> float | None:
        if group.empty:
            return None
        return float(group.groupby("date")[column].mean().mean())

    return {
        "period": period, "n": n, "threshold": threshold,
        "events": int(len(frame)), "trades": int(len(traded)),
        "coverage": float(len(traded) / len(frame)) if len(frame) else None,
        "long_count": int(len(long)), "short_count": int(len(short)),
        "tail_count_traded": int(len(tails)),
        "p_d10_given_long_all": fraction(long, 10),
        "p_d1_given_short_all": fraction(short, 1),
        "p_d10_given_long_tail": fraction(long_tails, 10),
        "p_d1_given_short_tail": fraction(short_tails, 1),
        "signed_immediate_net_event": mean(traded, "immediate_signed_net"),
        "signed_delayed_net_event": mean(traded, "delayed_signed_net"),
        "signed_wait_delta_event": mean(traded.assign(
            delta=traded["delayed_signed_net"] - traded["immediate_signed_net"]
        ), "delta"),
        "signed_immediate_net_equal_date": day_mean(frame, "immediate_signed_net"),
        "signed_delayed_net_equal_date": day_mean(frame, "delayed_signed_net"),
        "long_only_immediate_net_equal_date": day_mean(frame.assign(
            long_only=np.where(frame["side"] == 1, frame["immediate_long_net"], 0.0)
        ), "long_only"),
        "long_only_delayed_net_equal_date": day_mean(frame.assign(
            long_only=np.where(frame["side"] == 1, frame["delayed_long_net"], 0.0)
        ), "long_only"),
        "long_selected_immediate_net": mean(long, "immediate_long_net"),
        "long_selected_delayed_net": mean(long, "delayed_long_net"),
        "oracle_long_immediate_net_equal_date": day_mean(frame, "immediate_long_net"),
        "oracle_long_delayed_net_equal_date": day_mean(frame, "delayed_long_net"),
        "d10_long_immediate_net": mean(long[long["oracle_decile"] == 10], "immediate_long_net"),
        "d10_long_delayed_net": mean(long[long["oracle_decile"] == 10], "delayed_long_net"),
        "d1_long_immediate_net": mean(long[long["oracle_decile"] == 1], "immediate_long_net"),
        "d1_long_delayed_net": mean(long[long["oracle_decile"] == 1], "delayed_long_net"),
        "d1_short_immediate_net": mean(d1_short, "immediate_signed_net"),
        "d1_short_delayed_net": mean(d1_short, "delayed_signed_net"),
        "remaining_long_hit_rate": float(long["delayed_long_net"].gt(0).mean()) if len(long) else None,
        "remaining_short_hit_rate": float(short["delayed_long_net"].lt(-2 * cost).mean()) if len(short) else None,
    }


def run(events_path: Path, output: Path, threshold: float = 0.005, cost: float = 0.0006) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite research output: {output}")
    columns = ["date", "symbol", "directional_oracle_eligible", "oracle_decile", "target_quality_valid"]
    events = pd.read_parquet(events_path, columns=columns)
    events = events[events["directional_oracle_eligible"].eq(True) & events["target_quality_valid"].eq(1)]
    events = events[events["oracle_decile"].between(1, 10)].copy()
    events["date"] = pd.to_datetime(events["date"]).dt.normalize()
    if events.duplicated(["date", "symbol"]).any():
        raise ValueError("Duplicate Oracle event keys")
    symbols = sorted(events["symbol"].unique())
    start = events["date"].min().date()
    end = (events["date"].max() + pd.offsets.BDay(35)).date()
    print(f"Loading daily bars: {len(symbols)} symbols, {start}..{end}", flush=True)
    bars = load_universe_bars(get_sqlalchemy_engine(), symbols, start_date=start, end_date=end)
    prices = price_panel(bars)
    keep = ["date", "symbol", "px_close", "entry_open", "exit_open"]
    for n in DAYS:
        keep.extend([f"close_{n}", f"entry_open_{n}"])
    loaded_bar_count = len(bars)
    joined = events.merge(prices[keep], on=["date", "symbol"], how="left", validate="one_to_one")
    del bars, prices
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for n in DAYS:
        frame = policy_rows(joined, n, threshold, cost)
        for period, subset in (
            ("all", frame),
            ("development_2018_2023", frame[frame["date"] < "2024-01-01"]),
            ("control_2024_2025", frame[frame["date"] >= "2024-01-01"]),
        ):
            rows.append(summarize(subset, n, period, threshold, cost))
        print(f"J+{n}: eligible={len(frame)} traded={(frame['side'] != 0).sum()}", flush=True)
    result = pd.DataFrame(rows)
    result.to_csv(output / "curve.csv", index=False)
    (output / "report.json").write_text(json.dumps({
        "status": "DESCRIPTIVE_ONLY_NO_N_SELECTED", "oracle_events_path": str(events_path),
        "oracle_events": len(events), "oracle_symbols": len(symbols),
        "daily_bars_loaded": int(loaded_bar_count), "checkpoint_days": list(DAYS),
        "clock": "Oracle J close; observe close J+N; enter open J+N+1; exit open J+21",
        "threshold": threshold, "round_trip_cost": cost,
        "limitations": [
            "Current-stock universe has survivorship bias; no PIT tradability filter.",
            "The original OOF folds end in July 2025, not a new independent holdout.",
            "Tail-only conditional probabilities use future labels for evaluation, never for decisions.",
            "Equal-event/date returns are not a portfolio backtest or risk-adjusted PnL.",
            "Choosing the best N ex post would be overfitting; no deployment authorized.",
        ],
    }, indent=2), encoding="utf-8")
    print(f"Saved {output / 'curve.csv'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=float, default=0.005)
    args = parser.parse_args()
    run(args.events, args.output, args.threshold)
