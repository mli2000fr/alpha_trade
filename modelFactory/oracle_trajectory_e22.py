"""E22 research-only Oracle trajectory ablation.

Adds causal ordered lags or compact path-shape features to the canonical O0
row. It never persists serving models or database predictions.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.feature_profiles import load_feature_profile
from modelFactory.oracle.dataset import GUARD_COL, build_dataset
from modelFactory.oracle.leakage import assert_training_cutoff_valid
from modelFactory.oracle.train import (
    get_universe_symbols,
    precision_recall_at_top_pct,
    roc_auc,
)
from modelFactory.oracle.walk_forward import build_folds_adaptive, run_walk_forward

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = Path("config/research/e22_oracle_trajectory.json")


def _session_order(frame: pd.DataFrame) -> pd.Series:
    dates = pd.Index(sorted(pd.to_datetime(frame["date"]).dropna().unique()))
    mapping = {value: index for index, value in enumerate(dates)}
    return pd.to_datetime(frame["date"]).map(mapping).astype("Int64")


def add_ordered_lags(
    frame: pd.DataFrame,
    source_columns: list[str],
    lag_sessions: int = 5,
) -> tuple[pd.DataFrame, list[str]]:
    """Add J-1..J-N values; gaps in a symbol's session history become NaN."""
    if lag_sessions < 1:
        raise ValueError("lag_sessions must be positive")
    result = frame.copy()
    result["_e22_original_order"] = np.arange(len(result))
    result["_e22_session"] = _session_order(result)
    result = result.sort_values(["symbol", "date", "_e22_original_order"])
    group = result.groupby("symbol", sort=False)
    added: list[str] = []
    for column in source_columns:
        if column not in result.columns:
            continue
        for lag in range(1, lag_sessions + 1):
            name = f"e22_{column}_lag{lag}"
            shifted = group[column].shift(lag)
            prior_session = group["_e22_session"].shift(lag)
            continuous = result["_e22_session"] - prior_session == lag
            result[name] = shifted.where(continuous)
            added.append(name)
    result = result.sort_values("_e22_original_order").drop(
        columns=["_e22_original_order", "_e22_session"])
    return result, added


def _longest_signed_streak(values: np.ndarray) -> float:
    signs = np.sign(values)
    best = current = 0
    previous = 0
    for sign in signs:
        if not np.isfinite(sign) or sign == 0:
            current = previous = 0
        elif sign == previous:
            current += 1
        else:
            previous, current = sign, 1
        best = max(best, current)
    return float(best)


def add_path_shape_features(
    frame: pd.DataFrame,
    window: int = 6,
) -> tuple[pd.DataFrame, list[str]]:
    """Compact causal path descriptors for the inclusive window J-5..J."""
    if window < 3:
        raise ValueError("trajectory window must be at least 3")
    required = ["daily_return", "intraday_range", "overnight_gap", "volume_ratio_20"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"missing trajectory sources: {missing}")

    result = frame.copy()
    result["_e22_original_order"] = np.arange(len(result))
    result["_e22_session"] = _session_order(result)
    result = result.sort_values(["symbol", "date", "_e22_original_order"])
    grouped = result.groupby("symbol", sort=False)

    lagged: dict[str, pd.DataFrame] = {}
    for column in required:
        pieces = [grouped[column].shift(lag) for lag in range(window)]
        values = pd.concat(pieces, axis=1)
        values.columns = range(window)
        lagged[column] = values
    sessions = pd.concat(
        [grouped["_e22_session"].shift(lag) for lag in range(window)], axis=1)
    sessions.columns = range(window)
    continuous = (sessions[0] - sessions[window - 1] == window - 1)

    returns = lagged["daily_return"].iloc[:, ::-1]
    cumulative = (1.0 + returns).cumprod(axis=1)
    running_peak = cumulative.cummax(axis=1)
    drawdown = cumulative / running_peak - 1.0
    abs_returns = returns.abs()
    signs = np.sign(returns)

    features: dict[str, pd.Series] = {
        "e22_path_return_sum_6": returns.sum(axis=1),
        "e22_path_realized_vol_6": returns.std(axis=1, ddof=0),
        "e22_path_positive_fraction_6": (returns > 0).mean(axis=1),
        # La première différence est NaN par construction : elle ne constitue
        # pas un changement de signe.
        "e22_path_sign_changes_6": signs.diff(axis=1).iloc[:, 1:].ne(0).sum(axis=1),
        "e22_path_longest_streak_6": returns.apply(
            lambda row: _longest_signed_streak(row.to_numpy(dtype=float)), axis=1),
        "e22_path_max_abs_share_6": (
            abs_returns.max(axis=1) / abs_returns.sum(axis=1).replace(0, np.nan)),
        "e22_path_max_drawdown_6": drawdown.min(axis=1),
        "e22_path_runup_6": cumulative.max(axis=1) - 1.0,
        "e22_path_range_mean_6": lagged["intraday_range"].mean(axis=1),
        "e22_path_range_expansion_6": (
            lagged["intraday_range"][0]
            / lagged["intraday_range"].iloc[:, 1:].mean(axis=1).replace(0, np.nan)),
        "e22_path_gap_abs_sum_6": lagged["overnight_gap"].abs().sum(axis=1),
        "e22_path_volume_mean_6": lagged["volume_ratio_20"].mean(axis=1),
        "e22_path_return_volume_corr_6": returns.corrwith(
            lagged["volume_ratio_20"].iloc[:, ::-1], axis=1),
    }
    x = np.arange(window, dtype=float)
    centered = x - x.mean()
    features["e22_path_return_slope_6"] = (
        returns.sub(returns.mean(axis=1), axis=0).mul(centered, axis=1).sum(axis=1)
        / float(np.square(centered).sum()))

    added = list(features)
    for name, values in features.items():
        result[name] = values.where(continuous)
    result = result.sort_values("_e22_original_order").drop(
        columns=["_e22_original_order", "_e22_session"])
    return result, added


def _average_precision(y_true: pd.Series, scores: pd.Series) -> float | None:
    valid = y_true.notna() & scores.notna()
    y = y_true[valid].astype(int).to_numpy()
    score = scores[valid].astype(float).to_numpy()
    if len(y) == 0 or len(np.unique(y)) < 2:
        return None
    order = np.argsort(-score, kind="mergesort")
    ranked = y[order]
    positives = int(ranked.sum())
    if positives == 0:
        return None
    precision = np.cumsum(ranked) / np.arange(1, len(ranked) + 1)
    return float((precision * ranked).sum() / positives)


def summarize_oos(oos: pd.DataFrame) -> dict[str, Any]:
    target, score = "oracle_extreme10", "proba_extreme"
    p10 = precision_recall_at_top_pct(oos, score, pct=.10, target_col=target)
    p20 = precision_recall_at_top_pct(oos, score, pct=.20, target_col=target)
    dated = oos.copy()
    dated["semester"] = (
        pd.to_datetime(dated["date"]).dt.year.astype(str) + "H"
        + ((pd.to_datetime(dated["date"]).dt.month.sub(1) // 6) + 1).astype(str))
    semesters = {}
    for key, part in dated.groupby("semester"):
        metric = precision_recall_at_top_pct(part, score, pct=.20, target_col=target)
        semesters[key] = {
            "precision_at_20pct": metric["precision"],
            "recall_at_20pct": metric["recall"],
            "auc": roc_auc(part[target].to_numpy(), part[score].to_numpy()),
            "rows": int(len(part)),
            "dates": int(part["date"].nunique()),
        }
    return {
        "rows": int(len(oos)),
        "dates": int(oos["date"].nunique()),
        "auc": roc_auc(oos[target].to_numpy(), oos[score].to_numpy()),
        "average_precision": _average_precision(oos[target], oos[score]),
        "precision_at_10pct": p10["precision"],
        "recall_at_10pct": p10["recall"],
        "precision_at_20pct": p20["precision"],
        "recall_at_20pct": p20["recall"],
        "semesters": semesters,
    }


def _delta(value: float | None, baseline: float | None) -> float | None:
    return None if value is None or baseline is None else float(value - baseline)


def compare_variant(variant: dict[str, Any], baseline: dict[str, Any],
                    gates: dict[str, float]) -> dict[str, Any]:
    overall, base = variant["overall"], baseline["overall"]
    fold_base = {row["fold_start"]: row for row in baseline["folds"]}
    fold_pairs = [(row, fold_base[row["fold_start"]]) for row in variant["folds"]
                  if row["fold_start"] in fold_base]
    wins = sum((row.get("auc") or -np.inf) > (ref.get("auc") or -np.inf)
               for row, ref in fold_pairs)
    semester_deltas = {
        key: _delta(value.get("precision_at_20pct"),
                    base["semesters"].get(key, {}).get("precision_at_20pct"))
        for key, value in overall["semesters"].items()
        if key in base["semesters"]
    }
    metrics = {
        "average_precision_delta": _delta(
            overall["average_precision"], base["average_precision"]),
        "auc_delta": _delta(overall["auc"], base["auc"]),
        "precision_at_20pct_delta": _delta(
            overall["precision_at_20pct"], base["precision_at_20pct"]),
        "fold_auc_win_rate": wins / len(fold_pairs) if fold_pairs else None,
        "worst_semester_precision_at_20pct_delta": (
            min(value for value in semester_deltas.values() if value is not None)
            if any(value is not None for value in semester_deltas.values()) else None),
        "semester_precision_at_20pct_deltas": semester_deltas,
    }
    checks = {
        "average_precision": metrics["average_precision_delta"] is not None
            and metrics["average_precision_delta"] >= gates["average_precision_delta_min"],
        "auc": metrics["auc_delta"] is not None
            and metrics["auc_delta"] >= gates["auc_delta_min"],
        "precision_at_20pct": metrics["precision_at_20pct_delta"] is not None
            and metrics["precision_at_20pct_delta"] >= gates["precision_at_20pct_delta_min"],
        "fold_stability": metrics["fold_auc_win_rate"] is not None
            and metrics["fold_auc_win_rate"] >= gates["fold_auc_win_rate_min"],
        "semester_safety": metrics["worst_semester_precision_at_20pct_delta"] is not None
            and metrics["worst_semester_precision_at_20pct_delta"]
                >= gates["worst_semester_precision_at_20pct_delta_min"],
    }
    return {**metrics, "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}


def build_latest_adaptive_folds(
    dataset: pd.DataFrame,
    *,
    min_train_dates: int,
    val_dates: int,
    test_dates: int,
    step_dates: int,
    max_splits: int,
    forecast_horizon: int,
) -> list[dict[str, Any]]:
    """Matérialise les N folds valides les plus récents."""
    specs = build_folds_adaptive(
        dataset,
        min_train_dates=min_train_dates,
        val_dates=val_dates,
        test_dates=test_dates,
        step_dates=step_dates,
        max_splits=10_000,
        forecast_horizon=forecast_horizon,
        materialize=False,
    )
    selected = specs[-max_splits:]
    folds: list[dict[str, Any]] = []
    dates = pd.to_datetime(dataset["date"])
    guards = pd.to_datetime(dataset[GUARD_COL])
    for spec in selected:
        val_start = pd.Timestamp(spec["val_start"])
        test_start = pd.Timestamp(spec["t_start"])
        train = dataset[dates.isin(spec["train_dates"]) & (guards < val_start)].copy()
        val = dataset[dates.isin(spec["val_dates"]) & (guards < test_start)].copy()
        test = dataset[dates.isin(spec["test_dates"])].copy()
        if train.empty or val.empty or test.empty:
            continue
        assert_training_cutoff_valid(
            training_cutoff=str(val_start.date()),
            max_oracle_available_date=train[GUARD_COL].max(),
        )
        folds.append({
            "t_start": spec["t_start"],
            "t_end": spec["t_end"],
            "val_start": spec["val_start"],
            "train": train,
            "val": val,
            "test": test,
        })
    LOGGER.info(
        "E22 latest folds=%d first=%s last=%s",
        len(folds),
        (folds[0]["t_start"], folds[0]["t_end"]) if folds else "-",
        (folds[-1]["t_start"], folds[-1]["t_end"]) if folds else "-",
    )
    return folds


def run(args: argparse.Namespace) -> Path:
    config = json.loads(args.config.read_text(encoding="utf-8"))
    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, args.batch_id, args.horizon)
    if args.max_symbols:
        symbols = symbols[:args.max_symbols]
    if not symbols:
        raise ValueError("No Oracle label universe for this batch/horizon")
    profile = load_feature_profile("oracle", args.oracle_profile)
    dataset, base_columns = build_dataset(
        engine, args.batch_id, symbols,
        start_date=args.start_date, end_date=args.end_date,
        horizon=args.horizon, require_global_rank=False,
        feature_whitelist=profile["feature_columns"],
        generator_options=profile["generator_options"],
    )
    if dataset.empty:
        raise ValueError("Empty Oracle dataset")
    lagged, lag_columns = add_ordered_lags(
        dataset, config["lag_source_columns"], config["lag_sessions"])
    augmented, path_columns = add_path_shape_features(
        lagged, config["trajectory_window_sessions"])
    wf = config["walk_forward"]
    if wf.get("fold_selection", "latest") != "latest":
        raise ValueError("E22 supports only walk_forward.fold_selection=latest")
    folds = build_latest_adaptive_folds(
        augmented,
        min_train_dates=wf["min_train_dates"], val_dates=wf["val_dates"],
        test_dates=wf["test_dates"], step_dates=wf["step_dates"],
        max_splits=wf["max_splits"], forecast_horizon=args.horizon,
    )
    if not folds:
        raise ValueError("No valid walk-forward folds")

    output = args.output or (
        Path("artifacts/research/oracle_trajectory")
        / datetime.now(UTC).strftime(f"e22-h{args.horizon}-%Y%m%d%H%M%S"))
    output.mkdir(parents=True, exist_ok=False)
    variants = {
        "O0_BASELINE": list(base_columns),
        "O0_LAGS_5": list(base_columns) + lag_columns,
        "O0_PATH_SHAPE_6": list(base_columns) + path_columns,
    }
    results: dict[str, Any] = {}
    for name, columns in variants.items():
        LOGGER.info("E22 variant=%s features=%d", name, len(columns))
        trained = run_walk_forward(augmented, columns, folds=folds, ablation="O0")
        if trained.get("status") != "completed":
            results[name] = {"status": trained.get("status"), "reason": trained.get("reason")}
            continue
        oos = trained["oos"]
        oos.to_parquet(output / f"{name.lower()}_oos.parquet", index=False)
        results[name] = {
            "status": "completed",
            "feature_count": len(trained["feature_columns"]),
            "added_features": [column for column in columns if column not in base_columns],
            "overall": summarize_oos(oos),
            "folds": trained["folds"],
        }

    baseline = results.get("O0_BASELINE", {})
    comparisons = {}
    if baseline.get("status") == "completed":
        for name in ["O0_LAGS_5", "O0_PATH_SHAPE_6"]:
            if results.get(name, {}).get("status") == "completed":
                comparisons[name] = compare_variant(
                    results[name], baseline, config["gates_vs_o0"])
    report = {
        "experiment": config["experiment"],
        "status": "COMPLETED_RESEARCH_ONLY",
        "batch_id": args.batch_id,
        "horizon": args.horizon,
        "period": [args.start_date, args.end_date],
        "symbols": len(symbols),
        "folds": len(folds),
        "fold_coverage": {
            "first_test_start": folds[0]["t_start"],
            "last_test_end": folds[-1]["t_end"],
            "selection": "latest",
        },
        "config": config,
        "results": results,
        "comparisons_vs_o0": comparisons,
        "serving_changed": False,
        "database_writes": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print(f"E22 terminé: {output}")
    for name, comparison in comparisons.items():
        print(name, comparison["status"], {
            key: value for key, value in comparison.items()
            if key.endswith("_delta") or key == "fold_auc_win_rate"})
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--oracle-profile", default="oracle.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-symbols", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.start_date > args.end_date:
        parser.error("Invalid date window")
    if args.horizon not in [5, 10, 15, 20]:
        parser.error("--horizon must be one of 5,10,15,20")
    run(args)


if __name__ == "__main__":
    main()
