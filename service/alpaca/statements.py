"""Sprint S12.3 — Récupération paginée des Alpaca account activities.

Endpoint : ``GET /v2/account/activities`` (filtrable par
``activity_types``, ``date``, ``page_token``, ``page_size``).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterable

from service.alpaca.trading_client import AlpacaTradingClient

LOGGER = logging.getLogger(__name__)

#: Activités pertinentes pour la réconciliation des fills.
FILL_ACTIVITY_TYPES: tuple[str, ...] = ("FILL", "PFILL")


def fetch_account_activities(
    client: AlpacaTradingClient,
    *,
    since: date | datetime | None = None,
    until: date | datetime | None = None,
    activity_types: Iterable[str] = FILL_ACTIVITY_TYPES,
    page_size: int = 100,
    max_pages: int = 200,
) -> list[dict[str, Any]]:
    """Récupère toutes les activities (paginé) sur la fenêtre demandée.

    Le paramètre ``page_token`` Alpaca correspond à l'``id`` de la dernière
    activity de la page précédente.
    """
    params: dict[str, str] = {
        "page_size": str(page_size),
        "activity_types": ",".join(activity_types),
        "direction": "asc",
    }
    if since is not None:
        params["after"] = _iso(since)
    if until is not None:
        params["until"] = _iso(until)

    out: list[dict[str, Any]] = []
    page_token: str | None = None
    for _ in range(max_pages):
        if page_token:
            params["page_token"] = page_token
        try:
            resp = client._request("GET", "/v2/account/activities", params=dict(params))  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("fetch_account_activities: %s", exc)
            break
        if not isinstance(resp, list) or not resp:
            break
        out.extend(resp)
        if len(resp) < page_size:
            break
        page_token = str(resp[-1].get("id") or "")
        if not page_token:
            break
    return out


def _iso(d: date | datetime) -> str:
    if isinstance(d, datetime):
        return d.isoformat()
    return d.isoformat()


# ---------------------------------------------------------------------------
# Sprint S21.4 — Loader SQL ``broker_statements`` → MonthlyReportInputs
# ---------------------------------------------------------------------------


def _decimal_to_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _compute_realized_pnl_fifo(fills: list[dict[str, Any]]) -> float:
    """PnL réalisé FIFO par symbole.

    Convention : `qty` positive = BUY, négative = SELL. Lot ouvert sur BUY,
    consommé sur SELL ; PnL = (sell_price - buy_price) * sell_qty.
    """
    from collections import defaultdict, deque

    lots: dict[str, deque] = defaultdict(deque)
    pnl = 0.0
    for f in sorted(fills, key=lambda r: r.get("transaction_time") or ""):
        sym = str(f.get("symbol") or "")
        qty = _decimal_to_float(f.get("qty"))
        side = str(f.get("side") or "").lower()
        price = _decimal_to_float(f.get("price"))
        if not sym or qty <= 0 or price <= 0:
            continue
        if side == "buy":
            lots[sym].append([qty, price])
        elif side == "sell":
            remaining = qty
            queue = lots[sym]
            while remaining > 0 and queue:
                lot_qty, lot_price = queue[0]
                used = min(lot_qty, remaining)
                pnl += (price - lot_price) * used
                lot_qty -= used
                remaining -= used
                if lot_qty <= 1e-12:
                    queue.popleft()
                else:
                    queue[0][0] = lot_qty
    return pnl


def load_monthly_inputs_from_db(
    engine: Any,
    *,
    account_id: str,
    period_start: date,
    period_end: date,
    table: str = "broker_statements",
):
    """Construit ``MonthlyReportInputs`` à partir de ``broker_statements``.

    - ``activity_type IN ('FILL', 'PFILL')`` → ``FillRow``
    - ``activity_type IN ('DIV')`` → ``CashEvent(kind='dividend')``
    - ``activity_type IN ('DIVNRA', 'DIVTAX', 'WHTAX')`` → ``withholding``
    - ``activity_type IN ('FEE', 'CFEE')`` → ``fee``
    - ``activity_type IN ('INT')`` → ``interest``

    Le PnL réalisé est calculé par FIFO sur **l'historique complet** des
    fills antérieurs à ``period_end`` afin que les SELL du mois courant
    soient correctement appariés à des BUY de mois antérieurs ; seuls les
    SELL de la période donnent lieu à du PnL inclus dans le rapport.
    """
    from sqlalchemy import text

    from reporting.monthly_report import CashEvent, FillRow, MonthlyReportInputs

    end_excl = datetime.combine(period_end, datetime.min.time())
    start_dt = datetime.combine(period_start, datetime.min.time())

    # Tous les fills jusqu'à end_excl (pour FIFO correct)
    full_query = text(
        f"""
        SELECT activity_id, activity_type, symbol, side, qty, price,
               transaction_time
          FROM {table}
         WHERE account_id = :account_id
           AND activity_type IN ('FILL', 'PFILL')
           AND transaction_time <  :end_excl
         ORDER BY transaction_time ASC, activity_id ASC
        """
    )
    # Cash events de la période uniquement
    cash_query = text(
        f"""
        SELECT activity_id, activity_type, symbol, side, qty, price,
               transaction_time
          FROM {table}
         WHERE account_id = :account_id
           AND activity_type NOT IN ('FILL', 'PFILL')
           AND transaction_time >= :start
           AND transaction_time <  :end_excl
         ORDER BY transaction_time ASC, activity_id ASC
        """
    )

    fill_rows: list[FillRow] = []
    cash_events: list[CashEvent] = []
    trades_count = 0

    with engine.connect() as conn:
        all_fills = [dict(r) for r in conn.execute(full_query, {
            "account_id": account_id, "end_excl": end_excl,
        }).mappings().fetchall()]
        cash_rows = conn.execute(cash_query, {
            "account_id": account_id, "start": start_dt, "end_excl": end_excl,
        }).mappings().fetchall()

    realized = _compute_realized_pnl_fifo_period(all_fills, period_start, period_end)

    for row in all_fills:
        ts = _to_datetime(row.get("transaction_time"))
        if ts is None:
            continue
        if not (start_dt <= ts < end_excl):
            continue
        atype = str(row.get("activity_type") or "").upper()
        sym = str(row.get("symbol") or "")
        qty = _decimal_to_float(row.get("qty"))
        price = _decimal_to_float(row.get("price"))
        fill_rows.append(FillRow(
            fill_id=str(row.get("activity_id")),
            symbol=sym,
            qty=qty,
            price=price,
            expected_price=price,
            fees=0.0,
        ))
        if atype == "FILL":
            trades_count += 1

    for row in cash_rows:
        atype = str(row.get("activity_type") or "").upper()
        sym = str(row.get("symbol") or "")
        if atype == "DIV":
            cash_events.append(CashEvent(
                event_id=str(row.get("activity_id")), symbol=sym, kind="dividend",
                amount=_decimal_to_float(row.get("price")) * _decimal_to_float(row.get("qty") or 1),
            ))
        elif atype in ("DIVNRA", "DIVTAX", "WHTAX"):
            cash_events.append(CashEvent(
                event_id=str(row.get("activity_id")), symbol=sym, kind="withholding",
                amount=_decimal_to_float(row.get("price")),
            ))
        elif atype in ("FEE", "CFEE"):
            cash_events.append(CashEvent(
                event_id=str(row.get("activity_id")), symbol=sym, kind="fee",
                amount=_decimal_to_float(row.get("price")),
            ))
        elif atype == "INT":
            cash_events.append(CashEvent(
                event_id=str(row.get("activity_id")), symbol=sym, kind="interest",
                amount=_decimal_to_float(row.get("price")),
            ))

    return MonthlyReportInputs(
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        fills=fill_rows,
        cash_events=cash_events,
        realized_pnl=realized,
        trades_count=trades_count,
    )


def _to_datetime(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        # SQLite renvoie souvent une str ISO
        return datetime.fromisoformat(str(val))
    except Exception:
        return None


def _compute_realized_pnl_fifo_period(
    fills: list[dict[str, Any]],
    period_start: date,
    period_end: date,
) -> float:
    """FIFO global — n'attribue à la période que les SELL effectués entre
    ``period_start`` (inclus) et ``period_end`` (exclus)."""
    from collections import defaultdict, deque

    start_dt = datetime.combine(period_start, datetime.min.time())
    end_excl = datetime.combine(period_end, datetime.min.time())

    lots: dict[str, deque] = defaultdict(deque)
    pnl = 0.0
    for f in sorted(fills, key=lambda r: _to_datetime(r.get("transaction_time")) or datetime.min):
        sym = str(f.get("symbol") or "")
        qty = _decimal_to_float(f.get("qty"))
        side = str(f.get("side") or "").lower()
        price = _decimal_to_float(f.get("price"))
        ts = _to_datetime(f.get("transaction_time"))
        if not sym or qty <= 0 or price <= 0:
            continue
        if side == "buy":
            lots[sym].append([qty, price])
        elif side == "sell":
            remaining = qty
            queue = lots[sym]
            in_period = ts is not None and start_dt <= ts < end_excl
            while remaining > 0 and queue:
                lot_qty, lot_price = queue[0]
                used = min(lot_qty, remaining)
                if in_period:
                    pnl += (price - lot_price) * used
                lot_qty -= used
                remaining -= used
                if lot_qty <= 1e-12:
                    queue.popleft()
                else:
                    queue[0][0] = lot_qty
    return pnl


__all__ = [
    "fetch_account_activities",
    "FILL_ACTIVITY_TYPES",
    "load_monthly_inputs_from_db",
]

