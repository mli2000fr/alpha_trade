from __future__ import annotations

import pytest

from service.yahoo import clientYahooFinance


class _FakeTicker:
    def __init__(self, *, info: dict[str, object] | None = None, fast_info: dict[str, object] | None = None) -> None:
        self.info = info or {}
        self.fast_info = fast_info or {}


class _FakeYFinance:
    def __init__(self, tickers: dict[str, _FakeTicker]) -> None:
        self._tickers = tickers

    def Ticker(self, symbol: str):  # noqa: N802 - API yfinance mimée
        return self._tickers[symbol]


def test_fetch_symbol_fundamentals_record_reads_sector_and_market_cap_from_yfinance(monkeypatch) -> None:
    fake_yf = _FakeYFinance(
        {
            "AAPL": _FakeTicker(
                info={"sector": "Technology"},
                fast_info={"market_cap": 3_123_000_000_000},
            )
        }
    )
    monkeypatch.setattr(clientYahooFinance, "_import_yfinance", lambda: fake_yf)

    record = clientYahooFinance.fetch_symbol_fundamentals_record("aapl")

    assert record["symbol"] == "AAPL"
    assert record["sector"] == "Technology"
    assert record["market_cap"] == pytest.approx(3_123_000_000_000.0)
    assert record["source"] == "Yahoo Finance"


def test_fetch_symbol_fundamentals_record_returns_none_for_blank_market_cap(monkeypatch) -> None:
    fake_yf = _FakeYFinance(
        {
            "MSFT": _FakeTicker(
                info={"sector": "Technology", "marketCap": ""},
                fast_info={},
            )
        }
    )
    monkeypatch.setattr(clientYahooFinance, "_import_yfinance", lambda: fake_yf)

    record = clientYahooFinance.fetch_symbol_fundamentals_record("MSFT")

    assert record["sector"] == "Technology"
    assert record["market_cap"] is None

