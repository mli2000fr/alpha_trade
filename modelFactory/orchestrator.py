"""modelFactory/orchestrator.py — Orchestrateur distribué multi-symboles."""
from __future__ import annotations

import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import torch
from sqlalchemy.engine import Engine

from modelFactory.config import TrainingConfig
from modelFactory.data_loader import load_benchmark_bars, load_symbol_bars, load_symbol_sentiment, load_universe_bars
from modelFactory.db_registry import load_candidate_symbols
from modelFactory.global_model import train_global_model
from modelFactory.trainer import TrainResult, train_symbol

LOGGER = logging.getLogger(__name__)


def _selection_score_from_result(result: dict) -> float:
    if not result or result.get("status") != "completed":
        return float("-inf")
    return float(
        result.get("selection_score")
        or result.get("test", {}).get("threshold_business_score")
        or result.get("test", {}).get("auc")
        or result.get("val", {}).get("threshold_business_score")
        or 0.0
    )


def _build_ranking(challengers: dict[str, dict], champion_name: str) -> list[dict[str, object]]:
    sortable = sorted(challengers.items(), key=lambda item: _selection_score_from_result(item[1]), reverse=True)
    ranking: list[dict[str, object]] = []
    for idx, (model_name, result) in enumerate(sortable, start=1):
        status = result.get("status", "unknown")
        if model_name == champion_name and status == "completed":
            status = "selected_default_champion"
        ranking.append(
            {
                "rank": idx,
                "model_name": model_name,
                "selection_score": None if _selection_score_from_result(result) == float("-inf") else _selection_score_from_result(result),
                "status": status,
                "reason": result.get("reason"),
            }
        )
    return ranking


def _inject_global_model_into_symbol_artifacts(
    symbol: str,
    cfg: TrainingConfig,
    global_result: dict,
) -> None:
    symbol_dir = (Path(cfg.artifacts_dir) / symbol).resolve()
    config_path = symbol_dir / "config.json"
    metrics_path = symbol_dir / "metrics.json"
    if not config_path.exists() or not metrics_path.exists():
        return

    with open(config_path, encoding="utf-8") as fh:
        config_data = json.load(fh)
    with open(metrics_path, encoding="utf-8") as fh:
        metrics = json.load(fh)

    symbol_global = global_result.get("by_symbol", {}).get(symbol)
    if symbol_global is None:
        symbol_global = {
            "status": global_result.get("status", "unknown"),
            "model_name": "global_model",
            "backend_model_name": global_result.get("backend_model_name"),
            "reason": global_result.get("reason", "symbol_not_available_in_global_test"),
            "selection_score": global_result.get("selection_score"),
            "val": global_result.get("val", {}),
            "test": global_result.get("test", {}),
        }
    else:
        symbol_global = {
            **symbol_global,
            "artifact_symbol": global_result.get("artifact_symbol"),
            "artifact_paths": global_result.get("artifact_paths", {}),
        }

    artifact_routes = config_data.get("artifact_routes") or {"selected_model": config_data.get("architecture_selected", "lstm_attention"), "models": {}}
    models = artifact_routes.setdefault("models", {})
    models["global_model"] = {
        "status": symbol_global.get("status", global_result.get("status", "unknown")),
        "artifact_symbol": global_result.get("artifact_symbol"),
        "model_path": global_result.get("artifact_paths", {}).get("model_path"),
        "config_path": global_result.get("artifact_paths", {}).get("config_path"),
        "calibrator_path": global_result.get("artifact_paths", {}).get("calibrator_path"),
        "inference_backend": "global_tabular",
        "backend_model_name": global_result.get("backend_model_name"),
    }
    config_data["artifact_routes"] = artifact_routes

    challengers = metrics.get("challengers") or {}
    challengers["global_model"] = symbol_global
    challenger_map = {k: v for k, v in challengers.items() if k != "ranking"}
    challengers["ranking"] = _build_ranking(challenger_map, config_data.get("architecture_selected", "lstm_attention"))
    metrics["challengers"] = challengers
    metrics["global_model"] = symbol_global

    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config_data, fh, indent=2, default=str)
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, default=str)


def _gpu_requested_or_available(cfg: TrainingConfig) -> bool:
    return cfg.accelerator == "gpu" or (cfg.accelerator == "auto" and torch.cuda.is_available())


def _train_worker(symbol: str, cfg: TrainingConfig, universe_symbols: list[str] | None = None) -> TrainResult:
    """Worker function exécutée dans un sous-process. Crée son propre engine."""
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    bars = load_symbol_bars(engine, symbol)
    benchmark_df = None
    if cfg.data.feature_set == "expert" or cfg.data.enable_cross_sectional_features:
        benchmark_df = load_benchmark_bars(engine, cfg.data.benchmark_symbol)
    sentiment_df = None
    if cfg.data.include_sentiment_features:
        sentiment_df = load_symbol_sentiment(engine, symbol)
    universe_df = None
    if cfg.data.enable_cross_sectional_features:
        effective_universe = list(dict.fromkeys((universe_symbols or []) + [symbol]))
        universe_df = load_universe_bars(engine, effective_universe)
    return train_symbol(symbol, bars, cfg, engine, sentiment_df=sentiment_df, benchmark_df=benchmark_df, universe_df=universe_df)


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

    use_gpu = _gpu_requested_or_available(cfg)
    effective_workers = 1 if use_gpu else cfg.max_workers
    if use_gpu and cfg.max_workers != 1:
        LOGGER.warning(
            "run_training_batch gpu_detected accelerator=%s requested_max_workers=%d -> forcing effective_workers=1",
            cfg.accelerator,
            cfg.max_workers,
        )

    LOGGER.info(
        "run_training_batch start symbols=%d max_workers=%d effective_workers=%d accelerator=%s cuda_available=%s",
        len(symbols),
        cfg.max_workers,
        effective_workers,
        cfg.accelerator,
        torch.cuda.is_available(),
    )
    results: list[TrainResult] = []

    if effective_workers == 1:
        for sym in symbols:
            try:
                if cfg.data.enable_cross_sectional_features:
                    result = _train_worker(sym, cfg, symbols)
                else:
                    result = _train_worker(sym, cfg)
                results.append(result)
                LOGGER.info("orchestrator done symbol=%s status=%s", sym, result.status)
            except Exception as exc:
                LOGGER.exception("orchestrator worker_exception symbol=%s", sym)
                results.append(TrainResult(sym, "N/A", "failed", skip_reason=str(exc)))
    else:
        with ProcessPoolExecutor(max_workers=effective_workers) as pool:
            if cfg.data.enable_cross_sectional_features:
                futures = {pool.submit(_train_worker, sym, cfg, symbols): sym for sym in symbols}
            else:
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

    if cfg.global_model.enabled and symbols:
        global_result = train_global_model(symbols, cfg, artifacts_dir=Path(cfg.artifacts_dir), engine=engine)
        LOGGER.info("run_training_batch global_model status=%s", global_result.get("status"))
        for result in results:
            if result.status != "completed":
                continue
            _inject_global_model_into_symbol_artifacts(result.symbol, cfg, global_result)
            result.metrics["global_model"] = global_result.get("by_symbol", {}).get(result.symbol, global_result)
    LOGGER.info("run_training_batch finished completed=%d skipped=%d failed=%d", completed, skipped, failed)
    return results

