from __future__ import annotations

from datetime import datetime

import pytest

from service.tushare.adapters import adapt_staging_row, parse_provider_date, payload_hash
from service.tushare.symbols import parse_tushare_symbol


@pytest.mark.parametrize(
    ("value", "market", "board"),
    [
        ("000001.SZ", "CN_A", "SZ_MAIN"),
        ("300750.SZ", "CN_A", "CHINEXT"),
        ("688981.SH", "CN_A", "STAR"),
        ("600000.SH", "CN_A", "SH_MAIN"),
        ("430047.BJ", "CN_BJ", "BSE"),
    ],
)
def test_symbol_preserves_leading_zeros_and_board(value: str, market: str, board: str) -> None:
    symbol = parse_tushare_symbol(value.lower())
    assert symbol.provider_symbol == value
    assert symbol.local_symbol == value[:6]
    assert symbol.market_code == market
    assert symbol.board_code == board


def test_invalid_symbol_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_tushare_symbol("1.SZ")


def test_daily_adapter_keeps_chinese_payload_and_lineage() -> None:
    observed = datetime(2026, 9, 21, 10, 0)
    raw = {
        "ts_code": "000001.SZ",
        "trade_date": "20260918",
        "open": 10.1,
        "high": 10.8,
        "low": 9.9,
        "close": 10.6,
        "pre_close": 10.0,
        "vol": 1234.5,
        "amount": 9999.0,
        "name": "平安银行",
    }
    row = adapt_staging_row(
        "daily",
        raw,
        run_id="run-1",
        raw_id=None,
        observed_at=observed,
        available_at=observed,
    )
    assert row["provider_symbol"] == "000001.SZ"
    assert row["business_date"].isoformat() == "2026-09-18"
    assert row["market_code"] == "CN_A"
    assert "平安银行" in row["raw_payload"]
    assert len(row["payload_hash"]) == 64


def test_bse_calendar_row_keeps_cn_bj_scope() -> None:
    observed = datetime(2026, 9, 21, 10, 0)
    row = adapt_staging_row(
        "trade_cal",
        {"exchange": "BSE", "cal_date": "20260921", "is_open": 1},
        run_id="run-1",
        raw_id=None,
        observed_at=observed,
        available_at=observed,
    )
    assert row["market_code"] == "CN_BJ"


def test_payload_hash_is_deterministic_and_detects_provider_correction() -> None:
    assert payload_hash({"b": 2, "a": 1}) == payload_hash({"a": 1, "b": 2})
    assert payload_hash({"close": 10}) != payload_hash({"close": 11})


def test_provider_dates_are_strict() -> None:
    assert parse_provider_date("20260921").isoformat() == "2026-09-21"
    assert parse_provider_date("") is None
    with pytest.raises(ValueError):
        parse_provider_date("2026/09/21")
