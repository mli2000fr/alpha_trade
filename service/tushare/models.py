from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TusharePage:
    endpoint: str
    fields: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    http_status: int
    provider_code: int


@dataclass(frozen=True, slots=True)
class EndpointSpec:
    api_name: str
    symbol_fields: tuple[str, ...]
    date_fields: tuple[str, ...]
    entity_fields: tuple[str, ...]
    fields: tuple[str, ...]
    date_parameter_mode: str = "range"


ENDPOINT_SPECS: dict[str, EndpointSpec] = {
    "stock_basic": EndpointSpec(
        "stock_basic", ("ts_code",), ("list_date",), ("ts_code", "list_status"),
        ("ts_code", "symbol", "name", "area", "industry", "fullname", "enname", "cnspell", "market", "exchange", "curr_type", "list_status", "list_date", "delist_date", "is_hs", "act_name", "act_ent_type"),
        "none",
    ),
    "namechange": EndpointSpec(
        "namechange", ("ts_code",), ("start_date", "ann_date"), ("ts_code", "start_date", "name"),
        ("ts_code", "name", "start_date", "end_date", "ann_date", "change_reason"),
    ),
    "trade_cal": EndpointSpec(
        "trade_cal", (), ("cal_date",), ("exchange", "cal_date"),
        ("exchange", "cal_date", "is_open", "pretrade_date"),
    ),
    "daily": EndpointSpec(
        "daily", ("ts_code",), ("trade_date",), ("ts_code", "trade_date"),
        ("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"),
    ),
    "adj_factor": EndpointSpec(
        "adj_factor", ("ts_code",), ("trade_date",), ("ts_code", "trade_date"),
        ("ts_code", "trade_date", "adj_factor"),
    ),
    "suspend_d": EndpointSpec(
        "suspend_d", ("ts_code",), ("trade_date",), ("ts_code", "trade_date", "suspend_type"),
        ("ts_code", "trade_date", "suspend_timing", "suspend_type"),
    ),
    "stk_limit": EndpointSpec(
        "stk_limit", ("ts_code",), ("trade_date",), ("ts_code", "trade_date"),
        ("trade_date", "ts_code", "pre_close", "up_limit", "down_limit"),
    ),
    "index_daily": EndpointSpec(
        "index_daily", ("ts_code",), ("trade_date",), ("ts_code", "trade_date"),
        ("ts_code", "trade_date", "close", "open", "high", "low", "pre_close", "change", "pct_chg", "vol", "amount"),
    ),
    "index_weight": EndpointSpec(
        "index_weight", ("con_code",), ("trade_date",), ("index_code", "con_code", "trade_date"),
        ("index_code", "con_code", "trade_date", "weight"),
    ),
}


__all__ = ["ENDPOINT_SPECS", "EndpointSpec", "TusharePage"]
