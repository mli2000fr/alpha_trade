"""Compare deux univers Oracle sur leurs prédictions Walk-Forward OOF."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.train import decile_monotonicity, precision_recall_at_top_pct, roc_auc


def load_oof(engine: Any, batch_id: str, horizon: int = 20) -> pd.DataFrame:
    query = text(
        "SELECT p.prediction_date date,p.symbol,p.proba_extreme,p.fold_start,"
        "l.oracle_extreme10,l.oracle_pct_rank,l.oracle_decile,l.future_return "
        "FROM oracle_extreme_predictions p JOIN global_oracle_labels l "
        "ON l.prediction_date=p.prediction_date AND l.symbol=p.symbol "
        "AND l.batch_id=p.batch_id AND l.horizon=:h "
        "WHERE p.batch_id=:batch_id AND p.fold_start IS NOT NULL "
        "AND l.target_quality_valid=1"
    )
    with engine.connect() as connection:
        frame = pd.read_sql(query, connection, params={"batch_id": batch_id, "h": horizon})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["fold_start"] = pd.to_datetime(frame["fold_start"]).dt.normalize()
    frame["semester"] = frame["date"].dt.year.astype(str) + "H" + np.where(frame["date"].dt.month <= 6, "1", "2")
    return frame


def daily_top_metrics(frame: pd.DataFrame, pct: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for date, group in frame.groupby("date"):
        group = group.dropna(subset=["proba_extreme", "oracle_extreme10", "future_return"])
        if len(group) < 20:
            continue
        count = max(1, int(np.ceil(len(group) * pct)))
        chosen = group.nlargest(count, "proba_extreme")
        actual = group[group["oracle_extreme10"].eq(1)]
        rows.append({
            "date": date,
            "universe": len(group),
            "precision": float(chosen["oracle_extreme10"].mean()),
            "recall": float(chosen["oracle_extreme10"].sum() / len(actual)) if len(actual) else np.nan,
            "selected_abs_return": float(chosen["future_return"].abs().mean()),
            "universe_abs_return": float(group["future_return"].abs().mean()),
            "actual_extreme_abs_return": float(actual["future_return"].abs().mean()) if len(actual) else np.nan,
        })
    result = pd.DataFrame(rows)
    if not result.empty:
        result["amplitude_lift"] = result["selected_abs_return"] / result["universe_abs_return"]
        result["extreme_amplitude_retention"] = (
            result["selected_abs_return"] / result["actual_extreme_abs_return"]
        )
    return result


def summarize(frame: pd.DataFrame) -> dict[str, Any]:
    score = frame["proba_extreme"].to_numpy(dtype=float)
    target = frame["oracle_extreme10"].to_numpy(dtype=float)
    valid = np.isfinite(score) & np.isfinite(target)
    pr10 = precision_recall_at_top_pct(frame, "proba_extreme", pct=0.10, target_col="oracle_extreme10")
    pr20 = precision_recall_at_top_pct(frame, "proba_extreme", pct=0.20, target_col="oracle_extreme10")
    mono, _ = decile_monotonicity(frame, "proba_extreme")
    daily10 = daily_top_metrics(frame, 0.10)
    daily20 = daily_top_metrics(frame, 0.20)
    return {
        "rows": int(len(frame)),
        "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "first_date": frame["date"].min().date().isoformat(),
        "last_date": frame["date"].max().date().isoformat(),
        "folds": int(frame["fold_start"].nunique()),
        "prevalence": float(np.mean(target[valid])),
        "auc": roc_auc(target[valid], score[valid]),
        "brier": float(np.mean((score[valid] - target[valid]) ** 2)),
        "precision_at_10pct": pr10["precision"],
        "recall_at_10pct": pr10["recall"],
        "precision_at_20pct": pr20["precision"],
        "recall_at_20pct": pr20["recall"],
        "decile_monotonicity": mono,
        "top10_amplitude_lift": float(daily10["amplitude_lift"].mean()),
        "top10_extreme_amplitude_retention": float(daily10["extreme_amplitude_retention"].mean()),
        "top20_amplitude_lift": float(daily20["amplitude_lift"].mean()),
        "top20_extreme_amplitude_retention": float(daily20["extreme_amplitude_retention"].mean()),
    }


def grouped_metrics(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    rows = []
    for value, part in frame.groupby(column):
        metrics = summarize(part)
        rows.append({column: str(value), **metrics})
    return pd.DataFrame(rows)


def grouped_core_metrics(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Agrégation légère pour les nombreuses modalités, sans boucles quotidiennes."""
    rows = []
    for value, part in frame.groupby(column):
        score = part["proba_extreme"].to_numpy(dtype=float)
        target = part["oracle_extreme10"].to_numpy(dtype=float)
        valid = np.isfinite(score) & np.isfinite(target)
        pr20 = precision_recall_at_top_pct(
            part, "proba_extreme", pct=0.20, target_col="oracle_extreme10"
        )
        rows.append({
            column: str(value),
            "rows": int(len(part)),
            "dates": int(part["date"].nunique()),
            "symbols": int(part["symbol"].nunique()),
            "prevalence": float(np.mean(target[valid])),
            "auc": roc_auc(target[valid], score[valid]),
            "precision_at_20pct": pr20["precision"],
            "recall_at_20pct": pr20["recall"],
        })
    return pd.DataFrame(rows)


def moving_block_interval(values: pd.Series, *, seed: int = 20260908) -> tuple[float, float]:
    """IC 95 % par bootstrap de blocs de 21 séances pour préserver l'autocorrélation."""
    array = values.dropna().to_numpy(dtype=float)
    if len(array) < 42:
        return np.nan, np.nan
    block = 21
    blocks_needed = int(np.ceil(len(array) / block))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, len(array) - block + 1, size=(2_000, blocks_needed))
    samples = np.concatenate([array[starts + offset] for offset in range(block)], axis=1)[:, : len(array)]
    means = samples.mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def paired_daily_comparison(old: pd.DataFrame, new: pd.DataFrame, pct: float) -> dict[str, Any]:
    old_daily = daily_top_metrics(old, pct).set_index("date")
    new_daily = daily_top_metrics(new, pct).set_index("date")
    paired = old_daily.join(new_daily, lsuffix="_old", rsuffix="_new", how="inner")
    result: dict[str, Any] = {"dates": int(len(paired))}
    for metric in ("precision", "recall", "amplitude_lift", "extreme_amplitude_retention"):
        delta = paired[f"{metric}_new"] - paired[f"{metric}_old"]
        result[f"delta_{metric}"] = float(delta.mean())
        result[f"win_rate_{metric}"] = float((delta > 0).mean())
        low, high = moving_block_interval(delta)
        result[f"delta_{metric}_ci95"] = [low, high]
    return result


def common_symbol_control(old: pd.DataFrame, new: pd.DataFrame) -> dict[str, Any]:
    common_symbols = sorted(set(old["symbol"]) & set(new["symbol"]))
    left = old[old["symbol"].isin(common_symbols)].copy()
    right = new[new["symbol"].isin(common_symbols)].copy()
    merged = left.merge(right, on=["date", "symbol"], suffixes=("_old", "_new"))
    return {
        "symbols": len(common_symbols),
        "rows": int(len(merged)),
        "future_return_max_abs_diff": float(
            (merged["future_return_old"] - merged["future_return_new"]).abs().max()
        ),
        "score_spearman": float(merged[["proba_extreme_old", "proba_extreme_new"]].corr(method="spearman").iloc[0, 1]),
        "old": summarize(left),
        "new": summarize(right),
    }


def run(old_batch: str, new_batch: str, output_root: Path, new_selection_csv: Path | None = None) -> Path:
    engine = get_sqlalchemy_engine()
    old = load_oof(engine, old_batch)
    new = load_oof(engine, new_batch)
    if old.empty or new.empty:
        raise RuntimeError(f"OOF manquant: old={len(old)} new={len(new)}")
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "old_batch": old_batch,
        "new_batch": new_batch,
        "old": summarize(old),
        "new": summarize(new),
        "paired_daily_top10": paired_daily_comparison(old, new, 0.10),
        "paired_daily_top20": paired_daily_comparison(old, new, 0.20),
        "common_symbol_control": common_symbol_control(old, new),
    }
    output = output_root / f"p0e-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    grouped_metrics(old, "fold_start").to_csv(output / "old_by_fold.csv", index=False)
    grouped_metrics(new, "fold_start").to_csv(output / "new_by_fold.csv", index=False)
    grouped_metrics(old, "semester").to_csv(output / "old_by_semester.csv", index=False)
    grouped_metrics(new, "semester").to_csv(output / "new_by_semester.csv", index=False)
    if new_selection_csv is not None and new_selection_csv.exists():
        strata = pd.read_csv(new_selection_csv)
        enriched = new.merge(
            strata[["symbol", "cap_bucket", "vol_quintile", "beta_quintile", "sector"]],
            on="symbol",
            how="left",
        )
        for column in ("cap_bucket", "vol_quintile", "beta_quintile"):
            grouped_metrics(enriched.dropna(subset=[column]), column).to_csv(
                output / f"new_by_{column}.csv", index=False
            )
        grouped_core_metrics(enriched.dropna(subset=["sector"]), "sector").to_csv(
            output / "new_by_sector.csv", index=False
        )
    print(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="P0e — comparaison OOF de deux univers Oracle")
    parser.add_argument("--old-batch", required=True)
    parser.add_argument("--new-batch", required=True)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/research/oracle_universe_p0e"))
    parser.add_argument("--new-selection-csv", type=Path, default=None)
    args = parser.parse_args()
    run(args.old_batch, args.new_batch, args.output_root, args.new_selection_csv)


if __name__ == "__main__":
    main()
