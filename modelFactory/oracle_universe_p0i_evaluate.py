"""P0i — évaluation post-hoc d'un run Oracle dynamique shadow.

Le script ne réentraîne rien et n'écrit dans aucune table. Les labels réalisés
doivent être reconstruits séparément par ``oracle.build_labels --dry-run`` afin
que les dates postérieures à la fin de l'entraînement soient évaluables.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.train import precision_recall_at_top_pct, roc_auc
from modelFactory.oracle_universe_p0e_compare import (
    daily_top_metrics,
    load_oof,
    moving_block_interval,
)


def load_shadow(run_dir: Path) -> pd.DataFrame:
    parts = sorted((run_dir / "parts").glob("*.parquet"))
    if not parts:
        raise FileNotFoundError(f"Aucun fragment shadow dans {run_dir / 'parts'}")
    # Les cibles embarquées dans le shadow peuvent être incomplètes après la fin
    # de l'entraînement. P0i les remplace toujours par le Parquet post-hoc ; les
    # retirer avant concaténation évite aussi les changements de dtype all-NA.
    fragments = [
        pd.read_parquet(path).drop(
            columns=["future_return", "oracle_extreme10"], errors="ignore"
        )
        for path in parts
    ]
    frame = pd.concat(fragments, ignore_index=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    return frame


def prepare_evaluation(scores: pd.DataFrame, labels: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    labels = labels.copy()
    labels["prediction_date"] = pd.to_datetime(
        labels["prediction_date"], errors="coerce"
    ).dt.normalize()
    keep = [
        "prediction_date", "symbol", "future_return", "oracle_extreme10",
        "target_quality_valid", "target_quality_reason",
    ]
    merged = scores.drop(
        columns=["future_return", "oracle_extreme10"], errors="ignore"
    ).merge(
        labels[keep], left_on=["date", "symbol"],
        right_on=["prediction_date", "symbol"], how="left", validate="one_to_one",
    )
    valid = (
        merged["target_quality_valid"].eq(1)
        & merged["future_return"].notna()
        & merged["oracle_extreme10"].notna()
    )
    evaluated = merged.loc[valid].copy()
    evaluated["semester"] = (
        evaluated["date"].dt.year.astype(str)
        + "H"
        + evaluated["date"].dt.month.le(6).map({True: "1", False: "2"})
    )
    evaluated["month"] = evaluated["date"].dt.to_period("M").astype(str)
    coverage = {
        "shadow_rows": int(len(scores)),
        "label_rows_joined": int(merged["future_return"].notna().sum()),
        "valid_rows": int(len(evaluated)),
        "invalid_or_unavailable_rows": int(len(scores) - len(evaluated)),
        "shadow_dates": int(scores["date"].nunique()),
        "evaluated_dates": int(evaluated["date"].nunique()),
    }
    return evaluated, coverage


def amplitude_deciles(frame: pd.DataFrame) -> tuple[float | None, pd.DataFrame]:
    data = frame.dropna(subset=["proba_extreme", "future_return"]).copy()
    if data.empty:
        return None, pd.DataFrame()
    data["score_decile"] = (
        np.floor(
            data.groupby("date")["proba_extreme"].rank(pct=True).clip(upper=1 - 1e-9) * 10
        ).clip(0, 9).astype(int) + 1
    )
    data["abs_return"] = data["future_return"].abs()
    table = data.groupby("score_decile")["abs_return"].agg(
        mean_abs_return="mean", median_abs_return="median", rows="size"
    )
    if len(table) < 2:
        return None, table
    monotonicity = table["mean_abs_return"].corr(
        pd.Series(table.index, index=table.index, dtype=float), method="spearman"
    )
    return float(monotonicity), table


def summarize_amplitude(frame: pd.DataFrame) -> dict[str, Any]:
    score = frame["proba_extreme"].to_numpy(dtype=float)
    target = frame["oracle_extreme10"].to_numpy(dtype=float)
    valid = np.isfinite(score) & np.isfinite(target)
    pr10 = precision_recall_at_top_pct(
        frame, "proba_extreme", pct=0.10, target_col="oracle_extreme10"
    )
    pr20 = precision_recall_at_top_pct(
        frame, "proba_extreme", pct=0.20, target_col="oracle_extreme10"
    )
    daily10 = daily_top_metrics(frame, 0.10)
    daily20 = daily_top_metrics(frame, 0.20)
    monotonicity, _ = amplitude_deciles(frame)
    lift10_ci = moving_block_interval(daily10["amplitude_lift"] - 1.0)
    lift20_ci = moving_block_interval(daily20["amplitude_lift"] - 1.0)
    return {
        "rows": int(len(frame)),
        "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "first_date": frame["date"].min().date().isoformat(),
        "last_date": frame["date"].max().date().isoformat(),
        "prevalence": float(np.mean(target[valid])),
        "auc": roc_auc(target[valid], score[valid]),
        "precision_at_10pct": pr10["precision"],
        "recall_at_10pct": pr10["recall"],
        "precision_at_20pct": pr20["precision"],
        "recall_at_20pct": pr20["recall"],
        "amplitude_decile_monotonicity": monotonicity,
        "top10_mean_abs_return": float(daily10["selected_abs_return"].mean()),
        "top10_amplitude_lift": float(daily10["amplitude_lift"].mean()),
        "top10_lift_minus_one_ci95": list(lift10_ci),
        "top10_extreme_amplitude_retention": float(
            daily10["extreme_amplitude_retention"].mean()
        ),
        "top20_mean_abs_return": float(daily20["selected_abs_return"].mean()),
        "top20_amplitude_lift": float(daily20["amplitude_lift"].mean()),
        "top20_lift_minus_one_ci95": list(lift20_ci),
        "top20_extreme_amplitude_retention": float(
            daily20["extreme_amplitude_retention"].mean()
        ),
    }


def grouped_summary(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return pd.DataFrame([
        {column: str(value), **summarize_amplitude(part)}
        for value, part in frame.groupby(column, sort=True)
    ])


def universe_turnover(scores: pd.DataFrame) -> dict[str, float | int]:
    scopes = [set(group["symbol"].astype(str)) for _, group in scores.groupby("date", sort=True)]
    turnover = [
        1.0 - len(previous & current) / max(1, len(previous | current))
        for previous, current in zip(scopes, scopes[1:])
    ]
    sizes = [len(scope) for scope in scopes]
    return {
        "dates": len(scopes),
        "daily_min": min(sizes) if sizes else 0,
        "daily_median": float(np.median(sizes)) if sizes else 0.0,
        "daily_max": max(sizes) if sizes else 0,
        "mean_daily_jaccard_turnover": float(np.mean(turnover)) if turnover else 0.0,
        "max_daily_jaccard_turnover": float(np.max(turnover)) if turnover else 0.0,
    }


def selection_concentration(frame: pd.DataFrame, pct: float = 0.20) -> dict[str, float | int]:
    selections = []
    for _, group in frame.groupby("date", sort=True):
        count = max(1, int(np.ceil(len(group) * pct)))
        selections.append(group.nlargest(count, "proba_extreme")[["date", "symbol"]])
    selected = pd.concat(selections, ignore_index=True)
    shares = selected["symbol"].value_counts(normalize=True)
    return {
        "rows": int(len(selected)),
        "symbols": int(selected["symbol"].nunique()),
        "largest_symbol_share": float(shares.iloc[0]),
        "top10_symbols_share": float(shares.iloc[:10].sum()),
        "symbol_hhi": float(np.square(shares).sum()),
    }


def score_drift(frame: pd.DataFrame) -> dict[str, Any]:
    stats = frame.groupby("semester")["proba_extreme"].agg(
        rows="size", mean="mean", std="std", median="median"
    )
    return {str(index): row.to_dict() for index, row in stats.iterrows()}


def direction_diagnostic(frame: pd.DataFrame, pct: float = 0.20) -> dict[str, float | int]:
    """Décrit le sens réalisé du TOP score sans en faire un gate P0i."""
    selections = []
    for _, group in frame.groupby("date", sort=True):
        count = max(1, int(np.ceil(len(group) * pct)))
        selections.append(group.nlargest(count, "proba_extreme"))
    selected = pd.concat(selections, ignore_index=True)
    true_extremes = selected[selected["oracle_extreme10"].eq(1)]
    return {
        "rows": int(len(selected)),
        "mean_signed_return": float(selected["future_return"].mean()),
        "positive_return_rate": float(selected["future_return"].gt(0).mean()),
        "negative_return_rate": float(selected["future_return"].lt(0).mean()),
        "true_extreme_rows": int(len(true_extremes)),
        "positive_rate_among_true_extremes": float(
            true_extremes["future_return"].gt(0).mean()
        ),
    }


def run(
    shadow_dir: Path,
    labels_path: Path,
    output_root: Path,
    *,
    reference_batch: str | None = None,
    reference_start: str | None = None,
    reference_end: str | None = None,
) -> Path:
    scores = load_shadow(shadow_dir)
    labels = pd.read_parquet(labels_path)
    evaluated, coverage = prepare_evaluation(scores, labels)
    if evaluated.empty:
        raise RuntimeError("Aucun score shadow ne possède de label H20 valide.")
    overall = summarize_amplitude(evaluated)
    semesters = grouped_summary(evaluated, "semester")
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "experiment": "P0i_oracle_dynamic_shadow_holdout",
        "shadow_dir": str(shadow_dir),
        "labels_path": str(labels_path),
        "research_only": True,
        "trading_eligible": False,
        "coverage": coverage,
        "overall": overall,
        "by_semester": semesters.to_dict("records"),
        "universe": universe_turnover(scores),
        "top20_concentration": selection_concentration(evaluated),
        "score_drift": score_drift(evaluated),
        "direction_diagnostic_not_a_gate": {
            "overall": direction_diagnostic(evaluated),
            "by_semester": {
                str(value): direction_diagnostic(part)
                for value, part in evaluated.groupby("semester", sort=True)
            },
        },
        "decision_evidence": {
            "top20_lift_above_random_ci": bool(
                overall["top20_lift_minus_one_ci95"][0] > 0
            ),
            "all_semesters_top20_lift_above_one": bool(
                semesters["top20_amplitude_lift"].gt(1.0).all()
            ),
            "all_semesters_auc_above_half": bool(semesters["auc"].gt(0.5).all()),
        },
    }
    if reference_batch:
        reference = load_oof(get_sqlalchemy_engine(), reference_batch)
        if reference_start:
            reference = reference[reference["date"] >= pd.Timestamp(reference_start)]
        if reference_end:
            reference = reference[reference["date"] <= pd.Timestamp(reference_end)]
        if not reference.empty:
            reference_summary = summarize_amplitude(reference)
            report["prior_oof_reference"] = {
                "comparison_type": "nonpaired_temporal_context_only",
                "batch_id": reference_batch,
                "summary": reference_summary,
                "delta_shadow_minus_reference": {
                    metric: float(overall[metric] - reference_summary[metric])
                    for metric in (
                        "auc", "precision_at_10pct", "precision_at_20pct",
                        "top10_amplitude_lift", "top20_amplitude_lift",
                    )
                },
            }
    output = output_root / f"p0i-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    grouped_summary(evaluated, "semester").to_csv(output / "by_semester.csv", index=False)
    grouped_summary(evaluated, "month").to_csv(output / "by_month.csv", index=False)
    _, deciles = amplitude_deciles(evaluated)
    deciles.to_csv(output / "amplitude_by_score_decile.csv")
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="P0i — audit d'un Oracle dynamique shadow")
    parser.add_argument("--shadow-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/oracle_universe_p0i"),
    )
    parser.add_argument("--reference-batch", default=None)
    parser.add_argument("--reference-start", default=None)
    parser.add_argument("--reference-end", default=None)
    args = parser.parse_args()
    run(
        args.shadow_dir, args.labels, args.output_root,
        reference_batch=args.reference_batch,
        reference_start=args.reference_start,
        reference_end=args.reference_end,
    )


if __name__ == "__main__":
    main()
