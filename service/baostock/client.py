from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

from service.baostock.models import DAILY_FIELDS, INDEX_FIELDS, BaoStockPage


class BaoStockError(RuntimeError):
    pass


class BaoStockClient:
    """Petit adaptateur testable autour du SDK BaoStock sans clé API."""

    def __init__(self, backend: ModuleType | Any | None = None) -> None:
        self.backend = backend
        self.connected = False
        self.calls = 0

    def connect(self) -> None:
        if self.connected:
            return
        if self.backend is None:
            try:
                self.backend = importlib.import_module("baostock")
            except ImportError as exc:
                raise BaoStockError(
                    "Dépendance BaoStock absente : installer requirements.txt"
                ) from exc
        result = self.backend.login()
        if str(getattr(result, "error_code", "")) != "0":
            raise BaoStockError(f"Connexion BaoStock refusée : {getattr(result, 'error_msg', '')}")
        self.connected = True

    def close(self) -> None:
        if self.connected and self.backend is not None:
            self.backend.logout()
        self.connected = False

    def __enter__(self) -> BaoStockClient:
        self.connect()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _page(self, endpoint: str, result: Any, request: dict[str, Any]) -> BaoStockPage:
        self.calls += 1
        code = str(getattr(result, "error_code", ""))
        if code != "0":
            raise BaoStockError(
                f"BaoStock endpoint={endpoint} code={code}: {getattr(result, 'error_msg', '')}"
            )
        fields = tuple(str(field) for field in getattr(result, "fields", []) or [])
        rows: list[dict[str, Any]] = []
        while result.next():
            values = list(result.get_row_data())
            if len(values) != len(fields):
                raise BaoStockError(f"Schéma BaoStock incompatible pour {endpoint}")
            rows.append(dict(zip(fields, values, strict=True)))
        response = {"error_code": code, "error_msg": getattr(result, "error_msg", ""), "rows": rows}
        return BaoStockPage(endpoint, fields, tuple(rows), request, response, provider_code=int(code))

    def stock_basic(self) -> BaoStockPage:
        self.connect()
        request = {"method": "query_stock_basic"}
        return self._page("stock_basic", self.backend.query_stock_basic(), request)

    def trade_calendar(self, start_date: str, end_date: str) -> BaoStockPage:
        self.connect()
        request = {"method": "query_trade_dates", "start_date": start_date, "end_date": end_date}
        result = self.backend.query_trade_dates(start_date=start_date, end_date=end_date)
        return self._page("trade_cal", result, request)

    def daily(self, symbol: str, start_date: str, end_date: str, *, index: bool = False) -> BaoStockPage:
        self.connect()
        endpoint = "index_daily" if index else "daily"
        fields = INDEX_FIELDS if index else DAILY_FIELDS
        request = {
            "method": "query_history_k_data_plus",
            "symbol": symbol,
            "fields": fields,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": "d",
            "adjustflag": "3",
        }
        result = self.backend.query_history_k_data_plus(
            symbol,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3",
        )
        return self._page(endpoint, result, request)

    def adjustment_factors(self, symbol: str, start_date: str, end_date: str) -> BaoStockPage:
        self.connect()
        request = {
            "method": "query_adjust_factor",
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
        }
        result = self.backend.query_adjust_factor(code=symbol, start_date=start_date, end_date=end_date)
        return self._page("adj_factor", result, request)


__all__ = ["BaoStockClient", "BaoStockError"]
