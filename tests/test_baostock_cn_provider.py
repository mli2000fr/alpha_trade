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
