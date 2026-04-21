from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from sqlalchemy import text

from backtesting.backfill_scores_history import BackfillScoresHistoryService
from database.connection import get_sqlalchemy_engine
from event_sentiment.signal_aggregator import SentimentBoostConfig
from screener.models import ScreenerConfig
from selector.alpha_scanner import AlphaScannerConfig
from selector.strict_filter_profiles import STRICT_SWING_CASH_FILTERS

DEFAULT_BACKFILL_START = pd.Timestamp("2025-01-01").date()
DEFAULT_BACKFILL_END = pd.Timestamp("2025-03-31").date()
DEFAULT_LOOKBACK_START = pd.Timestamp("2024-10-01").date()
DEFAULT_OUTPUT_DIR = Path("prompt/fix_swing/cash_eq2000_mp2_filtered_f2_oos_2025Q1_strict")
DEFAULT_LOG_PATH = Path("prompt/fix_swing/strict_oos_2025Q1_manifest.json")
DEFAULT_CHUNK_SIZE = 10_000
DEFAULT_SELECTION_SIZE = 100
DEFAULT_SCREENER_WORKERS = 8
STRICT_FILTERS = STRICT_SWING_CASH_FILTERS.to_backtest_filter_dict()


def _parse_date(value: str) -> date:
    return pd.Timestamp(value).date()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill strict 2025Q1 + rerun OOS filtré")
    parser.add_argument("--backfill-start", default=str(DEFAULT_BACKFILL_START))
    parser.add_argument("--backfill-end", default=str(DEFAULT_BACKFILL_END))
    parser.add_argument("--oos-start", default=str(DEFAULT_BACKFILL_START))
    parser.add_argument("--oos-end", default=str(DEFAULT_BACKFILL_END))
    parser.add_argument("--lookback-start", default=str(DEFAULT_LOOKBACK_START))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--manifest-path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--selection-size", type=int, default=DEFAULT_SELECTION_SIZE)
    parser.add_argument("--screener-workers", type=int, default=DEFAULT_SCREENER_WORKERS)
    parser.add_argument("--skip-purge", action="store_true")
    return parser


def purge_history_range(start: date, end: date) -> int:
    engine = get_sqlalchemy_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "DELETE FROM stock_scores_history WHERE snapshot_date BETWEEN :start_date AND :end_date"
            ),
            {"start_date": start, "end_date": end},
        )
    return int(result.rowcount or 0)


def get_history_coverage(start: date, end: date) -> dict[str, Any]:
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT snapshot_date) AS days,
                       COUNT(*) AS rows_n,
                       MIN(snapshot_date) AS dmin,
                       MAX(snapshot_date) AS dmax
                FROM stock_scores_history
                WHERE snapshot_date BETWEEN :start_date AND :end_date
                """
            ),
            {"start_date": start, "end_date": end},
        ).mappings().one()
    coverage = dict(row)
    for key in ("dmin", "dmax"):
        if coverage.get(key) is not None:
            coverage[key] = str(coverage[key])
    return coverage


def run_backfill(start: date, end: date, *, chunk_size: int, selection_size: int, screener_workers: int) -> dict[str, Any]:
    service = BackfillScoresHistoryService(
        screener_config=ScreenerConfig(chunk_size=chunk_size),
        scanner_config=AlphaScannerConfig.strict_swing_cash(
            chunk_size=chunk_size,
            selection_size=selection_size,
        ),
        sentiment_config=SentimentBoostConfig(),
        screener_max_workers=screener_workers,
    )
    result = service.backfill(
        start_date=start,
        end_date=end,
        overwrite_existing=True,
        limit_days=None,
    )
    return {
        "start_date": str(result.start_date),
        "end_date": str(result.end_date),
        "trading_days_requested": result.trading_days_requested,
        "trading_days_processed": result.trading_days_processed,
        "rows_inserted": result.rows_inserted,
        "trading_days_skipped_existing": result.trading_days_skipped_existing,
    }


def run_filtered_oos(*, oos_start: date, oos_end: date, lookback_start: date, output_dir: Path) -> subprocess.CompletedProcess[str]:
    script_path = PROJECT_ROOT / "prompt" / "fix_swing" / "run_filtered_case_real.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--start",
        str(oos_start),
        "--end",
        str(oos_end),
        "--lookback-start",
        str(lookback_start),
        "--output-dir",
        str(output_dir),
    ]
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def main() -> None:
    args = _build_parser().parse_args()
    backfill_start = _parse_date(args.backfill_start)
    backfill_end = _parse_date(args.backfill_end)
    oos_start = _parse_date(args.oos_start)
    oos_end = _parse_date(args.oos_end)
    lookback_start = _parse_date(args.lookback_start)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "params": {
            "backfill_start": str(backfill_start),
            "backfill_end": str(backfill_end),
            "oos_start": str(oos_start),
            "oos_end": str(oos_end),
            "lookback_start": str(lookback_start),
            "output_dir": str(output_dir),
            "chunk_size": args.chunk_size,
            "selection_size": args.selection_size,
            "screener_workers": args.screener_workers,
            "skip_purge": bool(args.skip_purge),
            "filters": STRICT_FILTERS,
        }
    }

    if not args.skip_purge:
        deleted_rows = purge_history_range(backfill_start, backfill_end)
        manifest["purge"] = {"deleted_rows": deleted_rows}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest["coverage_before_backfill"] = get_history_coverage(backfill_start, backfill_end)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest["backfill_result"] = run_backfill(
        backfill_start,
        backfill_end,
        chunk_size=args.chunk_size,
        selection_size=args.selection_size,
        screener_workers=args.screener_workers,
    )
    manifest["coverage_after_backfill"] = get_history_coverage(backfill_start, backfill_end)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    rerun = run_filtered_oos(
        oos_start=oos_start,
        oos_end=oos_end,
        lookback_start=lookback_start,
        output_dir=output_dir,
    )
    manifest["rerun"] = {
        "returncode": rerun.returncode,
        "stdout": rerun.stdout,
        "stderr": rerun.stderr,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


