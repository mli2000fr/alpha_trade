"""Tests Phase 7.3 — cross-check Stooq (audit_global §7.3)."""
from __future__ import annotations

from datetime import date

import pytest

from dataIntegrityEngine.cross_check_stooq import compare_with_stooq
from service.stooq import clientStooq


def test_parse_csv_basic() -> None:
    raw = "Date,Open,High,Low,Close,Volume\n2026-04-15,100.0,101.5,99.5,101.0,1000000\n"
    bars = clientStooq._parse_csv(raw)
    assert len(bars) == 1
    assert bars[0]["close"] == 101.0
    assert bars[0]["volume"] == 1000000.0
    assert bars[0]["date"] == date(2026, 4, 15)


def test_parse_csv_empty_or_no_data() -> None:
    assert clientStooq._parse_csv("") == []
    assert clientStooq._parse_csv("No data") == []


def test_compare_with_stooq_close_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    target_date = date.today()
    fake = [{"date": target_date, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1_000_000.0}]
    monkeypatch.setattr(
        "dataIntegrityEngine.cross_check_stooq.fetch_daily_bars",
        lambda symbol, **kw: fake,
    )
    ingested = {"FAKE": [{"date": target_date, "close": 110.0, "volume": 990_000.0}]}
    anomalies = compare_with_stooq(ingested, lookback_days=5, today=target_date)
    kinds = {a["kind"] for a in anomalies}
    assert "close_mismatch" in kinds


def test_compare_with_stooq_volume_ratio_low(monkeypatch: pytest.MonkeyPatch) -> None:
    target_date = date.today()
    fake = [{"date": target_date, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 10_000_000.0}]
    monkeypatch.setattr(
        "dataIntegrityEngine.cross_check_stooq.fetch_daily_bars",
        lambda symbol, **kw: fake,
    )
    ingested = {"FAKE": [{"date": target_date, "close": 100.5, "volume": 200_000.0}]}
    anomalies = compare_with_stooq(ingested, lookback_days=5, today=target_date)
    kinds = {a["kind"] for a in anomalies}
    assert "volume_ratio_low" in kinds


def test_compare_with_stooq_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    target_date = date.today()
    monkeypatch.setattr(
        "dataIntegrityEngine.cross_check_stooq.fetch_daily_bars",
        lambda symbol, **kw: [],
    )
    ingested = {"FAKE": [{"date": target_date, "close": 100.0, "volume": 1000.0}]}
    anomalies = compare_with_stooq(ingested, lookback_days=5, today=target_date)
    assert any(a["kind"] == "missing_in_stooq" for a in anomalies)


def test_stooq_symbol_normalisation() -> None:
    assert clientStooq._stooq_symbol("AAPL") == "aapl.us"
    assert clientStooq._stooq_symbol("aapl.us") == "aapl.us"

