"""Consolidation rétrospective des ablations Oracle sur labels corrigés.

Les scores OOF sont comparés sur une population commune. Les rendements
persistés avec les anciennes prédictions sont volontairement ignorés : la
source de vérité est l'export de labels dont ``target_quality_valid`` vaut 1.
Ce module est research-only et ne promeut aucun profil.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text
from sklearn.metrics import roc_auc_score

from database.connection import get_sqlalchemy_engine


def prepare_labels(path: Path, start_date: str, end_date: str) -> pd.DataFrame:
    labels = pd.read_parquet(path)
    required = {
        "prediction_date", "symbol", "future_return", "oracle_extreme10",
        "target_quality_valid",
    }
    missing = sorted(required - set(labels.columns))
    if missing:
        raise ValueError(f"Colonnes labels absentes: {missing}")
    labels = labels[list(required)].copy()
    labels["date"] = pd.to_datetime(labels.pop("prediction_date"), errors="coerce").dt.normalize()
    labels["symbol"] = labels["symbol"].astype(str).str.upper().str.strip()
    labels["future_return"] = pd.to_numeric(labels["future_return"], errors="coerce")
    labels["oracle_extreme10"] = pd.to_numeric(labels["oracle_extreme10"], errors="coerce")
    labels = labels[
        labels["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        & labels["target_quality_valid"].fillna(False).astype(bool)
    ].dropna(subset=["date", "symbol", "future_return", "oracle_extreme10"])
    labels = labels.drop_duplicates(["date", "symbol"], keep="last")
    labels["abs_future_return"] = labels["future_return"].abs()
    return labels[["date", "symbol", "future_return", "abs_future_return", "oracle_extreme10"]]


def load_scores(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    query = text(
        "SELECT prediction_date AS date, symbol, proba_extreme "
        "FROM oracle_extreme_predictions "
        "WHERE batch_id=:batch_id AND prediction_date BETWEEN :start_date AND :end_date"
    )
    with engine.connect() as connection:
        frame = pd.read_sql(
            query, connection,
            params={"batch_id": batch_id, "start_date": start_date, "end_date": end_date},
        )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["proba_extreme"] = pd.to_numeric(frame["proba_extreme"], errors="coerce")
    return frame.dropna().drop_duplicates(["date", "symbol"], keep="last")


def key_fingerprint(frame: pd.DataFrame) -> int:
    keys = frame[["date", "symbol"]].sort_values(["date", "symbol"]).reset_index(drop=True)
    return int(pd.util.hash_pandas_object(keys, index=False).sum())


def _daily_spearman(group: pd.DataFrame) -> float:
    if group["score_pct"].nunique() < 2 or group["abs_future_return"].nunique() < 2:
        return np.nan
    return float(group["score_pct"].corr(group["abs_future_return"], method="spearman"))


def evaluate_batch(scores: pd.DataFrame, labels: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    merged = scores.merge(labels, on=["date", "symbol"], how="inner", validate="one_to_one")
    if merged.empty:
        raise ValueError("Aucune ligne commune scores/labels.")
    merged["score_pct"] = merged.groupby("date")["proba_extreme"].rank(method="average", pct=True)
    merged["top20"] = merged["score_pct"].ge(0.80)
    merged["top10"] = merged["score_pct"].ge(0.90)
    daily_rows: list[dict[str, Any]] = []
    for date, group in merged.groupby("date", sort=True):
        top = group[group["top20"]]
        rest = group[~group["top20"]]
        if top.empty or rest.empty:
            continue
        daily_rows.append({
            "date": date,
            "top20_abs_return": float(top["abs_future_return"].mean()),
            "rest80_abs_return": float(rest["abs_future_return"].mean()),
            "amplitude_lift": float(top["abs_future_return"].mean() - rest["abs_future_return"].mean()),
            "spearman": _daily_spearman(group),
        })
    daily = pd.DataFrame(daily_rows)
    semester = merged["date"].dt.year.astype(str) + "H" + np.where(merged["date"].dt.month.le(6), "1", "2")
    merged["semester"] = semester
    semester_lifts = []
    for name, group in merged.groupby("semester", sort=True):
        top = group[group["top20"]]["abs_future_return"].mean()
        rest = group[~group["top20"]]["abs_future_return"].mean()
        semester_lifts.append({"semester": name, "amplitude_lift": float(top - rest)})
    auc = float(roc_auc_score(merged["oracle_extreme10"].astype(int), merged["proba_extreme"]))
    report = {
        "rows": int(len(merged)), "dates": int(merged["date"].nunique()),
        "symbols": int(merged["symbol"].nunique()), "key_fingerprint": key_fingerprint(merged),
        "auc_extreme10": auc,
        "precision_top10": float(merged.loc[merged["top10"], "oracle_extreme10"].mean()),
        "mean_top20_abs_return": float(merged.loc[merged["top20"], "abs_future_return"].mean()),
        "mean_rest80_abs_return": float(merged.loc[~merged["top20"], "abs_future_return"].mean()),
        "mean_amplitude_lift": float(daily["amplitude_lift"].mean()),
        "mean_daily_spearman": float(daily["spearman"].mean()),
        "positive_day_ratio": float(daily["amplitude_lift"].gt(0).mean()),
        "positive_semester_ratio": float(np.mean([row["amplitude_lift"] > 0 for row in semester_lifts])),
        "semesters": semester_lifts,
    }
    return report, daily


def compare_batches(
    engine: Any, batch_ids: list[str], labels_path: Path, *,
    start_date: str, end_date: str, baseline_batch_id: str, output: Path,
) -> dict[str, Any]:
    if baseline_batch_id not in batch_ids:
        raise ValueError("La baseline doit appartenir aux batchs comparés.")
    labels = prepare_labels(labels_path, start_date, end_date)
    output.mkdir(parents=True, exist_ok=False)
    reports: dict[str, dict[str, Any]] = {}
    daily_by_batch: dict[str, pd.DataFrame] = {}
    for batch_id in batch_ids:
        report, daily = evaluate_batch(load_scores(engine, batch_id, start_date, end_date), labels)
        reports[batch_id] = report
        daily_by_batch[batch_id] = daily
    baseline = reports[baseline_batch_id]
    baseline_daily = daily_by_batch[baseline_batch_id][["date", "amplitude_lift"]].rename(
        columns={"amplitude_lift": "baseline_lift"}
    )
    for batch_id, report in reports.items():
        paired = daily_by_batch[batch_id].merge(baseline_daily, on="date", how="inner")
        delta = paired["amplitude_lift"] - paired["baseline_lift"]
        report["vs_baseline"] = {
            "delta_auc": report["auc_extreme10"] - baseline["auc_extreme10"],
            "delta_precision_top10": report["precision_top10"] - baseline["precision_top10"],
            "mean_paired_daily_lift_delta": float(delta.mean()),
            "positive_paired_day_ratio": float(delta.gt(0).mean()),
        }
    ranking = sorted(
        ({"batch_id": batch_id, **report} for batch_id, report in reports.items()),
        key=lambda row: (row["mean_amplitude_lift"], row["auc_extreme10"]), reverse=True,
    )
    campaign = {
        "schema_version": 1,
        "experiment": "oracle_ablation_corrected_amplitude_comparison",
        "status": "completed", "research_only": True, "serving_ready": False,
        "retrospective": True,
        "promotion_authorized": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "baseline_batch_id": baseline_batch_id,
        "labels_path": str(labels_path),
        "period": {"start": start_date, "end": end_date},
        "ranking": ranking,
        "interpretation_rule": (
            "Comparaison rétrospective déjà observée: elle peut nommer un candidat de confirmation, "
            "jamais promouvoir un profil."
        ),
    }
    (output / "report.json").write_text(json.dumps(campaign, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(ranking).drop(columns=["semesters"], errors="ignore").to_csv(output / "ranking.csv", index=False)
    return campaign


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-ids", required=True, help="Liste séparée par des virgules.")
    parser.add_argument("--baseline-batch-id", required=True)
    parser.add_argument("--labels-path", type=Path, required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    batch_ids = [value.strip() for value in args.batch_ids.split(",") if value.strip()]
    output = args.output or Path("artifacts/research/oracle_ablation_compare") / (
        f"comparison-{datetime.now(UTC):%Y%m%d%H%M%S}"
    )
    campaign = compare_batches(
        get_sqlalchemy_engine(), batch_ids, args.labels_path,
        start_date=args.start_date, end_date=args.end_date,
        baseline_batch_id=args.baseline_batch_id, output=output,
    )
    print(json.dumps({
        "output": str(output),
        "top": [{"batch_id": row["batch_id"], "auc": row["auc_extreme10"],
                 "amplitude_lift": row["mean_amplitude_lift"],
                 "vs_baseline": row["vs_baseline"]} for row in campaign["ranking"][:5]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
