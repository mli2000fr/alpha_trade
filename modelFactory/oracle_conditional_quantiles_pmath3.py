"""P-MATH-3: conditional H20 return quantiles inside the OOF Oracle TOP20 pool.

Research-only. Quantile models learn raw future returns; direction is evaluated
separately against D1/D10 using a frozen, label-free score from q10 and q90.
No database writes, serving artifacts, or backtest configuration changes.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import GUARD_COL, build_dataset as build_oracle_dataset
from modelFactory.oracle.train import get_universe_symbols
from modelFactory.oracle_separability_pmath0 import (
    DECILE, TARGET, attach_task, balanced_by_date, fit_preprocessor, transform,
)
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.shared_directional import ORACLE_GATE_SCORE_COL, _load_gate, load_profile

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = Path("config/research/pmath3_conditional_quantiles.json")
RETURN = "future_return"


def pinball_loss(target: np.ndarray, forecast: np.ndarray, quantile: float) -> float:
    error = np.asarray(target, dtype=float) - np.asarray(forecast, dtype=float)
    return float(np.mean(np.maximum(quantile * error, (quantile - 1.0) * error)))


def rearrange_quantiles(predictions: np.ndarray) -> tuple[np.ndarray, float]:
    """Correct crossings without using targets or refitting any model."""
    raw = np.asarray(predictions, dtype=float)
    if raw.ndim != 2 or raw.shape[1] < 2:
        raise ValueError("Expected a two-dimensional matrix of ordered quantiles")
    crossing = float(np.mean(np.any(np.diff(raw, axis=1) < 0.0, axis=1)))
    return np.sort(raw, axis=1), crossing


def tail_scores(predictions: np.ndarray, quantiles: list[float]) -> dict[str, np.ndarray]:
    """Frozen location and skew diagnostics, never trained on D1/D10 labels."""
    lookup = {round(float(q), 2): idx for idx, q in enumerate(quantiles)}
    q10 = predictions[:, lookup[0.10]]
    q50 = predictions[:, lookup[0.50]]
    q90 = predictions[:, lookup[0.90]]
    return {
        "tail_midpoint_q10_q90": (q10 + q90) / 2.0,
        "conditional_median_q50": q50,
        "tail_asymmetry_q10_q50_q90": q90 + q10 - 2.0 * q50,
    }


def select_train_rows(train: pd.DataFrame, maximum: int, seed: int) -> pd.DataFrame:
    """Reproducible training-only subsample spanning the full train calendar."""
    if len(train) <= maximum:
        return train.copy()
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(train), size=maximum, replace=False)
    return train.iloc[np.sort(indices)].copy()


def daily_top_fraction(frame: pd.DataFrame, score: str, fraction: float = 0.10) -> pd.Series:
    ranks = frame.groupby("date")[score].rank(method="first", ascending=False)
    sizes = frame.groupby("date")[score].transform("size")
    count = np.ceil(sizes * fraction).clip(lower=1)
    return ranks.le(count)


def _fold_specs(dataset: pd.DataFrame, config: dict[str, Any], horizon: int) -> list[dict[str, Any]]:
    wf = config["walk_forward"]
    if wf.get("fold_selection") != "latest":
        raise ValueError("P-MATH-3 requires latest walk-forward folds")
    folds = build_folds_adaptive(
        dataset, min_train_dates=int(wf["min_train_dates"]), val_dates=int(wf["val_dates"]),
        test_dates=int(wf["test_dates"]), step_dates=int(wf["step_dates"]),
        max_splits=10_000, forecast_horizon=horizon, materialize=False,
    )
    return folds[-int(wf["max_splits"]):]


def _split(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(frame["date"])
    guards = pd.to_datetime(frame[GUARD_COL])
    train = frame[dates.isin(spec["train_dates"]) & guards.lt(pd.Timestamp(spec["val_start"]))]
    test = frame[dates.isin(spec["test_dates"])]
    return train, test


def fit_quantile_models(
    train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray,
    quantiles: list[float], model_config: dict[str, Any], seed: int,
) -> np.ndarray:
    predictions: list[np.ndarray] = []
    for q in quantiles:
        model = lgb.LGBMRegressor(
            objective="quantile", alpha=float(q),
            n_estimators=int(model_config["n_estimators"]),
            learning_rate=float(model_config["learning_rate"]),
            max_depth=int(model_config["max_depth"]),
            num_leaves=int(model_config["num_leaves"]),
            min_child_samples=int(model_config["min_child_samples"]),
            colsample_bytree=float(model_config["colsample_bytree"]),
            subsample=float(model_config["subsample"]),
            subsample_freq=1,
            reg_lambda=float(model_config["reg_lambda"]),
            n_jobs=int(model_config["n_jobs"]), random_state=seed,
            verbosity=-1,
        )
        model.fit(train_x, train_y)
        # Booster prediction keeps the same feature order without sklearn's
        # spurious ndarray/feature-name warning (fit also receives an ndarray).
        predictions.append(model.booster_.predict(test_x))
    return np.column_stack(predictions)


def _fold_metrics(
    train: pd.DataFrame, test: pd.DataFrame, features: list[str],
    config: dict[str, Any], fold_index: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    model_cfg = config["model"]
    quantiles = [float(q) for q in config["quantiles"]]
    seed = int(model_cfg["random_seed"]) + fold_index * 1000
    sample = select_train_rows(train, int(model_cfg["max_train_rows"]), seed)
    prep = fit_preprocessor(
        sample, features, lower_q=float(model_cfg["winsor_lower"]),
        upper_q=float(model_cfg["winsor_upper"]),
        max_missing_rate=float(model_cfg["max_missing_rate"]),
    )
    train_x, test_x = transform(sample, prep), transform(test, prep)
    train_y = pd.to_numeric(sample[RETURN], errors="coerce").to_numpy(float)
    test_y = pd.to_numeric(test[RETURN], errors="coerce").to_numpy(float)
    if not (np.isfinite(train_y).all() and np.isfinite(test_y).all()):
        raise ValueError("Nonfinite H20 returns in P-MATH-3 fold")
    raw = fit_quantile_models(train_x, train_y, test_x, quantiles, model_cfg, seed)
    predicted, crossing = rearrange_quantiles(raw)
    scores = tail_scores(predicted, quantiles)
    baseline_quantiles = np.quantile(train_y, quantiles)
    quantile_rows: list[dict[str, float]] = []
    for index, q in enumerate(quantiles):
        model_loss = pinball_loss(test_y, predicted[:, index], q)
        constant_loss = pinball_loss(test_y, np.full(len(test_y), baseline_quantiles[index]), q)
        quantile_rows.append({
            "quantile": q, "pinball_model": model_loss, "pinball_constant": constant_loss,
            "relative_improvement": 1.0 - model_loss / constant_loss if constant_loss > 0 else float("nan"),
            "observed_below": float(np.mean(test_y <= predicted[:, index])),
        })
    scored = test[["date", "symbol", DECILE, RETURN]].copy().reset_index(drop=True)
    scored["fold_index"] = fold_index
    for index, q in enumerate(quantiles):
        scored[f"q{int(q * 100):02d}"] = predicted[:, index]
    for name, values in scores.items():
        scored[name] = values

    # Direct D1/D10 baseline is trained only on labels available before validation.
    train_binary = attach_task(train, "D1_VS_D10")
    train_binary = balanced_by_date(
        train_binary, max_per_class=int(model_cfg["classifier_train_max_per_class"]), seed=seed + 1)
    if train_binary[TARGET].nunique() < 2:
        raise ValueError("P-MATH-3 baseline lacks both D1/D10 classes")
    baseline = LogisticRegression(max_iter=500, solver="lbfgs", random_state=seed)
    baseline.fit(transform(train_binary, prep), train_binary[TARGET].to_numpy(int))
    scored["direct_logistic_score"] = baseline.predict_proba(test_x)[:, 1]
    extremes = scored[scored[DECILE].isin([1, 10])].copy()
    if extremes[DECILE].nunique() < 2:
        raise ValueError("P-MATH-3 test fold lacks D1/D10")
    truth = extremes[DECILE].eq(10).to_numpy(int)
    aucs = {
        name: float(roc_auc_score(truth, extremes[name]))
        for name in (*scores, "direct_logistic_score")
    }
    top_returns: dict[str, float] = {}
    top_precisions: dict[str, float] = {}
    for name in (config["primary_direction_score"], "direct_logistic_score"):
        chosen = scored.loc[daily_top_fraction(scored, name)]
        top_returns[name] = float(chosen[RETURN].mean())
        top_precisions[name] = float(chosen[DECILE].eq(10).mean())
    mean_model_loss = float(np.mean([row["pinball_model"] for row in quantile_rows]))
    mean_constant_loss = float(np.mean([row["pinball_constant"] for row in quantile_rows]))
    metric = {
        "fold_index": fold_index, "rows_train_available": len(train), "rows_train_quantile": len(sample),
        "rows_train_direct": len(train_binary), "rows_test": len(test),
        "features_used": len(prep.features), "crossing_rate_before_rearrangement": crossing,
        "mean_pinball_model": mean_model_loss,
        "mean_pinball_constant": mean_constant_loss,
        "pinball_relative_improvement": 1.0 - mean_model_loss / mean_constant_loss,
        "outer_quantile_abs_coverage_error": float(np.mean([
            abs(quantile_rows[1]["observed_below"] - 0.10),
            abs(quantile_rows[5]["observed_below"] - 0.90),
        ])),
        "auc_d1_d10": aucs,
        "top_decile_mean_return": top_returns,
        "top_decile_d10_precision": top_precisions,
        "quantiles": quantile_rows,
    }
    return metric, scored


def summarize(folds: list[dict[str, Any]], gates: dict[str, Any], primary: str) -> dict[str, Any]:
    pinball = np.array([row["pinball_relative_improvement"] for row in folds])
    coverage = np.array([row["outer_quantile_abs_coverage_error"] for row in folds])
    auc = np.array([row["auc_d1_d10"][primary] for row in folds])
    auc_direct = np.array([row["auc_d1_d10"]["direct_logistic_score"] for row in folds])
    delta = auc - auc_direct
    lift = np.array([
        row["top_decile_mean_return"][primary]
        - row["top_decile_mean_return"]["direct_logistic_score"]
        for row in folds
    ])
    distribution_checks = {
        "pinball_improvement": float(np.median(pinball)) >= float(gates["pinball_relative_improvement_min"]),
        "pinball_stability": float(np.mean(pinball > 0)) >= float(gates["pinball_positive_fold_rate_min"]),
        "outer_quantile_calibration": float(np.median(coverage)) <= float(gates["outer_quantile_abs_coverage_error_max"]),
    }
    direction_checks = {
        "absolute_auc": float(np.median(auc)) >= float(gates["d1_d10_auc_median_min"]),
        "incremental_auc": float(np.median(delta)) >= float(gates["d1_d10_auc_delta_vs_logistic_min"]),
        "auc_fold_stability": float(np.mean(delta > 0)) >= float(gates["d1_d10_auc_positive_fold_rate_min"]),
        "economic_lift": float(np.median(lift)) >= float(gates["d1_d10_signed_top_decile_return_lift_min"]),
    }
    return {
        "folds": len(folds),
        "pinball_improvement_median": float(np.median(pinball)),
        "pinball_positive_fold_rate": float(np.mean(pinball > 0)),
        "outer_quantile_abs_coverage_error_median": float(np.median(coverage)),
        "d1_d10_auc_median": float(np.median(auc)),
        "direct_logistic_auc_median": float(np.median(auc_direct)),
        "d1_d10_auc_delta_median": float(np.median(delta)),
        "d1_d10_auc_delta_positive_fold_rate": float(np.mean(delta > 0)),
        "top_decile_return_lift_median": float(np.median(lift)),
        "distribution_gate_checks": distribution_checks,
        "direction_gate_checks": direction_checks,
        "distribution_verdict": "GO_DISTRIBUTION_ONLY" if all(distribution_checks.values()) else "NO_GO_DISTRIBUTION",
        "direction_verdict": "GO_DIRECTION" if all(distribution_checks.values()) and all(direction_checks.values()) else "NO_GO_DIRECTION",
    }


def run(args: argparse.Namespace) -> Path:
    config = json.loads(args.config.read_text(encoding="utf-8"))
    quantiles = [float(q) for q in config["quantiles"]]
    if quantiles != [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]:
        raise ValueError("P-MATH-3 quantile contract changed")
    if args.max_folds is not None:
        config["walk_forward"]["max_splits"] = args.max_folds
    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, args.batch_id, args.horizon)
    if args.max_symbols:
        symbols = symbols[:args.max_symbols]
    profile = load_profile(Path(args.state_profile or config["state_profile"]))
    pool, features = build_oracle_dataset(
        engine, args.batch_id, symbols, start_date=args.start_date, end_date=args.end_date,
        horizon=args.horizon, require_global_rank=False, need_targets=False,
        feature_whitelist=profile["feature_columns"], generator_options=profile["generator_options"],
    )
    pool["date"] = pd.to_datetime(pool["date"]).dt.normalize()
    pool["symbol"] = pool["symbol"].astype(str).str.upper()
    gate = _load_gate(Path("artifacts/models") / args.batch_id / "_oracle_oof_gate.parquet", float(config["pool_pct"]))
    eligible = gate[gate["shared_oracle_eligible"]][["date", "symbol", ORACLE_GATE_SCORE_COL]]
    pool = pool.merge(eligible, on=["date", "symbol"], how="inner", validate="one_to_one")
    pool = pool.dropna(subset=[DECILE, GUARD_COL, RETURN]).reset_index(drop=True)
    specs = _fold_specs(pool, config, args.horizon)
    if not specs:
        raise ValueError("No P-MATH-3 walk-forward folds")
    output = args.output or Path("artifacts/research/pmath3_conditional_quantiles") / datetime.now(UTC).strftime("pmath3-%Y%m%d%H%M%S")
    output.mkdir(parents=True, exist_ok=False)
    metrics: list[dict[str, Any]] = []
    predictions: list[pd.DataFrame] = []
    for fold_index, spec in enumerate(specs):
        train, test = _split(pool, spec)
        LOGGER.info("P-MATH-3 fold=%d train=%d test=%d", fold_index, len(train), len(test))
        fold_metric, fold_predictions = _fold_metrics(train, test, features, config, fold_index)
        fold_metric.update({"test_start": spec["t_start"], "test_end": spec["t_end"]})
        metrics.append(fold_metric)
        predictions.append(fold_predictions)
        (output / "progress.json").write_text(json.dumps({
            "folds_complete": len(metrics), "folds_planned": len(specs),
            "last_test_end": spec["t_end"],
        }, indent=2, default=str), encoding="utf-8")
    pd.DataFrame([{key: value for key, value in row.items() if key not in ("auc_d1_d10", "top_decile_mean_return", "top_decile_d10_precision", "quantiles")}
                  | {f"auc_{key}": value for key, value in row["auc_d1_d10"].items()}
                  | {f"top_return_{key}": value for key, value in row["top_decile_mean_return"].items()}
                  for row in metrics]).to_csv(output / "fold_metrics.csv", index=False)
    pd.DataFrame([{"fold_index": row["fold_index"], **item} for row in metrics for item in row["quantiles"]]).to_csv(
        output / "quantile_metrics.csv", index=False)
    pd.concat(predictions, ignore_index=True).to_parquet(output / "oos_predictions.parquet", index=False)
    summary = summarize(metrics, config["gates"], config["primary_direction_score"])
    report = {
        "experiment": config["experiment"], "status": "COMPLETED_RESEARCH_ONLY",
        "batch_id": args.batch_id, "horizon": args.horizon, "period": [args.start_date, args.end_date],
        "pool": {"rows": len(pool), "dates": pool["date"].nunique(), "symbols": pool["symbol"].nunique()},
        "folds": len(specs), "features_requested": len(features),
        "primary_direction_score": config["primary_direction_score"],
        "summary": summary, "fold_details": metrics, "config": config,
        "serving_changed": False, "database_writes": False,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"P-MATH-3 terminé: {output}")
    print(summary["distribution_verdict"], summary["direction_verdict"],
          f"pinball={summary['pinball_improvement_median']:+.4f}",
          f"D1_D10_AUC={summary['d1_d10_auc_median']:.4f}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state-profile")
    parser.add_argument("--max-symbols", type=int)
    parser.add_argument("--max-folds", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run(args)


if __name__ == "__main__":
    main()
