from __future__ import annotations

import contextlib
import importlib
import time
from collections.abc import Callable
from types import ModuleType
from typing import Any

from service.baostock.models import DAILY_FIELDS, INDEX_FIELDS, BaoStockPage


class BaoStockError(RuntimeError):
    pass


class BaoStockClient:
    """Adaptateur résilient autour du SDK BaoStock sans clé API."""

    def __init__(
        self,
        backend: ModuleType | Any | None = None,
        *,
        socket_timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        retry_delay_seconds: float = 2.0,
    ) -> None:
        if socket_timeout_seconds <= 0:
            raise ValueError("socket_timeout_seconds doit être positif")
        if max_attempts < 1:
            raise ValueError("max_attempts doit être positif")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds ne peut pas être négatif")
        self.backend = backend
        self.connected = False
        self.calls = 0
        self.socket_timeout_seconds = socket_timeout_seconds
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds

    def _is_real_backend(self) -> bool:
        return str(getattr(self.backend, "__name__", "")).startswith("baostock")

    def _default_socket(self) -> Any | None:
        if not self._is_real_backend():
            return None
        try:
            context = importlib.import_module("baostock.common.context")
            return getattr(context, "default_socket", None)
        except (ImportError, AttributeError):
            return None

    def _configure_socket_timeout(self) -> None:
        sock = self._default_socket()
        if sock is not None:
            sock.settimeout(self.socket_timeout_seconds)

    def _drop_connection(self) -> None:
        sock = self._default_socket()
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.shutdown(2)
            with contextlib.suppress(OSError):
                sock.close()
        self.connected = False

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
            self._drop_connection()
            raise BaoStockError(f"Connexion BaoStock refusée : {getattr(result, 'error_msg', '')}")
        self.connected = True
        self._configure_socket_timeout()

    def close(self) -> None:
        if self.connected and self.backend is not None:
            with contextlib.suppress(OSError, TimeoutError):
                self.backend.logout()
        self._drop_connection()

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

        # Le SDK masque les erreurs socket sur la page suivante et retourne False.
        # Une dernière page encore pleine signifie que la pagination n'a pas
        # reçu sa page terminale (même un total exact de 1000 reçoit ensuite
        # une page vide). Refuser cette réponse évite une série tronquée.
        data = getattr(result, "data", None)
        per_page = getattr(result, "per_page_count", None)
        try:
            page_size = int(per_page)
        except (TypeError, ValueError):
            page_size = 0
        if page_size > 0 and isinstance(data, list) and len(data) == page_size:
            raise BaoStockError(
                f"Pagination BaoStock incomplète pour {endpoint}: dernière page pleine"
            )

        response = {"error_code": code, "error_msg": getattr(result, "error_msg", ""), "rows": rows}
        return BaoStockPage(endpoint, fields, tuple(rows), request, response, provider_code=int(code))

    def _request(
        self,
        endpoint: str,
        request: dict[str, Any],
        operation: Callable[[], Any],
    ) -> BaoStockPage:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self.connect()
                return self._page(endpoint, operation(), request)
            except (BaoStockError, OSError, TimeoutError, UnicodeError) as exc:
                last_error = exc
                self._drop_connection()
                if attempt < self.max_attempts:
                    if self.retry_delay_seconds:
                        time.sleep(self.retry_delay_seconds)
                    continue
                raise BaoStockError(
                    f"BaoStock endpoint={endpoint} en échec après {self.max_attempts} tentative(s): {exc}"
                ) from exc
        raise BaoStockError(f"BaoStock endpoint={endpoint} sans résultat: {last_error}")

    def stock_basic(self) -> BaoStockPage:
        request = {"method": "query_stock_basic"}
        return self._request("stock_basic", request, lambda: self.backend.query_stock_basic())

    def trade_calendar(self, start_date: str, end_date: str) -> BaoStockPage:
        request = {"method": "query_trade_dates", "start_date": start_date, "end_date": end_date}
        return self._request(
            "trade_cal",
            request,
            lambda: self.backend.query_trade_dates(start_date=start_date, end_date=end_date),
        )

    def daily(self, symbol: str, start_date: str, end_date: str, *, index: bool = False) -> BaoStockPage:
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
        return self._request(
            endpoint,
            request,
            lambda: self.backend.query_history_k_data_plus(
                symbol,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3",
            ),
        )

    def adjustment_factors(self, symbol: str, start_date: str, end_date: str) -> BaoStockPage:
        request = {
            "method": "query_adjust_factor",
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
        }
        return self._request(
            "adj_factor",
            request,
            lambda: self.backend.query_adjust_factor(
                code=symbol,
                start_date=start_date,
                end_date=end_date,
            ),
        )


__all__ = ["BaoStockClient", "BaoStockError"]
