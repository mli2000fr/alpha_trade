"""POC borné de flux de transactions signé après Oracle TOP20.

Collecte uniquement quelques fenêtres pré-clôture depuis Eroya. Aucun accès DB
en écriture, aucune modification du serving et aucune clé dans les artefacts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from modelFactory.eroya_directional_poc import EroyaClient
from modelFactory.oracle_ablation_amplitude_compare import prepare_labels

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
DEFAULT_ROOT = Path("artifacts/research/eroya_directional")


def _event_hash(date: pd.Timestamp, symbol: str) -> str:
    return hashlib.sha256(f"{date.date()}|{symbol}".encode()).hexdigest()


def select_events(gate: pd.DataFrame, *, start_date: str, end_date: str, count: int) -> pd.DataFrame:
    required = {"date", "symbol", "directional_oracle_eligible", "directional_oracle_oof_available"}
    missing = sorted(required - set(gate.columns))
    if missing:
        raise ValueError(f"Gate Oracle incomplet: {missing}")
    frame = gate.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame = frame[
        frame["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        & frame["directional_oracle_eligible"].fillna(False).astype(bool)
        & frame["directional_oracle_oof_available"].fillna(False).astype(bool)
    ].drop_duplicates(["date", "symbol"])
    if frame.empty:
        raise ValueError("Aucun événement Oracle OOF dans la fenêtre demandée.")
    frame["semester"] = frame["date"].dt.year.astype(str) + "H" + np.where(frame["date"].dt.month.le(6), "1", "2")
    frame["selection_hash"] = [
        _event_hash(date, symbol) for date, symbol in zip(frame["date"], frame["symbol"], strict=True)
    ]
    semesters = sorted(frame["semester"].unique())
    per_semester = max(1, math.ceil(count / len(semesters)))
    selected = (
        frame.sort_values(["semester", "selection_hash"])
        .groupby("semester", sort=True, group_keys=False).head(per_semester)
        .sort_values(["selection_hash", "date", "symbol"]).head(count)
        .sort_values(["date", "symbol"]).reset_index(drop=True)
    )
    return selected[["date", "symbol", "semester", "selection_hash"]]


def _window(date: pd.Timestamp, minutes: int) -> tuple[str, str]:
    close_et = datetime(date.year, date.month, date.day, 16, 0, tzinfo=ET)
    start = close_et - timedelta(minutes=minutes)
    return start.astimezone(UTC).isoformat().replace("+00:00", "Z"), close_et.astimezone(UTC).isoformat().replace("+00:00", "Z")


def fetch_ticks(
    client: EroyaClient, endpoint: str, symbol: str, start: str, end: str, *,
    max_records: int, page_limit: int = 50_000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    url = f"{endpoint}/{symbol}"
    params: dict[str, Any] | None = {
        "timestamp.gte": start, "timestamp.lte": end,
        "order": "asc", "sort": "timestamp", "limit": page_limit,
    }
    rows: list[dict[str, Any]] = []
    pages = 0
    truncated = False
    while url:
        response = client.get(url, params=params)
        if response.status_code != 200:
            return pd.DataFrame(), {"status": f"http_{response.status_code}", "pages": pages, "rows": len(rows)}
        payload = response.json()
        chunk = payload.get("results") or []
        rows.extend(chunk)
        pages += 1
        if len(rows) >= max_records:
            rows = rows[:max_records]
            truncated = bool(payload.get("next_url")) or len(rows) > max_records
            break
        url = payload.get("next_url") or ""
        params = None
    return pd.DataFrame(rows), {
        "status": "truncated" if truncated else "complete", "pages": pages,
        "rows": len(rows), "truncated": truncated,
    }


def signed_flow_features(trades: pd.DataFrame, quotes: pd.DataFrame) -> dict[str, Any]:
    if trades.empty or quotes.empty:
        return {"feature_status": "empty", "trade_count": len(trades), "quote_count": len(quotes)}
    t = trades.copy()
    q = quotes.copy()
    t["ts"] = pd.to_datetime(pd.to_numeric(t["sip_timestamp"], errors="coerce"), unit="ns", utc=True)
    q["ts"] = pd.to_datetime(
        pd.to_numeric(q["sip_timestamp"], errors="coerce"), unit="ns", utc=True,
    )
    for col in ("price", "size"):
        t[col] = pd.to_numeric(t[col], errors="coerce")
    for col in ("bid_price", "ask_price", "bid_size", "ask_size"):
        q[col] = pd.to_numeric(q[col], errors="coerce")
    t = t.dropna(subset=["ts", "price", "size"]).sort_values("ts")
    q = q.dropna(subset=["ts", "bid_price", "ask_price"]).sort_values("ts")
    q = q[(q["bid_price"] > 0) & (q["ask_price"] >= q["bid_price"])]
    if t.empty or q.empty:
        return {"feature_status": "invalid", "trade_count": len(t), "quote_count": len(q)}
    joined = pd.merge_asof(t, q, on="ts", direction="backward", tolerance=pd.Timedelta(seconds=5))
    joined["mid"] = (joined["bid_price"] + joined["ask_price"]) / 2.0
    valid = joined["mid"].notna() & joined["mid"].gt(0)
    joined["side"] = np.where(joined["price"] > joined["mid"], 1.0,
                              np.where(joined["price"] < joined["mid"], -1.0, 0.0))
    tick = np.sign(joined["price"].diff()).replace(0, np.nan).ffill().fillna(0.0)
    joined.loc[joined["side"].eq(0), "side"] = tick[joined["side"].eq(0)]
    joined.loc[~valid, "side"] = np.nan
    joined["dollar"] = joined["price"] * joined["size"]
    signed_volume = (joined["side"] * joined["size"]).sum(min_count=1)
    signed_dollar = (joined["side"] * joined["dollar"]).sum(min_count=1)
    total_volume = joined["size"].sum()
    total_dollar = joined["dollar"].sum()
    quote_depth = q["bid_size"].fillna(0) + q["ask_size"].fillna(0)
    imbalance = (q["bid_size"].fillna(0) - q["ask_size"].fillna(0)) / quote_depth.replace(0, np.nan)
    return {
        "feature_status": "complete",
        "trade_count": int(len(t)), "quote_count": int(len(q)),
        "quote_match_rate": float(valid.mean()),
        "signed_volume_ratio": float(signed_volume / total_volume) if total_volume else None,
        "signed_dollar_ratio": float(signed_dollar / total_dollar) if total_dollar else None,
        "mean_quote_size_imbalance": float(imbalance.mean()) if imbalance.notna().any() else None,
        "trade_vwap": float(total_dollar / total_volume) if total_volume else None,
        "last_mid": float((q.iloc[-1]["bid_price"] + q.iloc[-1]["ask_price"]) / 2.0),
    }


def evaluate_direction(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    data = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    data = data[data["feature_status"].eq("complete")].copy()
    data["semester"] = data["date"].dt.year.astype(str) + "H" + np.where(data["date"].dt.month.le(6), "1", "2")
    tail = data[data["future_return"].ge(0.03) | data["future_return"].le(-0.03)].copy()
    tail["is_long_tail"] = tail["future_return"].ge(0.03).astype(int)
    results: dict[str, Any] = {}
    for feature in ("signed_volume_ratio", "signed_dollar_ratio", "mean_quote_size_imbalance"):
        valid = tail.dropna(subset=[feature])
        if valid.empty or valid["is_long_tail"].nunique() < 2:
            results[feature] = {"status": "insufficient_classes", "rows": int(len(valid))}
            continue
        auc = float(roc_auc_score(valid["is_long_tail"], valid[feature]))
        orientation = 1 if auc >= 0.5 else -1
        fixed_auc = auc if orientation == 1 else 1.0 - auc
        semester_rows = []
        for semester, group in valid.groupby("semester", sort=True):
            if group["is_long_tail"].nunique() < 2:
                semester_rows.append({"semester": semester, "rows": len(group), "auc": None})
                continue
            semester_auc = float(roc_auc_score(group["is_long_tail"], group[feature]))
            semester_rows.append({
                "semester": semester, "rows": int(len(group)),
                "auc": semester_auc if orientation == 1 else 1.0 - semester_auc,
            })
        calculable = [row["auc"] for row in semester_rows if row["auc"] is not None]
        spearman = data[[feature, "future_return"]].dropna().corr(method="spearman").iloc[0, 1]
        results[feature] = {
            "status": "evaluated", "rows": int(len(valid)), "raw_auc": auc,
            "orientation": orientation, "oriented_auc": fixed_auc,
            "spearman_future_return": float(spearman),
            "positive_semester_ratio": float(np.mean(np.asarray(calculable) > 0.5)) if calculable else 0.0,
            "semesters": semester_rows,
            "gates": {
                "rows_ge_150": len(valid) >= 150,
                "auc_distance_ge_003": abs(auc - 0.5) >= 0.03,
                "abs_spearman_ge_003": abs(float(spearman)) >= 0.03,
                "positive_semester_ratio_ge_070": bool(calculable) and float(np.mean(np.asarray(calculable) > 0.5)) >= 0.70,
            },
        }
        results[feature]["gates"]["all_passed"] = all(results[feature]["gates"].values())
    return {
        "rows_with_labels": int(len(data)), "tail_rows": int(len(tail)),
        "features": results,
        "go_multivariate": any(
            result.get("gates", {}).get("all_passed", False) for result in results.values()
        ),
        "rule": "Une famille signée doit passer N, AUC, IC et stabilité avant tout modèle multivarié.",
    }


def run(args: argparse.Namespace) -> Path:
    key = os.environ.get("EROYA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("EROYA_API_KEY absente.")
    gate = pd.read_parquet(Path("artifacts/models") / args.oracle_batch_id / "_oracle_oof_gate.parquet")
    events = select_events(gate, start_date=args.start_date, end_date=args.end_date, count=args.events)
    output = args.output or DEFAULT_ROOT / f"signed-flow-pilot-{datetime.now(UTC):%Y%m%d%H%M%S}-{args.oracle_batch_id[-6:]}"
    output.mkdir(parents=True, exist_ok=False)
    client = EroyaClient(key)
    feature_rows, collection_rows = [], []
    all_trades, all_quotes = [], []
    for event in events.itertuples(index=False):
        start, end = _window(event.date, args.window_minutes)
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
        feature_rows.append({"event_id": event_id, "date": event.date, "symbol": event.symbol,
                             "semester": event.semester, **signed_flow_features(trades, quotes)})
        collection_rows.append({"event_id": event_id, "trade": tmeta, "quote": qmeta})
    pd.concat(all_trades, ignore_index=True).to_parquet(output / "trades.parquet", index=False)
    pd.concat(all_quotes, ignore_index=True).to_parquet(output / "quotes.parquet", index=False)
    features = pd.DataFrame(feature_rows)
    features.to_parquet(output / "features.parquet", index=False)
    evaluation = None
    if args.labels_path:
        labels = prepare_labels(Path(args.labels_path), args.start_date, args.end_date)
        labeled = features.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
        labeled.to_parquet(output / "labeled_features.parquet", index=False)
        evaluation = evaluate_direction(features, labels)
    report = {
        "schema_version": 1, "experiment": "signed_trade_flow_feasibility_pilot",
        "status": "completed", "research_only": True, "serving_ready": False,
        "oracle_batch_id": args.oracle_batch_id, "window_minutes": args.window_minutes,
        "events_requested": args.events, "events_selected": len(events),
        "complete_feature_events": int(features["feature_status"].eq("complete").sum()),
        "selection_uses_future_outcome": False,
        "collection": collection_rows,
        "evaluation": evaluation,
        "decision_rule": (
            "Sans labels ce run valide uniquement la faisabilité. Avec labels, les gates "
            "préfixés restent requis avant tout modèle multivarié."
        ),
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2023-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--events", type=int, default=12)
    parser.add_argument("--window-minutes", type=int, default=5)
    parser.add_argument("--max-records", type=int, default=100_000)
    parser.add_argument("--labels-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = run(args)
    print(json.dumps({"output": str(path), "report": str(path / "report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
