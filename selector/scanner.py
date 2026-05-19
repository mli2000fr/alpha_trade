"""Sprint S7 — `AlphaScanner` orchestrateur fin.

Phase 3.3.a (S6) avait extrait la logique pure dans
``selector.{factors,filters,ranking}``. Sprint S7 (A-015) finit le travail :

- Configuration → ``selector.config``
- I/O DB → ``selector.db_io``
- Helpers run-summary CLI → ``selector.run_summary``
- CLI standalone → ``selector.cli``

Cette classe se contente d'orchestrer le scan multi-thread et de
déléguer chaque méthode à un module spécialisé. Tous les noms publics
ET privés (``apply_filters``, ``_apply_filters_with_stats``,
``apply_sector_neutrality``, ``_winsorize_and_normalize``, …) sont
préservés pour la rétrocompatibilité (tests, ``backtesting/*``, IHM).
"""

from __future__ import annotations

import logging
import os
import threading
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import replace
from datetime import UTC, date, datetime

import pandas as pd
from sqlalchemy.engine import Engine

from core.run_summary import attach_live_progress
from database.connection import get_sqlalchemy_engine
from selector import db_io as _db_io
from selector.ablation import (
    RuntimeSelectorVariant,
    build_ablation_summary_and_artifact,
    resolve_runtime_variants,
    write_ablation_artifact,
)
from selector.config import AlphaScannerConfig
from selector.factors import compute_factor_frame, winsorize_and_normalize
from selector.filters import (
    apply_filters_with_stats,
    enrich_and_filter_equities,
    log_filter_stats,
    merge_optional_symbol_overlays,
)
from selector.ranking import (
    apply_factor_neutralization,
    apply_sector_neutrality,
    merge_scores,
    rank_and_select,
)
from selector.run_summary import _build_run_id, _summarize_zero_candidate_filters

LOGGER = logging.getLogger("selector.alpha_scanner")


class SelectorDataQualityError(RuntimeError):
    """Préflight bloquant : les sources externes requises pour les filtres actifs sont insuffisantes."""

    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__("AlphaScanner bloqué par le data quality gate.")
        self.payload = payload


class AlphaScanner:
    """Scanner multi-facteurs basé sur prix journaliers + table auxiliaire de scores.

    Sprint S7 — orchestrateur fin : I/O DB déléguée à ``selector.db_io`` ;
    logique pure à ``selector.{factors,filters,ranking}``.
    """

    def __init__(
        self,
        engine: Engine | None = None,
        config: AlphaScannerConfig | None = None,
    ) -> None:
        self.engine = engine or get_sqlalchemy_engine()
        self.config = config or AlphaScannerConfig.strict_swing_cash()
        self._stock_metadata_columns_cache: set[str] | None = None
        self._stock_quote_snapshots_columns_cache: set[str] | None = None
        self._aggregated_filter_stats: Counter[str] = Counter()
        self._filter_stats_lock = threading.Lock()
        self._last_data_quality_gate: dict[str, object] | None = None
        self._last_preselection_audit: dict[str, object] | None = None
        self._last_ablation_summary: dict[str, object] | None = None
        self.progress_callback = None

    # ------------------------------------------------------------------
    # Introspection schéma (cache local)
    # ------------------------------------------------------------------
    def get_aggregated_filter_stats(self) -> dict[str, int]:
        """Phase 3.3.b — snapshot agrégé (cross-chunks) des stats de filtrage."""
        with self._filter_stats_lock:
            return dict(self._aggregated_filter_stats)

    def get_last_data_quality_gate(self) -> dict[str, object] | None:
        return dict(self._last_data_quality_gate) if self._last_data_quality_gate else None

    def get_last_preselection_audit(self) -> dict[str, object] | None:
        return dict(self._last_preselection_audit) if self._last_preselection_audit else None

    def get_last_ablation_summary(self) -> dict[str, object] | None:
        return dict(self._last_ablation_summary) if self._last_ablation_summary else None

    def preflight_data_quality(self, *, reference_date: date | None = None) -> dict[str, object]:
        effective_reference_date = reference_date or getattr(self, "snapshot_date_override", None) or date.today()
        payload = _db_io.build_data_quality_gate(
            self.engine,
            self.config,
            reference_date=effective_reference_date,
        )
        self._last_data_quality_gate = payload
        return payload

    def _build_runtime_config_from_data_quality_gate(
        self,
        data_quality_gate: Mapping[str, object],
    ) -> AlphaScannerConfig:
        checks = data_quality_gate.get("checks")
        if not isinstance(checks, Mapping):
            return self.config
        overrides: dict[str, object] = {}
        skipped_filters: list[str] = []
        for payload in checks.values():
            if not isinstance(payload, Mapping) or payload.get("applied_filter_fallback") != "skip_filter":
                continue
            filter_key = str(payload.get("filter_key") or "").strip()
            if filter_key == "spread":
                overrides.update({
                    "max_spread_bps": None,
                    "max_spread_bps_iex": None,
                    "min_quote_size": None,
                })
            elif filter_key == "earnings_blackout":
                overrides["earnings_blackout_days"] = None
            elif filter_key == "market_cap_ttl":
                overrides["market_cap_max_age_days"] = None
            if filter_key:
                skipped_filters.append(filter_key)
        if not overrides:
            return self.config
        LOGGER.warning(
            "AlphaScanner poursuit avec fallback data-quality | skipped_filters=%s overrides=%s",
            skipped_filters,
            sorted(overrides),
        )
        return replace(self.config, **overrides)

    def _capture_preselection_audit(self) -> dict[str, object]:
        payload = _db_io.build_preselection_rejection_audit(
            self.engine,
            self.config,
            self._get_stock_metadata_columns(),
        )
        self._last_preselection_audit = payload
        return payload

    def _get_stock_metadata_columns(self) -> set[str]:
        if self._stock_metadata_columns_cache is None:
            self._stock_metadata_columns_cache = _db_io.get_stock_metadata_columns(self.engine)
        return set(self._stock_metadata_columns_cache or set())

    def _get_stock_quote_snapshots_columns(self) -> set[str]:
        if self._stock_quote_snapshots_columns_cache is None:
            self._stock_quote_snapshots_columns_cache = (
                _db_io.get_stock_quote_snapshots_columns(self.engine)
            )
        return set(self._stock_quote_snapshots_columns_cache or set())

    # ------------------------------------------------------------------
    # Lecture DB (délégation)
    # ------------------------------------------------------------------
    def fetch_market_data(self, symbols: Sequence[str]) -> pd.DataFrame:
        return _db_io.fetch_market_data(self.engine, self.config, symbols)

    def fetch_scores(self, symbols: Sequence[str]) -> pd.DataFrame:
        return _db_io.fetch_scores(self.engine, self.config, symbols)

    def fetch_instrument_metadata(self, symbols: Sequence[str]) -> pd.DataFrame:
        return _db_io.fetch_instrument_metadata(
            self.engine, self._get_stock_metadata_columns(), symbols
        )

    def _load_benchmark_returns(self, start_date: date, end_date: date) -> pd.DataFrame:
        return _db_io.load_benchmark_returns(self.engine, self.config, start_date, end_date)

    def fetch_quote_snapshots(
        self, symbols: Sequence[str], *, reference_date: date | None = None
    ) -> pd.DataFrame:
        return _db_io.fetch_quote_snapshots(
            self.engine,
            self._get_stock_quote_snapshots_columns(),
            symbols,
            reference_date=reference_date,
        )

    def fetch_next_earnings(
        self, symbols: Sequence[str], *, reference_date: date | None = None
    ) -> pd.DataFrame:
        return _db_io.fetch_next_earnings(
            self.engine, self.config, symbols, reference_date=reference_date
        )

    # ------------------------------------------------------------------
    # Calcul (délégation pure)
    # ------------------------------------------------------------------
    def compute_factors(self, market_data: pd.DataFrame) -> pd.DataFrame:
        if market_data.empty:
            from selector.factors import FACTOR_COLUMNS  # local import to keep top minimal
            return pd.DataFrame(columns=FACTOR_COLUMNS)
        dates = pd.to_datetime(market_data["date"], utc=False)
        benchmark_returns = self._load_benchmark_returns(
            start_date=dates.min().date(),
            end_date=dates.max().date(),
        )
        return compute_factor_frame(market_data, benchmark_returns, self.config)

    def merge_scores(self, computed_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame:
        return merge_scores(computed_df, scores_df, self.config)

    def _apply_factor_neutralization(self, df: pd.DataFrame) -> pd.DataFrame:
        return apply_factor_neutralization(df, self.config)

    def _apply_filters_with_stats(self, merged_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
        return apply_filters_with_stats(merged_df, self.config)

    def apply_filters(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        filtered, stats = self._apply_filters_with_stats(merged_df)
        self._log_filter_stats(stats)
        return filtered

    def _log_filter_stats(self, stats: dict[str, int]) -> None:
        log_filter_stats(stats)

    def apply_sector_neutrality(self, ranked_df: pd.DataFrame) -> pd.DataFrame:
        return apply_sector_neutrality(ranked_df, self.config)

    def rank_and_select(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        return rank_and_select(merged_df, self.config)

    def _enrich_and_filter_equities(
        self, merged_df: pd.DataFrame, metadata_df: pd.DataFrame
    ) -> pd.DataFrame:
        return enrich_and_filter_equities(merged_df, metadata_df)

    def _merge_optional_symbol_overlays(
        self,
        merged_df: pd.DataFrame,
        quotes_df: pd.DataFrame,
        earnings_df: pd.DataFrame,
    ) -> pd.DataFrame:
        return merge_optional_symbol_overlays(merged_df, quotes_df, earnings_df)

    # ------------------------------------------------------------------
    # Persistance DB (délégation)
    # ------------------------------------------------------------------
    def update_database(
        self, selected_df: pd.DataFrame, scored_df: pd.DataFrame | None = None
    ) -> int:
        return _db_io.update_database(
            self.engine,
            self.config,
            selected_df,
            scored_df,
            progress=self._progress_emitter(),
            snapshot_date_override=getattr(self, "snapshot_date_override", None),
        )

    def _reset_selector_outputs(self) -> None:
        with self._filter_stats_lock:
            self._aggregated_filter_stats.clear()
        _db_io.reset_selector_outputs(self.engine, self.config)

    def _prepare_scores_snapshot(self, scored_df: pd.DataFrame | None) -> list[dict[str, object]]:
        return _db_io.prepare_scores_snapshot(scored_df)

    def _iter_eligible_symbol_chunks(self):
        return _db_io.iter_eligible_symbol_chunks(
            self.engine, self.config, self._get_stock_metadata_columns()
        )

    def _scan_primary_candidates(self) -> tuple[pd.DataFrame, dict[str, int]]:
        all_frames: list[pd.DataFrame] = []
        workers = self._resolve_worker_count()
        max_in_flight = max(2, workers * 2)
        pending: set[Future[pd.DataFrame]] = set()
        submitted_chunks = 0
        completed_chunks = 0
        symbol_chunks = list(self._iter_eligible_symbol_chunks())
        eligible_symbols = sum(len(chunk) for chunk in symbol_chunks)
        total_chunks = len(symbol_chunks)

        def _scan_progress() -> None:
            self._emit_live_progress(
                current=completed_chunks,
                total=total_chunks,
                label="🎯 Progression Alpha Scanner — scan multi-facteurs",
                phase="scan_chunks",
                extra_summary={
                    "eligible_symbols": eligible_symbols,
                    "chunks_submitted": submitted_chunks,
                    "chunks_completed": completed_chunks,
                    "chunks_total": total_chunks,
                    "selected_candidates": sum(len(frame) for frame in all_frames),
                },
            )

        _scan_progress()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for symbols in symbol_chunks:
                while len(pending) >= max_in_flight:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    completed_chunks += self._collect_completed(done, all_frames)
                    _scan_progress()
                    LOGGER.info(
                        "Progression scan | chunks_termines=%s chunks_soumis=%s en_vol=%s candidats_cumules=%s",
                        completed_chunks,
                        submitted_chunks,
                        len(pending),
                        sum(len(frame) for frame in all_frames),
                    )
                pending.add(executor.submit(self._process_chunk, symbols))
                submitted_chunks += 1
                _scan_progress()
                LOGGER.info(
                    "Chunk soumis | index=%s taille=%s en_vol=%s",
                    submitted_chunks,
                    len(symbols),
                    len(pending),
                )

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                completed_chunks += self._collect_completed(done, all_frames)
                _scan_progress()
                LOGGER.info(
                    "Progression scan | chunks_termines=%s chunks_soumis=%s en_vol=%s candidats_cumules=%s",
                    completed_chunks,
                    submitted_chunks,
                    len(pending),
                    sum(len(frame) for frame in all_frames),
                )

        merged_candidates = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
        LOGGER.info("Agregation terminee | lignes_candidates=%s", len(merged_candidates))
        return merged_candidates, {
            "eligible_symbols": eligible_symbols,
            "chunks_submitted": submitted_chunks,
            "chunks_completed": completed_chunks,
            "chunks_total": total_chunks,
        }

    def _process_chunk_variants(
        self,
        symbols: Sequence[str],
        runtime_variants: Sequence[RuntimeSelectorVariant],
        as_of_date: date | None = None,
    ) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]]]:
        try:
            LOGGER.debug("Debut chunk ablation | symboles=%s variantes=%s", len(symbols), len(runtime_variants))
            needs_quotes = any(variant.config.max_spread_bps is not None for variant in runtime_variants)
            needs_earnings = any(
                variant.config.earnings_blackout_days is not None for variant in runtime_variants
            )
            market_data = self.fetch_market_data(symbols)
            computed = self.compute_factors(market_data)
            scores = self.fetch_scores(symbols)
            metadata_df = self.fetch_instrument_metadata(symbols)
            quotes_df = (
                self.fetch_quote_snapshots(symbols, reference_date=as_of_date)
                if needs_quotes
                else pd.DataFrame()
            )
            earnings_df = (
                self.fetch_next_earnings(symbols, reference_date=as_of_date)
                if needs_earnings
                else pd.DataFrame()
            )
            merged = self.merge_scores(computed, scores)
            merged = self._enrich_and_filter_equities(merged, metadata_df)
            merged = self._merge_optional_symbol_overlays(merged, quotes_df, earnings_df)
            frames_by_variant: dict[str, pd.DataFrame] = {}
            stats_by_variant: dict[str, dict[str, int]] = {}
            for variant in runtime_variants:
                filtered, chunk_stats = apply_filters_with_stats(merged, variant.config)
                LOGGER.debug(
                    "Chunk ablation variante | variant=%s fusion=%s filtre=%s disabled_filters=%s skipped_filters=%s",
                    variant.variant_id,
                    len(merged),
                    len(filtered),
                    list(variant.disabled_filters),
                    list(variant.skipped_filters),
                )
                frames_by_variant[variant.variant_id] = filtered
                stats_by_variant[variant.variant_id] = chunk_stats
            return frames_by_variant, stats_by_variant
        except Exception:
            LOGGER.exception("Chunk ablation en echec | symboles=%s", len(symbols))
            return ({variant.variant_id: pd.DataFrame() for variant in runtime_variants}, {})

    def _collect_completed_variant_results(
        self,
        done: set[Future[tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]]]]],
        all_frames_by_variant: dict[str, list[pd.DataFrame]],
        aggregated_stats_by_variant: dict[str, Counter[str]],
    ) -> int:
        completed = 0
        for future in done:
            frames_by_variant, stats_by_variant = future.result()
            completed += 1
            for variant_id, frame in frames_by_variant.items():
                if not frame.empty:
                    all_frames_by_variant.setdefault(variant_id, []).append(frame)
            for variant_id, stats in stats_by_variant.items():
                counter = aggregated_stats_by_variant.setdefault(variant_id, Counter())
                for key, value in stats.items():
                    counter[key] += int(value)
        return completed

    def _scan_ablation_candidates(
        self,
        runtime_variants: Sequence[RuntimeSelectorVariant],
    ) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]], dict[str, int]]:
        all_frames_by_variant = {variant.variant_id: [] for variant in runtime_variants}
        aggregated_stats_by_variant: dict[str, Counter[str]] = {
            variant.variant_id: Counter() for variant in runtime_variants
        }
        workers = self._resolve_worker_count()
        max_in_flight = max(2, workers * 2)
        pending: set[Future[tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]]]]] = set()
        submitted_chunks = 0
        completed_chunks = 0
        symbol_chunks = list(self._iter_eligible_symbol_chunks())
        eligible_symbols = sum(len(chunk) for chunk in symbol_chunks)
        total_chunks = len(symbol_chunks)

        def _scan_progress() -> None:
            primary_frames = all_frames_by_variant.get("primary", [])
            self._emit_live_progress(
                current=completed_chunks,
                total=total_chunks,
                label="🎯 Progression Alpha Scanner — scan multi-facteurs",
                phase="scan_chunks",
                extra_summary={
                    "eligible_symbols": eligible_symbols,
                    "chunks_submitted": submitted_chunks,
                    "chunks_completed": completed_chunks,
                    "chunks_total": total_chunks,
                    "selected_candidates": sum(len(frame) for frame in primary_frames),
                    "ablation_variants": len(runtime_variants) - 1,
                },
            )

        _scan_progress()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for symbols in symbol_chunks:
                while len(pending) >= max_in_flight:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    completed_chunks += self._collect_completed_variant_results(
                        done,
                        all_frames_by_variant,
                        aggregated_stats_by_variant,
                    )
                    _scan_progress()
                pending.add(executor.submit(self._process_chunk_variants, symbols, tuple(runtime_variants)))
                submitted_chunks += 1
                _scan_progress()

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                completed_chunks += self._collect_completed_variant_results(
                    done,
                    all_frames_by_variant,
                    aggregated_stats_by_variant,
                )
                _scan_progress()

        merged_candidates_by_variant = {
            variant_id: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            for variant_id, frames in all_frames_by_variant.items()
        }
        stats_by_variant = {
            variant_id: dict(counter)
            for variant_id, counter in aggregated_stats_by_variant.items()
        }
        return merged_candidates_by_variant, stats_by_variant, {
            "eligible_symbols": eligible_symbols,
            "chunks_submitted": submitted_chunks,
            "chunks_completed": completed_chunks,
            "chunks_total": total_chunks,
        }

    # ------------------------------------------------------------------
    # Orchestration multi-thread
    # ------------------------------------------------------------------
    def run(self) -> pd.DataFrame:
        """Exécute le scan complet et retourne le Top N final."""
        started_at = datetime.now(UTC)
        LOGGER.info(
            "Demarrage AlphaScanner | table_prix=%s table_scores=%s chunk_size=%s selection=%s workers=%s",
            self.config.price_table,
            self.config.score_table,
            self.config.chunk_size,
            self.config.selection_size,
            self._resolve_worker_count(),
        )

        data_quality_gate = self.preflight_data_quality()
        self._last_preselection_audit = None
        self._last_ablation_summary = None
        if data_quality_gate.get("status") == "blocked":
            LOGGER.error(
                "AlphaScanner bloque par le data quality gate | reference_date=%s blocking_checks=%s",
                data_quality_gate.get("reference_date"),
                data_quality_gate.get("blocking_checks", []),
            )
            raise SelectorDataQualityError(data_quality_gate)

        runtime_config = self._build_runtime_config_from_data_quality_gate(data_quality_gate)
        self._capture_preselection_audit()
        runtime_variants = resolve_runtime_variants(
            base_config=self.config,
            primary_runtime_config=runtime_config,
            data_quality_gate=data_quality_gate,
        )

        original_config = self.config
        self.config = runtime_config
        try:
            self._reset_selector_outputs()

            if len(runtime_variants) == 1:
                merged_candidates, scan_meta = self._scan_primary_candidates()
                merged_candidates = self._apply_factor_neutralization(merged_candidates)
                selected = self.rank_and_select(merged_candidates)
                scored_for_persistence = merged_candidates.copy()
            else:
                merged_candidates_by_variant, stats_by_variant, scan_meta = self._scan_ablation_candidates(runtime_variants)
                primary_variant = runtime_variants[0]
                primary_stats = stats_by_variant.get(primary_variant.variant_id, {})
                with self._filter_stats_lock:
                    self._aggregated_filter_stats.clear()
                    for key, value in primary_stats.items():
                        self._aggregated_filter_stats[key] += int(value)
                scored_candidates_by_variant: dict[str, pd.DataFrame] = {}
                selected_by_variant: dict[str, pd.DataFrame] = {}
                for variant in runtime_variants:
                    merged_variant = merged_candidates_by_variant.get(variant.variant_id, pd.DataFrame())
                    scored_variant = apply_factor_neutralization(merged_variant, variant.config)
                    selected_variant = rank_and_select(scored_variant, variant.config)
                    scored_candidates_by_variant[variant.variant_id] = scored_variant
                    selected_by_variant[variant.variant_id] = selected_variant
                    LOGGER.info(
                        "Ablation selector | variant=%s selected=%s disabled_filters=%s skipped_filters=%s",
                        variant.variant_id,
                        len(selected_variant),
                        list(variant.disabled_filters),
                        list(variant.skipped_filters),
                    )
                selected = selected_by_variant.get(primary_variant.variant_id, pd.DataFrame())
                scored_for_persistence = scored_candidates_by_variant.get(primary_variant.variant_id, pd.DataFrame()).copy()
                plan = getattr(self.config, "ablation_plan", None)
                if plan is not None:
                    artifact_stem = _build_run_id("alpha-scanner-ablation")
                    summary_payload, artifact_payload = build_ablation_summary_and_artifact(
                        plan=plan,
                        runtime_variants=tuple(runtime_variants),
                        selected_by_variant=selected_by_variant,
                        rejected_by_filter_by_variant=stats_by_variant,
                        artifact_path=None,
                    )
                    artifact_path = write_ablation_artifact(
                        plan=plan,
                        artifact_payload=artifact_payload,
                        artifact_stem=artifact_stem,
                    )
                    summary_payload["artifact_path"] = artifact_path
                    self._last_ablation_summary = summary_payload

            if not scored_for_persistence.empty:
                if not selected.empty and {"symbol", "rank"}.issubset(selected.columns):
                    candidate_rank_map = selected.set_index("symbol")["rank"]
                    scored_for_persistence["candidate_rank"] = scored_for_persistence["symbol"].map(candidate_rank_map)
                elif "candidate_rank" not in scored_for_persistence.columns:
                    scored_for_persistence["candidate_rank"] = pd.NA

            self._emit_live_progress(
                current=scan_meta["chunks_total"],
                total=scan_meta["chunks_total"],
                label="🎯 Progression Alpha Scanner — sélection finale",
                phase="rank_select",
                extra_summary={
                    "eligible_symbols": scan_meta["eligible_symbols"],
                    "chunks_submitted": scan_meta["chunks_submitted"],
                    "chunks_completed": scan_meta["chunks_completed"],
                    "chunks_total": scan_meta["chunks_total"],
                    "selected_candidates": int(len(selected)),
                    "ablation_variants": len(runtime_variants) - 1,
                },
            )

            self.update_database(selected, scored_for_persistence)

            elapsed = (datetime.now(UTC) - started_at).total_seconds()

            if selected.empty:
                zero_candidate_diagnostic = _summarize_zero_candidate_filters(
                    self.get_aggregated_filter_stats()
                )
                LOGGER.critical(
                    "AlphaScanner a produit 0 candidats | duree=%.2fs | "
                    "Verifier : stock_bars_daily peuplee ? liquidity_threshold trop eleve ? "
                    "Marche en tendance baissiere (trend_score=0 pour tous) ? | %s",
                    elapsed,
                    zero_candidate_diagnostic,
                )
            else:
                LOGGER.info("AlphaScanner termine en %.2fs | candidats=%s", elapsed, len(selected))

            return selected
        finally:
            self.config = original_config

    def _process_chunk(self, symbols: Sequence[str], as_of_date: date | None = None) -> pd.DataFrame:
        try:
            LOGGER.debug("Debut chunk | symboles=%s", len(symbols))
            market_data = self.fetch_market_data(symbols)
            computed = self.compute_factors(market_data)
            scores = self.fetch_scores(symbols)
            metadata_df = self.fetch_instrument_metadata(symbols)
            quotes_df = (
                self.fetch_quote_snapshots(symbols, reference_date=as_of_date)
                if self.config.max_spread_bps is not None
                else pd.DataFrame()
            )
            earnings_df = (
                self.fetch_next_earnings(symbols, reference_date=as_of_date)
                if self.config.earnings_blackout_days is not None
                else pd.DataFrame()
            )
            merged = self.merge_scores(computed, scores)
            merged = self._enrich_and_filter_equities(merged, metadata_df)
            merged = self._merge_optional_symbol_overlays(merged, quotes_df, earnings_df)
            filtered, chunk_stats = self._apply_filters_with_stats(merged)
            self._log_filter_stats(chunk_stats)
            with self._filter_stats_lock:
                for key, value in chunk_stats.items():
                    self._aggregated_filter_stats[key] += int(value)
            LOGGER.debug(
                "Fin chunk | symboles=%s lignes_market=%s facteurs=%s scores=%s metadata=%s quotes=%s earnings=%s fusion=%s filtre=%s",
                len(symbols),
                len(market_data),
                len(computed),
                len(scores),
                len(metadata_df),
                len(quotes_df),
                len(earnings_df),
                len(merged),
                len(filtered),
            )
            return filtered
        except Exception:
            LOGGER.exception("Chunk en echec | symboles=%s", len(symbols))
            return pd.DataFrame()

    def _collect_completed(
        self, done: set[Future[pd.DataFrame]], all_frames: list[pd.DataFrame]
    ) -> int:
        completed = 0
        for future in done:
            frame = future.result()
            completed += 1
            if not frame.empty:
                all_frames.append(frame)
        return completed

    def _resolve_worker_count(self) -> int:
        if self.config.max_workers is not None:
            return self.config.max_workers
        return min(8, os.cpu_count() or 1)

    def _emit_live_progress(
        self,
        *,
        current: int,
        total: int,
        label: str,
        phase: str,
        extra_summary: dict[str, object] | None = None,
    ) -> None:
        callback = getattr(self, "progress_callback", None)
        if not callable(callback):
            return
        callback(
            attach_live_progress(
                extra_summary or {},
                current=current,
                total=total,
                label=label,
                phase=phase,
                unit="chunks"
                if phase == "scan_chunks"
                else "batches"
                if phase == "persist_db"
                else "étapes",
            )
        )

    def _progress_emitter(self):
        """Adaptateur pour ``selector.db_io.update_database``."""

        def _emit(**kwargs):
            self._emit_live_progress(**kwargs)

        return _emit

    # ------------------------------------------------------------------
    # Helpers de rétrocompatibilité (statiques)
    # ------------------------------------------------------------------
    @staticmethod
    def _winsorize_and_normalize(
        series: pd.Series | None,
        lower_pct: float = 0.01,
        upper_pct: float = 0.99,
    ) -> pd.Series:
        return winsorize_and_normalize(series, lower_pct=lower_pct, upper_pct=upper_pct)

    @staticmethod
    def _normalize_zero_one(series: pd.Series | None) -> pd.Series:
        return winsorize_and_normalize(series)


__all__ = ["AlphaScanner", "SelectorDataQualityError"]

