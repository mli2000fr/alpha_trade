"""Phase 3 EODHD — ingestion daily bars (mode shadow / dry-run par défaut).

Plan ``prompt/iex/plan_eodhd.md`` §5.6 + §6 Phase 3.

**Refactor S7-bis (2026-05-06)** : ce module est devenu un shim mince. La
logique réelle vit désormais dans le sous-package
:mod:`dataIntegrityEngine.eodhd` :

- :mod:`dataIntegrityEngine.eodhd.transforms` — helpers OHLCV purs.
- :mod:`dataIntegrityEngine.eodhd.progress` — emission run_summary / progress.
- :mod:`dataIntegrityEngine.eodhd.orchestrator` — :func:`run_eodhd_ingestion`.
- :mod:`dataIntegrityEngine.eodhd.cli` — CLI ``python -m
  dataIntegrityEngine.import_eodhd_bar``.

Ce shim **conserve** au niveau module tous les noms patchés par
``tests/test_import_eodhd_bar.py`` (``_get_tables``,
``_get_active_tradable_symbols``, ``_get_latest_bar_dates``,
``_upsert_stock_bars*``, ``_cached_fetch_splits``, ``_load_config_safe``,
``fetch_eod_bulk``, ``fetch_eod``, ``fetch_splits``,
``update_bars_available_false``, ``configure_root_logging``, ``date``).
L'orchestrateur appelle ces noms via ``import dataIntegrityEngine.import_eodhd_bar
as _shim`` afin que ``monkeypatch.setattr(import_eodhd_bar, ...)`` reste
effectif.
"""
from __future__ import annotations

import logging
import sys
from datetime import date, datetime  # noqa: F401 (re-export — utilisé par tests)
from functools import lru_cache
from typing import Iterable

from sqlalchemy import MetaData, Table, and_, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from common.config_loader import load_config
from common.utils import configure_root_logging  # noqa: F401 (re-export patchable)
from database.assets import (
    build_eligible_stock_metadata_filters,
    update_bars_available_false,  # noqa: F401 (re-export patchable)
)
from database.connection import SessionLocal, get_sqlalchemy_engine  # noqa: F401
from service.eodhd.adapters import (  # noqa: F401 (re-export)
    DATA_SOURCE_EODHD,
    eodhd_to_split_only,
    to_stock_bars_daily_row,
    to_stock_bars_row,
)
from service.eodhd.cache import (  # noqa: F401 (re-export)
    DEFAULT_TTL_SPLITS_SECONDS,
    EodhdDiskCache,
)
from service.eodhd.clientEodhd import (  # noqa: F401 (re-export patchable)
    EodhdBarsFetchError,
    EodhdCircuitOpen,
    EodhdSymbolNotFound,
    fetch_eod,
    fetch_eod_bulk,
    fetch_splits,
)
from service.eodhd.quota import (  # noqa: F401 (re-export)
    EodhdQuotaExceeded,
    EodhdQuotaTracker,
    get_default_tracker,
)

# Sous-modules de la nouvelle architecture
from dataIntegrityEngine.eodhd import transforms as _transforms
from dataIntegrityEngine.eodhd.cli import build_arg_parser as _build_arg_parser  # noqa: F401
from dataIntegrityEngine.eodhd.cli import main
from dataIntegrityEngine.eodhd.orchestrator import (
    DEFAULT_BULK_PUBLISH_OFFSET_HOURS,
    DEFAULT_PER_SYMBOL_LIMIT,
    DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS,
    _flush_pending_write_rows,  # noqa: F401 (compat)
    finalize as _finalize,  # noqa: F401
    resolve_target_date as _resolve_target_date,  # noqa: F401
    run_eodhd_ingestion,
)
from dataIntegrityEngine.eodhd.progress import (
    PROGRESS_LOG_EVERY,  # noqa: F401
    PROGRESS_LOG_FIRST_SYMBOLS,  # noqa: F401
    RUN_SUMMARY_PREFIX,
    build_run_id as _build_run_id,  # noqa: F401
    emit_live_progress_summary as _emit_live_progress_summary,  # noqa: F401
    emit_run_summary as _emit_run_summary,  # noqa: F401
    should_log_symbol_progress as _should_log_symbol_progress,  # noqa: F401
    utc_now_naive as _utc_now_naive,  # noqa: F401
)

LOGGER = logging.getLogger(__name__)
_PREFERRED_SERIES_SYMBOL_RE = _transforms._PREFERRED_SERIES_SYMBOL_RE


# ---------------------------------------------------------------------------
# Re-exports purs pour rétrocompat
# ---------------------------------------------------------------------------

_normalize_date = _transforms.normalize_date
_index_bulk_by_project_symbol = _transforms.index_bulk_by_project_symbol
_bulk_entry_to_raw_bar = _transforms.bulk_entry_to_raw_bar
_rows_to_raw_bars = _transforms.rows_to_raw_bars
_dedupe_raw_bars_by_date = _transforms.dedupe_raw_bars_by_date
_resolve_missing_fetch_window = _transforms.resolve_missing_fetch_window
_is_known_unsupported_fallback_symbol = _transforms.is_known_unsupported_fallback_symbol


# ---------------------------------------------------------------------------
# Config helpers (patchables : _load_config_safe)
# ---------------------------------------------------------------------------


def resolve_bars_provider(config: dict | None = None) -> str:
    """Lit ``market_data.bars_provider`` (fallback technique ``alpaca``).

    Convention opérateur: ``config.yaml`` versionné fixe ``bars_provider=eodhd``.
    Le fallback à ``alpaca`` ne s'applique qu'en absence/illisibilité de config.
    """
    cfg = config if config is not None else _load_config_safe()
    return str(((cfg or {}).get("market_data") or {}).get("bars_provider", "alpaca")).lower()


def _load_config_safe() -> dict:
    try:
        return load_config() or {}
    except FileNotFoundError:
        return {}
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("[eodhd] config.yaml illisible: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# DB tables (lazy autoload) — patchables
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_tables() -> tuple[Table, Table, Table]:
    metadata = MetaData()
    engine = get_sqlalchemy_engine()
    stock_metadata = Table("stock_metadata", metadata, autoload_with=engine)
    stock_bars = Table("stock_bars", metadata, autoload_with=engine)
    stock_bars_daily = Table("stock_bars_daily", metadata, autoload_with=engine)
    return stock_metadata, stock_bars, stock_bars_daily


def _reset_tables_cache() -> None:
    _get_tables.cache_clear()


def _get_active_tradable_symbols(session) -> list[str]:
    stock_metadata, _, _ = _get_tables()
    q = (
        select(stock_metadata.c.symbol)
        .where(and_(*build_eligible_stock_metadata_filters(stock_metadata)))
        .order_by(stock_metadata.c.symbol)
    )
    return [row[0] for row in session.execute(q).all()]


def _get_latest_bar_dates(session, symbols: Iterable[str]) -> dict[str, date]:
    universe = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    if not universe:
        return {}
    _, bars, _ = _get_tables()
    q = (
        select(bars.c.symbol, func.max(bars.c.timestamp).label("last_timestamp"))
        .where(and_(bars.c.timeframe == "1D", bars.c.symbol.in_(universe)))
        .group_by(bars.c.symbol)
    )
    try:
        rows = session.execute(q).all()
    except AttributeError:
        return {}

    latest_dates: dict[str, date] = {}
    for symbol, last_timestamp in rows:
        normalized = _transforms.normalize_date(last_timestamp)
        if normalized is not None:
            latest_dates[str(symbol).strip().upper()] = normalized
    return latest_dates


# ---------------------------------------------------------------------------
# Splits cache (patchable)
# ---------------------------------------------------------------------------


def _cached_fetch_splits(
    symbol: str,
    *,
    cache: EodhdDiskCache,
    tracker: EodhdQuotaTracker,
    ttl_seconds: float = DEFAULT_TTL_SPLITS_SECONDS,
    fetch_fn=None,
) -> list[dict]:
    namespace = "splits"
    key = symbol.strip().upper()

    cached = cache.get(namespace, key, ttl_seconds=ttl_seconds)
    if cached is not None:
        return list(cached) if isinstance(cached, list) else []

    fetch = fetch_fn if fetch_fn is not None else globals()["fetch_splits"]
    try:
        payload = fetch(symbol, tracker=tracker)
    except (EodhdBarsFetchError, EodhdQuotaExceeded, EodhdCircuitOpen) as exc:
        LOGGER.warning("[eodhd] splits indisponibles pour %s: %s -> []", symbol, exc)
        cache.set(namespace, key, [])
        return []

    cache.set(namespace, key, payload)
    return list(payload) if isinstance(payload, list) else []


# ---------------------------------------------------------------------------
# Upserts (patchables)
# ---------------------------------------------------------------------------


def _upsert_stock_bars_daily(session, rows: list[dict]) -> int:
    if not rows:
        return 0
    _, _, daily = _get_tables()
    stmt = mysql_insert(daily).values(rows)
    update_dict = {
        col: stmt.inserted[col]
        for col in ("open", "high", "low", "close", "volume", "adj_close",
                    "vwap", "daily_return", "is_filled",
                    "data_adjustment", "data_source")
        if col in daily.c
    }
    session.execute(stmt.on_duplicate_key_update(**update_dict))
    return len(rows)


def _upsert_stock_bars(session, rows: list[dict]) -> int:
    if not rows:
        return 0
    _, bars, _ = _get_tables()
    stmt = mysql_insert(bars).values(rows)
    update_dict = {
        col: stmt.inserted[col]
        for col in ("open_price", "high_price", "low_price", "close_price",
                    "volume", "trade_count", "vwa_price",
                    "data_adjustment", "data_source")
        if col in bars.c
    }
    session.execute(stmt.on_duplicate_key_update(**update_dict))
    return len(rows)


# ---------------------------------------------------------------------------
# Entrée CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "DEFAULT_PER_SYMBOL_LIMIT",
    "DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS",
    "DEFAULT_BULK_PUBLISH_OFFSET_HOURS",
    "RUN_SUMMARY_PREFIX",
    "main",
    "resolve_bars_provider",
    "run_eodhd_ingestion",
    # noms patchables (non-API mais préservés pour tests)
    "_get_tables",
    "_get_active_tradable_symbols",
    "_get_latest_bar_dates",
    "_upsert_stock_bars",
    "_upsert_stock_bars_daily",
    "_cached_fetch_splits",
    "_load_config_safe",
    "fetch_eod",
    "fetch_eod_bulk",
    "fetch_splits",
    "update_bars_available_false",
    "configure_root_logging",
    "date",
    "datetime",
]

