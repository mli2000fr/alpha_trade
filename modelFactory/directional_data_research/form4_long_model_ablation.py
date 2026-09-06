"""Ablation Walk-Forward du signal Form 4 dans la tête LONG mutualisée.

Recherche uniquement : compare sur les mêmes folds et les mêmes lignes un
CatBoost baseline aux mêmes features augmentées d'un petit bloc Form 4 PIT.
La période commence en 2022, première année couverte par la collecte Form 4.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.eroya_features import (
    build_form4_features, find_collection, load_form4_events,
)
from modelFactory.oracle.train import get_universe_symbols, roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.shared_directional import (
    LONG_TARGET_COL, SharedDirectionalConfig, _fit_dual_head, _prepare_X,
    _tail, attach_dual_threshold_targets, build_shared_dataset,
    load_forward_return_panel, load_profile,
)

FORM4_COLUMNS = [
    "form4_net_count_90d",
    "form4_net_value_signed_log_90d",
    "form4_net_count_90d_no10b5",
    "form4_net_value_signed_log_90d_no10b5",
    "form4_officer_net_count_90d",
    "form4_director_net_count_90d",
    "form4_exclusive_buy_90d",
    "form4_buy_value_share_90d",
    "form4_any_activity_90d",
    "form4_days_since_capped",
]


def restrict_experiment_period(frame: pd.DataFrame, start_date: str,
                               end_date: str) -> pd.DataFrame:
    """Retire les lignes de warm-up conservées par le générateur de features."""
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    return frame.loc[
        dates.between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    ].copy()


def prepare_form4_model_features(pool: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    raw = build_form4_features(pool, events)
    out = raw[["date", "symbol"]].copy()
    out["form4_net_count_90d"] = raw["eroya_form4_net_count_90d"]
    out["form4_net_value_signed_log_90d"] = np.sign(
        raw["eroya_form4_net_value_90d"]
    ) * np.log1p(raw["eroya_form4_net_value_90d"].abs())
    out["form4_net_count_90d_no10b5"] = raw["eroya_form4_net_count_90d_no10b5"]
    out["form4_net_value_signed_log_90d_no10b5"] = np.sign(
        raw["eroya_form4_net_value_90d_no10b5"]
    ) * np.log1p(raw["eroya_form4_net_value_90d_no10b5"].abs())
    out["form4_officer_net_count_90d"] = raw["eroya_form4_officer_net_count_90d"]
    out["form4_director_net_count_90d"] = raw["eroya_form4_director_net_count_90d"]
    buys = raw["eroya_form4_buy_count_90d"]
    sells = raw["eroya_form4_sell_count_90d"]
    out["form4_exclusive_buy_90d"] = ((buys > 0) & (sells == 0)).astype(float)
    out["form4_buy_value_share_90d"] = raw["eroya_form4_buy_value_share_90d"].fillna(0.0)
    out["form4_any_activity_90d"] = ((buys + sells) > 0).astype(float)
    out["form4_days_since_capped"] = raw["eroya_form4_days_since"].clip(0, 365).fillna(365.0)
    return out


def evaluate_long_score(frame: pd.DataFrame, score_column: str,
                        *, top_fraction: float = 0.10) -> dict[str, float | int | None]:
    valid = frame.dropna(subset=[score_column, LONG_TARGET_COL, "future_return"]).copy()
    y = valid[LONG_TARGET_COL].astype(int).to_numpy()
    top = _tail(valid, score_column, top_fraction, ascending=False)
    daily = top.groupby("date")["future_return"].mean()
    return {
        "rows": int(len(valid)), "selected_rows": int(len(top)),
        "selected_dates": int(top["date"].nunique()),
        "auc_long": roc_auc(y, valid[score_column].to_numpy()) if len(np.unique(y)) == 2 else None,
        "brier": float(np.mean(np.square(valid[score_column].to_numpy() - y))),
        "top10_precision_long": float(top[LONG_TARGET_COL].mean()),
        "top10_mean_return": float(top["future_return"].mean()),
        "top10_hit_rate": float((top["future_return"] > 0).mean()),
        "top10_daily_mean_return": float(daily.mean()),
    }


def run_ablation(*, batch_id: str, start_date: str, end_date: str, horizon: int,
                 profile_path: Path, output: Path, iterations: int = 600,
                 depth: int = 6, learning_rate: float = 0.03) -> dict:
    engine = get_sqlalchemy_engine()
    profile = load_profile(profile_path)
    symbols = get_universe_symbols(engine, batch_id, 20)
    config = SharedDirectionalConfig(
        horizon=horizon, objective="dual_classifier", target_mode="dual_threshold",
        context_mode="none", amplitude_weighting=False, min_train_dates=252,
        val_dates=63, test_dates=126, step_dates=126, max_splits=4,
        iterations=iterations, depth=depth, learning_rate=learning_rate,
    )
    gate_path = Path("artifacts/models") / batch_id / "_oracle_oof_gate.parquet"
    base_config = replace(config, horizon=20, objective="classifier",
                          target_mode="decile_direction")
    pool, base_columns, categoricals, population = build_shared_dataset(
        engine, batch_id, symbols, start_date=start_date, end_date=end_date,
        gate_path=gate_path, profile=profile, config=base_config)
    panel, target_diagnostics = load_forward_return_panel(
        engine, symbols, start_date=start_date, end_date=end_date,
        horizons=[horizon], sector_min_members=config.sector_min_members)
    dataset = attach_dual_threshold_targets(
        pool, panel, horizon=horizon, up_threshold=config.target_up_threshold,
        down_threshold=config.target_down_threshold)
    # build_oracle_dataset conserve volontairement un historique de warm-up
    # avant start_date. Il est utile au calcul des indicateurs mais ne doit
    # jamais définir les folds de cette expérience à couverture Form 4.
    dataset = restrict_experiment_period(dataset, start_date, end_date)
    form4_path = find_collection("form4_raw")
    form4 = prepare_form4_model_features(dataset, load_form4_events(form4_path))
    dataset = dataset.merge(form4, on=["date", "symbol"], how="left", validate="one_to_one")
    dataset[FORM4_COLUMNS] = dataset[FORM4_COLUMNS].fillna(0.0)
    folds = build_folds_adaptive(
        dataset, min_train_dates=config.min_train_dates, val_dates=config.val_dates,
        test_dates=config.test_dates, step_dates=config.step_dates,
        max_splits=config.max_splits, forecast_horizon=horizon)
    if len(folds) < 3:
        raise ValueError(f"Ablation Form 4 insuffisante: {len(folds)} folds seulement.")

    oof_parts: list[pd.DataFrame] = []
    fold_results: list[dict] = []
    for index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=[LONG_TARGET_COL]).copy()
        valid = fold["val"].dropna(subset=[LONG_TARGET_COL]).copy()
        test = fold["test"].dropna(subset=[LONG_TARGET_COL]).copy()
        if train[LONG_TARGET_COL].nunique() < 2 or valid[LONG_TARGET_COL].nunique() < 2:
            continue
        baseline_model = _fit_dual_head(train, valid, base_columns, categoricals,
                                        config, LONG_TARGET_COL)
        augmented_columns = [*base_columns, *FORM4_COLUMNS]
        form4_model = _fit_dual_head(train, valid, augmented_columns, categoricals,
                                     config, LONG_TARGET_COL)
        scored = test[["date", "symbol", "future_return", LONG_TARGET_COL]].copy()
        scored["baseline_probability"] = baseline_model.predict_proba(
            _prepare_X(test, base_columns, categoricals))[:, 1]
        scored["form4_probability"] = form4_model.predict_proba(
            _prepare_X(test, augmented_columns, categoricals))[:, 1]
        scored["fold_index"] = index
        base_metrics = evaluate_long_score(scored, "baseline_probability")
        form4_metrics = evaluate_long_score(scored, "form4_probability")
        fold_results.append({
            "fold_index": index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "baseline": base_metrics, "form4": form4_metrics,
            "delta_auc": form4_metrics["auc_long"] - base_metrics["auc_long"],
            "delta_top10_precision": form4_metrics["top10_precision_long"] - base_metrics["top10_precision_long"],
            "delta_top10_return": form4_metrics["top10_mean_return"] - base_metrics["top10_mean_return"],
        })
        oof_parts.append(scored)
    if len(oof_parts) < 3:
        raise ValueError("Moins de trois folds Form 4 ont produit des prédictions.")
    oof = pd.concat(oof_parts, ignore_index=True)
    baseline = evaluate_long_score(oof, "baseline_probability")
    augmented = evaluate_long_score(oof, "form4_probability")
    return_deltas = np.asarray([x["delta_top10_return"] for x in fold_results])
    auc_deltas = np.asarray([x["delta_auc"] for x in fold_results])
    precision_deltas = np.asarray([x["delta_top10_precision"] for x in fold_results])
    result = {
        "schema_version": 1, "experiment": "form4_long_incremental_ablation",
        "research_only": True, "serving_ready": False, "batch_id": batch_id,
        "period": [start_date, end_date], "horizon": horizon,
        "pit_contract": "filing_date plus one business day",
        "coverage_warning": "Form 4 source begins in 2022; no inference before start_date",
        "population": population, "target_diagnostics": target_diagnostics,
        "base_feature_count": len(base_columns), "form4_columns": FORM4_COLUMNS,
        "n_folds": len(fold_results), "baseline": baseline, "form4": augmented,
        "delta": {
            "auc_long": augmented["auc_long"] - baseline["auc_long"],
            "top10_precision_long": augmented["top10_precision_long"] - baseline["top10_precision_long"],
            "top10_mean_return": augmented["top10_mean_return"] - baseline["top10_mean_return"],
            "positive_auc_folds": int((auc_deltas > 0).sum()),
            "positive_precision_folds": int((precision_deltas > 0).sum()),
            "positive_return_folds": int((return_deltas > 0).sum()),
        },
        "folds": fold_results,
    }
    minimum_positive = math.ceil(len(fold_results) * 0.60)
    result["development_gates"] = {
        "auc_lift_gte_0_005": result["delta"]["auc_long"] >= 0.005,
        "return_lift_gte_0_0025": result["delta"]["top10_mean_return"] >= 0.0025,
        "positive_return_folds_gte_60pct": result["delta"]["positive_return_folds"] >= minimum_positive,
        "positive_auc_folds_gte_60pct": result["delta"]["positive_auc_folds"] >= minimum_positive,
    }
    result["development_gates_passed"] = all(result["development_gates"].values())
    output.mkdir(parents=True, exist_ok=False)
    oof.to_parquet(output / "paired_oof_predictions.parquet", index=False)
    (output / "report.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(fold_results).to_json(output / "folds.json", orient="records", indent=2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--start-date", default="2022-01-04")
    parser.add_argument("--end-date", default="2025-07-11")
    parser.add_argument("--horizon", type=int, choices=[10, 20], required=True)
    parser.add_argument("--feature-profile", type=Path,
                        default=Path("config/features/shared_direction/shared.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    args = parser.parse_args()
    output = args.output or Path("artifacts/research/eroya_directional") / (
        f"form4-model-ablation-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-h{args.horizon}-{args.batch_id[-6:]}")
    result = run_ablation(batch_id=args.batch_id, start_date=args.start_date,
                          end_date=args.end_date, horizon=args.horizon,
                          profile_path=args.feature_profile, output=output,
                          iterations=args.iterations, depth=args.depth,
                          learning_rate=args.learning_rate)
    print(json.dumps({"output": str(output), "horizon": args.horizon,
                      "delta": result["delta"], "gates": result["development_gates"],
                      "passed": result["development_gates_passed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
