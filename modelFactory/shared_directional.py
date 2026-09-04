"""Modèle directionnel mutualisé conditionné par les événements Oracle OOF.

Ce module est volontairement séparé du serving de production. Il entraîne un
unique CatBoost sur toutes les lignes du TOP20 Oracle strictement OOF et mesure
sa capacité à ordonner D1 versus D10. Une promotion vers la prédiction/backtest
ne doit intervenir qu'après passage des gates Walk-Forward documentés.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.cross_sectional import _load_sector_mapping, _map_to_gics_sector
from modelFactory.oracle.dataset import GUARD_COL, build_dataset as build_oracle_dataset
from modelFactory.oracle.leakage import assert_no_forbidden_features, assert_no_future_features
from modelFactory.oracle.train import roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive

LOGGER = logging.getLogger(__name__)

TARGET_COL = "shared_direction_target"
SCORE_COL = "direction_score"
SYMBOL_COL = "symbol_context"
SECTOR_COL = "sector_context"
DEFAULT_PROFILE = Path("config/features/shared_direction/shared.json")
DEFAULT_ARTIFACTS_ROOT = Path("artifacts/models/shared_directional")
FORBIDDEN_FEATURES = {
    "proba_extreme", "directional_oracle_proba_extreme", "global_rank_20",
    "future_return", "oracle_decile", "oracle_pct_rank", TARGET_COL,
}


@dataclass(frozen=True, slots=True)
class SharedDirectionalConfig:
    horizon: int = 20
    pool_pct: float = 0.20
    top_fraction: float = 0.10
    min_train_dates: int = 504
    val_dates: int = 126
    test_dates: int = 126
    step_dates: int = 126
    max_splits: int = 12
    iterations: int = 600
    depth: int = 6
    learning_rate: float = 0.03
    random_seed: int = 42
    amplitude_weight_min: float = 0.50
    amplitude_weight_max: float = 3.00
    context_mode: str = "symbol_sector"
    amplitude_weighting: bool = True
    objective: str = "classifier"

    def __post_init__(self) -> None:
        if not 0.0 < self.pool_pct < 1.0:
            raise ValueError("pool_pct doit être dans ]0,1[.")
        if not 0.0 < self.top_fraction < 0.5:
            raise ValueError("top_fraction doit être dans ]0,0.5[.")
        if min(self.min_train_dates, self.val_dates, self.test_dates, self.step_dates) < 1:
            raise ValueError("Les tailles Walk-Forward doivent être positives.")
        if self.max_splits < 1 or self.iterations < 10 or self.depth < 1:
            raise ValueError("Configuration d'entraînement mutualisé invalide.")
        if self.context_mode not in {"symbol_sector", "sector", "none"}:
            raise ValueError("context_mode doit être symbol_sector, sector ou none.")
        if self.objective not in {"classifier", "pairwise_ranker"}:
            raise ValueError("objective doit être classifier ou pairwise_ranker.")


def load_profile(path: Path | str = DEFAULT_PROFILE) -> dict[str, Any]:
    profile_path = Path(path)
    raw = profile_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if int(payload.get("schema_version", 0)) != 1 or payload.get("direction") != "shared":
        raise ValueError(f"Profil directionnel mutualisé invalide: {profile_path}")
    columns = payload.get("feature_columns")
    if not isinstance(columns, list) or not columns or len(columns) != len(set(columns)):
        raise ValueError("feature_columns mutualisées doivent être non vides et sans doublon.")
    forbidden = FORBIDDEN_FEATURES.intersection(columns)
    if forbidden:
        raise ValueError(f"Features interdites dans le profil mutualisé: {sorted(forbidden)}")
    return {
        **payload,
        "profile_path": str(profile_path.resolve()),
        "profile_file": profile_path.name,
        "sha256": sha256(raw).hexdigest(),
    }


def _load_gate(path: Path, pool_pct: float) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Cache Oracle OOF introuvable: {path}")
    gate = pd.read_parquet(path)
    required = {
        "date", "symbol", "directional_oracle_eligible",
        "directional_oracle_oof_available", "directional_oracle_extreme_pct",
    }
    missing = sorted(required.difference(gate.columns))
    if missing:
        raise ValueError(f"Cache Oracle OOF incomplet: {missing}")
    gate = gate.copy()
    gate["date"] = pd.to_datetime(gate["date"], errors="coerce").dt.normalize()
    gate["symbol"] = gate["symbol"].astype(str).str.upper()
    threshold = 1.0 - float(pool_pct)
    recomputed = gate["directional_oracle_extreme_pct"].astype(float) >= threshold
    declared = gate["directional_oracle_eligible"].fillna(False).astype(bool)
    available = gate["directional_oracle_oof_available"].fillna(False).astype(bool)
    if bool((declared & ~available).any()):
        raise ValueError("Cache Oracle OOF invalide: ligne éligible sans disponibilité OOF.")
    # Le percentile est la source canonique si l'utilisateur change pool_pct.
    gate["shared_oracle_eligible"] = available & recomputed
    return gate[["date", "symbol", "shared_oracle_eligible"]]


def build_shared_dataset(
    engine: Any,
    oracle_batch_id: str,
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    gate_path: Path,
    profile: dict[str, Any],
    config: SharedDirectionalConfig,
) -> tuple[pd.DataFrame, list[str], list[str], dict[str, Any]]:
    """Assemble le panel TOP20 Oracle OOF et la cible D1/D10.

    D2-D9 restent dans les folds de test pour mesurer le classement réel mais
    sont exclus du fit. ``proba_extreme`` sert uniquement de gate et n'entre
    jamais dans les features.
    """
    requested = [str(c) for c in profile["feature_columns"]]
    frame, feature_columns = build_oracle_dataset(
        engine,
        oracle_batch_id,
        symbols,
        start_date=start_date,
        end_date=end_date,
        horizon=config.horizon,
        require_global_rank=False,
        need_targets=True,
        feature_whitelist=requested,
        generator_options=dict(profile.get("generator_options") or {}),
    )
    if frame.empty:
        raise ValueError("Dataset mutualisé vide avant application du gate Oracle.")
    assert_no_forbidden_features(feature_columns)
    assert_no_future_features(feature_columns)
    forbidden = FORBIDDEN_FEATURES.intersection(feature_columns)
    if forbidden:
        raise ValueError(f"Features de fuite détectées: {sorted(forbidden)}")

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    gate = _load_gate(gate_path, config.pool_pct)
    frame = frame.merge(gate, on=["date", "symbol"], how="inner", validate="one_to_one")
    frame = frame[frame["shared_oracle_eligible"]].copy()
    if frame.empty:
        raise ValueError("Aucun événement dans le TOP Oracle OOF mutualisé.")

    decile = pd.to_numeric(frame["oracle_decile"], errors="coerce")
    frame[TARGET_COL] = np.where(decile.eq(10), 1.0, np.where(decile.eq(1), 0.0, np.nan))
    frame[SYMBOL_COL] = frame["symbol"].fillna("UNKNOWN").astype(str)
    try:
        raw_sector = _load_sector_mapping(engine) or {}
    except Exception:  # noqa: BLE001
        LOGGER.warning("Mapping secteur indisponible; fallback UNKNOWN.", exc_info=True)
        raw_sector = {}
    sector_map = {
        str(symbol).upper(): _map_to_gics_sector(str(sector))
        for symbol, sector in raw_sector.items() if sector is not None
    }
    frame[SECTOR_COL] = frame["symbol"].map(sector_map).fillna("UNKNOWN").astype(str)
    categorical_columns = {
        "symbol_sector": [SYMBOL_COL, SECTOR_COL],
        "sector": [SECTOR_COL],
        "none": [],
    }[config.context_mode]
    diagnostics = {
        "rows_oracle_pool": int(len(frame)),
        "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "labeled_d1": int(decile.eq(1).sum()),
        "labeled_d10": int(decile.eq(10).sum()),
        "middle_rejected_for_fit": int((~decile.isin([1, 10])).sum()),
        "sector_coverage": float(frame[SECTOR_COL].ne("UNKNOWN").mean()),
        "first_date": str(frame["date"].min().date()),
        "last_date": str(frame["date"].max().date()),
    }
    return frame, feature_columns, categorical_columns, diagnostics


def amplitude_weights(future_return: pd.Series, config: SharedDirectionalConfig) -> np.ndarray:
    if not config.amplitude_weighting:
        return np.ones(len(future_return), dtype=float)
    amplitude = pd.to_numeric(future_return, errors="coerce").abs().to_numpy(float)
    finite = amplitude[np.isfinite(amplitude) & (amplitude > 0)]
    scale = float(np.median(finite)) if finite.size else 1.0
    if not np.isfinite(scale) or scale <= 0:
        scale = 1.0
    return np.clip(amplitude / scale, config.amplitude_weight_min, config.amplitude_weight_max)


def binary_probability_to_ternary(probability_long: Iterable[float]) -> pd.DataFrame:
    """Convertit P(D10|D1∨D10) en probabilités avec abstention native.

    La masse directionnelle vaut ``|2p-1|`` et le reste devient FLAT. Les
    trois probabilités sont bornées et somment exactement à un.
    """
    raw = np.clip(np.asarray(list(probability_long), dtype=float), 0.0, 1.0)
    confidence = np.abs(2.0 * raw - 1.0)
    p_long = np.where(raw >= 0.5, confidence, 0.0)
    p_short = np.where(raw < 0.5, confidence, 0.0)
    p_flat = 1.0 - confidence
    return pd.DataFrame({"proba_short": p_short, "proba_flat": p_flat, "proba_long": p_long})


def _prepare_X(frame: pd.DataFrame, numeric: list[str], categorical: list[str]) -> pd.DataFrame:
    X = frame[numeric + categorical].copy()
    for column in numeric:
        X[column] = pd.to_numeric(X[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    for column in categorical:
        X[column] = X[column].fillna("UNKNOWN").astype(str)
    return X


def _fit_catboost(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    numeric: list[str],
    categorical: list[str],
    config: SharedDirectionalConfig,
    *,
    iterations: int | None = None,
) -> Any:
    from catboost import CatBoostClassifier, CatBoostRanker

    common = dict(
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
    if config.objective == "pairwise_ranker":
        model = CatBoostRanker(loss_function="PairLogit", eval_metric="NDCG:top=10", **common)
    else:
        model = CatBoostClassifier(loss_function="Logloss", eval_metric="AUC", **common)
    train = train.sort_values(["date", "symbol"]).copy()
    if valid is not None:
        valid = valid.sort_values(["date", "symbol"]).copy()
    X_train = _prepare_X(train, numeric, categorical)
    y_train = train[TARGET_COL].astype(int)
    kwargs: dict[str, Any] = {"cat_features": categorical}
    if config.objective == "pairwise_ranker":
        kwargs["group_id"] = train["date"].dt.strftime("%Y-%m-%d").to_numpy()
    else:
        kwargs["sample_weight"] = amplitude_weights(train["future_return"], config)
    if valid is not None and not valid.empty:
        eval_set: Any = (_prepare_X(valid, numeric, categorical), valid[TARGET_COL].astype(int))
        if config.objective == "pairwise_ranker":
            from catboost import Pool
            eval_set = Pool(
                _prepare_X(valid, numeric, categorical),
                label=valid[TARGET_COL].astype(int),
                group_id=valid["date"].dt.strftime("%Y-%m-%d").to_numpy(),
                cat_features=categorical,
            )
        kwargs.update({
            "eval_set": eval_set,
            "early_stopping_rounds": 60,
            "use_best_model": True,
        })
    model.fit(X_train, y_train, **kwargs)
    return model


def _tail(frame: pd.DataFrame, score: str, fraction: float, ascending: bool) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for _, group in frame.groupby("date", sort=False):
        n = max(1, math.ceil(len(group) * fraction))
        parts.append(group.nsmallest(n, score) if ascending else group.nlargest(n, score))
    return pd.concat(parts, ignore_index=True) if parts else frame.iloc[0:0].copy()


def _mean_daily_ic(frame: pd.DataFrame) -> float | None:
    values: list[float] = []
    for _, group in frame.groupby("date"):
        valid = group[[SCORE_COL, "future_return"]].dropna()
        if len(valid) >= 3 and valid[SCORE_COL].nunique() > 1:
            values.append(float(valid[SCORE_COL].corr(valid["future_return"], method="spearman")))
    return float(np.nanmean(values)) if values else None


def evaluate_oos(
    frame: pd.DataFrame,
    top_fraction: float,
    *,
    probability_score: bool = True,
) -> dict[str, Any]:
    work = frame.dropna(subset=[SCORE_COL, "future_return", "oracle_decile"]).copy()
    extremes = work[work["oracle_decile"].isin([1, 10])]
    long_tail = _tail(work, SCORE_COL, top_fraction, ascending=False)
    short_tail = _tail(work, SCORE_COL, top_fraction, ascending=True)

    def tail_metrics(tail: pd.DataFrame, expected_decile: int, opposite_decile: int, sign: float) -> dict[str, Any]:
        signed = sign * tail["future_return"]
        return {
            "rows": int(len(tail)),
            "dates": int(tail["date"].nunique()),
            "symbols": int(tail["symbol"].nunique()),
            "target_decile_precision": float(tail["oracle_decile"].eq(expected_decile).mean()),
            "opposite_decile_contamination": float(tail["oracle_decile"].eq(opposite_decile).mean()),
            "mean_signed_return": float(signed.mean()),
            "median_signed_return": float(signed.median()),
            "hit_rate": float((signed > 0).mean()),
        }

    abstention: dict[str, Any] = {}
    for raw_threshold in ((0.55, 0.60, 0.65, 0.70, 0.75, 0.80) if probability_score else ()):
        selected = extremes[(extremes[SCORE_COL] >= raw_threshold) | (extremes[SCORE_COL] <= 1.0 - raw_threshold)]
        correct = (
            ((selected[SCORE_COL] >= raw_threshold) & selected["oracle_decile"].eq(10))
            | ((selected[SCORE_COL] <= 1.0 - raw_threshold) & selected["oracle_decile"].eq(1))
        )
        abstention[f"raw_{raw_threshold:.2f}"] = {
            "coverage_extremes": float(len(selected) / len(extremes)) if len(extremes) else 0.0,
            "direction_accuracy": float(correct.mean()) if len(selected) else None,
            "rows": int(len(selected)),
        }
    y = extremes["oracle_decile"].eq(10).astype(int).to_numpy()
    return {
        "rows": int(len(work)),
        "extreme_rows": int(len(extremes)),
        "auc_d10_vs_d1": roc_auc(y, extremes[SCORE_COL].to_numpy()) if len(np.unique(y)) == 2 else None,
        "mean_daily_direction_ic": _mean_daily_ic(work),
        "long_top_decile": tail_metrics(long_tail, 10, 1, 1.0),
        "short_bottom_decile": tail_metrics(short_tail, 1, 10, -1.0),
        "abstention": abstention,
    }


def train_shared_directional(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
    config: SharedDirectionalConfig,
    artifact_dir: Path,
) -> dict[str, Any]:
    folds = build_folds_adaptive(
        dataset,
        min_train_dates=config.min_train_dates,
        val_dates=config.val_dates,
        test_dates=config.test_dates,
        step_dates=config.step_dates,
        max_splits=config.max_splits,
        forecast_horizon=config.horizon,
    )
    if not folds:
        raise ValueError("Aucun fold Walk-Forward mutualisé valide.")
    oos_parts: list[pd.DataFrame] = []
    fold_metrics: list[dict[str, Any]] = []
    best_iterations: list[int] = []
    for index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=[TARGET_COL]).copy()
        valid = fold["val"].dropna(subset=[TARGET_COL]).copy()
        test = fold["test"].copy()
        if train[TARGET_COL].nunique() < 2 or valid[TARGET_COL].nunique() < 2 or test.empty:
            LOGGER.warning("shared_direction fold=%d skipped: classes ou test insuffisants", index)
            continue
        model = _fit_catboost(train, valid, feature_columns, categorical_columns, config)
        if config.objective == "pairwise_ranker":
            score = np.asarray(model.predict(_prepare_X(test, feature_columns, categorical_columns)), dtype=float)
        else:
            score = model.predict_proba(_prepare_X(test, feature_columns, categorical_columns))[:, 1]
        scored = test[["date", "symbol", "future_return", "oracle_decile", TARGET_COL]].copy()
        scored[SCORE_COL] = score
        scored["fold_index"] = index
        oos_parts.append(scored)
        metrics = evaluate_oos(
            scored, config.top_fraction,
            probability_score=config.objective == "classifier",
        )
        metrics.update({
            "fold_index": index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "train_rows_extreme": int(len(train)),
            "valid_rows_extreme": int(len(valid)),
        })
        fold_metrics.append(metrics)
        best_iterations.append(max(1, int(model.get_best_iteration()) + 1))
        LOGGER.info(
            "shared_direction fold=%d auc=%s ic=%s long_ret=%s short_ret=%s",
            index, metrics["auc_d10_vs_d1"], metrics["mean_daily_direction_ic"],
            metrics["long_top_decile"]["mean_signed_return"],
            metrics["short_bottom_decile"]["mean_signed_return"],
        )
    if not oos_parts:
        raise ValueError("Tous les folds mutualisés ont été rejetés.")

    oos = pd.concat(oos_parts, ignore_index=True)
    overall = evaluate_oos(
        oos, config.top_fraction,
        probability_score=config.objective == "classifier",
    )
    labeled = dataset.dropna(subset=[TARGET_COL]).copy()
    final_iterations = max(10, int(np.median(best_iterations)))
    final_model = _fit_catboost(
        labeled, None, feature_columns, categorical_columns, config,
        iterations=final_iterations,
    )
    artifact_dir.mkdir(parents=True, exist_ok=False)
    model_path = artifact_dir / "model.cbm"
    final_model.save_model(str(model_path))
    oos_path = artifact_dir / "oof_predictions.parquet"
    oos.to_parquet(oos_path, index=False)
    metrics = {
        "status": "completed",
        "model_role": "direction_shared",
        "model_name": "catboost_pairwise" if config.objective == "pairwise_ranker" else "catboost_classifier",
        "objective": config.objective,
        "n_folds": len(fold_metrics),
        "final_iterations": final_iterations,
        "overall": overall,
        "folds": fold_metrics,
        "feature_count_numeric": len(feature_columns),
        "categorical_columns": categorical_columns,
        "trained_rows_extreme": int(len(labeled)),
        "trained_symbols": int(labeled["symbol"].nunique()),
        "trained_through_date": str(pd.Timestamp(dataset["date"].max()).date()),
        "artifact_paths": {"model": str(model_path), "oof": str(oos_path)},
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return metrics


def run_experiment(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    config: SharedDirectionalConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    config = config or SharedDirectionalConfig()
    profile = load_profile(profile_path)
    from modelFactory.oracle.train import get_universe_symbols

    symbols = get_universe_symbols(engine, oracle_batch_id, config.horizon)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    source_root = Path("artifacts/models") / oracle_batch_id
    gate_path = source_root / "_oracle_oof_gate.parquet"
    dataset, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols,
        start_date=start_date, end_date=end_date, gate_path=gate_path,
        profile=profile, config=config,
    )
    run_id = f"shared-direction-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{oracle_batch_id[-6:]}"
    artifact_dir = artifacts_root / run_id
    metrics = train_shared_directional(dataset, features, categoricals, config, artifact_dir)
    contract = {
        "schema_version": 1,
        "run_id": run_id,
        "source_oracle_batch_id": oracle_batch_id,
        "status": metrics["status"],
        "serving_ready": False,
        "research_only": True,
        "population": population,
        "target_contract": {
            "mode": "pairwise_d1_vs_d10_by_date" if config.objective == "pairwise_ranker" else "binary_d1_vs_d10",
            "middle_class": "excluded_from_fit_scored_in_oof",
            "horizon": config.horizon,
            "return_basis": "cross_sectional_decile",
            "amplitude_weighting": [config.amplitude_weight_min, config.amplitude_weight_max],
            "amplitude_weighting_enabled": (
                config.amplitude_weighting and config.objective == "classifier"
            ),
            "amplitude_weighting_note": (
                "PairLogit n'accepte pas les poids individuels."
                if config.objective == "pairwise_ranker" else None
            ),
        },
        "conditioning": {
            "source": "oracle_walk_forward_oof_test",
            "pool_pct": config.pool_pct,
            "oracle_score_is_feature": False,
            "gate_path": str(gate_path),
        },
        "abstention": {
            "mapping": "directional_mass=abs(2*p_d10-1); remainder=flat",
            "promotion_threshold": "not_selected_during_research",
        },
        "feature_profile": profile,
        "feature_columns": features,
        "categorical_columns": categoricals,
        "context_mode": config.context_mode,
        "objective": config.objective,
        "walk_forward": {
            "min_train_dates": config.min_train_dates,
            "val_dates": config.val_dates,
            "test_dates": config.test_dates,
            "step_dates": config.step_dates,
            "max_splits": config.max_splits,
        },
        "metrics": metrics,
    }
    (artifact_dir / "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (artifact_dir / "feature_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return artifact_dir, contract


def _format_summary(path: Path, contract: dict[str, Any]) -> str:
    metrics = contract["metrics"]
    overall = metrics["overall"]
    long = overall["long_top_decile"]
    short = overall["short_bottom_decile"]
    population = contract["population"]
    return "\n".join([
        f"SharedDirectional terminé: {path}",
        f"Population Oracle OOF: {population['rows_oracle_pool']} lignes, "
        f"{population['symbols']} symboles, {population['dates']} dates",
        f"Folds valides: {metrics['n_folds']}",
        f"AUC D10/D1: {overall['auc_d10_vs_d1']:.4f}",
        f"IC directionnel quotidien: {overall['mean_daily_direction_ic']:+.4f}",
        f"TOP LONG: D10={long['target_decile_precision']:.2%} "
        f"D1={long['opposite_decile_contamination']:.2%} ret={long['mean_signed_return']:+.2%}",
        f"TOP SHORT: D1={short['target_decile_precision']:.2%} "
        f"D10={short['opposite_decile_contamination']:.2%} ret={short['mean_signed_return']:+.2%}",
        "Serving désactivé: promotion uniquement après validation des gates OOS.",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Direction mutualisée sur événements Oracle OOF.")
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--feature-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--wf-min-train-size", type=int, default=504)
    parser.add_argument("--wf-val-size", type=int, default=126)
    parser.add_argument("--wf-test-size", type=int, default=126)
    parser.add_argument("--wf-step-size", type=int, default=126)
    parser.add_argument("--wf-max-splits", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--context-mode", choices=["symbol_sector", "sector", "none"], default="symbol_sector")
    parser.add_argument("--no-amplitude-weighting", action="store_true", default=False)
    parser.add_argument("--objective", choices=["classifier", "pairwise_ranker"], default="classifier")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    cfg = SharedDirectionalConfig(
        min_train_dates=args.wf_min_train_size,
        val_dates=args.wf_val_size,
        test_dates=args.wf_test_size,
        step_dates=args.wf_step_size,
        max_splits=args.wf_max_splits,
        iterations=args.iterations,
        depth=args.depth,
        learning_rate=args.learning_rate,
        context_mode=args.context_mode,
        amplitude_weighting=not args.no_amplitude_weighting,
        objective=args.objective,
    )
    path, contract = run_experiment(
        get_sqlalchemy_engine(), args.oracle_batch_id,
        start_date=args.start_date, end_date=args.end_date,
        profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
        symbols_limit=args.symbols_limit, config=cfg,
    )
    print(_format_summary(path, contract))


if __name__ == "__main__":
    main()
