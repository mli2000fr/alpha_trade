"""Tests unitaires pour ``service/market/macro_providers.py``."""
from __future__ import annotations

from datetime import date

import pytest

from service.market.macro_providers import (
    CompositeMacroProvider,
    EodhdMacroProvider,
    StooqMacroProvider,
    build_default_macro_provider,
)


# --- Stooq ------------------------------------------------------------------


class _FakeStooqBars:
    """Helper qui imite ``service.stooq.clientStooq.fetch_daily_bars``."""

    def __init__(self, mapping):
        self.mapping = mapping
        self.calls: list[tuple[str, date, date]] = []

    def __call__(self, symbol, *, start=None, end=None, timeout=10):
        self.calls.append((symbol, start, end))
        return list(self.mapping.get(symbol, []))


def test_stooq_provider_returns_last_close_and_caches(monkeypatch):
    bars = {
        "^vix": [
            {"date": date(2025, 4, 14), "close": 18.0},
            {"date": date(2025, 4, 15), "close": 22.5},
        ],
        "^vix9d": [
            {"date": date(2025, 4, 15), "close": 26.0},
        ],
        "^tnx": [
            {"date": date(2025, 4, 9), "close": 4.20},
            {"date": date(2025, 4, 10), "close": 4.25},
            {"date": date(2025, 4, 11), "close": 4.30},
            {"date": date(2025, 4, 14), "close": 4.40},
            {"date": date(2025, 4, 15), "close": 4.50},
        ],
    }
    fake = _FakeStooqBars(bars)
    monkeypatch.setattr("service.stooq.clientStooq.fetch_daily_bars", fake)

    p = StooqMacroProvider()
    d = date(2025, 4, 15)
    assert p.get_vix_close(d) == pytest.approx(22.5)
    assert p.get_vix_short_term_close(d) == pytest.approx(26.0)
    history = p.get_us10y_history(d, lookback_days=5)
    assert history is not None and history[0] == pytest.approx(4.20)
    assert history[-1] == pytest.approx(4.50)

    # Cache : 2e appel sur même date ne re-frappe pas l'API
    n_calls = len(fake.calls)
    p.get_vix_close(d)
    p.get_us10y_history(d, lookback_days=5)
    assert len(fake.calls) == n_calls


def test_stooq_provider_returns_none_on_provider_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("service.stooq.clientStooq.fetch_daily_bars", boom)
    p = StooqMacroProvider()
    assert p.get_vix_close(date(2025, 4, 15)) is None
    assert p.get_us10y_history(date(2025, 4, 15), lookback_days=5) is None


# --- EODHD ------------------------------------------------------------------


def test_eodhd_provider_normalises_payload(monkeypatch):
    payload_vix = [
        {"date": "2025-04-14", "close": 18.1},
        {"date": "2025-04-15", "close": 22.4},
    ]
    payload_y10 = [
        {"date": "2025-04-09", "close": 4.20},
        {"date": "2025-04-10", "close": 4.25},
        {"date": "2025-04-11", "close": 4.30},
        {"date": "2025-04-14", "close": 4.40},
        {"date": "2025-04-15", "close": 4.50},
    ]

    def fake_fetch(symbol, *, start=None, end=None, **kwargs):
        if symbol == "VIX.INDX":
            return payload_vix
        if symbol == "US10Y.INDX":
            return payload_y10
        return []

    monkeypatch.setattr("service.eodhd.clientEodhd.fetch_eod", fake_fetch)
    p = EodhdMacroProvider()
    d = date(2025, 4, 15)
    assert p.get_vix_close(d) == pytest.approx(22.4)
    history = p.get_us10y_history(d, lookback_days=5)
    assert history is not None and len(history) == 5
    assert history[-1] == pytest.approx(4.50)


# --- Composite + factory ----------------------------------------------------


def test_composite_uses_first_non_none():
    class P1:
        def get_vix_close(self, d): return None
        def get_vix_short_term_close(self, d): return None
        def get_us10y_history(self, d, n): return None

    class P2:
        def get_vix_close(self, d): return 19.5
        def get_vix_short_term_close(self, d): return 20.0
        def get_us10y_history(self, d, n): return [4.0, 4.1, 4.2]

    cp = CompositeMacroProvider([P1(), P2()])
    d = date(2025, 4, 15)
    assert cp.get_vix_close(d) == pytest.approx(19.5)
    assert cp.get_vix_short_term_close(d) == pytest.approx(20.0)
    assert cp.get_us10y_history(d, 3) == [4.0, 4.1, 4.2]


def test_factory_returns_none_when_disabled():
    assert build_default_macro_provider({"market_regimes": {"macro_provider": "none"}}) is None


def test_factory_default_is_composite_with_stooq(monkeypatch):
    monkeypatch.delenv("EODHD_API_TOKEN", raising=False)
    monkeypatch.delenv("EODHD_TOKEN", raising=False)
    p = build_default_macro_provider({})
    assert isinstance(p, CompositeMacroProvider)
    # Sans clé EODHD, un seul provider (Stooq)
    assert len(p._providers) == 1
    assert isinstance(p._providers[0], StooqMacroProvider)


def test_factory_explicit_eodhd_overrides_symbol():
    p = build_default_macro_provider({
        "market_regimes": {
            "macro_provider": "eodhd",
            "vix": {"symbol": "VIX"},
            "yields": {"symbol_10y": "US10Y"},
        }
    })
    assert isinstance(p, EodhdMacroProvider)
    assert p._symbols["vix"] == "VIX.INDX"
    assert p._symbols["us10y"] == "US10Y.INDX"


def test_eodhd_default_short_vix_symbol_is_vix9d():
    p = EodhdMacroProvider()
    assert p._symbols["vix_short"] == "VIX9D.INDX"


