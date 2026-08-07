"""modelFactory/orchestrator.py — Orchestrateur distribué multi-symboles."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

import numpy as np
import pandas as pd
import torch
from sqlalchemy.engine import Engine
from sqlalchemy import text

from modelFactory.batch_diagnostics import persist_batch_diagnostics
from modelFactory.champion_selection import (
    build_challenger_ranking,
    persist_artifact_signature_manifest,
    select_champion,
)
from modelFactory.config import TrainingConfig
from modelFactory.data_loader import (
    load_benchmark_bars,
    load_symbol_bars,
    load_symbol_latest_bar_date,
    load_symbol_latest_bar_dates,
    load_symbol_selector_context,
    load_symbol_sentiment,
    resolve_training_start_date,
)
from modelFactory.features import build_feature_contract
from modelFactory.features import fingerprint as compute_feature_fingerprint
from modelFactory.features import normalize_feature_columns
from modelFactory.reproducibility import apply_reproducibility, derive_seed
from modelFactory.db_registry import (
    load_symbols_for_source,
    replace_model_governance,
    update_training_batch,
)
from common.tradable_universe import load_tradable_universe_for_period
from modelFactory.global_model import train_global_model, train_global_model_wf
from modelFactory.runtime_status import update_runtime_status
from modelFactory.trainer import TrainResult, train_symbol
from database.selector_reference import filter_symbols_from_start, normalize_start_symbol

LOGGER = logging.getLogger(__name__)
SymbolSource = Literal[
    "tradable-universe",
    "stock-bars-daily",
    "ticket-recherche",
]

# Cache pour le diagnostic de liquidité — lu par cli.py après run_training_batch()
_last_liquidity_diag: dict[str, Any] = {}


def get_last_liquidity_diagnostics() -> dict[str, Any]:
    """Retourne le diagnostic de liquidité du dernier batch.

    Utilisé par cli.py pour l'injecter dans metadata_json
    et par le rapport pour afficher les symboles filtrés.
    """
    return _last_liquidity_diag


def _with_batch_artifacts_dir(cfg: TrainingConfig, batch_id: str) -> TrainingConfig:
    """Scopes durable training artifacts under one immutable campaign directory."""
    return replace(
        cfg,
        artifacts_dir=Path(cfg.artifacts_dir) / batch_id,
        benchmark_artifacts_dir=Path(cfg.benchmark_artifacts_dir) / batch_id,
        global_benchmark_artifacts_dir=Path(cfg.global_benchmark_artifacts_dir) / batch_id,
        catboost_artifacts_dir=Path(cfg.catboost_artifacts_dir) / batch_id,
        batch_id=batch_id,
    )


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
        "feature_columns": global_result.get("feature_columns"),
        "feature_fingerprint": global_result.get("feature_fingerprint"),
        "feature_contract": global_result.get("feature_contract"),
        "selected_decision_threshold": global_result.get("threshold_optimization", {}).get("selected_threshold"),
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
    config_data["artifact_signature_required"] = True
    config_data["artifact_signature_manifest_path"] = str(config_path.with_name("artifact_signature_manifest.json"))
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
        "selection_reason": champion_decision.get("selection_reason"),
        "selected_model_eligible": bool(champion_decision.get("selected_model_eligible", False)),
    }
    config_data["selection_reason"] = champion_decision.get("selection_reason")
    config_data["selected_model_eligible"] = bool(champion_decision.get("selected_model_eligible", False))

    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(config_data, fh, indent=2, default=str)
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    persist_artifact_signature_manifest(
        config_path.with_name("artifact_signature_manifest.json"),
        symbol=symbol,
        run_id=config_data.get("run_id") if isinstance(config_data, dict) else None,
        selected_model=selected_model,
        artifact_routes_models=models,
    )

    run_id = config_data.get("run_id")
    if engine is not None and isinstance(run_id, str) and run_id:
        try:
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
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "inject_global_model governance_write_failed symbol=%s run_id=%s error=%s",
                symbol,
                run_id,
                exc,
            )
            update_runtime_status(
                last_db_issue_operation="replace_model_governance",
                last_db_issue_reason=f"training_db_issue:{type(exc).__name__}",
                current_symbol=symbol,
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
      features/date de début historique différent, ou entraînés avant la
      dernière barre disponible pour le symbole.
    """
    current_fp = compute_feature_fingerprint(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=cfg.data.include_screener_scores,
        include_short_score=cfg.data.include_short_score_features,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_global_stacking=cfg.global_model.stacking_enabled,
    )
    current_contract = build_feature_contract(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=cfg.data.include_screener_scores,
        include_short_score=cfg.data.include_short_score_features,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_global_stacking=cfg.global_model.stacking_enabled,
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
    latest_dates = (
        load_symbol_latest_bar_dates(engine, symbols, end_date=cfg.data.training_end_date)
        if mode == "refresh-stale"
        else {}
    )
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

        persisted_data = cfg_data.get("data") or {}
        persisted_training_start_date = _parse_iso_date(persisted_data.get("training_start_date"))
        persisted_training_end_date = _parse_iso_date(persisted_data.get("training_end_date"))
        persisted_contract = cfg_data.get("feature_contract")
        persisted_contract_columns = normalize_feature_columns((persisted_contract or {}).get("feature_columns") if isinstance(persisted_contract, dict) else None)
        persisted_contract_fp = str((persisted_contract or {}).get("feature_fingerprint") or "").strip() if isinstance(persisted_contract, dict) else ""
        persisted_top_level_columns = normalize_feature_columns(cfg_data.get("feature_columns"))
        if persisted_training_start_date is None:
            persisted_history_window = persisted_data.get("history_window_years")
            try:
                persisted_history_window_years = int(str(persisted_history_window).strip()) if persisted_history_window is not None else None
            except (TypeError, ValueError):
                persisted_history_window_years = None
            persisted_training_start_date = resolve_training_start_date(
                latest_dates.get(symbol),
                history_window_years=persisted_history_window_years,
            )
        trained_through_date = _parse_iso_date(cfg_data.get("trained_through_date"))
        latest_available_date = latest_dates.get(symbol)

        if persisted != current_fp:
            kept.append(symbol)
            continue
        if not isinstance(persisted_contract, dict):
            kept.append(symbol)
            continue
        if persisted_contract_columns != current_contract["feature_columns"]:
            kept.append(symbol)
            continue
        if persisted_contract_fp != current_contract["feature_fingerprint"]:
            kept.append(symbol)
            continue
        if persisted_top_level_columns is not None and persisted_top_level_columns != current_contract["feature_columns"]:
            kept.append(symbol)
            continue
        if persisted_training_start_date != cfg.data.training_start_date:
            kept.append(symbol)
            continue
        if persisted_training_end_date != cfg.data.training_end_date:
            kept.append(symbol)
            continue
        if trained_through_date is None or latest_available_date is None or trained_through_date < latest_available_date:
            kept.append(symbol)
            continue
        skipped.append(symbol)
    LOGGER.info(
        "ml_mode=%s current_fp=%s training_start_date=%s training_end_date=%s symbols_kept=%d symbols_skipped=%d",
        mode, current_fp, cfg.data.training_start_date, cfg.data.training_end_date, len(kept), len(skipped),
    )
    return kept


def _train_worker(
    symbol: str,
    cfg: TrainingConfig,
    universe_symbols: list[str] | None = None,
    *,
    cross_sectional_cache: pd.DataFrame | None = None,    fundamental_cache: pd.DataFrame | None = None,    batch_id: str | None = None,
) -> TrainResult:
    """Worker function exécutée dans un sous-process. Crée son propre engine."""
    from common.utils import configure_root_logging
    from database.connection import get_sqlalchemy_engine

    # Les workers ProcessPoolExecutor (spawn) n'héritent pas de la config
    # logging du processus parent. On la réapplique pour que les logs INFO
    # (walk_forward, tabular_wf, etc.) soient visibles dans le fichier.
    configure_root_logging(
        level=logging.DEBUG if cfg.debug_train else logging.INFO,
        log_path="./log/model_factory.log",
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # ── Limiter les threads PyTorch par worker ──
    # Par défaut, PyTorch utilise tous les cœurs CPU (OpenMP/MKL). Avec
    # N workers, chacun essaie de prendre tous les cœurs → N × cpu_count
    # threads → oversubscription massive → ralentissement. On limite à
    # cpu_count // max_workers threads par worker (2 par worker pour 6
    # workers sur 12 cœurs). En single-worker, on garde le défaut.
    if cfg.max_workers > 1:
        import os
        cpu_count = os.cpu_count() or 4
        threads = max(1, cpu_count // cfg.max_workers)
        torch.set_num_threads(threads)
        LOGGER.debug("_train_worker symbol=%s torch_threads=%d (max_workers=%d cpu=%d)",
                     symbol, threads, cfg.max_workers, cpu_count)

    apply_reproducibility(
        cfg.reproducibility.__class__(
            seed=derive_seed(cfg.reproducibility.seed, "orchestrator_worker", symbol),
            deterministic=cfg.reproducibility.deterministic,
        ),
        context=f"orchestrator_worker:{symbol}",
    )
    engine = get_sqlalchemy_engine()
    history_end_date = load_symbol_latest_bar_date(engine, symbol, end_date=cfg.data.training_end_date)
    history_start_date = resolve_training_start_date(history_end_date, cfg.data.training_start_date)
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
    selector_df = None
    if cfg.data.include_screener_scores or cfg.data.include_short_score_features:
        selector_df = load_symbol_selector_context(
            engine,
            symbol,
            end_date=history_end_date,
            start_date=history_start_date,
        )
    cross_sectional_df = None
    _needs_cross_sectional = cfg.data.enable_cross_sectional_features
    if _needs_cross_sectional:
        if cross_sectional_cache is not None and not cross_sectional_cache.empty:
            # Filter pre-computed cache to this symbol's rows
            cross_sectional_df = cross_sectional_cache[cross_sectional_cache["symbol"] == symbol].copy()
        else:
            # Fallback: compute on the fly (ProcessPoolExecutor path)
            from modelFactory.cross_sectional import build_cross_sectional_features_from_db
            effective_universe = list(dict.fromkeys((universe_symbols or []) + [symbol]))
            cross_sectional_df, _ = build_cross_sectional_features_from_db(
                engine,
                effective_universe,
                benchmark_df=benchmark_df,
                min_universe_size=cfg.data.cross_sectional_min_universe,
                start_date=history_start_date,
                end_date=history_end_date,
            )

    # ── Approche 2 — Phase 2 (multiprocessing) : charger global_rank depuis disque ──
    if cfg.global_model.stacking_enabled and cross_sectional_df is not None:
        _global_rank_path = Path(cfg.artifacts_dir) / "_global_rank_cache.parquet"
        if _global_rank_path.exists():
            global_rank_df = pd.read_parquet(_global_rank_path)
            if not global_rank_df.empty:
                # Détection dynamique des colonnes multi-horizons (global_rank_3, _5, _10)
                _rank_cols = [c for c in global_rank_df.columns if c.startswith("global_rank")]
                if _rank_cols:
                    cross_sectional_df = cross_sectional_df.merge(
                        global_rank_df[["symbol", "date"] + _rank_cols],
                        on=["symbol", "date"], how="left",
                    )
                    for _col in _rank_cols:
                        cross_sectional_df[_col] = (
                            cross_sectional_df[_col].fillna(0.5).astype(np.float64)
                        )
                # Rétro-compatibilité : colonne "global_rank" sans suffixe → "global_rank_10"
                if "global_rank" in global_rank_df.columns and "global_rank" not in _rank_cols:
                    cross_sectional_df["global_rank"] = cross_sectional_df.get(
                        "global_rank_10",
                        cross_sectional_df.get("global_rank", pd.Series(0.5, index=cross_sectional_df.index)),
                    ).fillna(0.5).astype(np.float64)

    return train_symbol(
        symbol,
        bars,
        cfg,
        engine,
        sentiment_df=sentiment_df,
        benchmark_df=benchmark_df,
        universe_df=None,  # not used when cross_sectional_df is provided
        selector_df=selector_df,
        cross_sectional_df=cross_sectional_df,
        batch_id=batch_id,
        fundamental_df=fundamental_cache,
    )


def run_training_batch(
    cfg: TrainingConfig,
    engine: Engine,
    symbols: Optional[list[str]] = None,
    *,
    mode: str = "rebuild-all",
    symbol_source: SymbolSource = "tradable-universe",
    universe_date: date | None = None,
    start_symbol: str | None = None,
    batch_id: str | None = None,
) -> list[TrainResult]:
    """Entraîne tous les symboles de l'univers sélectionné en parallèle.

    Args:
        cfg: Configuration d'entraînement.
        engine: Engine SQLAlchemy pour charger l'univers.
        symbols: Liste explicite de symboles (sinon charge selon ``symbol_source``).
        mode: Phase 4.2.g — ``rebuild-all`` (défaut), ``rebuild-missing``
            (skippe les symboles déjà entraînés au feature_fingerprint
            courant), ou ``refresh-stale``.
        symbol_source: Source nominale si ``symbols`` n'est pas fourni.
        universe_date: Date PIT utilisée pour les sources ponctuelles.
        start_symbol: Si renseigné, filtre les symboles pour ne garder que ceux
            alphabétiquement >= à cette valeur. Exemple: ``HGI`` démarre à HGI.
        batch_id: Identifiant partagé par les runs créés pendant cette campagne.

    Returns:
        Liste de TrainResult.
    """
    batch_id = batch_id or f"model-factory-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid4().hex[:6]}"
    cfg = _with_batch_artifacts_dir(cfg, batch_id)

    if symbols is None:
        if symbol_source == "tradable-universe":
            period_start = cfg.data.training_start_date
            period_end = cfg.data.training_end_date or universe_date
            if period_start is None or period_end is None:
                raise ValueError(
                    "training_start_date et training_end_date ou universe_date sont obligatoires "
                    "pour la source tradable-universe."
                )
            symbols = load_tradable_universe_for_period(
                engine,
                period_start,
                period_end,
            )
        else:
            symbols = load_symbols_for_source(engine, symbol_source)

    if start_symbol is not None:
        normalized_start = normalize_start_symbol(start_symbol)
        if normalized_start:
            symbols = filter_symbols_from_start(symbols, start_symbol=normalized_start)
            LOGGER.info("run_training_batch start_symbol=%s symbols_filtered=%d", normalized_start, len(symbols))

    if not symbols:
        LOGGER.warning("run_training_batch no_tradable_symbols")
        return []

    # ── Exclusion des symboles ticket (config/ticket_exclude.txt) ──
    if getattr(cfg.data, "exclude_ticket_symbols", False):
        _exclude_path = Path("config/ticket_exclude.txt")
        if _exclude_path.exists():
            _exclude_raw = _exclude_path.read_text(encoding="utf-8").strip()
            if _exclude_raw:
                _excluded = {s.strip().upper() for s in _exclude_raw.replace("\n", ",").split(",") if s.strip()}
                if _excluded:
                    _before = len(symbols)
                    symbols = [s for s in symbols if s.upper() not in _excluded]
                    LOGGER.info(
                        "run_training_batch exclude_ticket_symbols excluded=%d kept=%d path=%s",
                        _before - len(symbols), len(symbols), _exclude_path,
                    )
                    if not symbols:
                        LOGGER.warning("run_training_batch all_symbols_excluded_by_ticket")
                        return []

    if mode != "rebuild-all":
        symbols = _filter_symbols_by_mode(engine, symbols, mode=mode, cfg=cfg)
        if not symbols:
            LOGGER.info("run_training_batch all_symbols_skipped mode=%s", mode)
            return []

    # ── Filtrage liquidité (Sprint 2026-07-24) ──────────────────────────
    liquidity_excluded: list[str] = []
    liquidity_diag: dict[str, Any] = {}
    if cfg.data.enable_liquidity_filter:
        from modelFactory.liquidity_filter import filter_symbols_by_liquidity

        liquidity_excluded, liquidity_diag = filter_symbols_by_liquidity(
            engine,
            symbols,
            end_date=cfg.data.training_end_date,
            min_avg_volume_20d=cfg.data.liquidity_min_avg_volume_20d,
            min_market_cap=cfg.data.liquidity_min_market_cap,
            max_market_cap=getattr(cfg.data, "liquidity_max_market_cap", 0.0),
            max_avg_high_low_range_pct=cfg.data.liquidity_max_avg_high_low_range_pct,
            min_daily_dollar_volume=getattr(cfg.data, "liquidity_min_daily_dollar_volume", 0.0),
            min_price=getattr(cfg.data, "liquidity_min_price", 0.0),
            max_spread_bps=getattr(cfg.data, "liquidity_max_spread_bps", 40.0),
            spread_fallback_mode=getattr(cfg.data, "liquidity_spread_fallback_mode", "pass"),
            spread_max_quote_age_days=getattr(cfg.data, "liquidity_spread_max_quote_age_days", 5),
        )
        if liquidity_excluded:
            symbols = [s for s in symbols if s not in set(liquidity_excluded)]
            LOGGER.info(
                "run_training_batch liquidity_filter excluded=%d kept=%d",
                len(liquidity_excluded), len(symbols),
            )
            LOGGER.info(
                "run_training_batch liquidity_filter kept symbols: %s",
                ",".join(sorted(symbols)),
            )
            if not symbols:
                LOGGER.warning("run_training_batch all_symbols_filtered_by_liquidity")
                return []
    else:
        LOGGER.info("run_training_batch liquidity_filter disabled")

    # Stocker pour que cli.py puisse l'injecter dans metadata_json
    global _last_liquidity_diag
    _last_liquidity_diag = liquidity_diag

    # ── Filtrage per-symbol max (test rapide, top N par volume moyen) ──
    # Ne PAS appliquer au Global Ranking — sauvegarder la liste complète avant.
    _global_symbols = list(symbols)
    _ps_max = getattr(cfg.data, "per_symbol_max_symbols", 0)
    _ps_stratified = getattr(cfg.data, "per_symbol_selection_stratified", False)
    if _ps_max > 0 and len(symbols) > _ps_max:
        _orig_count = len(symbols)
        try:
            _vol_df = pd.read_sql(
                text(
                    "SELECT symbol, AVG(volume) AS avg_vol "
                    "FROM alpha_trade.stock_bars_daily "
                    "WHERE symbol IN :syms "
                    "GROUP BY symbol"
                ),
                engine,
                params={"syms": tuple(symbols)},
            )
            if _vol_df.empty:
                LOGGER.warning(
                    "per_symbol_max_symbols: no volume data for %d symbols, "
                    "keeping alphabetical truncation",
                    len(symbols),
                )
                symbols = symbols[:_ps_max]
            elif _ps_stratified and len(_vol_df) >= 10:
                # Stratifié par déciles : ~N/10 symboles par décile
                # On trie d'abord par volume décroissant pour que le top de
                # chaque décile soit représentatif, pas juste alphabétique.
                _vol_df = _vol_df.sort_values("avg_vol", ascending=False)
                _vol_df["decile"] = pd.qcut(_vol_df["avg_vol"], q=10, labels=False)
                _per_decile = max(1, _ps_max // 10)
                _selected: list[str] = []
                for _d in range(10):
                    _decile_syms = _vol_df[_vol_df["decile"] == _d]["symbol"].tolist()
                    _selected.extend(_decile_syms[:_per_decile])
                symbols = _selected[:_ps_max]
            else:
                # Top N par volume moyen (fallback si < 10 symboles pour stratifié)
                _vol_df = _vol_df.sort_values("avg_vol", ascending=False)
                symbols = _vol_df.head(_ps_max)["symbol"].tolist()
        except Exception as _exc:
            LOGGER.warning(
                "per_symbol_max_symbols: volume query failed, fallback alphabetical. "
                "error=%s symbols_count=%d",
                _exc, _orig_count,
            )
            symbols = symbols[:_ps_max]
        LOGGER.info(
            "run_training_batch per_symbol_max_symbols limit=%d orig=%d kept=%d stratified=%s",
            _ps_max, _orig_count, len(symbols), _ps_stratified,
        )

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
    # ── Log exhaustif des symboles retenus pour l'entraînement ──
    LOGGER.info(
        "TRAINING_SYMBOLS_FINAL per_symbol=%d (after --per-symbol-max-symbols filter) global=%d symbols=[%s]",
        len(symbols), len(_global_symbols), ",".join(symbols),
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

    # Pre-compute cross-sectional features ONCE for all symbols.
    # Each symbol only needs its own (symbol, date) rows, which we look up
    # by symbol in _train_worker.  This avoids loading the entire universe
    # 12k times.  Sector features piggyback on the same raw panel.
    cross_sectional_cache: pd.DataFrame | None = None
    _needs_cross_sectional = cfg.data.enable_cross_sectional_features
    if _needs_cross_sectional and _global_symbols:
        from modelFactory.cross_sectional import build_cross_sectional_features_from_db, _load_sector_mapping
        from modelFactory.data_loader import load_benchmark_bars, load_symbol_latest_bar_date
        LOGGER.info("run_training_batch pre-computing cross-sectional features for %d symbols", len(_global_symbols))
        bench_df = None
        if cfg.data.feature_set == "expert" or cfg.data.benchmark_symbol:
            try:
                bench_df = load_benchmark_bars(
                    engine,
                    cfg.data.benchmark_symbol,
                    end_date=cfg.data.training_end_date,
                    start_date=cfg.data.training_start_date,
                )
            except Exception:
                pass

        sector_map: dict[str, str] | None = _load_sector_mapping(engine)
        if sector_map:
            LOGGER.info("run_training_batch sector features enabled: %d symbols mapped to %d sectors",
                        len(sector_map), len(set(sector_map.values())))
        else:
            LOGGER.warning("run_training_batch sector features enabled but no sector mapping loaded")

        cross_sectional_cache, _ = build_cross_sectional_features_from_db(
            engine,
            _global_symbols,
            benchmark_df=bench_df,
            min_universe_size=cfg.data.cross_sectional_min_universe,
            start_date=cfg.data.training_start_date,
            end_date=cfg.data.training_end_date,
            sector_map=sector_map,
        )
        LOGGER.info(
            "run_training_batch cross-sectional cache ready rows=%d symbols=%d",
            len(cross_sectional_cache),
            cross_sectional_cache["symbol"].nunique() if not cross_sectional_cache.empty else 0,
        )

    # ── Fundamental features cache ──
    fundamental_cache: pd.DataFrame | None = None
    if cfg.data.include_fundamentals_features and _global_symbols:
        from modelFactory.fundamental_features import load_fundamentals_from_db
        LOGGER.info("run_training_batch loading fundamentals for %d symbols", len(_global_symbols))
        fundamental_cache = load_fundamentals_from_db(
            _global_symbols,
            start_date=cfg.data.training_start_date or "2020-01-01",
            end_date=cfg.data.training_end_date or pd.Timestamp.now().date(),
            engine=engine,
        )
        LOGGER.info(
            "run_training_batch fundamentals cache ready rows=%d symbols=%d",
            len(fundamental_cache),
            fundamental_cache["symbol"].nunique() if not fundamental_cache.empty else 0,
        )

    # ── Approche 2 — Phase 1 : Global Ranking Model Walk-Forward (FLAG A) ──
    global_result_wf: dict[str, Any] | None = None
    _needs_global = cfg.global_model.enabled
    if _needs_global and _global_symbols:
        update_runtime_status(current_phase="global_ranking_wf", progress_item="__GLOBAL__")
        LOGGER.info("run_training_batch global_ranking_wf start symbols=%d", len(_global_symbols))
        from modelFactory.global_ranking import train_global_ranking_wf
        global_result_wf = train_global_ranking_wf(
            _global_symbols, cfg, artifacts_dir=Path(cfg.artifacts_dir), engine=engine,
        )
        LOGGER.info(
            "run_training_batch global_ranking_wf status=%s ic_rank_mean=%s decile_spreads=%s",
            global_result_wf.get("status"),
            global_result_wf.get("ic_rank_mean"),
            global_result_wf.get("decile_spreads"),
        )

        # ── P0-8 (2026-08-07) : persister immédiatement les résultats du global ranking
        #    dans model_training_batch pour que le diagnostic IHM les affiche même
        #    si le batch est encore en cours (per-symbol training pas encore fait).
        _gr_ic = global_result_wf.get("ic_rank_mean")
        _gr_ic_std = global_result_wf.get("ic_rank_std")
        _gr_ds = global_result_wf.get("decile_spreads") or {}
        _gr_hd = global_result_wf.get("horizon_details") or {}
        if _gr_ic is not None:
            try:
                update_training_batch(
                    engine, batch_id,
                    ic_rank=float(_gr_ic),
                    ic_rank_std=float(_gr_ic_std) if _gr_ic_std is not None else None,
                    decile_spread_h3=float(_gr_ds.get(3)) if _gr_ds.get(3) is not None else None,
                    decile_spread_h5=float(_gr_ds.get(5)) if _gr_ds.get(5) is not None else None,
                    decile_spread_h10=float(_gr_ds.get(10)) if _gr_ds.get(10) is not None else None,
                )
                # ── Mettre à jour metadata_json avec les détails par horizon ──
                with engine.begin() as _conn:
                    _existing_meta = _conn.execute(
                        text("SELECT metadata_json FROM model_training_batch WHERE batch_id = :bid"),
                        {"bid": batch_id},
                    ).scalar()
                _meta_dict: dict[str, Any] = {}
                if _existing_meta:
                    try:
                        _meta_dict = json.loads(str(_existing_meta))
                    except Exception:
                        _meta_dict = {}
                _meta_dict["global_ranking"] = {
                    "ic_rank_mean": float(_gr_ic),
                    "ic_rank_std": float(_gr_ic_std) if _gr_ic_std is not None else None,
                    "decile_spreads": {str(h): float(v) for h, v in _gr_ds.items()} if _gr_ds else {},
                    "horizon_details": _gr_hd,
                    "symbols_count": int(global_result_wf.get("symbols_count", len(_global_symbols))),
                    "splits_count": int(global_result_wf.get("splits_count", 0)),
                    "pred_rows": int(global_result_wf.get("pred_rows", 0)),
                    "ic_by_horizon": global_result_wf.get("ic_by_horizon", {}),
                }
                update_training_batch(
                    engine, batch_id,
                    metadata_json=json.dumps(_meta_dict, default=str),
                )
                LOGGER.info(
                    "run_training_batch global_ranking persisted EARLY batch_id=%s ic=%.4f ic_std=%.4f",
                    batch_id, float(_gr_ic), float(_gr_ic_std) if _gr_ic_std is not None else float("nan"),
                )
            except Exception as _exc:
                LOGGER.warning(
                    "run_training_batch global_ranking early persist failed: %s",
                    _exc,
                )

        # ── Phase 2 : merge global_rank into cross-sectional cache (FLAG B) ──
        global_rank_df = global_result_wf.get("global_rank_df") if isinstance(global_result_wf, dict) else None
        if cfg.global_model.stacking_enabled and global_rank_df is not None and not global_rank_df.empty:
            _rank_cols = [c for c in global_rank_df.columns if c.startswith("global_rank")]
            # ── P1-5 fix (2026-08-04) : mesurer la couverture OOF + gate + global_rank_available ──
            _total_dates = 0
            if cross_sectional_cache is not None and not cross_sectional_cache.empty and "date" in cross_sectional_cache.columns:
                _total_dates = cross_sectional_cache["date"].nunique()
            _covered_dates = global_rank_df["date"].nunique() if "date" in global_rank_df.columns else 0
            _coverage_pct = round(100 * _covered_dates / _total_dates, 1) if _total_dates > 0 else 0.0
            LOGGER.info(
                "run_training_batch stacking coverage: %d/%d dates (%.1f%%) — "
                "dates hors validation Global Ranking → fallback 0.5",
                _covered_dates, _total_dates, _coverage_pct,
            )
            if _coverage_pct < 50:
                LOGGER.warning(
                    "run_training_batch stacking LOW COVERAGE: only %.1f%% of per-symbol dates "
                    "have real global_rank values. Remaining dates use neutral fallback 0.5.",
                    _coverage_pct,
                )
            if _coverage_pct < 10:
                LOGGER.error(
                    "run_training_batch stacking COVERAGE CRITICAL (%.1f%% < 10%%) — "
                    "disabling stacking for this run. global_rank will not be injected.",
                    _coverage_pct,
                )
                cfg = replace(cfg, global_model=replace(cfg.global_model, stacking_enabled=False))
                global_rank_df = None  # prevent merge below
            if global_rank_df is not None and not global_rank_df.empty:
                global_rank_df["global_rank_available"] = True
                if cross_sectional_cache is not None and not cross_sectional_cache.empty:
                    cross_sectional_cache = cross_sectional_cache.merge(
                        global_rank_df[["symbol", "date"] + _rank_cols + ["global_rank_available"]],
                        on=["symbol", "date"], how="left",
                    )
                    for _rc in _rank_cols:
                        cross_sectional_cache[_rc] = cross_sectional_cache[_rc].fillna(0.5).astype(np.float64)
                    cross_sectional_cache["global_rank_available"] = cross_sectional_cache["global_rank_available"].fillna(False).astype(bool)
                    # ── P1-5 : couverture par symbole + gate ──
                    _cov_by_sym = cross_sectional_cache.groupby("symbol")["global_rank_available"].mean()
                    _low_cov = _cov_by_sym[_cov_by_sym < 0.3]
                    _critical_cov = _cov_by_sym[_cov_by_sym < 0.1]
                    if len(_critical_cov) > 0:
                        LOGGER.warning(
                            "run_training_batch stacking: %d symbols with <10%% global_rank coverage "
                            "→ stacking DISABLED for these symbols. %s",
                            len(_critical_cov),
                            ",".join(_critical_cov.index[:10]) + ("..." if len(_critical_cov) > 10 else ""),
                        )
                        _crit_mask = cross_sectional_cache["symbol"].isin(_critical_cov.index)
                        for _rc in _rank_cols:
                            cross_sectional_cache.loc[_crit_mask, _rc] = 0.5
                        cross_sectional_cache.loc[_crit_mask, "global_rank_available"] = False
                    elif len(_low_cov) > 0:
                        LOGGER.warning(
                            "run_training_batch stacking: %d symbols with <30%% global_rank coverage. "
                            "Symbols: %s",
                            len(_low_cov),
                            ",".join(_low_cov.index[:10]) + ("..." if len(_low_cov) > 10 else ""),
                        )
                    LOGGER.info(
                        "run_training_batch stacking per-symbol coverage: median=%.1f%% min=%.1f%% n_symbols=%d",
                        100 * _cov_by_sym.median(), 100 * _cov_by_sym.min(), len(_cov_by_sym),
                    )
                else:
                    cross_sectional_cache = global_rank_df[["symbol", "date"] + _rank_cols + ["global_rank_available"]].copy()
                LOGGER.info(
                    "run_training_batch stacking enabled: %d global_rank cols merged into cache rows=%d",
                    len(_rank_cols), len(cross_sectional_cache),
                )
                # Persister pour les workers multiprocessing
                _global_rank_path = Path(cfg.artifacts_dir) / "_global_rank_cache.parquet"
                _global_rank_path.parent.mkdir(parents=True, exist_ok=True)
                global_rank_df.to_parquet(_global_rank_path, index=False)
                LOGGER.info(
                    "run_training_batch global_rank persisted to %s rows=%d",
                    _global_rank_path, len(global_rank_df),
                )
        elif cfg.global_model.stacking_enabled:
            LOGGER.warning("run_training_batch stacking enabled but no global_rank_df produced")

    # ── Sauvegarder _per_symbol_features.json AVANT la boucle per-symbol ──
    # BLOQUANT et early : si l'écriture échoue (disque plein, permissions),
    # on arrête tout de suite plutôt qu'après des heures d'entraînement.
    # Ce fichier est la source de vérité pour la prédiction live/backtest.
    from modelFactory.features import get_feature_columns
    _ps_feature_columns = get_feature_columns(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_screener_scores=cfg.data.include_screener_scores,
        include_short_score=cfg.data.include_short_score_features,
        include_macro_vix=cfg.data.include_macro_vix_features,
        include_macro_vxn=cfg.data.include_macro_vxn_features,
        include_macro_vix3m=cfg.data.include_macro_vix3m_features,
        include_macro_move=cfg.data.include_macro_move_features,
        include_global_stacking=cfg.global_model.stacking_enabled,
        include_fundamentals=False,  # Fondamentaux réservés au Global Model, jamais en per-symbol
        include_factors=cfg.data.include_factors_features,
        include_macro_regime=cfg.data.include_macro_regime_features,
        include_score_components=False,  # P0-6 : composants score reservés per-sector + global
    )
    _ps_features = {
        "feature_columns": _ps_feature_columns,
        "feature_set": cfg.data.feature_set,
        "include_sentiment": cfg.data.include_sentiment_features,
        "include_screener_scores": cfg.data.include_screener_scores,
        "include_short_score": cfg.data.include_short_score_features,
        "include_macro_vix": cfg.data.include_macro_vix_features,
        "include_macro_vxn": cfg.data.include_macro_vxn_features,
        "include_macro_vix3m": cfg.data.include_macro_vix3m_features,
        "include_macro_move": cfg.data.include_macro_move_features,
        "include_fundamentals": False,  # Fondamentaux réservés au Global Model
        "include_factors": cfg.data.include_factors_features,
        "include_macro_regime": cfg.data.include_macro_regime_features,
        "include_score_components": False,  # P0-6 : réservé per-sector + global
        "enable_cross_sectional": cfg.data.enable_cross_sectional_features,
        "global_stacking_enabled": cfg.global_model.stacking_enabled,
    }
    _model_dir = Path(cfg.artifacts_dir)
    _model_dir.mkdir(parents=True, exist_ok=True)
    _model_dir.joinpath("_per_symbol_features.json").write_text(
        json.dumps(_ps_features, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    LOGGER.info(
        "run_training_batch _per_symbol_features.json saved: %d features, "
        "feature_set=%s, stacking=%s, cross_sectional=%s",
        len(_ps_feature_columns),
        cfg.data.feature_set,
        cfg.global_model.stacking_enabled,
        cfg.data.enable_cross_sectional_features,
    )

    # ── P0-6 (2026-08-07) : Global Model Only ──
    if cfg.data.global_model_only:
        LOGGER.info("🏁🏁🏁 orchestrator global_model_only — training Global Model standalone 🏁🏁🏁")
        if cfg.global_model.enabled and _global_symbols:
            update_runtime_status(current_phase="global_model_standalone", progress_item="__GLOBAL__")
            _gm_result = train_global_model(
                _global_symbols, cfg, artifacts_dir=Path(cfg.artifacts_dir), engine=engine,
            )
            LOGGER.info("global_model_standalone result: %s", _gm_result.get("status"))
            if _gm_result.get("status") == "completed":
                results.append(TrainResult("__GLOBAL__", batch_id, "completed", metrics=_gm_result))
                # ── Persist to DB so IHM diagnostics can see it ──
                _gm_run_id = f"{batch_id}__global__"
                try:
                    from modelFactory.db_registry import (
                        ensure_registry_entry, insert_metrics,
                        insert_training_run, replace_model_governance,
                        update_training_run,
                    )
                    _registry_id = ensure_registry_entry(engine, "__GLOBAL__")
                    insert_training_run(engine, _gm_run_id, _registry_id, "__GLOBAL__",
                                        status="completed", batch_id=batch_id)
                    update_training_run(engine, _gm_run_id, status="completed",
                                        finished_at=datetime.now(timezone.utc),
                                        config_path=str(Path(cfg.artifacts_dir) / "__GLOBAL__" / "config.json"))
                    _gm_val = _gm_result.get("val_metrics") or _gm_result.get("val") or {}
                    _gm_test = _gm_result.get("test_metrics") or _gm_result.get("test") or {}
                    if _gm_val:
                        insert_metrics(engine, _gm_run_id, "__GLOBAL__", "val", _gm_val, model_name="global_model")
                    if _gm_test:
                        insert_metrics(engine, _gm_run_id, "__GLOBAL__", "test", _gm_test, model_name="global_model")
                    replace_model_governance(
                        engine, run_id=_gm_run_id, symbol="__GLOBAL__",
                        challengers={"global_model": _gm_result},
                        artifact_routes_models={},
                        selected_model="global_model",
                        selection_mode="global_model_only",
                        selection_metric="directional_accuracy",
                        ranking=[],
                    )
                    LOGGER.info("global_model_only persisted to DB: run_id=%s", _gm_run_id)
                except Exception as _db_exc:
                    LOGGER.warning("global_model_only DB persist failed: %s", _db_exc)
        else:
            LOGGER.warning("global_model_only: enable_global_model=%s symbols=%d — nothing to train",
                           cfg.global_model.enabled, len(_global_symbols))
        return results

    # ── Per-Sector mode (Sprint 2026-08-03) ──
    if cfg.training_mode == "per_sector":
        from modelFactory.trainer_sector import run_per_sector_batch

        sector_results = run_per_sector_batch(
            symbols,
            engine,
            cfg,
            batch_id=batch_id,
        )
        # Convert sector results to TrainResult format for compatibility
        for sr in sector_results:
            results.append(TrainResult(
                sr.get("sector", "unknown"),
                batch_id or "N/A",
                sr.get("status", "failed"),
                skip_reason=sr.get("reason"),
            ))
        LOGGER.info("orchestrator per_sector done sectors=%d statuses=%s",
                     len(sector_results),
                     {r.get("sector"): r.get("status") for r in sector_results})
        LOGGER.info("🏁🏁🏁 orchestrator per_sector ALL DONE — moving to summary 🏁🏁🏁")
    else:
        # ── Per-Symbol mode (legacy) ──
        if effective_workers == 1:
            for index, sym in enumerate(symbols, start=1):
                try:
                    update_runtime_status(
                        current_phase="symbol_train_start",
                        current_symbol=sym,
                        current_symbol_index=index,
                        progress_item=sym,
                    )
                    if _needs_cross_sectional:
                        result = _train_worker(sym, cfg, symbols, cross_sectional_cache=cross_sectional_cache, fundamental_cache=fundamental_cache, batch_id=batch_id)
                    else:
                        result = _train_worker(sym, cfg, fundamental_cache=fundamental_cache, batch_id=batch_id)
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
                # Cross-sectional cache NOT passed to subprocess (pickling overhead).
                # Each worker falls back to symbol-by-symbol DB loading.
                # Same for fundamentals — workers load from DB independently.
                if _needs_cross_sectional:
                    futures = {pool.submit(_train_worker, sym, cfg, symbols, batch_id=batch_id): sym for sym in symbols}
                else:
                    futures = {pool.submit(_train_worker, sym, cfg, batch_id=batch_id): sym for sym in symbols}
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

    # ── Log IC Rank + Decile Spreads du Global Ranking Model ──
    if cfg.global_model.enabled and global_result_wf:
        _ic = global_result_wf.get("ic_rank_mean")
        _ds = global_result_wf.get("decile_spreads") or {}
        if _ic is not None:
            LOGGER.info(
                "run_training_batch global_ranking ic_rank_mean=%.4f ic_rank_std=%.4f decile_spreads=H3=%.4f H5=%.4f H10=%.4f",
                _ic, global_result_wf.get("ic_rank_std", float("nan")),
                float(_ds.get(3)) if _ds.get(3) is not None else float("nan"),
                float(_ds.get(5)) if _ds.get(5) is not None else float("nan"),
                float(_ds.get(10)) if _ds.get(10) is not None else float("nan"),
            )

    update_runtime_status(
        current_phase="batch_completed",
        progress_current=len(results),
        symbols_completed=completed,
        symbols_skipped=skipped,
        symbols_failed=failed,
        progress_item=None,
    )
    LOGGER.info("run_training_batch finished completed=%d skipped=%d failed=%d", completed, skipped, failed)

    # ── Persister les diagnostics batch pour le live/backtest ──
    if completed > 0:
        try:
            diag_count = persist_batch_diagnostics(engine, batch_id)
            LOGGER.info(
                "run_training_batch diagnostics persisted rows=%d batch_id=%s",
                diag_count, batch_id,
            )
        except Exception as exc:
            LOGGER.warning(
                "run_training_batch diagnostics persist failed batch_id=%s error=%s",
                batch_id, exc,
            )

    # ── Persister l'IC Rank + IC IR du Global Ranking Model ──
    if cfg.global_model.enabled and global_result_wf:
        _ic = global_result_wf.get("ic_rank_mean")
        _ic_std = global_result_wf.get("ic_rank_std")
        _ds = global_result_wf.get("decile_spreads") or {}
        if _ic is not None:
            try:
                update_training_batch(
                    engine, batch_id,
                    ic_rank=float(_ic),
                    ic_rank_std=float(_ic_std) if _ic_std is not None else None,
                    decile_spread_h3=float(_ds.get(3)) if _ds.get(3) is not None else None,
                    decile_spread_h5=float(_ds.get(5)) if _ds.get(5) is not None else None,
                    decile_spread_h10=float(_ds.get(10)) if _ds.get(10) is not None else None,
                )
                LOGGER.info(
                    "run_training_batch ic_rank+decile_spread persisted batch_id=%s ic_rank=%.4f ic_std=%.4f decile_h3=%.4f decile_h5=%.4f decile_h10=%.4f",
                    batch_id, float(_ic), float(_ic_std) if _ic_std is not None else float("nan"),
                    float(_ds.get(3)) if _ds.get(3) is not None else float("nan"),
                    float(_ds.get(5)) if _ds.get(5) is not None else float("nan"),
                    float(_ds.get(10)) if _ds.get(10) is not None else float("nan"),
                )
            except Exception as exc:
                LOGGER.warning(
                    "run_training_batch ic_rank persist failed batch_id=%s error=%s",
                    batch_id, exc,
                )

        # ── Persister les détails par horizon dans metadata_json (IHM/rapport) ──
        _features_path = Path(cfg.artifacts_dir) / "_global_ranking_features.json"
        if _features_path.exists():
            try:
                _gr_meta = json.loads(_features_path.read_text(encoding="utf-8"))
                _hd = _gr_meta.get("horizon_details")
                if _hd:
                    # Nettoyer les champs volumineux inutiles pour IHM/rapport
                    for _h_info in _hd.values():
                        if isinstance(_h_info, dict):
                            _h_info.pop("feature_importance_all", None)
                    _gr_details = {
                        "horizon_details": _hd,
                        "ic_by_horizon": _gr_meta.get("ic_by_horizon", {}),
                        "decile_spreads": _gr_meta.get("decile_spreads", {}),
                        "symbols_count": _gr_meta.get("symbols_count"),
                        "splits_count": _gr_meta.get("splits_count"),
                        "pred_rows": _gr_meta.get("pred_rows"),
                        "horizons": _gr_meta.get("horizons", []),
                    }
                    # Lire metadata_json existant
                    with engine.begin() as conn:
                        _row = conn.execute(
                            text("SELECT metadata_json FROM model_training_batch WHERE batch_id = :bid"),
                            {"bid": batch_id},
                        ).mappings().first()
                    _existing = {}
                    if _row and _row.get("metadata_json"):
                        try:
                            _existing = json.loads(str(_row["metadata_json"]))
                        except Exception:
                            pass
                    _existing["global_ranking"] = _gr_details
                    update_training_batch(engine, batch_id, metadata_json=json.dumps(_existing, ensure_ascii=False))
                    LOGGER.info("run_training_batch horizon_details persisted batch_id=%s horizons=%s",
                                batch_id, list(_hd.keys()))
            except Exception as exc:
                LOGGER.warning("run_training_batch horizon_details persist failed: %s", exc)

        # ── Per-Symbol IC retiré (métrique non pertinente, 2026-08-02) ──

    return results

