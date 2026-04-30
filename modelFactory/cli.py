"""modelFactory/cli.py — CLI pour le module Model Factory."""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from common.utils import configure_root_logging
from core.run_summary import attach_schema_version
from database.connection import get_sqlalchemy_engine
from modelFactory.config import (
    BaselineConfig,
    CalibrationConfig,
    ChampionSelectionConfig,
    DataConfig,
    GlobalModelConfig,
    ModelConfig,
    ThresholdOptimizationConfig,
    TargetOptimizationConfig,
    TrainingConfig,
    WalkForwardConfig,
)


LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
ML_MODES = ("rebuild-all", "rebuild-missing", "refresh-stale")
SYMBOL_SOURCES = ("candidates", "stock-bars-daily")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Model Factory — LSTM per-symbol training & prediction")
    p.add_argument("--mode", choices=["train", "predict"], required=True, help="train ou predict")
    p.add_argument("--symbols", nargs="*", default=None, help="Liste de symboles (défaut: is_candidate=1)")
    p.add_argument(
        "--symbol-source",
        type=str,
        default="candidates",
        choices=list(SYMBOL_SOURCES),
        help="Source des symboles quand --symbols n'est pas fourni : candidates | stock-bars-daily",
    )
    p.add_argument("--max-workers", type=int, default=4)
    p.add_argument("--max-epochs", type=int, default=50)
    p.add_argument("--sequence-length", type=int, default=60)
    p.add_argument("--forecast-horizon", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--hidden-size", type=int, default=128)
    p.add_argument("--artifacts-dir", type=str, default="artifacts/models")
    p.add_argument("--include-sentiment", action="store_true", default=False,
                   help="Inclure les features sentiment (ticker_daily_sentiment_features) dans le modèle")
    p.add_argument("--enable-cross-sectional", action="store_true", default=False,
                   help="Active les features cross-sectionnelles PIT-safe calculées depuis l'univers historique")
    p.add_argument("--cross-sectional-min-universe", type=int, default=20,
                   help="Nombre minimum de symboles disponibles par date pour calculer des ranks cross-sectionnels fiables")
    p.add_argument("--feature-set", type=str, default="v1", choices=["v1", "expert"])
    p.add_argument("--benchmark-symbol", type=str, default="SPY")
    p.add_argument("--target-mode", type=str, default="binary", choices=["binary", "swing_cash"])
    p.add_argument("--target-up-threshold", type=float, default=0.0,
                   help="Seuil de rendement futur pour classer une hausse tradeable")
    p.add_argument("--target-down-threshold", type=float, default=0.0,
                   help="Seuil de rendement futur pour classer une baisse marquée / zone no-trade")
    p.add_argument("--decision-threshold", type=float, default=0.5,
                   help="Seuil de probabilité pour émettre un signal long (sinon no-trade)")
    p.add_argument("--calibration-method", type=str, default="none", choices=["none", "platt"])
    p.add_argument("--calibration-min-samples", type=int, default=64)
    p.add_argument("--calibration-max-iter", type=int, default=100)
    # Phase 4.2.g — walk-forward actif PAR DÉFAUT (BooleanOptionalAction).
    p.add_argument(
        "--walkforward",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Active une évaluation walk-forward avant l'entraînement final (défaut: ON Phase 4.2.g)",
    )
    p.add_argument(
        "--ml-mode",
        type=str,
        default="rebuild-all",
        choices=list(ML_MODES),
        help="Stratégie d'entraînement (Phase 4.2.g) : rebuild-all | rebuild-missing | refresh-stale",
    )
    p.add_argument("--wf-min-train-size", type=int, default=504)
    p.add_argument("--wf-val-size", type=int, default=126)
    p.add_argument("--wf-test-size", type=int, default=126)
    p.add_argument("--wf-step-size", type=int, default=126)
    p.add_argument("--wf-max-splits", type=int, default=3)
    p.add_argument("--compare-lightgbm", action="store_true", default=False,
                   help="Entraîne aussi une baseline LightGBM et compare ses métriques")
    p.add_argument("--enable-catboost", action="store_true", default=False,
                   help="Entraîne aussi une baseline CatBoost et compare ses métriques")
    p.add_argument("--enable-global-model", action="store_true", default=False,
                   help="Entraîne aussi un modèle global multi-symboles en comparaison")
    p.add_argument("--global-model-name", type=str, default="catboost", choices=["catboost", "lightgbm"])
    p.add_argument("--global-artifact-symbol", type=str, default="__GLOBAL__")
    p.add_argument("--select-champion", action="store_true", default=False,
                   help="Active la sélection automatique du champion parmi les modèles éligibles à l’inférence")
    p.add_argument("--default-champion", type=str, default="lstm_attention",
                   choices=["lstm_attention", "lightgbm", "catboost", "global_model"])
    p.add_argument("--champion-selection-metric", type=str, default="selection_score",
                   choices=["selection_score", "business_score", "auc"])
    # Phase 4.2.e — Quarantaine champion.
    p.add_argument("--champion-min-runs", type=int, default=0,
                   help="Nb min de runs walk-forward complétés avant qu'un nouveau champion soit servi")
    p.add_argument("--champion-min-days", type=int, default=0,
                   help="Nb min de jours d'observation avant qu'un nouveau champion soit servi")
    p.add_argument("--lgbm-max-depth", type=int, default=4)
    p.add_argument("--lgbm-n-estimators", type=int, default=200)
    p.add_argument("--lgbm-learning-rate", type=float, default=0.05)
    p.add_argument("--catboost-depth", type=int, default=6)
    p.add_argument("--catboost-iterations", type=int, default=300)
    p.add_argument("--catboost-learning-rate", type=float, default=0.03)
    p.add_argument("--optimize-target", action="store_true", default=False,
                   help="Sélectionne automatiquement le meilleur horizon swing parmi plusieurs candidats")
    p.add_argument("--candidate-horizons", nargs="*", type=int, default=[3, 5, 10, 15])
    p.add_argument("--candidate-up-thresholds", nargs="*", type=float, default=[0.0, 0.01, 0.02])
    p.add_argument("--candidate-down-thresholds", nargs="*", type=float, default=[0.0, -0.005, -0.01])
    p.add_argument("--min-trades-fraction", type=float, default=0.15)
    p.add_argument("--optimize-thresholds", action="store_true", default=False,
                   help="Sélectionne automatiquement le meilleur decision_threshold sur validation")
    p.add_argument("--candidate-decision-thresholds", nargs="*", type=float, default=[0.50, 0.55, 0.60, 0.65, 0.70])
    p.add_argument("--min-action-rate", type=float, default=0.03)
    p.add_argument("--max-action-rate", type=float, default=0.35)
    p.add_argument("--min-precision-long", type=float, default=0.52)
    p.add_argument("--accelerator", type=str, default="auto", choices=["auto", "cpu", "gpu"])
    p.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def main(args: list[str] | None = None) -> None:
    parser = build_arg_parser()
    opts = parser.parse_args(args)

    configure_root_logging(
        level=getattr(logging, opts.log_level),
        log_path="./log/model_factory.log",
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = TrainingConfig(
        data=DataConfig(
            sequence_length=opts.sequence_length,
            forecast_horizon=opts.forecast_horizon,
            include_sentiment_features=opts.include_sentiment,
            enable_cross_sectional_features=opts.enable_cross_sectional,
            cross_sectional_min_universe=opts.cross_sectional_min_universe,
            feature_set=opts.feature_set,
            benchmark_symbol=opts.benchmark_symbol,
            target_mode=opts.target_mode,
            target_up_threshold=opts.target_up_threshold,
            target_down_threshold=opts.target_down_threshold,
            decision_threshold=opts.decision_threshold,
        ),
        model=ModelConfig(batch_size=opts.batch_size, hidden_size=opts.hidden_size, max_epochs=opts.max_epochs),
        calibration=CalibrationConfig(
            method=opts.calibration_method,
            min_samples=opts.calibration_min_samples,
            max_iter=opts.calibration_max_iter,
        ),
        walk_forward=WalkForwardConfig(
            enabled=opts.walkforward,
            min_train_size=opts.wf_min_train_size,
            val_size=opts.wf_val_size,
            test_size=opts.wf_test_size,
            step_size=opts.wf_step_size,
            max_splits=opts.wf_max_splits,
        ),
        baseline=BaselineConfig(
            enabled=opts.compare_lightgbm,
            enable_catboost=opts.enable_catboost,
            model_name="lightgbm",
            max_depth=opts.lgbm_max_depth,
            n_estimators=opts.lgbm_n_estimators,
            learning_rate=opts.lgbm_learning_rate,
            catboost_depth=opts.catboost_depth,
            catboost_iterations=opts.catboost_iterations,
            catboost_learning_rate=opts.catboost_learning_rate,
        ),
        global_model=GlobalModelConfig(
            enabled=opts.enable_global_model,
            model_name=opts.global_model_name,
            artifact_symbol=opts.global_artifact_symbol,
            use_cross_sectional_features=opts.enable_cross_sectional,
        ),
        champion_selection=ChampionSelectionConfig(
            enabled=opts.select_champion,
            allow_auto_selection=opts.select_champion,
            default_champion=opts.default_champion,
            selection_metric=opts.champion_selection_metric,
            min_runs=int(opts.champion_min_runs),
            min_days=int(opts.champion_min_days),
        ),
        target_optimization=TargetOptimizationConfig(
            enabled=opts.optimize_target,
            candidate_horizons=tuple(opts.candidate_horizons),
            candidate_up_thresholds=tuple(opts.candidate_up_thresholds),
            candidate_down_thresholds=tuple(opts.candidate_down_thresholds),
            min_trades_fraction=opts.min_trades_fraction,
        ),
        threshold_optimization=ThresholdOptimizationConfig(
            enabled=opts.optimize_thresholds,
            candidate_decision_thresholds=tuple(opts.candidate_decision_thresholds),
            min_action_rate=opts.min_action_rate,
            max_action_rate=opts.max_action_rate,
            min_precision_long=opts.min_precision_long,
        ),
        artifacts_dir=Path(opts.artifacts_dir),
        max_workers=opts.max_workers,
        accelerator=opts.accelerator,
    )

    engine = get_sqlalchemy_engine()

    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    run_id = f"model-factory-{started_at.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"

    if opts.mode == "train":
        from modelFactory.orchestrator import run_training_batch
        results = run_training_batch(
            cfg,
            engine,
            symbols=opts.symbols,
            mode=opts.ml_mode,
            symbol_source=opts.symbol_source,
        )
        completed = sum(1 for r in results if r.status == "completed")
        skipped = sum(1 for r in results if r.status == "skipped")
        failed = sum(1 for r in results if r.status == "failed")
        quarantined = sum(
            1 for r in results
            if isinstance(getattr(r, "metrics", None), dict)
            and r.metrics.get("champion_quarantine") is True
        )
        print(f"\n{'=' * 60}")
        print(f"  Model Factory — Training Summary")
        print(f"  Completed: {completed}  Skipped: {skipped}  Failed: {failed}")
        print(f"{'=' * 60}")
        finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        _emit_run_summary(_build_run_summary(
            mode="train",
            run_id=run_id,
            opts=opts,
            cfg=cfg,
            started_at=started_at,
            finished_at=finished_at,
            symbols_total=len(opts.symbols or []) or len(results),
            completed=completed,
            skipped=skipped,
            failed=failed,
            quarantined=quarantined,
        ))

    elif opts.mode == "predict":
        from modelFactory.db_registry import load_candidate_symbols
        from modelFactory.predictor import predict_batch
        symbols = opts.symbols or load_candidate_symbols(engine)
        preds = predict_batch(symbols, Path(opts.artifacts_dir), engine, accelerator=opts.accelerator)
        print(f"\n{'=' * 60}")
        print(f"  Model Factory — Predictions: {len(preds)} rows")
        print(f"{'=' * 60}")
        if not preds.empty:
            print(preds.to_string(index=False))
        finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        _emit_run_summary(_build_run_summary(
            mode="predict",
            run_id=run_id,
            opts=opts,
            cfg=cfg,
            started_at=started_at,
            finished_at=finished_at,
            symbols_total=len(symbols),
            completed=int(len(preds)),
            skipped=max(0, len(symbols) - int(len(preds))),
            failed=0,
            quarantined=0,
        ))


# ---------------------------------------------------------------------------
# Phase 4.2.h — run_summary ML standardisé.
# ---------------------------------------------------------------------------

def _emit_run_summary(summary: dict[str, object]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _build_run_summary(
    *,
    mode: str,
    run_id: str,
    opts: argparse.Namespace,
    cfg: TrainingConfig,
    started_at: datetime,
    finished_at: datetime,
    symbols_total: int,
    completed: int,
    skipped: int,
    failed: int,
    quarantined: int,
) -> dict[str, object]:
    from modelFactory.features import fingerprint as compute_feature_fingerprint
    feature_fp = compute_feature_fingerprint(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )
    payload: dict[str, object] = {
        "run_id": run_id,
        "mode": mode,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "walkforward_enabled": bool(getattr(opts, "walkforward", False)),
        "ml_mode": str(getattr(opts, "ml_mode", "rebuild-all")),
        "symbol_source": str(getattr(opts, "symbol_source", "candidates")),
        "feature_fingerprint": feature_fp,
        "champion_min_runs": int(getattr(opts, "champion_min_runs", 0)),
        "champion_min_days": int(getattr(opts, "champion_min_days", 0)),
        "symbols_total": int(symbols_total),
        "symbols_completed": int(completed),
        "symbols_skipped": int(skipped),
        "symbols_failed": int(failed),
        "symbols_quarantined": int(quarantined),
    }
    return attach_schema_version(payload, version=1)
