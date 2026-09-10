"""Ranker directionnel de recherche, conditionné au TOP20 Oracle OOF.

Ce module ne participe ni au serving ni au backtest de production. Il entraîne
un ranker transversal indépendant pour H3 et H20, puis mesure séparément les
queues LONG et SHORT. Le score Oracle est conservé comme benchmark mais reste
strictement interdit dans les features du modèle.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.train import get_universe_symbols
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.shared_directional import (
    DEFAULT_PROFILE,
    EXCESS_SPY_COL,
    ORACLE_GATE_SCORE_COL,
    SECTOR_RESIDUAL_COL,
    SPY_RETURN_COL,
    SharedDirectionalConfig,
    _prepare_X,
    attach_signed_return_target,
    build_shared_dataset,
    load_forward_return_panel,
    load_profile,
)

LOGGER = logging.getLogger(__name__)

RANK_LABEL_COL = "conditional_rank_label"
RANK_SCORE_COL = "conditional_rank_score"
E2B_SCORE_COL = "e2b_long_score"
GLOBAL_RANK_COL = "global_rank_baseline"
DEFAULT_ARTIFACTS_ROOT = Path("artifacts/models/conditional_oracle_ranker")


@dataclass(frozen=True, slots=True)
class ConditionalRankerConfig:
    horizons: tuple[int, ...] = (3, 20)
    pool_pct: float = 0.20
    selection_fraction: float = 0.20
    min_train_dates: int = 504
    val_dates: int = 126
    test_dates: int = 126
    step_dates: int = 126
    max_splits: int = 12
    iterations: int = 600
    depth: int = 6
    learning_rate: float = 0.03
    random_seed: int = 42
    context_mode: str = "none"
    target_up_threshold: float = 0.03
    target_down_threshold: float = -0.03
    sector_min_members: int = 5

    def __post_init__(self) -> None:
        horizons = tuple(sorted({int(value) for value in self.horizons}))
        object.__setattr__(self, "horizons", horizons)
        if not horizons or any(value < 1 for value in horizons):
            raise ValueError("Les horizons du ranker doivent être positifs.")
        if not 0.0 < self.pool_pct < 1.0:
            raise ValueError("pool_pct doit être dans ]0,1[.")
        if not 0.0 < self.selection_fraction < 0.5:
            raise ValueError("selection_fraction doit être dans ]0,0.5[.")
        if min(self.min_train_dates, self.val_dates, self.test_dates, self.step_dates) < 1:
            raise ValueError("Les fenêtres Walk-Forward doivent être positives.")
        if self.iterations < 10 or self.depth < 1 or self.max_splits < 1:
            raise ValueError("Configuration ranker invalide.")
        if self.context_mode not in {"none", "sector", "symbol_sector"}:
            raise ValueError("context_mode invalide.")
        if self.target_up_threshold <= 0 or self.target_down_threshold >= 0:
            raise ValueError("Les seuils directionnels doivent encadrer zéro.")


def attach_conditional_rank_target(
    oracle_pool: pd.DataFrame,
    forward_panel: pd.DataFrame,
    *,
    horizon: int,
) -> pd.DataFrame:
    """Joint le rendement brut Hx et crée une relevance 0..9 par date."""
    frame = attach_signed_return_target(
        oracle_pool, forward_panel, horizon=horizon, residualization="raw",
    )
    valid = pd.to_numeric(frame["future_return"], errors="coerce")
    percentile = valid.groupby(frame["date"]).rank(method="average", pct=True)
    frame[RANK_LABEL_COL] = np.floor(percentile.mul(10.0).sub(1e-12)).clip(0, 9)
    frame.loc[valid.isna(), RANK_LABEL_COL] = np.nan
    return frame


def _fit_ranker(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    features: list[str],
    categoricals: list[str],
    config: ConditionalRankerConfig,
    *,
    iterations: int | None = None,
) -> Any:
    from catboost import CatBoostRanker, Pool

    train = train.sort_values(["date", "symbol"]).copy()
    if train.empty or train["date"].nunique() < 2:
        raise ValueError("Train ranker insuffisant.")
    model = CatBoostRanker(
        loss_function="PairLogit",
        eval_metric="NDCG:top=10",
        iterations=int(iterations or config.iterations),
        depth=config.depth,
        learning_rate=config.learning_rate,
        l2_leaf_reg=5.0,
        random_seed=config.random_seed,
        random_strength=1.0,
        bootstrap_type="Bayesian",
        bagging_temperature=1.0,
        allow_writing_files=False,
        verbose=False,
        thread_count=-1,
    )
    kwargs: dict[str, Any] = {
        "group_id": train["date"].dt.strftime("%Y-%m-%d").to_numpy(),
        "cat_features": categoricals,
    }
    if valid is not None and not valid.empty:
        valid = valid.sort_values(["date", "symbol"]).copy()
        kwargs.update({
            "eval_set": Pool(
                _prepare_X(valid, features, categoricals),
                label=valid[RANK_LABEL_COL].astype(int),
                group_id=valid["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                cat_features=categoricals,
            ),
            "early_stopping_rounds": 60,
            "use_best_model": True,
        })
    model.fit(
        _prepare_X(train, features, categoricals),
        train[RANK_LABEL_COL].astype(int),
        **kwargs,
    )
    return model


def _tail(frame: pd.DataFrame, score: str, fraction: float, *, low: bool) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for _, group in frame.groupby("date", sort=False):
        usable = group.dropna(subset=[score])
        if usable.empty:
            continue
        count = max(1, math.ceil(len(usable) * fraction))
        parts.append(usable.nsmallest(count, score) if low else usable.nlargest(count, score))
    return pd.concat(parts, ignore_index=True) if parts else frame.iloc[0:0].copy()


def _side_metrics(
    selected: pd.DataFrame,
    *,
    side: str,
    up_threshold: float,
    down_threshold: float,
) -> dict[str, Any]:
    if selected.empty:
        return {
            "rows": 0, "dates": 0, "symbols": 0, "mean_raw_return": None,
            "median_raw_return": None, "mean_signed_return": None,
            "median_signed_return": None, "signed_hit_rate": None,
            "event_precision": None,
        }
    raw = pd.to_numeric(selected["future_return"], errors="coerce")
    sign = 1.0 if side == "long" else -1.0
    signed = sign * raw
    event = raw.ge(up_threshold) if side == "long" else raw.le(down_threshold)
    return {
        "rows": int(len(selected)),
        "dates": int(selected["date"].nunique()),
        "symbols": int(selected["symbol"].nunique()),
        "mean_raw_return": float(raw.mean()),
        "median_raw_return": float(raw.median()),
        "mean_signed_return": float(signed.mean()),
        "median_signed_return": float(signed.median()),
        "signed_hit_rate": float(signed.gt(0).mean()),
        "event_precision": float(event.mean()),
    }


def _matched_expectation(
    frame: pd.DataFrame,
    fraction: float,
    *,
    side: str,
    up_threshold: float,
    down_threshold: float,
) -> dict[str, Any]:
    rows = 0
    return_sum = event_sum = hit_sum = 0.0
    sign = 1.0 if side == "long" else -1.0
    for _, group in frame.groupby("date", sort=False):
        raw = pd.to_numeric(group["future_return"], errors="coerce").dropna()
        if raw.empty:
            continue
        count = max(1, math.ceil(len(raw) * fraction))
        event = raw.ge(up_threshold) if side == "long" else raw.le(down_threshold)
        rows += count
        return_sum += float(sign * raw.mean() * count)
        event_sum += float(event.mean() * count)
        hit_sum += float((sign * raw).gt(0).mean() * count)
    return {
        "rows": rows,
        "expected_mean_signed_return": return_sum / rows if rows else None,
        "expected_event_precision": event_sum / rows if rows else None,
        "expected_signed_hit_rate": hit_sum / rows if rows else None,
    }


def _daily_ic_values(frame: pd.DataFrame, score: str) -> np.ndarray:
    values: list[float] = []
    for _, group in frame.groupby("date", sort=False):
        usable = group[[score, "future_return"]].dropna()
        if len(usable) >= 3 and usable[score].nunique() > 1 and usable["future_return"].nunique() > 1:
            values.append(float(usable[score].corr(usable["future_return"], method="spearman")))
    return np.asarray(values, dtype=float)


def _ndcg_at_fraction(frame: pd.DataFrame, score: str, fraction: float) -> float | None:
    values: list[float] = []
    for _, group in frame.groupby("date", sort=False):
        usable = group.dropna(subset=[score, RANK_LABEL_COL])
        if len(usable) < 2:
            continue
        count = max(1, math.ceil(len(usable) * fraction))

        def dcg(relevance: np.ndarray) -> float:
            gains = np.power(2.0, relevance.astype(float)) - 1.0
            return float(np.sum(gains / np.log2(np.arange(2, len(gains) + 2))))

        predicted = usable.sort_values(score, ascending=False)[RANK_LABEL_COL].to_numpy()[:count]
        ideal = usable.sort_values(RANK_LABEL_COL, ascending=False)[RANK_LABEL_COL].to_numpy()[:count]
        denominator = dcg(ideal)
        if denominator > 0:
            values.append(dcg(predicted) / denominator)
    return float(np.mean(values)) if values else None


def _selection_pair(
    frame: pd.DataFrame,
    score: str,
    config: ConditionalRankerConfig,
) -> dict[str, Any]:
    long_rows = _tail(frame, score, config.selection_fraction, low=False)
    short_rows = _tail(frame, score, config.selection_fraction, low=True)
    long = _side_metrics(
        long_rows, side="long", up_threshold=config.target_up_threshold,
        down_threshold=config.target_down_threshold,
    )
    short = _side_metrics(
        short_rows, side="short", up_threshold=config.target_up_threshold,
        down_threshold=config.target_down_threshold,
    )
    spread = (
        float(long["mean_raw_return"] - short["mean_raw_return"])
        if long["rows"] and short["rows"] else None
    )
    return {"long": long, "short": short, "spread_raw": spread}


def evaluate_ranker(frame: pd.DataFrame, config: ConditionalRankerConfig) -> dict[str, Any]:
    """Évalue l’ordre quotidien et les deux côtés sans forcer leur symétrie."""
    work = frame.dropna(subset=["date", "symbol", "future_return", RANK_SCORE_COL]).copy()
    if work.empty:
        raise ValueError("Prédictions ranker vides.")
    model = _selection_pair(work, RANK_SCORE_COL, config)
    matched_long = _matched_expectation(
        work, config.selection_fraction, side="long",
        up_threshold=config.target_up_threshold, down_threshold=config.target_down_threshold,
    )
    matched_short = _matched_expectation(
        work, config.selection_fraction, side="short",
        up_threshold=config.target_up_threshold, down_threshold=config.target_down_threshold,
    )
    for side, matched in (("long", matched_long), ("short", matched_short)):
        metrics = model[side]
        metrics["return_lift_vs_matched"] = (
            metrics["mean_signed_return"] - matched["expected_mean_signed_return"]
        )
        metrics["precision_lift_vs_matched"] = (
            metrics["event_precision"] - matched["expected_event_precision"]
        )

    baseline_scores = {
        "oracle_percentile_directionless_control": ORACLE_GATE_SCORE_COL,
        "momentum_20": "momentum_20",
        "relative_strength_20": "relative_strength_20",
        "global_ranking_existing": GLOBAL_RANK_COL,
        "e2b_long_h3": E2B_SCORE_COL,
    }
    baselines: dict[str, Any] = {}
    for name, column in baseline_scores.items():
        if column not in work.columns:
            baselines[name] = {"available": False, "reason": "column_absent"}
            continue
        subset = work.dropna(subset=[column])
        if subset.empty:
            baselines[name] = {"available": False, "reason": "no_overlap"}
            continue
        baselines[name] = {
            "available": True,
            "coverage": float(len(subset) / len(work)),
            "metrics": _selection_pair(subset, column, config),
        }

    daily_ic = _daily_ic_values(work, RANK_SCORE_COL)
    ic_mean = float(daily_ic.mean()) if len(daily_ic) else None
    ic_std = float(daily_ic.std(ddof=1)) if len(daily_ic) > 1 else None
    ic_se = ic_std / math.sqrt(len(daily_ic)) if ic_std is not None else None
    semesters: dict[str, Any] = {}
    semester_labels = work["date"].map(
        lambda value: f"{pd.Timestamp(value).year}H{1 if pd.Timestamp(value).month <= 6 else 2}"
    )
    for semester, group in work.groupby(semester_labels, sort=True):
        pair = _selection_pair(group, RANK_SCORE_COL, config)
        values = _daily_ic_values(group, RANK_SCORE_COL)
        semesters[str(semester)] = {
            "rows": int(len(group)),
            "dates": int(group["date"].nunique()),
            "mean_daily_ic": float(values.mean()) if len(values) else None,
            "long_mean_signed_return": pair["long"]["mean_signed_return"],
            "short_mean_signed_return": pair["short"]["mean_signed_return"],
            "spread_raw": pair["spread_raw"],
        }

    ranked = work.copy()
    ranked["score_bucket"] = (
        ranked.groupby("date")[RANK_SCORE_COL].rank(method="first", pct=True)
        .mul(10).sub(1e-12).astype(int).clip(0, 9)
    )
    buckets = [{
        "bucket": int(bucket) + 1,
        "rows": int(len(group)),
        "mean_score": float(group[RANK_SCORE_COL].mean()),
        "mean_raw_return": float(group["future_return"].mean()),
        "long_event_rate": float(group["future_return"].ge(config.target_up_threshold).mean()),
        "short_event_rate": float(group["future_return"].le(config.target_down_threshold).mean()),
    } for bucket, group in ranked.groupby("score_bucket", sort=True)]

    return {
        "rows": int(len(work)),
        "dates": int(work["date"].nunique()),
        "symbols": int(work["symbol"].nunique()),
        "pool_mean_return": float(work["future_return"].mean()),
        "pool_long_event_rate": float(work["future_return"].ge(config.target_up_threshold).mean()),
        "pool_short_event_rate": float(work["future_return"].le(config.target_down_threshold).mean()),
        "mean_daily_ic": ic_mean,
        "median_daily_ic": float(np.median(daily_ic)) if len(daily_ic) else None,
        "daily_ic_std": ic_std,
        "daily_ic_positive_rate": float((daily_ic > 0).mean()) if len(daily_ic) else None,
        "daily_ic_ci95": [ic_mean - 1.96 * ic_se, ic_mean + 1.96 * ic_se]
        if ic_mean is not None and ic_se is not None else None,
        "ndcg_at_selection_fraction": _ndcg_at_fraction(
            work, RANK_SCORE_COL, config.selection_fraction,
        ),
        "selection_fraction": config.selection_fraction,
        "model": model,
        "matched_random_expectation": {"long": matched_long, "short": matched_short},
        "baselines": baselines,
        "score_buckets": buckets,
        "semesters": semesters,
    }


def _load_global_rank_baseline(
    engine: Any,
    batch_id: str | None,
    horizon: int,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    if not batch_id:
        return pd.DataFrame(columns=["date", "symbol", GLOBAL_RANK_COL])
    if horizon not in {3, 5, 10, 15, 20}:
        raise ValueError("Horizon Global Rank non autorisé.")
    from sqlalchemy import text

    query = text(
        f"SELECT `date`, symbol, global_rank_{horizon} AS {GLOBAL_RANK_COL} "
        "FROM alpha_trade.global_rank_history "
        "WHERE batch_id=:batch_id AND `date` BETWEEN :start_date AND :end_date"
    )
    frame = pd.read_sql(
        query, engine,
        params={"batch_id": batch_id, "start_date": start_date, "end_date": end_date},
    )
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol", GLOBAL_RANK_COL])
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    return frame.drop_duplicates(["date", "symbol"], keep="last")


def _load_e2b_baseline(artifact: Path | None) -> pd.DataFrame:
    if artifact is None:
        return pd.DataFrame(columns=["date", "symbol", E2B_SCORE_COL])
    paths = [artifact / "oof_predictions.parquet"]
    paths.extend(sorted(artifact.glob("confirmation-*/predictions.parquet")))
    frames: list[pd.DataFrame] = []
    for path in paths:
        if not path.is_file():
            continue
        frame = pd.read_parquet(path)
        score = (
            "calibrated_proba_long"
            if "calibrated_proba_long" in frame.columns
            else "raw_proba_long"
        )
        if score not in frame.columns:
            continue
        frames.append(
            frame[["date", "symbol", score]].rename(columns={score: E2B_SCORE_COL})
        )
    if not frames:
        return pd.DataFrame(columns=["date", "symbol", E2B_SCORE_COL])
    result = pd.concat(frames, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    result["symbol"] = result["symbol"].astype(str).str.upper()
    return result.drop_duplicates(["date", "symbol"], keep="last")


def _merge_baselines(
    dataset: pd.DataFrame,
    global_rank: pd.DataFrame,
    e2b: pd.DataFrame,
) -> pd.DataFrame:
    result = dataset
    for baseline in (global_rank, e2b):
        if not baseline.empty:
            result = result.merge(
                baseline, on=["date", "symbol"], how="left", validate="one_to_one",
            )
    return result


def _fold_stability(folds: list[dict[str, Any]]) -> dict[str, Any]:
    ic = np.asarray([fold["mean_daily_ic"] for fold in folds], dtype=float)
    spread = np.asarray([fold["model"]["spread_raw"] for fold in folds], dtype=float)
    long_lift = np.asarray([
        fold["model"]["long"]["return_lift_vs_matched"] for fold in folds
    ], dtype=float)
    short_lift = np.asarray([
        fold["model"]["short"]["return_lift_vs_matched"] for fold in folds
    ], dtype=float)
    return {
        "mean_daily_ic": float(ic.mean()),
        "ic_positive_folds": int((ic > 0).sum()),
        "spread_mean": float(spread.mean()),
        "spread_positive_folds": int((spread > 0).sum()),
        "long_return_lift_mean": float(long_lift.mean()),
        "long_positive_lift_folds": int((long_lift > 0).sum()),
        "short_return_lift_mean": float(short_lift.mean()),
        "short_positive_lift_folds": int((short_lift > 0).sum()),
    }


def _development_gates(
    overall: dict[str, Any],
    stability: dict[str, Any],
    fold_count: int,
) -> dict[str, Any]:
    required_stable = max(1, math.ceil(fold_count * 0.75))
    long = overall["model"]["long"]
    short = overall["model"]["short"]
    rank_gates = {
        "mean_daily_ic_gte_0_02": bool(overall["mean_daily_ic"] >= 0.02),
        "ic_positive_folds_gte_75pct": bool(
            stability["ic_positive_folds"] >= required_stable
        ),
        "spread_raw_gte_0_005": bool(overall["model"]["spread_raw"] >= 0.005),
        "spread_positive_folds_gte_75pct": bool(
            stability["spread_positive_folds"] >= required_stable
        ),
    }
    long_gates = {
        "mean_signed_return_positive": bool(long["mean_signed_return"] > 0),
        "return_lift_gte_0_0025": bool(long["return_lift_vs_matched"] >= 0.0025),
        "precision_lift_gte_0_02": bool(long["precision_lift_vs_matched"] >= 0.02),
        "positive_lift_folds_gte_75pct": bool(
            stability["long_positive_lift_folds"] >= required_stable
        ),
    }
    short_gates = {
        "selected_raw_return_negative": bool(short["mean_raw_return"] < 0),
        "mean_signed_return_positive": bool(short["mean_signed_return"] > 0),
        "return_lift_gte_0_0025": bool(short["return_lift_vs_matched"] >= 0.0025),
        "precision_lift_gte_0_02": bool(short["precision_lift_vs_matched"] >= 0.02),
        "positive_lift_folds_gte_75pct": bool(
            stability["short_positive_lift_folds"] >= required_stable
        ),
    }
    rank_passed = all(rank_gates.values())
    return {
        "required_stable_folds": required_stable,
        "rank": rank_gates,
        "long": long_gates,
        "short": short_gates,
        "rank_passed": rank_passed,
        "long_passed": bool(rank_passed and all(long_gates.values())),
        "short_passed": bool(rank_passed and all(short_gates.values())),
    }


def train_horizon(
    dataset: pd.DataFrame,
    features: list[str],
    categoricals: list[str],
    config: ConditionalRankerConfig,
    horizon: int,
    artifact_dir: Path,
) -> dict[str, Any]:
    folds = build_folds_adaptive(
        dataset,
        min_train_dates=config.min_train_dates,
        val_dates=config.val_dates,
        test_dates=config.test_dates,
        step_dates=config.step_dates,
        max_splits=config.max_splits,
        forecast_horizon=horizon,
    )
    if not folds:
        raise ValueError(f"Aucun fold conditionnel H{horizon} valide.")
    oos_parts: list[pd.DataFrame] = []
    fold_metrics: list[dict[str, Any]] = []
    best_iterations: list[int] = []
    keep = [
        "date", "symbol", "future_return", SPY_RETURN_COL, EXCESS_SPY_COL,
        SECTOR_RESIDUAL_COL, RANK_LABEL_COL, ORACLE_GATE_SCORE_COL,
        "momentum_20", "relative_strength_20", GLOBAL_RANK_COL, E2B_SCORE_COL,
    ]
    for index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=[RANK_LABEL_COL]).copy()
        valid = fold["val"].dropna(subset=[RANK_LABEL_COL]).copy()
        test = fold["test"].dropna(subset=[RANK_LABEL_COL]).copy()
        if any(part.empty or part["date"].nunique() < 2 for part in (train, valid, test)):
            LOGGER.warning("conditional_ranker h=%d fold=%d skipped", horizon, index)
            continue
        model = _fit_ranker(train, valid, features, categoricals, config)
        scored = test[[column for column in keep if column in test.columns]].copy()
        scored[RANK_SCORE_COL] = model.predict(
            _prepare_X(test, features, categoricals)
        )
        scored["fold_index"] = index
        metrics = evaluate_ranker(scored, config)
        metrics.update({
            "fold_index": index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "train_rows": int(len(train)),
            "valid_rows": int(len(valid)),
        })
        fold_metrics.append(metrics)
        oos_parts.append(scored)
        best_iterations.append(max(1, int(model.get_best_iteration()) + 1))
        LOGGER.info(
            "conditional_ranker h=%d fold=%d ic=%+.4f spread=%+.4f long=%+.4f short=%+.4f",
            horizon, index, metrics["mean_daily_ic"], metrics["model"]["spread_raw"],
            metrics["model"]["long"]["mean_signed_return"],
            metrics["model"]["short"]["mean_signed_return"],
        )
    if not oos_parts:
        raise ValueError(f"Tous les folds conditionnels H{horizon} ont été rejetés.")

    oos = pd.concat(oos_parts, ignore_index=True)
    overall = evaluate_ranker(oos, config)
    stability = _fold_stability(fold_metrics)
    gates = _development_gates(overall, stability, len(fold_metrics))
    labeled = dataset.dropna(subset=[RANK_LABEL_COL]).copy()
    final_iterations = max(10, int(np.median(best_iterations)))
    final_model = _fit_ranker(
        labeled, None, features, categoricals, config, iterations=final_iterations,
    )
    artifact_dir.mkdir(parents=True, exist_ok=False)
    model_path = artifact_dir / "ranker.cbm"
    oof_path = artifact_dir / "oof_predictions.parquet"
    final_model.save_model(str(model_path))
    oos.to_parquet(oof_path, index=False)
    metrics = {
        "status": "completed",
        "horizon": horizon,
        "objective": "PairLogit_query_by_date",
        "target": "daily_decile_of_raw_future_return_within_oracle_pool",
        "n_folds": len(fold_metrics),
        "final_iterations": final_iterations,
        "overall": overall,
        "folds": fold_metrics,
        "fold_stability": stability,
        "development_gates": gates,
        "development_passed_long": gates["long_passed"],
        "development_passed_short": gates["short_passed"],
        "trained_rows": int(len(labeled)),
        "trained_dates": int(labeled["date"].nunique()),
        "trained_symbols": int(labeled["symbol"].nunique()),
        "trained_through_date": str(pd.Timestamp(labeled["date"].max()).date()),
        "artifact_paths": {"model": str(model_path), "oof": str(oof_path)},
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8",
    )
    return metrics


def run_campaign(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    config: ConditionalRankerConfig,
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    global_rank_batch_id: str | None = None,
    e2b_artifact: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    profile = load_profile(profile_path)
    symbols = get_universe_symbols(engine, oracle_batch_id, 20)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    gate_path = Path("artifacts/models") / oracle_batch_id / "_oracle_oof_gate.parquet"
    shared_config = SharedDirectionalConfig(
        horizon=20, pool_pct=config.pool_pct, context_mode=config.context_mode,
    )
    pool, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols,
        start_date=start_date, end_date=end_date, gate_path=gate_path,
        profile=profile, config=shared_config,
    )
    forward_panel, target_diagnostics = load_forward_return_panel(
        engine, symbols, start_date=start_date, end_date=end_date,
        horizons=config.horizons, sector_min_members=config.sector_min_members,
    )
    e2b = _load_e2b_baseline(e2b_artifact)
    run_id = (
        f"conditional-oracle-ranker-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-"
        f"{oracle_batch_id[-6:]}"
    )
    campaign_dir = artifacts_root / run_id
    campaign_dir.mkdir(parents=True, exist_ok=False)
    results: dict[str, Any] = {}
    for horizon in config.horizons:
        dataset = attach_conditional_rank_target(pool, forward_panel, horizon=horizon)
        global_rank = _load_global_rank_baseline(
            engine, global_rank_batch_id, horizon, start_date, end_date,
        )
        dataset = _merge_baselines(
            dataset, global_rank, e2b if horizon == 3 else e2b.iloc[0:0],
        )
        results[str(horizon)] = train_horizon(
            dataset, features, categoricals, config, horizon, campaign_dir / f"h{horizon}",
        )

    verdicts = {
        str(horizon): {
            "long": (
                "GO_DEVELOPMENT"
                if results[str(horizon)]["development_passed_long"] else "NO_GO"
            ),
            "short": (
                "GO_DEVELOPMENT"
                if results[str(horizon)]["development_passed_short"] else "NO_GO"
            ),
        }
        for horizon in config.horizons
    }
    contract = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment": "conditional_oracle_top20_daily_ranker",
        "status": "completed",
        "research_only": True,
        "serving_ready": False,
        "source_oracle_batch_id": oracle_batch_id,
        "global_rank_baseline_batch_id": global_rank_batch_id,
        "e2b_baseline_artifact": str(e2b_artifact) if e2b_artifact else None,
        "scientific_contract": {
            "horizons": list(config.horizons),
            "pool_pct": config.pool_pct,
            "selection_fraction": config.selection_fraction,
            "effective_fraction_of_full_universe_per_side": (
                config.pool_pct * config.selection_fraction
            ),
            "target": "raw_adjusted_future_return_ranked_0_to_9_within_date_and_oracle_pool",
            "query_group": "date",
            "model": "CatBoostRanker_PairLogit",
            "oracle_score_is_feature": False,
            "long_event_threshold": config.target_up_threshold,
            "short_event_threshold": config.target_down_threshold,
            "confirmation_status": (
                "not_run_and_2026_is_already_observed_by_prior_research"
            ),
        },
        "walk_forward": {
            "min_train_dates": config.min_train_dates,
            "val_dates": config.val_dates,
            "test_dates": config.test_dates,
            "step_dates": config.step_dates,
            "max_splits": config.max_splits,
        },
        "population": population,
        "target_diagnostics": target_diagnostics,
        "feature_profile": profile,
        "feature_columns": features,
        "categorical_columns": categoricals,
        "context_mode": config.context_mode,
        "results": results,
        "verdicts": verdicts,
    }
    (campaign_dir / "campaign.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8",
    )
    (campaign_dir / "feature_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8",
    )
    return campaign_dir, contract


def _format_campaign(path: Path, campaign: dict[str, Any]) -> str:
    lines = [f"Ranker conditionnel Oracle terminé: {path}"]
    for horizon in campaign["scientific_contract"]["horizons"]:
        metrics = campaign["results"][str(horizon)]
        overall = metrics["overall"]
        lines.append(
            f"H{horizon}: folds={metrics['n_folds']} IC={overall['mean_daily_ic']:+.4f} "
            f"spread={overall['model']['spread_raw']:+.2%} "
            f"LONG={overall['model']['long']['mean_signed_return']:+.2%} "
            f"SHORT={overall['model']['short']['mean_signed_return']:+.2%} "
            f"verdict={campaign['verdicts'][str(horizon)]}"
        )
    lines.append("Serving inchangé : artefacts de recherche uniquement.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ranker directionnel dans le TOP20 Oracle OOF."
    )
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--horizons", default="3,20")
    parser.add_argument("--pool-pct", type=float, default=0.20)
    parser.add_argument("--selection-fraction", type=float, default=0.20)
    parser.add_argument("--feature-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--global-rank-batch-id", default=None)
    parser.add_argument("--e2b-artifact", type=Path, default=None)
    parser.add_argument("--wf-min-train-size", type=int, default=504)
    parser.add_argument("--wf-val-size", type=int, default=126)
    parser.add_argument("--wf-test-size", type=int, default=126)
    parser.add_argument("--wf-step-size", type=int, default=126)
    parser.add_argument("--wf-max-splits", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument(
        "--context-mode", choices=["none", "sector", "symbol_sector"], default="none",
    )
    parser.add_argument("--target-up-threshold", type=float, default=0.03)
    parser.add_argument("--target-down-threshold", type=float, default=-0.03)
    parser.add_argument("--sector-min-members", type=int, default=5)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    try:
        horizons = tuple(
            int(value.strip()) for value in args.horizons.split(",") if value.strip()
        )
    except ValueError as exc:
        raise ValueError(
            "--horizons doit contenir des entiers séparés par des virgules."
        ) from exc
    config = ConditionalRankerConfig(
        horizons=horizons,
        pool_pct=args.pool_pct,
        selection_fraction=args.selection_fraction,
        min_train_dates=args.wf_min_train_size,
        val_dates=args.wf_val_size,
        test_dates=args.wf_test_size,
        step_dates=args.wf_step_size,
        max_splits=args.wf_max_splits,
        iterations=args.iterations,
        depth=args.depth,
        learning_rate=args.learning_rate,
        context_mode=args.context_mode,
        target_up_threshold=args.target_up_threshold,
        target_down_threshold=args.target_down_threshold,
        sector_min_members=args.sector_min_members,
    )
    path, campaign = run_campaign(
        get_sqlalchemy_engine(), args.oracle_batch_id,
        start_date=args.start_date, end_date=args.end_date, config=config,
        profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
        symbols_limit=args.symbols_limit,
        global_rank_batch_id=args.global_rank_batch_id,
        e2b_artifact=args.e2b_artifact,
    )
    print(_format_campaign(path, campaign))


if __name__ == "__main__":
    main()
