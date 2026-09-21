from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from service.baostock.symbols import parse_baostock_symbol
from service.tushare.adapters import canonical_json, payload_hash


def parse_baostock_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date BaoStock invalide : {value!r}")


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Nombre BaoStock invalide : {value!r}") from exc


def adapt_staging_row(
    endpoint: str,
    row: dict[str, Any],
    *,
    run_id: str,
    raw_id: int | None,
    observed_at: datetime,
    available_at: datetime,
) -> dict[str, Any]:
    symbol_value = str(row.get("code") or "").strip().lower()
    symbol = parse_baostock_symbol(symbol_value) if symbol_value else None
    date_value = row.get("date") or row.get("calendar_date") or row.get("dividOperateDate")
    business_date = parse_baostock_date(date_value)
    if endpoint == "stock_basic":
        business_date = parse_baostock_date(row.get("ipoDate"))
    entity_date = business_date.isoformat() if business_date else ""
    entity_key = "|".join((symbol_value or "MARKET", entity_date, endpoint))
    trading = str(row.get("tradestatus") or "")
    is_st = str(row.get("isST") or "") == "1"
    if endpoint in {"daily", "index_daily"}:
        status = "SUSPENDED" if trading == "0" else "TRADE"
        if is_st:
            status += "|ST"
    else:
        status = str(row.get("status") or "") or None
    adjustment = row.get("adjustFactor")
    if adjustment in (None, ""):
        adjustment = row.get("foreAdjustFactor")
    return {
        "run_id": run_id,
        "raw_id": raw_id,
        "provider": "baostock",
        "endpoint": endpoint,
        "market_code": symbol.market_code if symbol else "CN_A",
        "provider_symbol": symbol.provider_symbol if symbol else None,
        "entity_key": entity_key[:192],
        "business_date": business_date,
        "payload_hash": payload_hash(row),
        "observed_at": observed_at,
        "available_at": available_at,
        "source_revision": entity_date or None,
        "name": str(row.get("code_name") or "")[:255] or None,
        "exchange_code": symbol.exchange_code if symbol else None,
        "board_code": symbol.board_code if symbol else None,
        "status_code": status[:32] if status else None,
        "open_price": _decimal(row.get("open")),
        "high_price": _decimal(row.get("high")),
        "low_price": _decimal(row.get("low")),
        "close_price": _decimal(row.get("close")),
        "pre_close": _decimal(row.get("preclose")),
        "volume": _decimal(row.get("volume")),
        "amount": _decimal(row.get("amount")),
        "adjustment_factor": _decimal(adjustment),
        "limit_up": None,
        "limit_down": None,
        "is_open": int(str(row.get("is_trading_day") or "0") == "1") if endpoint == "trade_cal" else None,
        "list_date": parse_baostock_date(row.get("ipoDate")),
        "delist_date": parse_baostock_date(row.get("outDate")),
        "reason_text": None,
        "raw_payload": canonical_json(row),
    }


__all__ = ["adapt_staging_row", "parse_baostock_date"]
