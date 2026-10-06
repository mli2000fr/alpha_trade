from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from service.baostock.adapters import adapt_staging_row
from service.baostock.client import BaoStockClient, BaoStockError
from service.baostock.symbols import parse_baostock_symbol


class FakeResult:
    def __init__(self, fields: list[str], rows: list[list[str]], code: str = "0") -> None:
        self.fields = fields
        self.rows = rows
        self.error_code = code
        self.error_msg = "fake error" if code != "0" else "success"
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeBackend:
    def login(self) -> FakeResult:
        return FakeResult([], [])

    def logout(self) -> FakeResult:
        return FakeResult([], [])

    def query_stock_basic(self) -> FakeResult:
        return FakeResult(
            ["code", "code_name", "ipoDate", "outDate", "type", "status"],
            [["sh.600000", "浦发银行", "1999-11-10", "", "1", "1"]],
        )

    def query_trade_dates(self, **_kwargs: Any) -> FakeResult:
        return FakeResult(["calendar_date", "is_trading_day"], [["2025-01-02", "1"]])

    def query_history_k_data_plus(self, *_args: Any, **_kwargs: Any) -> FakeResult:
        return FakeResult(
            ["date", "code", "open", "high", "low", "close", "preclose", "volume", "amount", "tradestatus", "isST"],
            [["2025-01-02", "sh.600000", "10", "11", "9", "10.5", "10", "100", "1000", "1", "0"]],
        )

    def query_adjust_factor(self, **_kwargs: Any) -> FakeResult:
        return FakeResult(
            ["code", "dividOperateDate", "foreAdjustFactor", "backAdjustFactor", "adjustFactor"],
            [["sh.600000", "2025-01-02", "1", "1", "1"]],
        )


def test_baostock_symbol_supports_main_star_and_chinext() -> None:
    assert parse_baostock_symbol("sh.600000").board_code == "SH_MAIN"
    assert parse_baostock_symbol("sh.688001").board_code == "STAR"
    assert parse_baostock_symbol("sz.300750").board_code == "CHINEXT"
    with pytest.raises(ValueError, match="BaoStock"):
        parse_baostock_symbol("bj.430047")


def test_baostock_client_has_no_token_and_returns_structured_pages() -> None:
    client = BaoStockClient(FakeBackend())
    client.connect()
    assert client.stock_basic().rows[0]["code"] == "sh.600000"
    assert client.trade_calendar("2025-01-01", "2025-01-03").rows[0]["is_trading_day"] == "1"
    assert client.daily("sh.600000", "2025-01-01", "2025-01-03").rows[0]["close"] == "10.5"
    assert client.adjustment_factors("sh.600000", "2025-01-01", "2025-01-03").rows
    client.close()


def test_baostock_client_surfaces_provider_errors() -> None:
    backend = FakeBackend()
    backend.login = lambda: FakeResult([], [], code="1001")  # type: ignore[method-assign]
    with pytest.raises(BaoStockError, match="Connexion"):
        BaoStockClient(backend).connect()


def test_baostock_daily_adapter_preserves_status_and_raw_payload() -> None:
    row = {
        "date": "2025-01-02",
        "code": "sh.688001",
        "open": "10",
        "high": "11",
        "low": "9",
        "close": "10.5",
        "preclose": "10",
        "volume": "100",
        "amount": "1000",
        "tradestatus": "0",
        "isST": "1",
    }
    adapted = adapt_staging_row(
        "daily",
        row,
        run_id="run",
        raw_id=None,
        observed_at=datetime(2025, 1, 3),
        available_at=datetime(2025, 1, 3),
    )
    assert adapted["provider"] == "baostock"
    assert adapted["board_code"] == "STAR"
    assert adapted["status_code"] == "SUSPENDED|ST"
    assert adapted["close_price"] == pytest.approx(10.5)
    assert '"code":"sh.688001"' in adapted["raw_payload"]


def test_cn_batch_defaults_to_free_provider() -> None:
    payload = yaml.safe_load(Path("batch_cn.yaml").read_text(encoding="utf-8"))
    assert payload["defaults"]["provider"] == "baostock"
    assert "token_env" not in payload["defaults"]
    assert payload["cn_tushare_optional"]["enabled"] is False
    assert payload["cn_akshare_enrichment"]["enabled"] is False

class RetryBackend(FakeBackend):
    def __init__(self) -> None:
        self.daily_calls = 0
        self.login_calls = 0

    def login(self) -> FakeResult:
        self.login_calls += 1
        return FakeResult([], [])

    def query_history_k_data_plus(self, *_args: Any, **_kwargs: Any) -> FakeResult:
        self.daily_calls += 1
        if self.daily_calls == 1:
            return FakeResult([], [], code="10002007")
        return super().query_history_k_data_plus(*_args, **_kwargs)


class TruncatedPaginationResult(FakeResult):
    def __init__(self) -> None:
        rows = [
            ["2025-01-02", "sh.600000", "10", "11", "9", "10.5", "10", "100", "1000", "1", "0"],
            ["2025-01-03", "sh.600000", "10.5", "11", "10", "10.8", "10.5", "100", "1000", "1", "0"],
        ]
        super().__init__(
            ["date", "code", "open", "high", "low", "close", "preclose", "volume", "amount", "tradestatus", "isST"],
            rows,
        )
        self.data = rows
        self.per_page_count = len(rows)


def test_baostock_client_reconnects_after_transient_provider_error() -> None:
    backend = RetryBackend()
    client = BaoStockClient(backend, max_attempts=2, retry_delay_seconds=0)
    page = client.daily("sh.600000", "2025-01-01", "2025-01-03")
    assert page.rows
    assert backend.daily_calls == 2
    assert backend.login_calls == 2


def test_baostock_client_rejects_a_silently_truncated_last_page() -> None:
    backend = FakeBackend()
    backend.query_history_k_data_plus = lambda *_args, **_kwargs: TruncatedPaginationResult()  # type: ignore[method-assign]
    client = BaoStockClient(backend, max_attempts=1, retry_delay_seconds=0)
    with pytest.raises(BaoStockError, match="Pagination BaoStock incomplète"):
        client.daily("sh.600000", "2025-01-01", "2025-01-03")


def test_baostock_client_rejects_invalid_resilience_configuration() -> None:
    with pytest.raises(ValueError, match="socket_timeout_seconds"):
        BaoStockClient(FakeBackend(), socket_timeout_seconds=0)
    with pytest.raises(ValueError, match="max_attempts"):
        BaoStockClient(FakeBackend(), max_attempts=0)

def test_explicit_symbols_bypass_the_full_stock_master_query() -> None:
    from service.baostock.ingestion import BaoStockIngestionService

    class NoMasterBackend(FakeBackend):
        def query_stock_basic(self) -> FakeResult:
            raise AssertionError("stock_basic ne doit pas être appelé pour un manifeste explicite")

    service = BaoStockIngestionService(
        client=BaoStockClient(NoMasterBackend()),
        engine=None,  # type: ignore[arg-type]
        run_id="run",
        symbols=["sz.000002", "sh.600000", "sh.600000"],
    )
    assert service.equity_symbols(include_inactive=True) == ["sh.600000", "sz.000002"]

def test_historical_windows_avoid_baostock_pagination() -> None:
    from service.baostock.ingestion import historical_windows

    windows = historical_windows(
        datetime(2018, 5, 10).date(),
        datetime(2025, 12, 31).date(),
    )
    assert windows == [
        (datetime(2018, 5, 10).date(), datetime(2020, 12, 31).date()),
        (datetime(2021, 1, 1).date(), datetime(2023, 12, 31).date()),
        (datetime(2024, 1, 1).date(), datetime(2025, 12, 31).date()),
    ]
    assert all((end - start).days < 1100 for start, end in windows)
