"""Phase 5.3.c — Tests cross-check Yahoo dividends.

Réf. ``prompt/refactor/plan_phase5.md`` § 5.3.c.

Pas de dépendance ``yfinance`` requise : on stubbe le module via
:func:`monkeypatch.setattr` sur l'attribut ``_yf`` du provider.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from corporate_actions.cross_check_yahoo import (
    YahooDividendCrossCheckProvider,
    diff_dividends,
)
from corporate_actions.models import CaType, CorporateActionEvent


class _FakeSeries(dict):
    def items(self):  # type: ignore[override]
        return super().items()


class _FakeTicker:
    def __init__(self, dividends_map: dict[date, float]) -> None:
        self.dividends = _FakeSeries(dividends_map)


class _FakeYf:
    def __init__(self, mapping: dict[str, dict[date, float]]) -> None:
        self._mapping = mapping

    def Ticker(self, sym: str):  # noqa: N802 (mimic yfinance API)
        return _FakeTicker(self._mapping.get(sym.upper(), {}))


def test_yahoo_provider_returns_empty_when_yfinance_absent(monkeypatch) -> None:
    provider = YahooDividendCrossCheckProvider()
    monkeypatch.setattr(provider, "_import_yfinance", lambda: None)
    assert provider.fetch_events(symbols=["AAPL"], start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)) == []


def test_yahoo_provider_filters_by_date_range() -> None:
    provider = YahooDividendCrossCheckProvider()
    provider._yf = _FakeYf({"AAPL": {date(2025, 12, 1): 0.24, date(2026, 4, 15): 0.25, date(2027, 1, 1): 0.26}})
    events = provider.fetch_events(
        symbols=["AAPL"], start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
    )
    assert len(events) == 1
    assert events[0].ex_date == date(2026, 4, 15)
    assert events[0].amount_per_share == 0.25
    assert events[0].ca_type == CaType.CASH_DIVIDEND
    assert events[0].provider == "yahoo"


def test_yahoo_provider_swallows_exceptions() -> None:
    """Une exception sur un symbole ne doit pas casser l'ensemble du run."""
    class _BoomYf:
        def Ticker(self, sym: str):  # noqa: N802
            raise RuntimeError("network down")

    provider = YahooDividendCrossCheckProvider()
    provider._yf = _BoomYf()
    # Ne lève pas, retourne []
    assert provider.fetch_events(symbols=["AAPL"], start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)) == []


def _make_div(symbol: str, ex: date, amount: float, *, provider: str = "alpaca") -> CorporateActionEvent:
    return CorporateActionEvent(
        provider=provider,
        provider_event_id=f"{provider}:{symbol}:{ex}",
        symbol=symbol,
        ca_type=CaType.CASH_DIVIDEND,
        amount_per_share=amount,
        ex_date=ex,
    )


def test_diff_dividends_detects_missing_in_ingested() -> None:
    ingested: list[CorporateActionEvent] = []
    yahoo = [_make_div("AAPL", date(2026, 4, 15), 0.25, provider="yahoo")]
    anomalies = diff_dividends(ingested=ingested, yahoo=yahoo)
    assert len(anomalies) == 1
    assert anomalies[0]["kind"] == "missing_in_ingested"


def test_diff_dividends_detects_amount_mismatch() -> None:
    ingested = [_make_div("AAPL", date(2026, 4, 15), 0.24)]
    yahoo = [_make_div("AAPL", date(2026, 4, 15), 0.27, provider="yahoo")]
    anomalies = diff_dividends(ingested=ingested, yahoo=yahoo)
    assert any(a["kind"] == "amount_mismatch" for a in anomalies)


def test_diff_dividends_detects_missing_in_yahoo() -> None:
    ingested = [_make_div("AAPL", date(2026, 4, 15), 0.24)]
    yahoo: list[CorporateActionEvent] = []
    anomalies = diff_dividends(ingested=ingested, yahoo=yahoo)
    assert any(a["kind"] == "missing_in_yahoo" for a in anomalies)


def test_diff_dividends_clean_when_aligned() -> None:
    ingested = [_make_div("AAPL", date(2026, 4, 15), 0.24)]
    yahoo = [_make_div("AAPL", date(2026, 4, 15), 0.24, provider="yahoo")]
    assert diff_dividends(ingested=ingested, yahoo=yahoo) == []

