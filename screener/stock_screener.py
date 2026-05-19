import argparse
import json
import logging
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import date, datetime, timezone
from typing import Callable, List, Optional
from uuid import uuid4

import pandas as pd

from common.utils import configure_root_logging
from core.run_summary import attach_live_progress, attach_schema_version
from screener.db_io import (
    get_engine,
    iter_symbol_chunks,
    load_historical_range_stats_for_symbols,
    load_prices_for_chunk,
    load_recent_prices_for_chunk,
    load_spy_return_6m,
    upsert_scores_snapshot,
)
from screener.models import ScreenerChunkMetrics, ScreenerConfig, ScreenerRunReport
from screener import RESULT_COLUMNS, compute_scores_from_prices
from screener.pipeline import finalize_scores_with_historical_range, screen_recent_prices

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
APPROX_TRADING_DAYS_PER_YEAR = 252
CHUNK_FAILURE_RATIO_WARNING_THRESHOLD = 0.05
CHUNK_ERROR_SAMPLE_LIMIT = 5
CHUNK_SYMBOL_SAMPLE_LIMIT = 3


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f'{prefix}-{_utc_now_naive().strftime("%Y%m%d%H%M%S")}-{uuid4().hex[:6]}'


def _emit_run_summary(summary: dict[str, object]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _emit_live_progress(
    progress_callback: Callable[[dict[str, object]], None] | None,
    summary: dict[str, object],
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        attach_live_progress(
            summary,
            current=int(summary.get("chunks_completed") or 0),
            total=int(summary.get("chunks_total") or 0),
            label="🔎 Progression stock screener",
            phase="scan_chunks",
            unit="chunks",
        )
    )


def _estimate_full_history_rows(symbol_count: int, config: ScreenerConfig) -> int:
    history_rows_per_symbol = max(config.min_history_days, config.lookback_history_years * APPROX_TRADING_DAYS_PER_YEAR)
    return symbol_count * history_rows_per_symbol


def _process_chunk_two_passes(
    symbols: List[str],
    config_dict: dict,
    spy_return_6m: float,
    as_of_date_iso: Optional[str],
) -> tuple[pd.DataFrame, ScreenerChunkMetrics]:
    """Exécute un chunk du screener dans un subprocess avec chargement en 2 passes."""
    started = time.perf_counter()
    config = ScreenerConfig.from_dict(config_dict)
    engine = get_engine()
    as_of = date.fromisoformat(as_of_date_iso) if as_of_date_iso else None

    try:
        if not config.enable_two_pass_loading:
            chunk_prices = load_prices_for_chunk(engine, symbols, config, as_of_date=as_of)
            scores = compute_scores_from_prices(chunk_prices, spy_return_6m, config, as_of_date=as_of)
            metrics = ScreenerChunkMetrics(
                input_symbols=len(symbols),
                recent_rows_loaded=len(chunk_prices),
                symbols_final=len(scores),
                duration_seconds=round(time.perf_counter() - started, 4),
            )
            return scores, metrics

        pass1_started = time.perf_counter()
        recent_prices = load_recent_prices_for_chunk(engine, symbols, config, as_of_date=as_of)
        candidates, stage_counts = screen_recent_prices(
            recent_prices,
            spy_return_6m=spy_return_6m,
            config=config,
            as_of_date=as_of,
        )
        pass1_seconds = round(time.perf_counter() - pass1_started, 4)

        if candidates.empty:
            metrics = ScreenerChunkMetrics(
                input_symbols=len(symbols),
                recent_rows_loaded=len(recent_prices),
                symbols_pass_history=stage_counts["symbols_pass_history"],
                symbols_pass_liquidity=stage_counts["symbols_pass_liquidity"],
                symbols_pass_relative_strength=stage_counts["symbols_pass_relative_strength"],
                pass1_seconds=pass1_seconds,
                duration_seconds=round(time.perf_counter() - started, 4),
            )
            return pd.DataFrame(columns=RESULT_COLUMNS), metrics

        pass2_started = time.perf_counter()
        historical_range_df = load_historical_range_stats_for_symbols(
            engine,
            candidates["symbol"].astype(str).tolist(),
            config,
            as_of_date=as_of,
        )
        scores = finalize_scores_with_historical_range(candidates, historical_range_df, config)
        pass2_seconds = round(time.perf_counter() - pass2_started, 4)
        rows_avoided_estimate = max(
            _estimate_full_history_rows(stage_counts["symbols_pass_relative_strength"], config) - len(historical_range_df),
            0,
        )
        metrics = ScreenerChunkMetrics(
            input_symbols=len(symbols),
            recent_rows_loaded=len(recent_prices),
            range_rows_loaded=len(historical_range_df),
            symbols_pass_history=stage_counts["symbols_pass_history"],
            symbols_pass_liquidity=stage_counts["symbols_pass_liquidity"],
            symbols_pass_relative_strength=stage_counts["symbols_pass_relative_strength"],
            symbols_final=len(scores),
            rows_avoided_estimate=rows_avoided_estimate,
            pass1_seconds=pass1_seconds,
            pass2_seconds=pass2_seconds,
            duration_seconds=round(time.perf_counter() - started, 4),
        )
        return scores, metrics
    except Exception as exc:
        LOGGER.exception("Chunk screener en echec | symboles=%s", len(symbols))
        return pd.DataFrame(columns=RESULT_COLUMNS), ScreenerChunkMetrics(
            input_symbols=len(symbols),
            failed=True,
            error_message=str(exc),
            duration_seconds=round(time.perf_counter() - started, 4),
        )


def _process_chunk(
    symbols: List[str],
    config_dict: dict,
    spy_return_6m: float,
    as_of_date_iso: Optional[str],
) -> pd.DataFrame:
    """Compatibilité backfill PIT: retourne seulement le DataFrame de scores."""
    scores, _ = _process_chunk_two_passes(symbols, config_dict, spy_return_6m, as_of_date_iso)
    return scores


def _resolve_worker_count(max_workers: Optional[int]) -> int:
    available_workers = os.cpu_count() or 1
    if max_workers is None:
        return available_workers
    if max_workers < 1:
        raise ValueError("max_workers doit être supérieur ou égal à 1.")
    return max_workers


def _empty_scores() -> pd.DataFrame:
    return pd.DataFrame(columns=RESULT_COLUMNS)


def _merge_run_metrics(summary: dict[str, object], chunk_metrics: ScreenerChunkMetrics) -> None:
    summary["chunks_completed"] = int(summary["chunks_completed"]) + 1
    summary["chunk_failures"] = int(summary["chunk_failures"]) + int(chunk_metrics.failed)
    summary["recent_rows_loaded"] = int(summary["recent_rows_loaded"]) + int(chunk_metrics.recent_rows_loaded)
    summary["range_rows_loaded"] = int(summary["range_rows_loaded"]) + int(chunk_metrics.range_rows_loaded)
    summary["symbols_pass_history"] = int(summary["symbols_pass_history"]) + int(chunk_metrics.symbols_pass_history)
    summary["symbols_pass_liquidity"] = int(summary["symbols_pass_liquidity"]) + int(chunk_metrics.symbols_pass_liquidity)
    summary["symbols_pass_relative_strength"] = int(summary["symbols_pass_relative_strength"]) + int(chunk_metrics.symbols_pass_relative_strength)
    summary["rows_avoided_estimate"] = int(summary["rows_avoided_estimate"]) + int(chunk_metrics.rows_avoided_estimate)
    summary["pass1_seconds"] = round(float(summary["pass1_seconds"]) + float(chunk_metrics.pass1_seconds), 4)
    summary["pass2_seconds"] = round(float(summary["pass2_seconds"]) + float(chunk_metrics.pass2_seconds), 4)


def _record_chunk_error_sample(
    summary: dict[str, object],
    chunk_metrics: ScreenerChunkMetrics,
    chunk_symbols: List[str],
) -> None:
    if not chunk_metrics.failed or not chunk_metrics.error_message:
        return
    error_samples = summary.setdefault("chunk_error_samples", [])
    if not isinstance(error_samples, list):
        return
    if len(error_samples) >= CHUNK_ERROR_SAMPLE_LIMIT:
        return
    error_samples.append(
        {
            "input_symbols": int(chunk_metrics.input_symbols),
            "sample_symbols": [str(symbol) for symbol in chunk_symbols[:CHUNK_SYMBOL_SAMPLE_LIMIT]],
            "error_message": str(chunk_metrics.error_message),
        }
    )


def _append_completed_results(done, all_results: List[pd.DataFrame], summary: dict[str, object], pending: dict) -> None:
    for future in done:
        chunk_symbols = list(pending.pop(future, []))
        chunk_result, chunk_metrics = future.result()
        _merge_run_metrics(summary, chunk_metrics)
        _record_chunk_error_sample(summary, chunk_metrics, chunk_symbols)
        if not chunk_result.empty:
            all_results.append(chunk_result)


def _build_run_report(summary: dict[str, object]) -> ScreenerRunReport:
    return ScreenerRunReport(**summary)


def _log_run_report(report: ScreenerRunReport) -> None:
    LOGGER.info("Resume screener | %s", report.to_summary_dict())


def run_screener_with_report(
    config: ScreenerConfig,
    max_workers: Optional[int] = None,
    as_of_date: Optional[date] = None,
    snapshot_date: Optional[date] = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> tuple[pd.DataFrame, ScreenerRunReport]:
    """Exécute le screener et retourne les scores ainsi qu'un rapport détaillé.

    :param snapshot_date: Date logique d'archivage dans ``stock_scores_history``.
        Si None, défaut ``date.today()``. À spécifier quand le workflow IHM a figé
        un ``trade_date`` partagé pour garantir la cohérence multi-étapes.

    Politique P0 de persistance : seul un run complet et non vide peut remplacer
    ``stock_scores`` et archiver ``stock_scores_history``. Un run vide ou partiel
    préserve explicitement le snapshot précédent.
    """
    started_at = _utc_now_naive()
    start_perf = time.perf_counter()
    engine = get_engine()
    workers = _resolve_worker_count(max_workers)
    as_of_iso = as_of_date.isoformat() if as_of_date else None
    summary: dict[str, object] = {
        "run_id": _build_run_id("stock-screener"),
        "benchmark_symbol": config.benchmark_symbol,
        "chunk_size": config.chunk_size,
        "workers": workers,
        "as_of_date": as_of_iso,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": None,
        "duration_seconds": 0.0,
        "targeted_symbols": 0,
        "chunks_total": 0,
        "chunks_completed": 0,
        "chunk_failures": 0,
        "recent_rows_loaded": 0,
        "range_rows_loaded": 0,
        "symbols_pass_history": 0,
        "symbols_pass_liquidity": 0,
        "symbols_pass_relative_strength": 0,
        "symbols_final": 0,
        "rows_avoided_estimate": 0,
        "benchmark_load_seconds": 0.0,
        "pass1_seconds": 0.0,
        "pass2_seconds": 0.0,
        "upsert_seconds": 0.0,
        "persistence_status": "pending",
        "persisted_rows": 0,
        "purge_performed": False,
        "archive_performed": False,
        "chunk_error_samples": [],
    }

    benchmark_started = time.perf_counter()
    spy_return_6m = load_spy_return_6m(engine, config, as_of_date=as_of_date)
    summary["benchmark_load_seconds"] = round(time.perf_counter() - benchmark_started, 4)

    max_in_flight = max(2, workers * 2)
    config_dict = config.to_dict()
    all_results: List[pd.DataFrame] = []
    pending: dict[object, List[str]] = {}

    LOGGER.info(
        "Demarrage screener | benchmark=%s chunk_size=%s workers=%s as_of=%s two_pass=%s first_pass_window_days=%s effective_first_pass_window_days=%s",
        config.benchmark_symbol,
        config.chunk_size,
        workers,
        as_of_iso or "live",
        config.enable_two_pass_loading,
        config.first_pass_window_days,
        config.effective_first_pass_window_days,
    )

    symbol_chunks = list(iter_symbol_chunks(engine, config.chunk_size))
    summary["chunks_total"] = len(symbol_chunks)
    summary["targeted_symbols"] = sum(len(symbol_chunk) for symbol_chunk in symbol_chunks)
    _emit_live_progress(progress_callback, summary)

    with ProcessPoolExecutor(max_workers=workers) as executor:
        for symbol_chunk in symbol_chunks:
            while len(pending) >= max_in_flight:
                done, _ = wait(set(pending), return_when=FIRST_COMPLETED)
                _append_completed_results(done, all_results, summary, pending)
                _emit_live_progress(progress_callback, summary)

            future = executor.submit(_process_chunk_two_passes, symbol_chunk, config_dict, spy_return_6m, as_of_iso)
            pending[future] = list(symbol_chunk)

        while pending:
            done, _ = wait(set(pending), return_when=FIRST_COMPLETED)
            _append_completed_results(done, all_results, summary, pending)
            _emit_live_progress(progress_callback, summary)

    if all_results:
        final_scores = pd.concat(all_results, ignore_index=True)
        final_scores = (
            final_scores.sort_values("total_score", ascending=False)
            .drop_duplicates("symbol")
            .reset_index(drop=True)
        )
    else:
        final_scores = _empty_scores()

    summary["symbols_final"] = len(final_scores)

    # Politique P0 : ne jamais détruire ni tronquer ``stock_scores`` sur un run
    # vide ou partiel. Le snapshot précédent reste la source de vérité tant que
    # le run courant n'est pas complet et non vide.
    if final_scores.empty:
        summary["persistence_status"] = "preserved_previous_scores_empty_run"
        LOGGER.error(
            "Persistance screener ignoree : run vide, snapshot precedent preserve | as_of=%s targeted_symbols=%s chunk_failures=%s",
            as_of_iso or "live",
            summary["targeted_symbols"],
            summary["chunk_failures"],
        )
    elif int(summary["chunk_failures"]) > 0:
        summary["persistence_status"] = "preserved_previous_scores_partial_run"
        LOGGER.error(
            "Persistance screener ignoree : run partiel, snapshot precedent preserve | as_of=%s chunk_failures=%s chunks_completed=%s/%s symbols_final=%s",
            as_of_iso or "live",
            summary["chunk_failures"],
            summary["chunks_completed"],
            summary["chunks_total"],
            len(final_scores),
        )
    else:
        upsert_started = time.perf_counter()
        upsert_scores_snapshot(engine, final_scores, chunksize=1000, snapshot_date=snapshot_date)
        summary["upsert_seconds"] = round(time.perf_counter() - upsert_started, 4)
        summary["persistence_status"] = "replaced_scores_full_run"
        summary["persisted_rows"] = len(final_scores)
        summary["purge_performed"] = True
        summary["archive_performed"] = True

    finished_at = _utc_now_naive()
    summary["finished_at"] = finished_at.isoformat(timespec="seconds")
    summary["duration_seconds"] = round(time.perf_counter() - start_perf, 4)
    report = _build_run_report(summary)
    _log_run_report(report)

    if report.chunk_failures > 0:
        LOGGER.warning(
            "Chunks screener en echec | chunk_failures=%s chunks_total=%s samples=%s",
            report.chunk_failures,
            report.chunks_total,
            report.chunk_error_samples,
        )

    if final_scores.empty:
        LOGGER.critical(
            "Screener a produit 0 scores | duree=%.2fs as_of=%s | "
            "Verifier : stock_bars_daily peuplee ? benchmark SPY present ? liquidity_threshold trop eleve ?",
            report.duration_seconds,
            as_of_iso or "live",
        )
    else:
        LOGGER.info(
            "Screener termine en %.2fs | symboles scores=%s recent_rows=%s range_rows=%s rows_avoided_estimate=%s",
            report.duration_seconds,
            len(final_scores),
            report.recent_rows_loaded,
            report.range_rows_loaded,
            report.rows_avoided_estimate,
        )

    return final_scores, report


def run_screener(
    config: ScreenerConfig,
    max_workers: Optional[int] = None,
    as_of_date: Optional[date] = None,
) -> pd.DataFrame:
    """
    :param as_of_date: Date de référence point-in-time (backtest).
        Si None, utilise les données jusqu'à aujourd'hui (mode live).
        Toujours spécifier en backtest pour garantir l'absence de look-ahead bias.
    """
    scores, _ = run_screener_with_report(
        config=config,
        max_workers=max_workers,
        as_of_date=as_of_date,
    )
    return scores


def _build_arg_parser() -> argparse.ArgumentParser:
    strict_defaults = ScreenerConfig.strict_swing_cash()
    parser = argparse.ArgumentParser(description="Stock screener haute performance")
    parser.add_argument("--chunk-size", type=int, default=strict_defaults.chunk_size, help="Taille des chunks de symboles")
    parser.add_argument("--max-workers", type=int, default=None, help="Nombre de processus")
    parser.add_argument("--benchmark", type=str, default=strict_defaults.benchmark_symbol, help="Symbole benchmark")
    parser.add_argument("--liquidity-threshold-usd", type=float, default=strict_defaults.liquidity_threshold_usd, help="Seuil minimal de liquidité moyenne en dollars")
    parser.add_argument("--min-relative-strength-index", type=float, default=strict_defaults.min_relative_strength_index, help="Force relative minimale vs benchmark")
    parser.add_argument("--historical-range-lookback-days", type=int, default=strict_defaults.historical_range_lookback_days, help="Fenêtre calendaire du range historique utilisé pour scorer la proximité des highs")
    parser.add_argument("--min-historical-range-score", type=float, default=strict_defaults.min_historical_range_score, help="Score minimal de position dans le range historique")
    parser.add_argument("--first-pass-window-days", type=int, default=strict_defaults.first_pass_window_days, help="Fenêtre calendaire chargée en passe 1")
    parser.add_argument("--disable-two-pass-loading", action="store_true", help="Désactive le chargement en 2 passes")
    parser.add_argument(
        "--trade-date",
        type=str,
        default=None,
        help="Date logique du run (YYYY-MM-DD). Utilisée comme snapshot_date pour l'archivage stock_scores_history. Défaut : aujourd'hui.",
    )
    return parser


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/stock_screener.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = _build_arg_parser().parse_args()
    snapshot_date_override: Optional[date] = None
    if args.trade_date:
        try:
            snapshot_date_override = date.fromisoformat(args.trade_date.strip())
        except ValueError:
            LOGGER.warning("Argument --trade-date=%r invalide ; fallback date.today().", args.trade_date)
    config = ScreenerConfig.strict_swing_cash(
        chunk_size=args.chunk_size,
        benchmark_symbol=args.benchmark,
        liquidity_threshold_usd=args.liquidity_threshold_usd,
        min_relative_strength_index=args.min_relative_strength_index,
        historical_range_lookback_days=args.historical_range_lookback_days,
        min_historical_range_score=args.min_historical_range_score,
        enable_two_pass_loading=not args.disable_two_pass_loading,
        first_pass_window_days=args.first_pass_window_days,
    )
    _, report = run_screener_with_report(
        config=config,
        max_workers=args.max_workers,
        as_of_date=snapshot_date_override,
        snapshot_date=snapshot_date_override,
        progress_callback=lambda payload: _emit_run_summary(payload),
    )
    payload = attach_schema_version(report.to_summary_dict())
    # Sprint S2 (A-017, A-023) — télémétrie ``data_source`` mixée et check
    # d'homogénéité en bord de pipeline. Best-effort : toute défaillance est
    # absorbée dans ``check_data_source_homogeneity``.
    try:
        from dataIntegrityEngine.data_source_health import check_data_source_homogeneity

        mix_check = check_data_source_homogeneity(get_engine())
        payload["data_source_mix_check"] = mix_check
        payload["data_source_mix"] = {
            "counts": mix_check.get("counts", {}),
            "ratios": mix_check.get("ratios", {}),
            "rows_total": mix_check.get("rows_total", 0),
            "dominant_source": mix_check.get("dominant_source"),
        }
    except Exception:
        LOGGER.debug("data_source_mix_check indisponible.", exc_info=True)
    # Phase 3.2.b — alerte si trop de chunks ont échoué.
    ratio = float(payload.get("chunk_failure_ratio") or 0.0)
    if ratio > CHUNK_FAILURE_RATIO_WARNING_THRESHOLD:
        LOGGER.warning(
            "Taux d'echec chunks screener eleve | chunk_failures=%s chunks_total=%s ratio=%.2f%% (seuil=%.2f%%)",
            payload.get("chunk_failures"),
            payload.get("chunks_total"),
            ratio * 100.0,
            CHUNK_FAILURE_RATIO_WARNING_THRESHOLD * 100.0,
        )
    _emit_run_summary(payload)


if __name__ == "__main__":
    main()
