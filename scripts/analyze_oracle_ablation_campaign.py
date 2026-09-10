"""Compare des batchs Oracle Extreme sur leurs prédictions Walk-Forward OOS."""
from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def _load_batch(engine, batch_id: str) -> tuple[dict[str, object], pd.DataFrame]:
    with engine.connect() as connection:
        batch_row = connection.execute(
            text(
                "SELECT batch_id, status, symbol_source, training_start_date, "
                "training_end_date, command_line, failure_reason "
                "FROM model_training_batch WHERE batch_id = :batch_id"
            ),
            {"batch_id": batch_id},
        ).mappings().first()
        frame = pd.read_sql(
            text(
                "SELECT prediction_date AS date, symbol, proba_extreme, "
                "future_return, oracle_extreme10, fold_start "
                "FROM alpha_trade.oracle_extreme_predictions "
                "WHERE batch_id = :batch_id "
                "AND oracle_extreme10 IS NOT NULL AND future_return IS NOT NULL"
            ),
            connection,
            params={"batch_id": batch_id},
        )
    return dict(batch_row or {}), frame


def _daily_top(frame: pd.DataFrame, pct: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for day, group in frame.groupby("date", sort=True):
        valid = group.dropna(subset=["proba_extreme", "oracle_extreme10"])
        if len(valid) < 20:
            continue
        selected = valid.nlargest(max(1, ceil(len(valid) * pct)), "proba_extreme")
        actual = int(valid["oracle_extreme10"].sum())
        rows.append(
            {
                "date": day,
                "precision": float(selected["oracle_extreme10"].mean()),
                "recall": float(selected["oracle_extreme10"].sum() / actual) if actual else np.nan,
                "selected_abs_return": float(selected["future_return"].abs().mean()),
                "universe_abs_return": float(valid["future_return"].abs().mean()),
            }
        )
    return pd.DataFrame(rows)


def _spearman_decile(frame: pd.DataFrame, value: pd.Series) -> float | None:
    valid = frame.dropna(subset=["proba_extreme"]).copy()
    if valid.empty:
        return None
    valid["_value"] = value.loc[valid.index]
    valid["_decile"] = (
        np.floor(
            valid.groupby("date")["proba_extreme"]
            .rank(pct=True)
            .clip(upper=1 - 1e-9)
            * 10
        )
        .clip(0, 9)
        .astype(int)
        + 1
    )
    by_decile = valid.groupby("_decile")["_value"].mean()
    if len(by_decile) < 2:
        return None
    result = by_decile.index.to_series().corr(by_decile, method="spearman")
    return float(result) if pd.notna(result) else None


def _metrics(
    frame: pd.DataFrame,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = _daily_top(frame, 0.10)
    daily20 = _daily_top(frame, 0.20)
    folds: list[dict[str, object]] = []
    for fold_start, fold in frame.groupby("fold_start", dropna=True, sort=True):
        fold_daily = _daily_top(fold, 0.10)
        fold_daily20 = _daily_top(fold, 0.20)
        folds.append(
            {
                "fold_start": str(fold_start),
                "precision": float(fold_daily["precision"].mean()),
                "precision20": float(fold_daily20["precision"].mean()),
                "recall": float(fold_daily["recall"].mean()),
                "auc": float(roc_auc_score(fold["oracle_extreme10"], fold["proba_extreme"])),
                "dates": int(fold_daily["date"].nunique()),
            }
        )
    fold_frame = pd.DataFrame(folds)
    prevalence = float(frame["oracle_extreme10"].mean())
    precision = float(daily["precision"].mean())
    overall = {
        "rows": int(len(frame)),
        "symbols": int(frame["symbol"].nunique()),
        "dates": int(frame["date"].nunique()),
        "first_date": str(frame["date"].min()),
        "last_date": str(frame["date"].max()),
        "folds": int(frame["fold_start"].nunique()),
        "prevalence": prevalence,
        "precision_at_10pct": precision,
        "recall_at_10pct": float(daily["recall"].mean()),
        "precision_at_20pct": float(daily20["precision"].mean()),
        "recall_at_20pct": float(daily20["recall"].mean()),
        "lift": precision / prevalence if prevalence else None,
        "auc": float(roc_auc_score(frame["oracle_extreme10"], frame["proba_extreme"])),
        "fold_precision_mean": float(fold_frame["precision"].mean()),
        "fold_precision_median": float(fold_frame["precision"].median()),
        "fold_precision_min": float(fold_frame["precision"].min()),
        "fold_precision_std": float(fold_frame["precision"].std(ddof=1)),
        "fold_precision20_min": float(fold_frame["precision20"].min()),
        "fold_precision20_std": float(fold_frame["precision20"].std(ddof=1)),
        "extreme_rate_decile_spearman": _spearman_decile(frame, frame["oracle_extreme10"].astype(float)),
        "abs_return_decile_spearman": _spearman_decile(frame, frame["future_return"].abs()),
        "top10_abs_return_lift": float(
            daily["selected_abs_return"].mean() / daily["universe_abs_return"].mean()
        ),
        "top20_abs_return_lift": float(
            daily20["selected_abs_return"].mean() / daily20["universe_abs_return"].mean()
        ),
    }
    return overall, daily, daily20, fold_frame


def _feature_count(batch_id: str) -> int | None:
    profile = Path("artifacts/models/oracle/champions") / batch_id / "feature_profile.json"
    if profile.is_file():
        try:
            return len(json.loads(profile.read_text(encoding="utf-8")).get("feature_columns") or [])
        except (OSError, json.JSONDecodeError):
            pass
    manifest = Path("artifacts/models") / batch_id / "cascade_manifest.json"
    if manifest.is_file():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            return len(((payload.get("oracle") or {}).get("profile") or {}).get("feature_columns") or [])
        except (OSError, json.JSONDecodeError):
            pass
    return None


def _paired_daily(candidate: pd.DataFrame, baseline: pd.DataFrame) -> dict[str, object]:
    paired = baseline[["date", "precision"]].merge(
        candidate[["date", "precision"]], on="date", suffixes=("_baseline", "_candidate")
    )
    delta = (paired["precision_candidate"] - paired["precision_baseline"]).to_numpy(dtype=float)
    if not len(delta):
        return {"paired_dates": 0}
    rng = np.random.default_rng(42)
    # H20 induit un fort chevauchement entre dates adjacentes. Un bootstrap
    # IID donnerait des intervalles artificiellement étroits ; on rééchantillonne
    # donc des blocs contigus de 20 séances.
    block_length = min(20, len(delta))
    blocks_per_sample = ceil(len(delta) / block_length)
    starts = rng.integers(
        0,
        len(delta) - block_length + 1,
        size=(5000, blocks_per_sample),
    )
    indices = starts[:, :, None] + np.arange(block_length)[None, None, :]
    bootstrap = delta[indices].reshape(5000, -1)[:, : len(delta)].mean(axis=1)
    return {
        "paired_dates": int(len(delta)),
        "bootstrap_block_length": block_length,
        "precision_delta": float(delta.mean()),
        "daily_win_rate": float((delta > 0).mean()),
        "delta_ci95_low": float(np.quantile(bootstrap, 0.025)),
        "delta_ci95_high": float(np.quantile(bootstrap, 0.975)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("batches", nargs="+", help="label=batch_id")
    args = parser.parse_args()
    engine = get_sqlalchemy_engine()

    baseline_meta, baseline_frame = _load_batch(engine, args.baseline)
    if baseline_frame.empty:
        raise SystemExit(f"Baseline Oracle vide: {args.baseline}")
    baseline_metrics, baseline_daily, baseline_daily20, baseline_folds = _metrics(baseline_frame)
    if args.compact:
        baseline_meta = {
            key: baseline_meta.get(key)
            for key in ("status", "symbol_source", "training_start_date", "training_end_date", "failure_reason")
        }
    output: dict[str, object] = {
        "baseline": {
            "batch_id": args.baseline,
            "batch": baseline_meta,
            "features": _feature_count(args.baseline),
            "metrics": baseline_metrics,
            "fold_metrics": [] if args.compact else baseline_folds.to_dict(orient="records"),
        },
        "candidates": [],
    }

    for spec in args.batches:
        label, batch_id = spec.split("=", 1)
        metadata, frame = _load_batch(engine, batch_id)
        if args.compact:
            metadata = {
                key: metadata.get(key)
                for key in ("status", "symbol_source", "training_start_date", "training_end_date", "failure_reason")
            }
        candidate: dict[str, object] = {
            "label": label,
            "batch_id": batch_id,
            "batch": metadata,
            "features": _feature_count(batch_id),
        }
        if frame.empty:
            candidate["error"] = "no_labeled_oos_predictions"
        else:
            metrics, daily, daily20, folds = _metrics(frame)
            candidate["metrics"] = metrics
            candidate["paired_vs_baseline"] = _paired_daily(daily, baseline_daily)
            candidate["paired_top20_vs_baseline"] = _paired_daily(daily20, baseline_daily20)
            fold_pair = baseline_folds[["fold_start", "precision"]].merge(
                folds[["fold_start", "precision"]],
                on="fold_start",
                suffixes=("_baseline", "_candidate"),
            )
            fold_pair["delta"] = fold_pair["precision_candidate"] - fold_pair["precision_baseline"]
            candidate["folds_better"] = int((fold_pair["delta"] > 0).sum())
            candidate["folds_paired"] = int(len(fold_pair))
            candidate["fold_delta_min"] = float(fold_pair["delta"].min()) if len(fold_pair) else None
            candidate["fold_metrics"] = [] if args.compact else folds.to_dict(orient="records")
        output["candidates"].append(candidate)

    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
