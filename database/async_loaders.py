"""Phase F / S23.3 — Loaders read-only async (POC).

Trois loaders chauds portés en async :

- :func:`fetch_market_data_async` — historique OHLCV par symboles.
- :func:`fetch_scores_async` — scores screener par run.
- :func:`fetch_open_orders_async` — ordres ouverts par compte.

Toujours opt-in via ``ALPHA_TRADE_ASYNC_DB=1``. Si désactivé ou si le moteur
async ne peut être construit, les fonctions retournent ``None`` et le
code appelant doit retomber sur la version sync.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional, Sequence

from database.async_engine import make_async_engine

LOGGER = logging.getLogger(__name__)


async def _fetch_all(query: str, params: dict) -> Optional[list[dict]]:
    engine = make_async_engine()
    if engine is None:
        return None
    try:
        from sqlalchemy import text  # type: ignore
    except ImportError:
        return None
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(query), params)
            return [dict(row._mapping) for row in result]
    except Exception as exc:
        LOGGER.warning("Async query failed (%s) — caller should fallback to sync", exc)
        return None


async def fetch_market_data_async(
    symbols: Sequence[str],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    *,
    table: str = "bars_daily",
) -> Optional[list[dict]]:
    """Charge l'historique OHLCV pour ``symbols`` entre ``start_date`` et ``end_date``.

    Retourne ``None`` si l'async n'est pas disponible (caller fallback sync).
    """
    if not symbols:
        return []
    placeholders = ", ".join(f":sym_{i}" for i in range(len(symbols)))
    where = [f"symbol IN ({placeholders})"]
    params: dict[str, Any] = {f"sym_{i}": s for i, s in enumerate(symbols)}
    if start_date is not None:
        where.append("date >= :start_date")
        params["start_date"] = start_date
    if end_date is not None:
        where.append("date <= :end_date")
        params["end_date"] = end_date
    sql = (
        f"SELECT symbol, date, open, high, low, close, volume "
        f"FROM {table} WHERE {' AND '.join(where)} ORDER BY symbol, date"
    )
    return await _fetch_all(sql, params)


async def fetch_scores_async(run_id: str, *, table: str = "screener_scores") -> Optional[list[dict]]:
    sql = f"SELECT symbol, score, rank FROM {table} WHERE run_id = :run_id ORDER BY rank"
    return await _fetch_all(sql, {"run_id": run_id})


async def fetch_open_orders_async(
    account_id: str,
    *,
    table: str = "execution_broker_orders",
) -> Optional[list[dict]]:
    sql = (
        f"SELECT broker_order_id, intent_id, symbol, status, qty "
        f"FROM {table} WHERE account_id = :account_id "
        f"AND status NOT IN ('FILLED', 'CANCELED', 'REJECTED', 'EXPIRED', 'FAILED')"
    )
    return await _fetch_all(sql, {"account_id": account_id})

