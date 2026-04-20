"""modelFactory/cli.py — CLI pour le module Model Factory."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from database.connection import get_sqlalchemy_engine
from modelFactory.config import DataConfig, ModelConfig, TrainingConfig
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
        ),
        model=ModelConfig(batch_size=opts.batch_size, hidden_size=opts.hidden_size, max_epochs=opts.max_epochs),
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
