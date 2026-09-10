"""POC du contexte intraday SPY/QQQ/IWM/VXX autour des événements Oracle."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from modelFactory.directional_data_research.intraday_session_path_pilot import _evaluate_family
from modelFactory.directional_data_research.signed_flow_pilot import DEFAULT_ROOT
from modelFactory.eroya_directional_poc import EroyaClient
from modelFactory.oracle_ablation_amplitude_compare import prepare_labels

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
ASSETS = ("SPY", "QQQ", "IWM", "VXX")
DIRECTION_FEATURES = (
    "equity_equal_return", "qqq_minus_spy_return", "iwm_minus_spy_return", "risk_on_return",
)
AMPLITUDE_FEATURES = (
    "spy_realized_vol", "equity_realized_vol_mean", "cross_asset_return_dispersion", "abs_vxx_return",
)


def fetch_asset_range(
    client: EroyaClient, symbol: str, start_date: str, end_date: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    requests = 0
    truncated = False
    for year in range(pd.Timestamp(start_date).year, pd.Timestamp(end_date).year + 1):
        year_start = max(pd.Timestamp(start_date), pd.Timestamp(year=year, month=1, day=1)).date().isoformat()
        year_end = min(pd.Timestamp(end_date), pd.Timestamp(year=year, month=12, day=31)).date().isoformat()
        url = f"aggs/ticker/{symbol}/range/5/minute/{year_start}/{year_end}"
        params: dict[str, Any] | None = {"adjusted": "true", "sort": "asc", "limit": 50_000}
        while url:
            response = client.get(url, params=params)
            requests += 1
            if response.status_code != 200:
                return pd.DataFrame(rows), {
                    "status": f"http_{response.status_code}", "requests": requests, "rows": len(rows),
                }
            payload = response.json()
            rows.extend(payload.get("results") or [])
            url = payload.get("next_url") or ""
            params = None
            if requests > 100:
                truncated = True
                url = ""
    return pd.DataFrame(rows), {
        "status": "truncated" if truncated else "complete", "requests": requests,
        "rows": len(rows), "truncated": truncated,
    }


def daily_asset_features(bars: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame()
    frame = bars.copy()
    frame["ts"] = pd.to_datetime(pd.to_numeric(frame["t"], errors="coerce"), unit="ms", utc=True)
    frame["ts_et"] = frame["ts"].dt.tz_convert(ET)
    minute = frame["ts_et"].dt.hour * 60 + frame["ts_et"].dt.minute
    frame = frame[(minute >= 9 * 60 + 30) & (minute < 16 * 60)].copy()
    for name in ("o", "c"):
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    frame = frame.dropna(subset=["o", "c"])
    frame["date"] = frame["ts_et"].dt.tz_localize(None).dt.normalize()
    rows = []
    for date, group in frame.groupby("date", sort=True):
        group = group.sort_values("ts")
        if len(group) < 60:
            continue
        session_return = float(group.iloc[-1]["c"] / group.iloc[0]["o"] - 1.0)
        log_returns = np.log(group["c"]).diff().dropna()
        rows.append({
            "date": date, f"{symbol.lower()}_return": session_return,
            f"{symbol.lower()}_realized_vol": float(np.sqrt(np.square(log_returns).sum())),
            f"{symbol.lower()}_bars": int(len(group)),
        })
    return pd.DataFrame(rows)


def build_market_features(asset_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    merged: pd.DataFrame | None = None
    for symbol in ASSETS:
        frame = asset_frames[symbol]
        merged = frame if merged is None else merged.merge(frame, on="date", how="inner", validate="one_to_one")
    if merged is None or merged.empty:
        return pd.DataFrame()
    equity_returns = merged[["spy_return", "qqq_return", "iwm_return"]]
    equity_vols = merged[["spy_realized_vol", "qqq_realized_vol", "iwm_realized_vol"]]
    merged["equity_equal_return"] = equity_returns.mean(axis=1)
    merged["qqq_minus_spy_return"] = merged["qqq_return"] - merged["spy_return"]
    merged["iwm_minus_spy_return"] = merged["iwm_return"] - merged["spy_return"]
    merged["risk_on_return"] = merged["equity_equal_return"] - merged["vxx_return"]
    merged["equity_realized_vol_mean"] = equity_vols.mean(axis=1)
    merged["cross_asset_return_dispersion"] = equity_returns.std(axis=1, ddof=0)
    merged["abs_vxx_return"] = merged["vxx_return"].abs()
    return merged


def evaluate(events: pd.DataFrame, market: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    data = events[["date", "symbol"]].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.merge(market, on="date", how="inner", validate="many_to_one")
    data = data.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    data["semester"] = data["date"].dt.year.astype(str) + "H" + np.where(data["date"].dt.month.le(6), "1", "2")
    tail = data[data["future_return"].ge(0.03) | data["future_return"].le(-0.03)].copy()
    tail["is_long_tail"] = tail["future_return"].ge(0.03).astype(int)
    total_tests = len(DIRECTION_FEATURES) + len(AMPLITUDE_FEATURES)
    direction = _evaluate_family(
        tail, list(DIRECTION_FEATURES), "is_long_tail", "future_return",
        minimum_rows=250, total_tests=total_tests,
    )
    amplitude = _evaluate_family(
        data, list(AMPLITUDE_FEATURES), "oracle_extreme10", "abs_future_return",
        minimum_rows=300, total_tests=total_tests,
    )
    return {
        "rows_with_market_and_labels": int(len(data)), "tail_rows": int(len(tail)),
        "total_tests": total_tests, "direction": direction, "amplitude": amplitude,
        "direction_discovery": any(v.get("gates", {}).get("all_passed", False) for v in direction.values()),
        "amplitude_discovery": any(v.get("gates", {}).get("all_passed", False) for v in amplitude.values()),
        "confirmation_required": True,
    }


def run(args: argparse.Namespace) -> Path:
    key = os.environ.get("EROYA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("EROYA_API_KEY absente.")
    source = Path(args.events_source)
    events = pd.read_parquet(source / "features.parquet")
    output = args.output or DEFAULT_ROOT / f"intraday-market-context-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    client = EroyaClient(key)
    raw_frames: list[pd.DataFrame] = []
    daily: dict[str, pd.DataFrame] = {}
    collection: dict[str, Any] = {}
    for symbol in ASSETS:
        bars, metadata = fetch_asset_range(client, symbol, args.start_date, args.end_date)
        if not bars.empty:
            bars.insert(0, "asset", symbol)
            raw_frames.append(bars)
        daily[symbol] = daily_asset_features(bars, symbol)
        collection[symbol] = {**metadata, "complete_dates": int(len(daily[symbol]))}
        print(f"asset={symbol} rows={len(bars)} dates={len(daily[symbol])} status={metadata['status']}", flush=True)
    pd.concat(raw_frames, ignore_index=True).to_parquet(output / "market_bars_5m.parquet", index=False)
    market = build_market_features(daily)
    market.to_parquet(output / "market_features.parquet", index=False)
    labels = prepare_labels(Path(args.labels_path), args.start_date, args.end_date)
    result = evaluate(events, market, labels)
    report = {
        "schema_version": 1, "experiment": "intraday_market_context_discovery",
        "status": "completed", "research_only": True, "serving_ready": False,
        "events_source": str(source), "assets": ASSETS,
        "vxx_role": "tradable stress proxy; not VIX", "selection_uses_future_outcome": False,
        "signal_available": "after close J", "earliest_entry": "open J+1",
        "collection": collection, "market_complete_dates": int(len(market)), "evaluation": result,
        "decision_rule": "Eight prefixed tests, Bonferroni; confirmation required for any discovery.",
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"completed direction={result['direction_discovery']} amplitude={result['amplitude_discovery']}", flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-source", required=True)
    parser.add_argument("--labels-path", required=True)
    parser.add_argument("--start-date", default="2018-07-05")
    parser.add_argument("--end-date", default="2022-03-04")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = run(args)
    print(json.dumps({"output": str(path), "report": str(path / "report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
