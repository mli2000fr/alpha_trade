"""modelFactory/orchestrator.py — Orchestrateur distribué multi-symboles."""
from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

from sqlalchemy.engine import Engine

from modelFactory.config import TrainingConfig
from modelFactory.data_loader import load_symbol_bars, load_symbol_sentiment
from modelFactory.db_registry import load_candidate_symbols
from modelFactory.trainer import TrainResult, train_symbol

LOGGER = logging.getLogger(__name__)


def _train_worker(symbol: str, cfg: TrainingConfig) -> TrainResult:
    """Worker function exécutée dans un sous-process. Crée son propre engine."""
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    bars = load_symbol_bars(engine, symbol)
    sentiment_df = None
    if cfg.data.include_sentiment_features:
        sentiment_df = load_symbol_sentiment(engine, symbol)
    return train_symbol(symbol, bars, cfg, engine, sentiment_df=sentiment_df)


def run_training_batch(
    cfg: TrainingConfig,
    engine: Engine,
    symbols: Optional[list[str]] = None,
) -> list[TrainResult]:
    """Entraîne tous les symboles candidats en parallèle.

    Args:
        cfg: Configuration d'entraînement.
        engine: Engine SQLAlchemy pour charger l'univers.
        symbols: Liste explicite de symboles (sinon charge is_candidate=1).

    Returns:
        Liste de TrainResult.
    """
    if symbols is None:
        symbols = load_candidate_symbols(engine)

    if not symbols:
        LOGGER.warning("run_training_batch no_candidates")
        return []

    LOGGER.info("run_training_batch start symbols=%d max_workers=%d", len(symbols), cfg.max_workers)
    results: list[TrainResult] = []

    with ProcessPoolExecutor(max_workers=cfg.max_workers) as pool:
        futures = {pool.submit(_train_worker, sym, cfg): sym for sym in symbols}
        for future in as_completed(futures):
            sym = futures[future]
            try:
                result = future.result()
                results.append(result)
                LOGGER.info("orchestrator done symbol=%s status=%s", sym, result.status)
            except Exception as exc:
                LOGGER.exception("orchestrator worker_exception symbol=%s", sym)
                results.append(TrainResult(sym, "N/A", "failed", skip_reason=str(exc)))

    # Summary
    completed = sum(1 for r in results if r.status == "completed")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    LOGGER.info("run_training_batch finished completed=%d skipped=%d failed=%d", completed, skipped, failed)
    return results

