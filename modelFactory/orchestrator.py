"""modelFactory/orchestrator.py — Orchestrateur distribué multi-symboles."""
from __future__ import annotations

from datetime import date
import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Literal, Optional

import torch
from sqlalchemy.engine import Engine

from modelFactory.champion_selection import build_challenger_ranking, select_champion
from modelFactory.config import TrainingConfig
from modelFactory.data_loader import (
    load_benchmark_bars,
    load_symbol_bars,
    load_symbol_latest_bar_date,
    load_symbol_latest_bar_dates,
    load_symbol_sentiment,
    load_universe_bars,
    resolve_history_window_start_date,
)
from modelFactory.features import fingerprint as compute_feature_fingerprint
from modelFactory.db_registry import load_candidate_symbols, load_stock_bars_daily_symbols, replace_model_governance
from modelFactory.global_model import train_global_model
from modelFactory.runtime_status import update_runtime_status
from modelFactory.trainer import TrainResult, train_symbol

LOGGER = logging.getLogger(__name__)
SymbolSource = Literal["candidates", "stock-bars-daily"]


def _inject_global_model_into_symbol_artifacts(
    symbol: str,
    cfg: TrainingConfig,
    global_result: dict,
    engine: Engine | None = None,
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

    challengers = metrics.get("challengers") or {}
    challengers["global_model"] = symbol_global
    challenger_map = {k: v for k, v in challengers.items() if k != "ranking"}
    champion_decision = select_champion(challenger_map, models, config_data.get("champion_selection", {}) and cfg.champion_selection or cfg.champion_selection)
    annotated = champion_decision["annotated_challengers"]
    selected_model = str(champion_decision["selected_model"])
    selection_mode = str(champion_decision["selection_mode"])
    artifact_routes["selected_model"] = selected_model
    config_data["artifact_routes"] = artifact_routes
    config_data["architecture_selected"] = selected_model
    config_data["selection_mode"] = selection_mode
    challengers = {**annotated}
    challengers["ranking"] = build_challenger_ranking(
        annotated,
        models,
        selected_model,
        selection_mode=selection_mode,
        champion_cfg=cfg.champion_selection,
    )
    metrics["challengers"] = challengers
    metrics["global_model"] = symbol_global
    metrics["champion"] = {
        "model_name": selected_model,
        "selection_mode": selection_mode,
        "selection_metric": cfg.champion_selection.selection_metric,
        "selection_score": champion_decision.get("selection_score", annotated.get(selected_model, {}).get("selection_score")),
    }

    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config_data, fh, indent=2, default=str)
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, default=str)

    run_id = config_data.get("run_id")
    if engine is not None and isinstance(run_id, str) and run_id:
        replace_model_governance(
            engine,
            run_id=run_id,
            symbol=symbol,
            challengers=annotated,
            artifact_routes_models=models,
            selected_model=selected_model,
            selection_mode=selection_mode,
            selection_metric=cfg.champion_selection.selection_metric,
            ranking=challengers.get("ranking"),
        )


def _gpu_requested_or_available(cfg: TrainingConfig) -> bool:
    return cfg.accelerator == "gpu" or (cfg.accelerator == "auto" and torch.cuda.is_available())


def _filter_symbols_by_mode(
    engine: Engine,
    symbols: list[str],
    *,
    mode: str,
    cfg: TrainingConfig,
) -> list[str]:
    """Phase 4.2.g — filtre la liste de symboles selon le mode ML.

    - ``rebuild-missing`` : ne garde que les symboles sans ``config.json``.
    - ``refresh-stale`` : garde les symboles sans artefacts, avec contrat de
      features/fenêtre historique différent, ou entraînés avant la dernière
      barre disponible pour le symbole.
    """
    current_fp = compute_feature_fingerprint(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )

    def _parse_iso_date(value: object) -> date | None:
        if isinstance(value, str) and value.strip():
            try:
                return date.fromisoformat(value.strip())
            except ValueError:
                return None
        return None

    artifacts_dir = Path(cfg.artifacts_dir)
    kept: list[str] = []
    skipped: list[str] = []
    latest_dates = load_symbol_latest_bar_dates(engine, symbols) if mode == "refresh-stale" else {}
    for symbol in symbols:
        config_path = artifacts_dir / symbol / "config.json"
        if not config_path.exists():
            kept.append(symbol)
            continue
        if mode == "rebuild-missing":
            skipped.append(symbol)
            continue
        try:
            with open(config_path, encoding="utf-8") as fh:
                cfg_data = json.load(fh)
            persisted = cfg_data.get("feature_fingerprint")
        except Exception:  # noqa: BLE001
            kept.append(symbol)
            continue

        persisted_history_window = (cfg_data.get("data") or {}).get("history_window_years")
        trained_through_date = _parse_iso_date(cfg_data.get("trained_through_date"))
        latest_available_date = latest_dates.get(symbol)

        if persisted != current_fp:
            kept.append(symbol)
            continue
        if persisted_history_window != cfg.data.history_window_years:
            kept.append(symbol)
            continue
        if trained_through_date is None or latest_available_date is None or trained_through_date < latest_available_date:
            kept.append(symbol)
            continue
        skipped.append(symbol)
    LOGGER.info(
        "ml_mode=%s current_fp=%s history_window_years=%s symbols_kept=%d symbols_skipped=%d",
        mode, current_fp, cfg.data.history_window_years, len(kept), len(skipped),
    )
    return kept


def _train_worker(symbol: str, cfg: TrainingConfig, universe_symbols: list[str] | None = None) -> TrainResult:
    """Worker function exécutée dans un sous-process. Crée son propre engine."""
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    history_end_date = load_symbol_latest_bar_date(engine, symbol)
    history_start_date = resolve_history_window_start_date(history_end_date, cfg.data.history_window_years)
    bars = load_symbol_bars(engine, symbol, end_date=history_end_date, start_date=history_start_date)
    benchmark_df = None
    if cfg.data.feature_set == "expert" or cfg.data.enable_cross_sectional_features:
        benchmark_df = load_benchmark_bars(
            engine,
            cfg.data.benchmark_symbol,
            end_date=history_end_date,
            start_date=history_start_date,
        )
    sentiment_df = None
    if cfg.data.include_sentiment_features:
        sentiment_df = load_symbol_sentiment(
            engine,
            symbol,
            end_date=history_end_date,
            start_date=history_start_date,
        )
    universe_df = None
    if cfg.data.enable_cross_sectional_features:
        effective_universe = list(dict.fromkeys((universe_symbols or []) + [symbol]))
        universe_df = load_universe_bars(
            engine,
            effective_universe,
            end_date=history_end_date,
            start_date=history_start_date,
        )
    return train_symbol(symbol, bars, cfg, engine, sentiment_df=sentiment_df, benchmark_df=benchmark_df, universe_df=universe_df)


def run_training_batch(
    cfg: TrainingConfig,
    engine: Engine,
    symbols: Optional[list[str]] = None,
    *,
    mode: str = "rebuild-all",
    symbol_source: SymbolSource = "candidates",
) -> list[TrainResult]:
    """Entraîne tous les symboles candidats en parallèle.

    Args:
        cfg: Configuration d'entraînement.
        engine: Engine SQLAlchemy pour charger l'univers.
        symbols: Liste explicite de symboles (sinon charge selon ``symbol_source``).
        mode: Phase 4.2.g — ``rebuild-all`` (défaut), ``rebuild-missing``
            (skippe les symboles déjà entraînés au feature_fingerprint
            courant), ou ``refresh-stale``.
        symbol_source: Source par défaut si ``symbols`` n'est pas fourni.

    Returns:
        Liste de TrainResult.
    """
    if symbols is None:
        if symbol_source == "stock-bars-daily":
            symbols = load_stock_bars_daily_symbols(engine)
        else:
            symbols = load_candidate_symbols(engine)

    if not symbols:
        LOGGER.warning("run_training_batch no_candidates")
        return []

    if mode != "rebuild-all":
        symbols = _filter_symbols_by_mode(engine, symbols, mode=mode, cfg=cfg)
        if not symbols:
            LOGGER.info("run_training_batch all_symbols_skipped mode=%s", mode)
            return []

    use_gpu = _gpu_requested_or_available(cfg)
    effective_workers = 1 if use_gpu else cfg.max_workers
    if cfg.debug_train and effective_workers != 1:
        LOGGER.warning(
            "run_training_batch debug_train enabled requested_max_workers=%d -> forcing effective_workers=1 for deterministic logs",
            cfg.max_workers,
        )
        effective_workers = 1
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
    update_runtime_status(
        current_phase="batch_start",
        progress_label="🧠 Progression ML Train",
        progress_total=len(symbols),
        progress_current=0,
        progress_item=None,
        symbols_total=len(symbols),
        symbols_completed=0,
        symbols_skipped=0,
        symbols_failed=0,
        current_symbol=None,
        current_symbol_index=0,
        current_symbol_total=len(symbols),
        effective_workers=effective_workers,
        accelerator=cfg.accelerator,
    )
    results: list[TrainResult] = []

    if effective_workers == 1:
        for index, sym in enumerate(symbols, start=1):
            try:
                update_runtime_status(
                    current_phase="symbol_train_start",
                    current_symbol=sym,
                    current_symbol_index=index,
                    progress_item=sym,
                )
                if cfg.data.enable_cross_sectional_features:
                    result = _train_worker(sym, cfg, symbols)
                else:
                    result = _train_worker(sym, cfg)
                results.append(result)
                update_runtime_status(
                    progress_current=len(results),
                    symbols_completed=sum(1 for r in results if r.status == "completed"),
                    symbols_skipped=sum(1 for r in results if r.status == "skipped"),
                    symbols_failed=sum(1 for r in results if r.status == "failed"),
                    current_phase=f"symbol_{result.status}",
                )
                LOGGER.info("orchestrator done symbol=%s status=%s", sym, result.status)
            except Exception as exc:
                LOGGER.exception("orchestrator worker_exception symbol=%s", sym)
                results.append(TrainResult(sym, "N/A", "failed", skip_reason=str(exc)))
                update_runtime_status(
                    progress_current=len(results),
                    symbols_completed=sum(1 for r in results if r.status == "completed"),
                    symbols_skipped=sum(1 for r in results if r.status == "skipped"),
                    symbols_failed=sum(1 for r in results if r.status == "failed"),
                    current_phase="symbol_failed",
                    current_symbol=sym,
                    current_symbol_index=index,
                    progress_item=sym,
                )
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
                    update_runtime_status(
                        progress_current=len(results),
                        symbols_completed=sum(1 for r in results if r.status == "completed"),
                        symbols_skipped=sum(1 for r in results if r.status == "skipped"),
                        symbols_failed=sum(1 for r in results if r.status == "failed"),
                        current_phase=f"symbol_{result.status}",
                        current_symbol=sym,
                        progress_item=sym,
                    )
                    LOGGER.info("orchestrator done symbol=%s status=%s", sym, result.status)
                except Exception as exc:
                    LOGGER.exception("orchestrator worker_exception symbol=%s", sym)
                    results.append(TrainResult(sym, "N/A", "failed", skip_reason=str(exc)))
                    update_runtime_status(
                        progress_current=len(results),
                        symbols_completed=sum(1 for r in results if r.status == "completed"),
                        symbols_skipped=sum(1 for r in results if r.status == "skipped"),
                        symbols_failed=sum(1 for r in results if r.status == "failed"),
                        current_phase="symbol_failed",
                        current_symbol=sym,
                        progress_item=sym,
                    )

    # Summary
    completed = sum(1 for r in results if r.status == "completed")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")

    if cfg.global_model.enabled and symbols:
        update_runtime_status(current_phase="global_model_training", progress_item="__GLOBAL__")
        global_result = train_global_model(symbols, cfg, artifacts_dir=Path(cfg.artifacts_dir), engine=engine)
        LOGGER.info("run_training_batch global_model status=%s", global_result.get("status"))
        for result in results:
            if result.status != "completed":
                continue
            _inject_global_model_into_symbol_artifacts(result.symbol, cfg, global_result, engine)
            result.metrics["global_model"] = global_result.get("by_symbol", {}).get(result.symbol, global_result)
    update_runtime_status(
        current_phase="batch_completed",
        progress_current=len(results),
        symbols_completed=completed,
        symbols_skipped=skipped,
        symbols_failed=failed,
        progress_item=None,
    )
    LOGGER.info("run_training_batch finished completed=%d skipped=%d failed=%d", completed, skipped, failed)
    return results

