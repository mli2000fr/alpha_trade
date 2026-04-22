"""modelFactory/cli.py — CLI pour le module Model Factory."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from database.connection import get_sqlalchemy_engine
from modelFactory.config import (
    BaselineConfig,
    CalibrationConfig,
    DataConfig,
    ModelConfig,
    TargetOptimizationConfig,
    TrainingConfig,
    WalkForwardConfig,
)
from common.utils import configure_root_logging


LOGGER = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Model Factory — LSTM per-symbol training & prediction")
    p.add_argument("--mode", choices=["train", "predict"], required=True, help="train ou predict")
    p.add_argument("--symbols", nargs="*", default=None, help="Liste de symboles (défaut: is_candidate=1)")
    p.add_argument("--max-workers", type=int, default=4)
    p.add_argument("--max-epochs", type=int, default=50)
    p.add_argument("--sequence-length", type=int, default=60)
    p.add_argument("--forecast-horizon", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--hidden-size", type=int, default=128)
    p.add_argument("--artifacts-dir", type=str, default="artifacts/models")
    p.add_argument("--include-sentiment", action="store_true", default=False,
                   help="Inclure les features sentiment (ticker_daily_sentiment_features) dans le modèle")
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
    p.add_argument("--walkforward", action="store_true", default=False,
                   help="Active une évaluation walk-forward avant l'entraînement final")
    p.add_argument("--wf-min-train-size", type=int, default=504)
    p.add_argument("--wf-val-size", type=int, default=126)
    p.add_argument("--wf-test-size", type=int, default=126)
    p.add_argument("--wf-step-size", type=int, default=126)
    p.add_argument("--wf-max-splits", type=int, default=3)
    p.add_argument("--compare-lightgbm", action="store_true", default=False,
                   help="Entraîne aussi une baseline LightGBM et compare ses métriques")
    p.add_argument("--lgbm-max-depth", type=int, default=4)
    p.add_argument("--lgbm-n-estimators", type=int, default=200)
    p.add_argument("--lgbm-learning-rate", type=float, default=0.05)
    p.add_argument("--optimize-target", action="store_true", default=False,
                   help="Sélectionne automatiquement le meilleur horizon swing parmi plusieurs candidats")
    p.add_argument("--candidate-horizons", nargs="*", type=int, default=[3, 5, 10, 15])
    p.add_argument("--min-trades-fraction", type=float, default=0.15)
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
            model_name="lightgbm",
            max_depth=opts.lgbm_max_depth,
            n_estimators=opts.lgbm_n_estimators,
            learning_rate=opts.lgbm_learning_rate,
        ),
        target_optimization=TargetOptimizationConfig(
            enabled=opts.optimize_target,
            candidate_horizons=tuple(opts.candidate_horizons),
            min_trades_fraction=opts.min_trades_fraction,
        ),
        artifacts_dir=Path(opts.artifacts_dir),
        max_workers=opts.max_workers,
        accelerator=opts.accelerator,
    )

    engine = get_sqlalchemy_engine()

    if opts.mode == "train":
        from modelFactory.orchestrator import run_training_batch
        results = run_training_batch(cfg, engine, symbols=opts.symbols)
        completed = sum(1 for r in results if r.status == "completed")
        skipped = sum(1 for r in results if r.status == "skipped")
        failed = sum(1 for r in results if r.status == "failed")
        print(f"\n{'=' * 60}")
        print(f"  Model Factory — Training Summary")
        print(f"  Completed: {completed}  Skipped: {skipped}  Failed: {failed}")
        print(f"{'=' * 60}")

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
