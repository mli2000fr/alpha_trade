from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from service.tushare.models import ENDPOINT_SPECS
from service.tushare.symbols import parse_tushare_symbol


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_provider_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date fournisseur invalide : {value!r}")


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Nombre fournisseur invalide : {value!r}") from exc


def _first(row: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        if row.get(field) not in (None, ""):
            return row[field]
    return None


def adapt_staging_row(
    endpoint: str,
    row: dict[str, Any],
    *,
    run_id: str,
    raw_id: int | None,
    observed_at: datetime,
    available_at: datetime,
) -> dict[str, Any]:
    spec = ENDPOINT_SPECS[endpoint]
    symbol_value = _first(row, spec.symbol_fields)
    symbol = None
    if symbol_value and str(symbol_value).upper().endswith((".SH", ".SZ", ".BJ")):
        symbol = parse_tushare_symbol(str(symbol_value))
    business_date = parse_provider_date(_first(row, spec.date_fields))
    entity_values = [str(row.get(field) or "") for field in spec.entity_fields]
    entity_key = "|".join(entity_values)
    if not entity_key.strip("|"):
        entity_key = payload_hash(row)
    revision = _first(row, ("update_time", "ann_date", "end_date", "trade_date"))
    reason = _first(row, ("change_reason", "suspend_timing", "suspend_type", "reason"))
    fallback_exchange = str(row.get("exchange") or "").upper()
    fallback_market = "CN_BJ" if fallback_exchange in {"BJ", "BSE"} else "CN_A"
    return {
        "run_id": run_id,
        "raw_id": raw_id,
        "provider": "tushare",
        "endpoint": endpoint,
        "market_code": symbol.market_code if symbol else fallback_market,
        "provider_symbol": symbol.provider_symbol if symbol else None,
        "entity_key": entity_key[:192],
        "business_date": business_date,
        "payload_hash": payload_hash(row),
        "observed_at": observed_at,
        "available_at": available_at,
        "source_revision": str(revision)[:128] if revision not in (None, "") else None,
        "name": str(_first(row, ("name", "fullname", "enname")) or "")[:255] or None,
        "exchange_code": symbol.exchange_code if symbol else str(row.get("exchange") or "")[:16] or None,
        "board_code": symbol.board_code if symbol else str(row.get("market") or "")[:32] or None,
        "status_code": str(_first(row, ("list_status", "suspend_type")) or "")[:32] or None,
        "open_price": _decimal(row.get("open")),
        "high_price": _decimal(row.get("high")),
        "low_price": _decimal(row.get("low")),
        "close_price": _decimal(row.get("close")),
        "pre_close": _decimal(row.get("pre_close")),
        "volume": _decimal(row.get("vol")),
        "amount": _decimal(row.get("amount")),
        "adjustment_factor": _decimal(row.get("adj_factor")),
        "limit_up": _decimal(row.get("up_limit")),
        "limit_down": _decimal(row.get("down_limit")),
        "is_open": int(row["is_open"]) if row.get("is_open") not in (None, "") else None,
        "list_date": parse_provider_date(row.get("list_date")),
        "delist_date": parse_provider_date(row.get("delist_date")),
        "reason_text": str(reason) if reason not in (None, "") else None,
        "raw_payload": canonical_json(row),
    }


__all__ = ["adapt_staging_row", "canonical_json", "parse_provider_date", "payload_hash"]
