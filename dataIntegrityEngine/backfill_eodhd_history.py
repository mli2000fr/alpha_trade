"""Phase 5 EODHD - Backfill historique long (5 ans actif / 30 ans ML).

Plan ``prompt/iex/plan_eodhd.md`` §6 Phase 5.

Objectif : remplir ``stock_bars`` + ``stock_bars_daily`` avec les barres
EODHD historiques pour permettre :
- les backtests longs (selector / weights_calibration) ;
- les modèles ML (LSTM) sur 30 ans de cycles de marché.

Architecture :
- **1 appel API par symbole** (``/eod/{ticker}.US`` cost=1) + 1 appel splits
  (cost=1, cache TTL 7j -> en pratique 1 fois par symbole sur la durée du
  backfill).
- **Bookmark** dans ``artifacts/eodhd_cache/backfill_state.json`` pour reprise
  idempotente sur interruption.
- **Mode dry-run** : ne touche pas la DB, log les volumes attendus.
- Reconstruction split-only via :func:`eodhd_to_split_only` (cohérent Phase 3).

Usage::

    # Univers actif sur 5 ans (par défaut)
    python -m dataIntegrityEngine.backfill_eodhd_history --write

    # Univers ML restreint sur 30 ans
    python -m dataIntegrityEngine.backfill_eodhd_history --write \\
        --years 30 --symbols AAPL MSFT NVDA AMZN GOOGL

    # Reprise après interruption (lit le bookmark)
    python -m dataIntegrityEngine.backfill_eodhd_history --write --resume

    # Force re-traitement complet (ignore bookmark)
    python -m dataIntegrityEngine.backfill_eodhd_history --write --no-resume
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from common.config_loader import load_config
from common.utils import configure_root_logging
from core.run_summary import attach_schema_version
from database.assets import update_bars_available_false
from database.connection import SessionLocal
from dataIntegrityEngine.import_eodhd_bar import (
    _cached_fetch_splits,
    _get_active_tradable_symbols,
    _is_known_unsupported_fallback_symbol,
    _get_tables,
    _upsert_stock_bars,
    _upsert_stock_bars_daily,
)
from service.eodhd.adapters import (
    eodhd_to_split_only,
    to_stock_bars_daily_row,
    to_stock_bars_row,
)
from service.eodhd.cache import EodhdDiskCache
from service.eodhd.clientEodhd import (
    EodhdBarsFetchError,
    fetch_eod,
)
from service.eodhd.quota import (
    EodhdQuotaExceeded,
    EodhdQuotaTracker,
    get_default_tracker,
)

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
DEFAULT_YEARS = 5
DEFAULT_BATCH_COMMIT = 50
DEFAULT_BOOKMARK_PATH = Path("artifacts") / "eodhd_cache" / "backfill_state.json"


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str = "backfill-eodhd") -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, Any]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Bookmark (reprise idempotente)
# ---------------------------------------------------------------------------


def load_bookmark(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"completed_symbols": [], "started_at": None, "last_run_id": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("[backfill] bookmark illisible (%s) -> reset", exc)
        return {"completed_symbols": [], "started_at": None, "last_run_id": None}


def save_bookmark(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _filter_remaining(symbols: list[str], bookmark: dict[str, Any]) -> list[str]:
    done: set[str] = set(bookmark.get("completed_symbols") or [])
    return [s for s in symbols if s not in done]


# ---------------------------------------------------------------------------
# Backfill un symbole
# ---------------------------------------------------------------------------


def _eod_rows_to_raw_bars(rows: list[dict]) -> list[dict]:
    raws: list[dict] = []
    for r in rows:
        try:
            raws.append({
                "date": r["date"],
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "adjusted_close": float(r.get("adjusted_close", r["close"])),
                "volume": int(r.get("volume") or 0),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return raws


def backfill_one_symbol(
    *,
    symbol: str,
    start: str,
    end: str,
    cache: EodhdDiskCache,
    tracker: EodhdQuotaTracker,
    session,
    dry_run: bool,
    fetch_eod_fn=None,
) -> dict[str, int]:
    """Retourne ``{"rows_daily", "rows_bars", "raw_rows", "errors"}``.

    ``fetch_eod_fn`` est résolu en *late binding* sur l'attribut module-level
    ``fetch_eod`` quand ``None``, ce qui permet aux tests de monkeypatcher
    via ``monkeypatch.setattr(backfill_eodhd_history, "fetch_eod", ...)``.
    """
    if fetch_eod_fn is None:
        import dataIntegrityEngine.backfill_eodhd_history as _self_module
        fetch_eod_fn = _self_module.fetch_eod
    try:
        eod_rows = fetch_eod_fn(symbol, start=start, end=end, tracker=tracker)
    except (EodhdBarsFetchError, EodhdQuotaExceeded) as exc:
        LOGGER.warning("[backfill] %s fetch_eod failed: %s", symbol, exc)
        return {"rows_daily": 0, "rows_bars": 0, "raw_rows": 0, "errors": 1}

    raws = _eod_rows_to_raw_bars(eod_rows)
    if not raws:
        return {"rows_daily": 0, "rows_bars": 0, "raw_rows": 0, "errors": 0}

    splits = _cached_fetch_splits(symbol, cache=cache, tracker=tracker)
    split_only = eodhd_to_split_only(raws, splits)

    rows_daily = [to_stock_bars_daily_row(b, symbol) for b in split_only]
    rows_bars = [to_stock_bars_row(b, symbol) for b in split_only]

    if dry_run:
        return {
            "rows_daily": 0,
            "rows_bars": 0,
            "raw_rows": len(raws),
            "errors": 0,
            "would_upsert_daily": len(rows_daily),
            "would_upsert_bars": len(rows_bars),
        }

    try:
        n_daily = _upsert_stock_bars_daily(session, rows_daily)
        n_bars = _upsert_stock_bars(session, rows_bars)
    except Exception:
        session.rollback()
        LOGGER.exception("[backfill] %s upsert failed -> rollback", symbol)
        return {"rows_daily": 0, "rows_bars": 0, "raw_rows": len(raws), "errors": 1}

    return {
        "rows_daily": n_daily,
        "rows_bars": n_bars,
        "raw_rows": len(raws),
        "errors": 0,
    }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_backfill(
    *,
    years: int = DEFAULT_YEARS,
    symbols: Optional[list[str]] = None,
    dry_run: bool = True,
    resume: bool = True,
    bookmark_path: Optional[Path] = None,
    batch_commit: int = DEFAULT_BATCH_COMMIT,
    config: Optional[dict] = None,
    session=None,
    tracker: Optional[EodhdQuotaTracker] = None,
    cache: Optional[EodhdDiskCache] = None,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """Backfill historique sur ``years`` années pour un univers donné."""
    cfg = config if config is not None else _load_config_safe()
    started_at = _utc_now_naive()
    today = today or date.today()
    end_date = today.isoformat()
    start_date = (today.replace(year=today.year - years)).isoformat()
    bookmark_path = bookmark_path or DEFAULT_BOOKMARK_PATH

    cache = cache or EodhdDiskCache(
        Path((cfg.get("eodhd") or {}).get("cache_dir", "artifacts/eodhd_cache"))
    )
    tracker = tracker or get_default_tracker()

    bookmark = load_bookmark(bookmark_path) if resume else {
        "completed_symbols": [], "started_at": None, "last_run_id": None,
    }

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True

    summary: dict[str, Any] = {
        "run_id": _build_run_id(),
        "provider": "eodhd",
        "mode": "dry_run" if dry_run else "write",
        "years": years,
        "start_date": start_date,
        "end_date": end_date,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": None,
        "duration_seconds": 0.0,
        "targeted_symbols": 0,
        "remaining_after_bookmark": 0,
        "symbols_processed": 0,
        "symbols_skipped_resumed": 0,
        "rows_upserted_stock_bars": 0,
        "rows_upserted_stock_bars_daily": 0,
        "raw_rows_total": 0,
        "errors": 0,
        "unsupported_fallback_symbols": 0,
        "metadata_marked_unavailable": 0,
        "stopped_reason": None,
        "bookmark_path": str(bookmark_path),
        "resume": resume,
    }

    try:
        # Univers
        if symbols:
            universe = [s.strip().upper() for s in symbols if s and s.strip()]
        else:
            universe = _get_active_tradable_symbols(session)
        summary["targeted_symbols"] = len(universe)

        remaining = _filter_remaining(universe, bookmark)
        summary["remaining_after_bookmark"] = len(remaining)
        summary["symbols_skipped_resumed"] = len(universe) - len(remaining)

        if not remaining:
            LOGGER.info("[backfill] aucun symbole restant (bookmark complet) - exit 0")
            return _finalize(summary, started_at, tracker, bookmark, bookmark_path)

        LOGGER.info(
            "[backfill] start | run_id=%s years=%d window=%s..%s symbols=%d remaining=%d mode=%s",
            summary["run_id"], years, start_date, end_date,
            len(universe), len(remaining), summary["mode"],
        )

        if bookmark.get("started_at") is None:
            bookmark["started_at"] = summary["started_at"]
        bookmark["last_run_id"] = summary["run_id"]

        for idx, symbol in enumerate(remaining, 1):
            if tracker.is_circuit_open():
                summary["stopped_reason"] = "circuit_open"
                LOGGER.warning(
                    "[backfill] circuit-breaker EODHD ouvert -> stop (idx=%d/%d)",
                    idx, len(remaining),
                )
                break

            if _is_known_unsupported_fallback_symbol(symbol):
                LOGGER.info(
                    "[backfill] symbole preferred/series non supporté ignoré avant fetch_eod: %s",
                    symbol,
                )
                summary["unsupported_fallback_symbols"] += 1
                if not dry_run:
                    update_bars_available_false(symbol)
                    summary["metadata_marked_unavailable"] += 1
                bookmark.setdefault("completed_symbols", []).append(symbol)
                continue

            result = backfill_one_symbol(
                symbol=symbol,
                start=start_date,
                end=end_date,
                cache=cache,
                tracker=tracker,
                session=session,
                dry_run=dry_run,
            )
            summary["symbols_processed"] += 1
            summary["raw_rows_total"] += int(result.get("raw_rows", 0))
            summary["rows_upserted_stock_bars_daily"] += int(result.get("rows_daily", 0))
            summary["rows_upserted_stock_bars"] += int(result.get("rows_bars", 0))
            summary["errors"] += int(result.get("errors", 0))

            # Marque comme complété (même si 0 row : symbole sans historique)
            if result.get("errors", 0) == 0:
                bookmark.setdefault("completed_symbols", []).append(symbol)

            # Commit + bookmark par batch
            if not dry_run and (idx % batch_commit == 0):
                try:
                    session.commit()
                except Exception:
                    session.rollback()
                    LOGGER.exception("[backfill] commit batch failed")
                    summary["errors"] += 1
                save_bookmark(bookmark_path, bookmark)

            if idx % 10 == 0:
                LOGGER.info(
                    "[backfill] progress %d/%d | rows_daily=%d rows_bars=%d errors=%d "
                    "calls_used=%d",
                    idx, len(remaining),
                    summary["rows_upserted_stock_bars_daily"],
                    summary["rows_upserted_stock_bars"],
                    summary["errors"],
                    tracker.snapshot()["calls_used"],
                )

        # Commit final
        if not dry_run:
            try:
                session.commit()
            except Exception:
                session.rollback()
                LOGGER.exception("[backfill] final commit failed")
                summary["errors"] += 1

        save_bookmark(bookmark_path, bookmark)
        return _finalize(summary, started_at, tracker, bookmark, bookmark_path)

    finally:
        if own_session:
            session.close()


def _finalize(summary, started_at, tracker, bookmark, bookmark_path):
    finished_at = _utc_now_naive()
    summary["finished_at"] = finished_at.isoformat(timespec="seconds")
    summary["duration_seconds"] = round((finished_at - started_at).total_seconds(), 2)
    summary["eodhd"] = tracker.snapshot()
    summary["bookmark"] = {
        "completed_count": len(bookmark.get("completed_symbols") or []),
        "path": str(bookmark_path),
    }
    LOGGER.info(
        "[backfill] resume | run_id=%s mode=%s processed=%d rows_daily=%d rows_bars=%d "
        "raw_rows=%d errors=%d duration_s=%.2f calls_used=%d",
        summary["run_id"], summary["mode"], summary["symbols_processed"],
        summary["rows_upserted_stock_bars_daily"], summary["rows_upserted_stock_bars"],
        summary["raw_rows_total"], summary["errors"], summary["duration_seconds"],
        summary["eodhd"]["calls_used"],
    )
    return summary


# ---------------------------------------------------------------------------
# Helpers config
# ---------------------------------------------------------------------------


def _load_config_safe() -> dict:
    try:
        return load_config() or {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--years", type=int, default=DEFAULT_YEARS,
                   help=f"Profondeur historique en années (défaut: {DEFAULT_YEARS}).")
    p.add_argument("--symbols", nargs="+", default=None,
                   help="Sous-univers explicite (sinon univers actif eligible).")
    p.add_argument("--bookmark", default=str(DEFAULT_BOOKMARK_PATH),
                   help="Chemin du bookmark JSON.")
    p.add_argument("--batch-commit", type=int, default=DEFAULT_BATCH_COMMIT)
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--dry-run", action="store_true", default=True)
    grp.add_argument("--write", action="store_true", default=False)
    grp_resume = p.add_mutually_exclusive_group()
    grp_resume.add_argument("--resume", dest="resume", action="store_true", default=True)
    grp_resume.add_argument("--no-resume", dest="resume", action="store_false")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/backfill_eodhd_history.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = _build_arg_parser().parse_args(argv)
    summary = run_backfill(
        years=args.years,
        symbols=args.symbols,
        dry_run=not args.write,
        resume=args.resume,
        bookmark_path=Path(args.bookmark),
        batch_commit=args.batch_commit,
    )
    _emit_run_summary(attach_schema_version(summary))
    return 0 if summary.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "DEFAULT_BOOKMARK_PATH",
    "DEFAULT_YEARS",
    "backfill_one_symbol",
    "load_bookmark",
    "main",
    "run_backfill",
    "save_bookmark",
]


