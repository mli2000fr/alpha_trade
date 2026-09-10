"""Confirmation disjointe du score contrariant -return_5m après Oracle TOP20."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr
from sklearn.metrics import roc_auc_score

from modelFactory.directional_data_research.signed_flow_pilot import (
    DEFAULT_ROOT, _event_hash, _window, fetch_ticks, select_events,
)
from modelFactory.eroya_directional_poc import EroyaClient
from modelFactory.oracle_ablation_amplitude_compare import prepare_labels

UTC = timezone.utc


def select_disjoint_events(
    gate: pd.DataFrame, excluded_features: pd.DataFrame, *, start_date: str, end_date: str, count: int,
) -> pd.DataFrame:
    excluded_dates = set(pd.to_datetime(excluded_features["date"], errors="coerce").dt.normalize().dropna())
    available = gate.copy()
    available["date"] = pd.to_datetime(available["date"], errors="coerce").dt.normalize()
    available["symbol"] = available["symbol"].astype(str).str.upper().str.strip()
    available = available[
        ~available["date"].isin(excluded_dates)
        & available["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        & available["directional_oracle_eligible"].fillna(False).astype(bool)
        & available["directional_oracle_oof_available"].fillna(False).astype(bool)
    ].copy()
    # Une seule observation par date réduit la dépendance cross-sectionnelle.
    # Le choix intra-date est un hash date/symbole, jamais l'ordre alphabétique.
    available["intra_date_hash"] = [
        _event_hash(date, symbol) for date, symbol in zip(available["date"], available["symbol"], strict=True)
    ]
    available = available.sort_values(["date", "intra_date_hash"]).drop_duplicates("date", keep="first")
    selected = select_events(available, start_date=start_date, end_date=end_date, count=count)
    if set(selected["date"]) & excluded_dates:
        raise AssertionError("La confirmation recouvre une date de découverte.")
    return selected


def exhaustion_feature(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {"feature_status": "empty", "trade_count": 0}
    frame = trades.copy()
    frame["ts"] = pd.to_datetime(pd.to_numeric(frame["sip_timestamp"], errors="coerce"), unit="ns", utc=True)
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["ts", "price"]).query("price > 0").sort_values("ts")
    if len(frame) < 2:
        return {"feature_status": "insufficient", "trade_count": int(len(frame))}
    recent_return = float(frame.iloc[-1]["price"] / frame.iloc[0]["price"] - 1.0)
    return {
        "feature_status": "complete", "trade_count": int(len(frame)),
        "return_5m": recent_return, "exhaustion_score": -recent_return,
    }


def evaluate(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    data = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    data = data[data["feature_status"].eq("complete")].copy()
    data["semester"] = data["date"].dt.year.astype(str) + "H" + np.where(data["date"].dt.month.le(6), "1", "2")
    tail = data[data["future_return"].ge(0.03) | data["future_return"].le(-0.03)].copy()
    tail["is_long_tail"] = tail["future_return"].ge(0.03).astype(int)
    if tail["is_long_tail"].nunique() < 2:
        raise ValueError("Confirmation sans deux classes directionnelles.")
    auc = float(roc_auc_score(tail["is_long_tail"], tail["exhaustion_score"]))
    long_score = tail.loc[tail["is_long_tail"].eq(1), "exhaustion_score"]
    short_score = tail.loc[tail["is_long_tail"].eq(0), "exhaustion_score"]
    p_value = float(mannwhitneyu(long_score, short_score, alternative="greater").pvalue)
    rho, rho_p = spearmanr(data["exhaustion_score"], data["future_return"], nan_policy="omit")
    semesters = []
    for semester, group in tail.groupby("semester", sort=True):
        semester_auc = None
        if group["is_long_tail"].nunique() == 2:
            semester_auc = float(roc_auc_score(group["is_long_tail"], group["exhaustion_score"]))
        semesters.append({"semester": semester, "rows": int(len(group)), "auc": semester_auc})
    calculable = [row["auc"] for row in semesters if row["auc"] is not None]
    stable = float(np.mean(np.asarray(calculable) > 0.5)) if calculable else 0.0
    gates = {
        "tail_rows_ge_300": len(tail) >= 300,
        "auc_ge_053": auc >= 0.53,
        "spearman_ge_003": float(rho) >= 0.03,
        "positive_semester_ratio_ge_070": stable >= 0.70,
        "one_sided_p_lt_005": p_value < 0.05,
    }
    gates["all_passed"] = all(gates.values())
    return {
        "rows_with_labels": int(len(data)), "tail_rows": int(len(tail)),
        "auc": auc, "spearman_future_return": float(rho), "spearman_p_value": float(rho_p),
        "one_sided_p_value": p_value, "positive_semester_ratio": stable,
        "semesters": semesters, "gates": gates,
        "verdict": "GO_RESEARCH_CONFIRMATION" if gates["all_passed"] else "NO_GO",
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
    excluded = pd.read_parquet(Path(args.exclude_source) / "features.parquet")
    events = select_disjoint_events(
        gate, excluded, start_date=args.start_date, end_date=args.end_date, count=args.events,
    )
    output = args.output or DEFAULT_ROOT / f"close-exhaustion-confirm-{datetime.now(UTC):%Y%m%d%H%M%S}-{args.oracle_batch_id[-6:]}"
    output.mkdir(parents=True, exist_ok=False)
    progress = output / "progress.log"
    client = EroyaClient(key)
    rows: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    all_trades: list[pd.DataFrame] = []
    for index, event in enumerate(events.itertuples(index=False), start=1):
        start, end = _window(event.date, 5)
        trades, meta = fetch_ticks(client, "trades", event.symbol, start, end, max_records=args.max_records)
        event_id = f"{event.date.date()}_{event.symbol}"
        if not trades.empty:
            trades.insert(0, "event_id", event_id)
            trades.insert(1, "event_date", event.date)
            trades.insert(2, "symbol", event.symbol)
        all_trades.append(trades)
        rows.append({
            "event_id": event_id, "date": event.date, "symbol": event.symbol,
            "semester": event.semester, **exhaustion_feature(trades),
        })
        metadata.append({"event_id": event_id, "trade": meta})
        if index == 1 or index % 20 == 0 or index == len(events):
            _progress(progress, f"events={index}/{len(events)} symbol={event.symbol} date={event.date.date()}")
    pd.concat(all_trades, ignore_index=True).to_parquet(output / "trades.parquet", index=False)
    features = pd.DataFrame(rows)
    features.to_parquet(output / "features.parquet", index=False)
    labels = prepare_labels(Path(args.labels_path), args.start_date, args.end_date)
    labeled = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    labeled.to_parquet(output / "labeled_features.parquet", index=False)
    result = evaluate(features, labels)
    report = {
        "schema_version": 1, "experiment": "close_exhaustion_disjoint_confirmation",
        "status": "completed", "research_only": True, "serving_ready": False,
        "oracle_batch_id": args.oracle_batch_id, "primary_hypothesis": "exhaustion_score=-return_5m",
        "disjoint_unit": "date", "excluded_date_count": int(pd.to_datetime(excluded["date"]).dt.normalize().nunique()),
        "events_selected": len(events), "selection_uses_future_outcome": False,
        "collection": metadata, "evaluation": result,
        "decision_rule": "Une hypothèse primaire, signe et fenêtre fixes; cinq gates requis.",
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _progress(progress, f"completed verdict={result['verdict']}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--exclude-source", required=True)
    parser.add_argument("--labels-path", required=True)
    parser.add_argument("--start-date", default="2022-03-07")
    parser.add_argument("--end-date", default="2025-06-30")
    parser.add_argument("--events", type=int, default=400)
    parser.add_argument("--max-records", type=int, default=100_000)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = run(args)
    print(json.dumps({"output": str(path), "report": str(path / "report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
