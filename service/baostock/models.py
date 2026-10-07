from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BaoStockPage:
    endpoint: str
    fields: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    http_status: int = 200
    provider_code: int = 0


DAILY_FIELDS = (
    "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,"
    "tradestatus,pctChg,isST"
)
INDEX_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,pctChg"


__all__ = ["BaoStockPage", "DAILY_FIELDS", "INDEX_FIELDS"]
