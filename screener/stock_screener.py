import argparse
import logging
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import date
from typing import List, Optional

import pandas as pd

from screener.db_io import (
    get_engine,
    iter_symbol_chunks,
    load_prices_for_chunk,
    load_spy_return_6m,
    upsert_scores_snapshot,
)
from screener.models import ScreenerConfig
from screener import RESULT_COLUMNS, compute_scores_from_prices

LOGGER = logging.getLogger(__name__)


def _process_chunk(
    symbols: List[str],
    config_dict: dict,
    spy_return_6m: float,
    as_of_date_iso: Optional[str],
) -> pd.DataFrame:
    """
    Fonction exécutée dans un subprocess (ProcessPoolExecutor).
    L'engine est créé via get_engine() / lru_cache isolé par processus.
    as_of_date est transmis comme ISO string (picklable) et reconverti ici.
    """
    config = ScreenerConfig.from_dict(config_dict)
    engine = get_engine()
    as_of = date.fromisoformat(as_of_date_iso) if as_of_date_iso else None
    chunk_prices = load_prices_for_chunk(engine, symbols, config, as_of_date=as_of)
    return compute_scores_from_prices(chunk_prices, spy_return_6m, config, as_of_date=as_of)


def _resolve_worker_count(max_workers: Optional[int]) -> int:
    available_workers = os.cpu_count() or 1
    if max_workers is None:
        return available_workers
    if max_workers < 1:
        raise ValueError("max_workers doit être supérieur ou égal à 1.")
    return max_workers


def _append_completed_results(done, all_results: List[pd.DataFrame]) -> None:
    for future in done:
        chunk_result = future.result()
        if not chunk_result.empty:
            all_results.append(chunk_result)


def _empty_scores() -> pd.DataFrame:
    return pd.DataFrame(columns=RESULT_COLUMNS)


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
    start = time.time()
    engine = get_engine()
    spy_return_6m = load_spy_return_6m(engine, config, as_of_date=as_of_date)

    workers = _resolve_worker_count(max_workers)
    max_in_flight = max(2, workers * 2)
    config_dict = config.to_dict()
    as_of_iso = as_of_date.isoformat() if as_of_date else None

    all_results: List[pd.DataFrame] = []
    pending = set()

    LOGGER.info(
        "Démarrage screener | benchmark=%s chunk_size=%s workers=%s as_of=%s",
        config.benchmark_symbol,
        config.chunk_size,
        workers,
        as_of_iso or "live",
    )

    with ProcessPoolExecutor(max_workers=workers) as executor:
        for symbol_chunk in iter_symbol_chunks(engine, config.chunk_size):
            while len(pending) >= max_in_flight:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                _append_completed_results(done, all_results)

            pending.add(executor.submit(_process_chunk, symbol_chunk, config_dict, spy_return_6m, as_of_iso))

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            _append_completed_results(done, all_results)

    if all_results:
        final_scores = pd.concat(all_results, ignore_index=True)
        final_scores = (
            final_scores.sort_values("total_score", ascending=False)
            .drop_duplicates("symbol")
            .reset_index(drop=True)
        )
    else:
        final_scores = _empty_scores()

    upsert_scores_snapshot(engine, final_scores, chunksize=1000)

    elapsed = time.time() - start

    # Monitoring : alerte si 0 symboles scorés (P1 — Engineering Quality)
    if final_scores.empty:
        LOGGER.critical(
            "Screener a produit 0 scores | durée=%.2fs as_of=%s | "
            "Vérifier : stock_bars_daily peuplée ? benchmark SPY présent ? liquidity_threshold trop élevé ?",
            elapsed,
            as_of_iso or "live",
        )
    else:
        LOGGER.info("Screener terminé en %.2fs | symboles scorés=%s", elapsed, len(final_scores))

    return final_scores


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stock screener haute performance")
    parser.add_argument("--chunk-size", type=int, default=500, help="Taille des chunks de symboles")
    parser.add_argument("--max-workers", type=int, default=None, help="Nombre de processus")
    parser.add_argument("--benchmark", type=str, default="SPY", help="Symbole benchmark")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_arg_parser().parse_args()
    config = ScreenerConfig(chunk_size=args.chunk_size, benchmark_symbol=args.benchmark)
    run_screener(config=config, max_workers=args.max_workers)


if __name__ == "__main__":
    main()
