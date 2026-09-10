"""Audit préfixé de la dynamique trades/NBBO sur les 30 dernières minutes.

Recherche uniquement trois sous-fenêtres définies avant collecte. Aucun modèle,
aucune écriture DB et aucune modification du serving.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.metrics import roc_auc_score

from modelFactory.directional_data_research.signed_flow_pilot import (
    DEFAULT_ROOT, _window, fetch_ticks, select_events, signed_flow_features,
)
from modelFactory.eroya_directional_poc import EroyaClient
from modelFactory.oracle_ablation_amplitude_compare import prepare_labels

UTC = timezone.utc
WINDOWS = {
    "early_30_15": (30.0, 15.0),
    "middle_15_5": (15.0, 5.0),
    "late_5_0": (5.0, 0.0),
}


def _tick_time(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(pd.to_numeric(frame["sip_timestamp"], errors="coerce"), unit="ns", utc=True)


def temporal_features(trades: pd.DataFrame, quotes: pd.DataFrame, close_utc: str) -> dict[str, Any]:
    if trades.empty or quotes.empty:
        return {"feature_status": "empty", "trade_count": len(trades), "quote_count": len(quotes)}
    close = pd.Timestamp(close_utc)
    trade_minutes = (close - _tick_time(trades)).dt.total_seconds() / 60.0
    quote_minutes = (close - _tick_time(quotes)).dt.total_seconds() / 60.0
    output: dict[str, Any] = {
        "feature_status": "complete", "trade_count": int(len(trades)), "quote_count": int(len(quotes)),
    }
    complete_windows = 0
    for name, (older, newer) in WINDOWS.items():
        t = trades[(trade_minutes <= older) & (trade_minutes > newer)].copy()
        q = quotes[(quote_minutes <= older) & (quote_minutes > newer)].copy()
        values = signed_flow_features(t, q)
        output[f"{name}_status"] = values.get("feature_status")
        output[f"{name}_trade_count"] = values.get("trade_count", 0)
        output[f"{name}_quote_count"] = values.get("quote_count", 0)
        for feature in ("signed_volume_ratio", "mean_quote_size_imbalance", "quote_match_rate"):
            output[f"{name}_{feature}"] = values.get(feature)
        complete_windows += values.get("feature_status") == "complete"
    if complete_windows != len(WINDOWS):
        output["feature_status"] = "partial"
    for feature in ("signed_volume_ratio", "mean_quote_size_imbalance"):
        early = output.get(f"early_30_15_{feature}")
        middle = output.get(f"middle_15_5_{feature}")
        late = output.get(f"late_5_0_{feature}")
        output[f"late_minus_early_{feature}"] = late - early if pd.notna(late) and pd.notna(early) else None
        output[f"flow_acceleration_{feature}"] = (
            (late - middle) - (middle - early)
            if pd.notna(late) and pd.notna(middle) and pd.notna(early) else None
        )
    return output


def candidate_features() -> list[str]:
    return [
        *(f"{window}_signed_volume_ratio" for window in WINDOWS),
        *(f"{window}_mean_quote_size_imbalance" for window in WINDOWS),
        "late_minus_early_signed_volume_ratio",
        "flow_acceleration_signed_volume_ratio",
        "late_minus_early_mean_quote_size_imbalance",
        "flow_acceleration_mean_quote_size_imbalance",
    ]


def evaluate(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    data = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    data = data[data["feature_status"].eq("complete")].copy()
    data["semester"] = data["date"].dt.year.astype(str) + "H" + np.where(data["date"].dt.month.le(6), "1", "2")
    tail = data[data["future_return"].ge(0.03) | data["future_return"].le(-0.03)].copy()
    tail["is_long_tail"] = tail["future_return"].ge(0.03).astype(int)
    names = candidate_features()
    results: dict[str, Any] = {}
    for name in names:
        valid = tail.dropna(subset=[name])
        if len(valid) < 2 or valid["is_long_tail"].nunique() < 2:
            results[name] = {"status": "insufficient_classes", "rows": int(len(valid))}
            continue
        raw_auc = float(roc_auc_score(valid["is_long_tail"], valid[name]))
        orientation = 1 if raw_auc >= 0.5 else -1
        long_values = valid.loc[valid["is_long_tail"].eq(1), name]
        short_values = valid.loc[valid["is_long_tail"].eq(0), name]
        p_value = float(mannwhitneyu(long_values, short_values, alternative="two-sided").pvalue)
        semesters = []
        for semester, group in valid.groupby("semester", sort=True):
            auc = None
            if group["is_long_tail"].nunique() == 2:
                semester_auc = float(roc_auc_score(group["is_long_tail"], group[name]))
                auc = semester_auc if orientation == 1 else 1.0 - semester_auc
            semesters.append({"semester": semester, "rows": int(len(group)), "auc": auc})
        aucs = [row["auc"] for row in semesters if row["auc"] is not None]
        correlation_data = data[[name, "future_return"]].dropna()
        spearman = float(correlation_data.corr(method="spearman").iloc[0, 1])
        positive_ratio = float(np.mean(np.asarray(aucs) > 0.5)) if aucs else 0.0
        gates = {
            "rows_ge_150": len(valid) >= 150,
            "auc_distance_ge_003": abs(raw_auc - 0.5) >= 0.03,
            "abs_spearman_ge_003": abs(spearman) >= 0.03,
            "positive_semester_ratio_ge_070": positive_ratio >= 0.70,
            "bonferroni_p_lt_005": min(1.0, p_value * len(names)) < 0.05,
        }
        gates["all_passed"] = all(gates.values())
        results[name] = {
            "status": "evaluated", "rows": int(len(valid)), "raw_auc": raw_auc,
            "orientation": orientation, "oriented_auc": raw_auc if orientation == 1 else 1.0 - raw_auc,
            "spearman_future_return": spearman, "p_value": p_value,
            "bonferroni_p_value": min(1.0, p_value * len(names)),
            "positive_semester_ratio": positive_ratio, "semesters": semesters, "gates": gates,
        }
    return {
        "rows_with_labels": int(len(data)), "tail_rows": int(len(tail)),
        "tested_feature_count": len(names), "multiplicity": "Bonferroni",
        "features": results,
        "go_next_stage": any(v.get("gates", {}).get("all_passed", False) for v in results.values()),
    }


def _progress(path: Path, message: str) -> None:
    timestamp = datetime.now(UTC).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")
    print(message, flush=True)


def run(args: argparse.Namespace) -> Path:
    key = os.environ.get("EROYA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("EROYA_API_KEY absente.")
    gate = pd.read_parquet(Path("artifacts/models") / args.oracle_batch_id / "_oracle_oof_gate.parquet")
    events = select_events(gate, start_date=args.start_date, end_date=args.end_date, count=args.events)
    output = args.output or DEFAULT_ROOT / f"signed-flow-temporal-{datetime.now(UTC):%Y%m%d%H%M%S}-{args.oracle_batch_id[-6:]}"
    output.mkdir(parents=True, exist_ok=False)
    progress_path = output / "progress.log"
    client = EroyaClient(key)
    feature_rows: list[dict[str, Any]] = []
    collection_rows: list[dict[str, Any]] = []
    all_trades: list[pd.DataFrame] = []
    all_quotes: list[pd.DataFrame] = []
    for index, event in enumerate(events.itertuples(index=False), start=1):
        start, end = _window(event.date, 30)
        trades, tmeta = fetch_ticks(client, "trades", event.symbol, start, end, max_records=args.max_records)
        quotes, qmeta = fetch_ticks(client, "quotes", event.symbol, start, end, max_records=args.max_records)
        event_id = f"{event.date.date()}_{event.symbol}"
        for frame in (trades, quotes):
            if not frame.empty:
                frame.insert(0, "event_id", event_id)
                frame.insert(1, "event_date", event.date)
                frame.insert(2, "symbol", event.symbol)
        all_trades.append(trades)
        all_quotes.append(quotes)
        feature_rows.append({
            "event_id": event_id, "date": event.date, "symbol": event.symbol,
            "semester": event.semester, **temporal_features(trades, quotes, end),
        })
        collection_rows.append({"event_id": event_id, "trade": tmeta, "quote": qmeta})
        if index == 1 or index % 10 == 0 or index == len(events):
            _progress(progress_path, f"events={index}/{len(events)} symbol={event.symbol} date={event.date.date()}")
    pd.concat(all_trades, ignore_index=True).to_parquet(output / "trades.parquet", index=False)
    pd.concat(all_quotes, ignore_index=True).to_parquet(output / "quotes.parquet", index=False)
    features = pd.DataFrame(feature_rows)
    features.to_parquet(output / "features.parquet", index=False)
    labels = prepare_labels(Path(args.labels_path), args.start_date, args.end_date)
    labeled = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    labeled.to_parquet(output / "labeled_features.parquet", index=False)
    evaluation = evaluate(features, labels)
    report = {
        "schema_version": 1, "experiment": "signed_flow_temporal_audit",
        "status": "completed", "research_only": True, "serving_ready": False,
        "oracle_batch_id": args.oracle_batch_id, "window_minutes": 30,
        "subwindows_minutes_before_close": WINDOWS,
        "events_requested": args.events, "events_selected": len(events),
        "complete_feature_events": int(features["feature_status"].eq("complete").sum()),
        "selection_uses_future_outcome": False, "collection": collection_rows,
        "evaluation": evaluation,
        "decision_rule": "Aucun modèle si aucune feature ne passe les cinq gates corrigés de multiplicité.",
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _progress(progress_path, f"completed go_next_stage={evaluation['go_next_stage']}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2022-03-07")
    parser.add_argument("--end-date", default="2025-06-30")
    parser.add_argument("--events", type=int, default=200)
    parser.add_argument("--max-records", type=int, default=300_000)
    parser.add_argument("--labels-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = run(args)
    print(json.dumps({"output": str(path), "report": str(path / "report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
