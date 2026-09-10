"""POC Oracle TOP20 sur la trajectoire 5 minutes de la séance J complète."""
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
from scipy.stats import mannwhitneyu, spearmanr
from sklearn.metrics import roc_auc_score

from modelFactory.directional_data_research.signed_flow_pilot import DEFAULT_ROOT, _event_hash, select_events
from modelFactory.eroya_directional_poc import EroyaClient
from modelFactory.oracle_ablation_amplitude_compare import prepare_labels

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
DIRECTION_FEATURES = [
    "morning_return", "afternoon_return", "afternoon_minus_morning",
    "close_vs_session_vwap", "close_location_session",
]
AMPLITUDE_FEATURES = [
    "realized_vol_5m", "session_range", "abs_morning_afternoon_divergence",
    "first_hour_volume_share", "last_hour_volume_share", "log_transactions",
]


def select_unique_date_events(
    gate: pd.DataFrame, *, start_date: str, end_date: str, count: int,
) -> pd.DataFrame:
    frame = gate.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame = frame[
        frame["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        & frame["directional_oracle_eligible"].fillna(False).astype(bool)
        & frame["directional_oracle_oof_available"].fillna(False).astype(bool)
    ].copy()
    frame["intra_date_hash"] = [
        _event_hash(date, symbol) for date, symbol in zip(frame["date"], frame["symbol"], strict=True)
    ]
    frame = frame.sort_values(["date", "intra_date_hash"]).drop_duplicates("date", keep="first")
    return select_events(frame, start_date=start_date, end_date=end_date, count=count)


def fetch_bars(client: EroyaClient, symbol: str, date: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, Any]]:
    day = date.strftime("%Y-%m-%d")
    response = client.get(
        f"aggs/ticker/{symbol}/range/5/minute/{day}/{day}",
        params={"adjusted": "true", "sort": "asc", "limit": 50_000},
    )
    if response.status_code != 200:
        return pd.DataFrame(), {"status": f"http_{response.status_code}", "rows": 0}
    rows = response.json().get("results") or []
    return pd.DataFrame(rows), {"status": "complete", "rows": len(rows)}


def regular_session_bars(bars: pd.DataFrame) -> pd.DataFrame:
    if bars.empty or "t" not in bars:
        return pd.DataFrame()
    frame = bars.copy()
    frame["ts"] = pd.to_datetime(pd.to_numeric(frame["t"], errors="coerce"), unit="ms", utc=True)
    frame["ts_et"] = frame["ts"].dt.tz_convert(ET)
    minute = frame["ts_et"].dt.hour * 60 + frame["ts_et"].dt.minute
    frame = frame[(minute >= 9 * 60 + 30) & (minute < 16 * 60)].sort_values("ts")
    for name in ("o", "h", "l", "c", "v", "vw", "n"):
        frame[name] = pd.to_numeric(frame.get(name), errors="coerce")
    return frame.dropna(subset=["o", "h", "l", "c", "v"])


def session_features(bars: pd.DataFrame) -> dict[str, Any]:
    frame = regular_session_bars(bars)
    if len(frame) < 60:
        return {"feature_status": "insufficient", "regular_bar_count": int(len(frame))}
    minute = frame["ts_et"].dt.hour * 60 + frame["ts_et"].dt.minute
    morning = frame[(minute >= 9 * 60 + 30) & (minute < 11 * 60)]
    afternoon = frame[(minute >= 13 * 60) & (minute < 16 * 60)]
    first_hour = frame[(minute >= 9 * 60 + 30) & (minute < 10 * 60 + 30)]
    last_hour = frame[(minute >= 15 * 60) & (minute < 16 * 60)]
    if morning.empty or afternoon.empty:
        return {"feature_status": "insufficient", "regular_bar_count": int(len(frame))}
    morning_return = float(morning.iloc[-1]["c"] / morning.iloc[0]["o"] - 1.0)
    afternoon_return = float(afternoon.iloc[-1]["c"] / afternoon.iloc[0]["o"] - 1.0)
    total_volume = float(frame["v"].sum())
    session_vwap = float((frame["vw"].fillna(frame["c"]) * frame["v"]).sum() / total_volume)
    session_low, session_high = float(frame["l"].min()), float(frame["h"].max())
    close = float(frame.iloc[-1]["c"])
    log_returns = np.log(frame["c"]).diff().dropna()
    return {
        "feature_status": "complete", "regular_bar_count": int(len(frame)),
        "morning_return": morning_return,
        "afternoon_return": afternoon_return,
        "afternoon_minus_morning": afternoon_return - morning_return,
        "close_vs_session_vwap": close / session_vwap - 1.0,
        "close_location_session": (
            ((close - session_low) / (session_high - session_low) - 0.5) * 2.0
            if session_high > session_low else 0.0
        ),
        "realized_vol_5m": float(np.sqrt(np.square(log_returns).sum())),
        "session_range": session_high / session_low - 1.0,
        "abs_morning_afternoon_divergence": abs(afternoon_return - morning_return),
        "first_hour_volume_share": float(first_hour["v"].sum() / total_volume),
        "last_hour_volume_share": float(last_hour["v"].sum() / total_volume),
        "log_transactions": float(np.log1p(frame["n"].fillna(0).sum())),
    }


def _evaluate_family(
    data: pd.DataFrame, features: list[str], target: str, continuous_target: str,
    *, minimum_rows: int, total_tests: int,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name in features:
        valid = data.dropna(subset=[name, target, continuous_target])
        valid = valid[valid[target].isin([0, 1])]
        if valid[target].nunique() < 2:
            results[name] = {"status": "insufficient_classes", "rows": int(len(valid))}
            continue
        auc = float(roc_auc_score(valid[target], valid[name]))
        positive = valid.loc[valid[target].eq(1), name]
        negative = valid.loc[valid[target].eq(0), name]
        p_value = float(mannwhitneyu(positive, negative, alternative="greater").pvalue)
        rho, rho_p = spearmanr(valid[name], valid[continuous_target], nan_policy="omit")
        semesters = []
        for semester, group in valid.groupby("semester", sort=True):
            semester_auc = None
            if group[target].nunique() == 2:
                semester_auc = float(roc_auc_score(group[target], group[name]))
            semesters.append({"semester": semester, "rows": int(len(group)), "auc": semester_auc})
        calculable = [row["auc"] for row in semesters if row["auc"] is not None]
        stable = float(np.mean(np.asarray(calculable) > 0.5)) if calculable else 0.0
        gates = {
            "rows_ge_minimum": len(valid) >= minimum_rows,
            "auc_ge_053": auc >= 0.53,
            "spearman_ge_003": float(rho) >= 0.03,
            "positive_semester_ratio_ge_070": stable >= 0.70,
            "bonferroni_p_lt_005": min(1.0, p_value * total_tests) < 0.05,
        }
        gates["all_passed"] = all(gates.values())
        results[name] = {
            "status": "evaluated", "rows": int(len(valid)), "auc": auc,
            "spearman": float(rho), "spearman_p_value": float(rho_p),
            "p_value": p_value, "bonferroni_p_value": min(1.0, p_value * total_tests),
            "positive_semester_ratio": stable, "semesters": semesters, "gates": gates,
        }
    return results


def evaluate(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    data = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    data = data[data["feature_status"].eq("complete")].copy()
    data["semester"] = data["date"].dt.year.astype(str) + "H" + np.where(data["date"].dt.month.le(6), "1", "2")
    tail = data[data["future_return"].ge(0.03) | data["future_return"].le(-0.03)].copy()
    tail["is_long_tail"] = tail["future_return"].ge(0.03).astype(int)
    total_tests = len(DIRECTION_FEATURES) + len(AMPLITUDE_FEATURES)
    direction = _evaluate_family(
        tail, DIRECTION_FEATURES, "is_long_tail", "future_return",
        minimum_rows=250, total_tests=total_tests,
    )
    amplitude = _evaluate_family(
        data, AMPLITUDE_FEATURES, "oracle_extreme10", "abs_future_return",
        minimum_rows=300, total_tests=total_tests,
    )
    return {
        "rows_with_labels": int(len(data)), "tail_rows": int(len(tail)),
        "total_tests": total_tests, "multiplicity": "Bonferroni across both families",
        "direction": direction, "amplitude": amplitude,
        "direction_discovery": any(v.get("gates", {}).get("all_passed", False) for v in direction.values()),
        "amplitude_discovery": any(v.get("gates", {}).get("all_passed", False) for v in amplitude.values()),
        "confirmation_required": True,
    }


def _progress(path: Path, message: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now(UTC).isoformat()} {message}\n")
    print(message, flush=True)


def run(args: argparse.Namespace) -> Path:
    key = os.environ.get("EROYA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("EROYA_API_KEY absente.")
    gate = pd.read_parquet(Path("artifacts/models") / args.oracle_batch_id / "_oracle_oof_gate.parquet")
    events = select_unique_date_events(gate, start_date=args.start_date, end_date=args.end_date, count=args.events)
    output = args.output or DEFAULT_ROOT / f"intraday-session-path-{datetime.now(UTC):%Y%m%d%H%M%S}-{args.oracle_batch_id[-6:]}"
    output.mkdir(parents=True, exist_ok=False)
    progress = output / "progress.log"
    client = EroyaClient(key)
    rows: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    all_bars: list[pd.DataFrame] = []
    for index, event in enumerate(events.itertuples(index=False), start=1):
        bars, meta = fetch_bars(client, event.symbol, event.date)
        event_id = f"{event.date.date()}_{event.symbol}"
        if not bars.empty:
            bars.insert(0, "event_id", event_id)
            bars.insert(1, "event_date", event.date)
            bars.insert(2, "symbol", event.symbol)
        all_bars.append(bars)
        rows.append({
            "event_id": event_id, "date": event.date, "symbol": event.symbol,
            "semester": event.semester, **session_features(bars),
        })
        metadata.append({"event_id": event_id, "bars": meta})
        if index == 1 or index % 20 == 0 or index == len(events):
            _progress(progress, f"events={index}/{len(events)} symbol={event.symbol} date={event.date.date()}")
    pd.concat(all_bars, ignore_index=True).to_parquet(output / "bars_5m.parquet", index=False)
    features = pd.DataFrame(rows)
    features.to_parquet(output / "features.parquet", index=False)
    labels = prepare_labels(Path(args.labels_path), args.start_date, args.end_date)
    labeled = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    labeled.to_parquet(output / "labeled_features.parquet", index=False)
    result = evaluate(features, labels)
    report = {
        "schema_version": 1, "experiment": "intraday_full_session_path_discovery",
        "status": "completed", "research_only": True, "serving_ready": False,
        "oracle_batch_id": args.oracle_batch_id, "events_selected": len(events),
        "unique_dates": int(events["date"].nunique()), "selection_uses_future_outcome": False,
        "market_hours": "09:30<=bar_start<16:00 America/New_York",
        "signal_available": "after close J", "earliest_entry": "open J+1",
        "collection": metadata, "features_complete": int(features["feature_status"].eq("complete").sum()),
        "evaluation": result,
        "decision_rule": "Découverte seulement; 11 tests corrigés Bonferroni et confirmation indépendante obligatoire.",
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _progress(progress, f"completed direction={result['direction_discovery']} amplitude={result['amplitude_discovery']}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--labels-path", required=True)
    parser.add_argument("--start-date", default="2018-07-05")
    parser.add_argument("--end-date", default="2022-03-04")
    parser.add_argument("--events", type=int, default=400)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = run(args)
    print(json.dumps({"output": str(path), "report": str(path / "report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
