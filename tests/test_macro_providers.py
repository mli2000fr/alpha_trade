"""Tests unitaires pour ``service/market/macro_providers.py``."""
from __future__ import annotations

import logging
from datetime import date

import pytest
from sqlalchemy import create_engine

from service.market.macro_providers import (
    CompositeMacroProvider,
    EodhdMacroProvider,
    FredMacroProvider,
    MACRO_PIT_MODE_J_MINUS_1_STRICT,
    StooqMacroProvider,
    TableFirstMacroProvider,
    build_default_macro_provider,
    populate_macro_indicators_table,
    recompute_macro_regime_table,
    resolve_macro_pit_mode,
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


def test_eodhd_provider_logs_positive_success_for_vix9d(monkeypatch, caplog):
    payload_vix_short = [
        {"date": "2025-04-14", "close": 14.05},
        {"date": "2025-04-15", "close": 14.15},
    ]
    calls: list[str] = []

    def fake_fetch(symbol, *, start=None, end=None, **kwargs):
        calls.append(symbol)
        if symbol == "VIX9D.INDX":
            return payload_vix_short
        return []

    monkeypatch.setattr("service.eodhd.clientEodhd.fetch_eod", fake_fetch)
    p = EodhdMacroProvider()
    d = date(2025, 4, 15)

    with caplog.at_level(logging.INFO, logger="service.market.macro_providers"):
        assert p.get_vix_short_term_close(d) == pytest.approx(14.15)
        assert p.get_vix_short_term_close(d) == pytest.approx(14.15)

    success_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO and "EodhdMacroProvider: fetch VIX9D.INDX ok" in record.getMessage()
    ]
    assert len(success_messages) == 1
    assert "key=vix_short" in success_messages[0]
    assert "last_close=14.1500" in success_messages[0]
    assert calls == ["VIX9D.INDX"]


def test_eodhd_provider_logs_positive_success_for_vix(monkeypatch, caplog):
    payload_vix = [
        {"date": "2025-04-14", "close": 18.10},
        {"date": "2025-04-15", "close": 22.40},
    ]

    def fake_fetch(symbol, *, start=None, end=None, **kwargs):
        if symbol == "VIX.INDX":
            return payload_vix
        return []

    monkeypatch.setattr("service.eodhd.clientEodhd.fetch_eod", fake_fetch)
    p = EodhdMacroProvider()

    with caplog.at_level(logging.INFO, logger="service.market.macro_providers"):
        assert p.get_vix_close(date(2025, 4, 15)) == pytest.approx(22.4)

    success_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO and "EodhdMacroProvider: fetch VIX.INDX ok" in record.getMessage()
    ]
    assert len(success_messages) == 1
    assert "key=vix" in success_messages[0]
    assert "last_close=22.4000" in success_messages[0]


def test_eodhd_provider_does_not_log_positive_success_on_empty_payload(monkeypatch, caplog):
    def fake_fetch(symbol, *, start=None, end=None, **kwargs):
        return []

    monkeypatch.setattr("service.eodhd.clientEodhd.fetch_eod", fake_fetch)
    p = EodhdMacroProvider()

    with caplog.at_level(logging.INFO, logger="service.market.macro_providers"):
        assert p.get_vix_short_term_close(date(2025, 4, 15)) is None

    assert not [
        record for record in caplog.records
        if record.levelno == logging.INFO and "EodhdMacroProvider: fetch VIX9D.INDX ok" in record.getMessage()
    ]


def test_eodhd_provider_exposes_macro_source_summary(monkeypatch):
    payload_vix = [{"date": "2025-04-15", "close": 22.4}]
    payload_vix_short = [{"date": "2025-04-15", "close": 14.15}]

    def fake_fetch(symbol, *, start=None, end=None, **kwargs):
        if symbol == "VIX.INDX":
            return payload_vix
        if symbol == "VIX9D.INDX":
            return payload_vix_short
        return []

    monkeypatch.setattr("service.eodhd.clientEodhd.fetch_eod", fake_fetch)
    p = EodhdMacroProvider()
    d = date(2025, 4, 15)

    assert p.get_vix_close(d) == pytest.approx(22.4)
    assert p.get_vix_short_term_close(d) == pytest.approx(14.15)
    assert p.get_macro_source_summary() == {
        "source_effective": "eodhd",
        "source_by_signal": {"vix": "eodhd", "vix_short": "eodhd"},
    }


def test_fred_provider_normalises_payload_and_exposes_source(monkeypatch):
    payload = [
        {"date": "2025-04-09", "value": "4.20"},
        {"date": "2025-04-10", "value": "4.25"},
        {"date": "2025-04-11", "value": "."},
        {"date": "2025-04-14", "value": "4.40"},
        {"date": "2025-04-15", "value": "4.50"},
    ]

    def fake_fetch(series_id, *, start=None, end=None, api_key_env="KEY_FRED", **kwargs):
        assert series_id == "DGS10"
        assert api_key_env == "KEY_FRED"
        return payload

    monkeypatch.setattr("service.fred.clientFred.fetch_series_observations", fake_fetch)
    p = FredMacroProvider()
    d = date(2025, 4, 15)

    history = p.get_us10y_history(d, lookback_days=4)

    assert history == pytest.approx([4.20, 4.25, 4.40, 4.50])
    assert p.get_macro_source_summary() == {
        "source_effective": "fred",
        "source_by_signal": {"yield_10y": "fred"},
    }


def test_fred_provider_logs_positive_success_for_10y(monkeypatch, caplog):
    payload = [
        {"date": "2025-04-09", "value": "4.20"},
        {"date": "2025-04-10", "value": "4.25"},
        {"date": "2025-04-14", "value": "4.40"},
        {"date": "2025-04-15", "value": "4.50"},
    ]

    def fake_fetch(series_id, *, start=None, end=None, api_key_env="KEY_FRED", **kwargs):
        assert series_id == "DGS10"
        return payload

    monkeypatch.setattr("service.fred.clientFred.fetch_series_observations", fake_fetch)
    p = FredMacroProvider()

    with caplog.at_level(logging.INFO, logger="service.market.macro_providers"):
        history = p.get_us10y_history(date(2025, 4, 15), lookback_days=4)

    assert history == pytest.approx([4.20, 4.25, 4.40, 4.50])
    success_messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO and "FredMacroProvider: fetch DGS10 ok" in record.getMessage()
    ]
    assert len(success_messages) == 1
    assert "key=us10y" in success_messages[0]
    assert "last_close=4.5000" in success_messages[0]


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


def test_composite_exposes_mixed_macro_source_summary():
    class P1:
        source_name = "stooq"

        def get_vix_close(self, d): return 19.5
        def get_vix_short_term_close(self, d): return None
        def get_us10y_history(self, d, n): return None

    class P2:
        source_name = "eodhd"

        def get_vix_close(self, d): return None
        def get_vix_short_term_close(self, d): return 20.0
        def get_us10y_history(self, d, n): return None

    cp = CompositeMacroProvider([P1(), P2()])
    d = date(2025, 4, 15)

    assert cp.get_vix_close(d) == pytest.approx(19.5)
    assert cp.get_vix_short_term_close(d) == pytest.approx(20.0)
    assert cp.get_macro_source_summary() == {
        "source_effective": "mixed",
        "source_by_signal": {"vix": "stooq", "vix_short": "eodhd"},
    }


def test_factory_returns_none_when_disabled():
    assert build_default_macro_provider({"market_regimes": {"macro_provider": "none"}}) is None


def test_factory_default_is_composite_with_stooq(monkeypatch):
    monkeypatch.delenv("EODHD_API_TOKEN", raising=False)
    monkeypatch.delenv("EODHD_TOKEN", raising=False)
    p = build_default_macro_provider({})
    assert isinstance(p, TableFirstMacroProvider)
    assert isinstance(p._provider, CompositeMacroProvider)
    # Sans clé EODHD, un seul provider (Stooq)
    assert len(p._provider._providers) == 1
    assert isinstance(p._provider._providers[0], StooqMacroProvider)


def test_factory_can_enable_strict_j_minus_1_for_backtests(monkeypatch):
    monkeypatch.delenv("EODHD_API_TOKEN", raising=False)
    monkeypatch.delenv("EODHD_TOKEN", raising=False)

    p = build_default_macro_provider(
        {"market_regimes": {"macro_pit_mode_backtest": "j_minus_1_strict"}},
        execution_context="backtest",
    )

    assert isinstance(p, TableFirstMacroProvider)
    assert p._strict_before is True
    assert resolve_macro_pit_mode(
        {"market_regimes": {"macro_pit_mode_backtest": "j_minus_1_strict"}},
        execution_context="backtest",
    ) == MACRO_PIT_MODE_J_MINUS_1_STRICT


def test_main_config_uses_eodhd_macro_provider() -> None:
    from common.config_loader import load_config

    cfg = load_config()

    assert cfg["market_regimes"]["macro_provider"] == "eodhd"
    assert cfg["market_regimes"]["yields"]["provider"] == "fred"
    assert cfg["market_regimes"]["sentiment_circuit_breaker"]["enabled"] is True
    assert cfg["fred"]["api_key_env"] == "KEY_FRED"


def test_factory_explicit_eodhd_overrides_symbol():
    p = build_default_macro_provider({
        "market_regimes": {
            "macro_provider": "eodhd",
            "vix": {"symbol": "VIX"},
            "yields": {"symbol_10y": "US10Y"},
        }
    })
    assert isinstance(p, TableFirstMacroProvider)
    assert isinstance(p._provider, EodhdMacroProvider)
    assert p._provider._symbols["vix"] == "VIX.INDX"
    assert p._provider._symbols["us10y"] == "US10Y.INDX"


def test_eodhd_default_short_vix_symbol_is_vix9d():
    p = EodhdMacroProvider()
    assert p._symbols["vix_short"] == "VIX9D.INDX"


def test_factory_routes_10y_to_fred_when_requested(monkeypatch):
    monkeypatch.setenv("KEY_FRED", "fred-test-token")
    monkeypatch.setattr("service.market.macro_providers.load_macro_indicator_daily_asof", lambda **kwargs: None)
    monkeypatch.setattr("service.market.macro_providers.load_macro_indicator_history_asof", lambda **kwargs: None)

    def fake_eodhd_fetch(symbol, *, start=None, end=None, **kwargs):
        if symbol == "VIX.INDX":
            return [{"date": "2025-04-15", "close": 22.4}]
        if symbol == "VIX9D.INDX":
            return [{"date": "2025-04-15", "close": 14.15}]
        if symbol == "US10Y.INDX":
            return [{"date": "2025-04-15", "close": 9.99}]
        return []

    def fake_fred_fetch(series_id, *, start=None, end=None, api_key_env="KEY_FRED", **kwargs):
        assert series_id == "DGS10"
        assert api_key_env == "KEY_FRED"
        return [
            {"date": "2025-04-09", "value": "4.20"},
            {"date": "2025-04-10", "value": "4.25"},
            {"date": "2025-04-14", "value": "4.40"},
            {"date": "2025-04-15", "value": "4.50"},
        ]

    monkeypatch.setattr("service.eodhd.clientEodhd.fetch_eod", fake_eodhd_fetch)
    monkeypatch.setattr("service.fred.clientFred.fetch_series_observations", fake_fred_fetch)

    p = build_default_macro_provider({
        "market_regimes": {
            "macro_provider": "eodhd",
            "vix": {"symbol": "VIX.INDX", "short_symbol": "VIX9D.INDX"},
            "yields": {"provider": "fred", "fred_series_10y": "DGS10", "symbol_10y": "US10Y"},
        },
        "fred": {"api_key_env": "KEY_FRED", "series_10y": "DGS10"},
    })
    d = date(2025, 4, 15)

    assert p is not None
    assert p.get_vix_close(d) == pytest.approx(22.4)
    assert p.get_vix_short_term_close(d) == pytest.approx(14.15)
    assert p.get_us10y_history(d, lookback_days=4) == pytest.approx([4.20, 4.25, 4.40, 4.50])
    assert p.get_macro_source_summary() == {
        "source_effective": "mixed",
        "source_by_signal": {"vix": "eodhd", "vix_short": "eodhd", "yield_10y": "fred"},
    }


def test_table_first_provider_uses_database_before_network(monkeypatch):
    from database.macro_indicators import get_macro_indicators_daily_table, persist_macro_indicator_daily

    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)
        persist_macro_indicator_daily(
            trade_date=date(2025, 4, 14),
            ten_y=4.40,
            engine=engine,
        )
        persist_macro_indicator_daily(
            trade_date=date(2025, 4, 15),
            vix=22.4,
            vix9d=14.15,
            ten_y=4.50,
            engine=engine,
        )

        calls = {"vix": 0, "vix_short": 0, "yield": 0}

        class _FallbackProvider:
            source_name = "eodhd"

            def get_vix_close(self, trade_date):
                calls["vix"] += 1
                return 99.0

            def get_vix_short_term_close(self, trade_date):
                calls["vix_short"] += 1
                return 88.0

            def get_us10y_history(self, trade_date, lookback_days):
                calls["yield"] += 1
                return [1.0, 2.0]

        provider = TableFirstMacroProvider(_FallbackProvider(), engine=engine)

        assert provider.get_vix_close(date(2025, 4, 15)) == pytest.approx(22.4)
        assert provider.get_vix_short_term_close(date(2025, 4, 15)) == pytest.approx(14.15)
        assert provider.get_us10y_history(date(2025, 4, 15), lookback_days=2) == pytest.approx([4.40, 4.50])
        assert provider.get_macro_source_summary() == {
            "source_effective": "db_cache",
            "source_by_signal": {"vix": "db_cache", "vix_short": "db_cache", "yield_10y": "db_cache"},
        }
        assert calls == {"vix": 0, "vix_short": 0, "yield": 0}
    finally:
        engine.dispose()


def test_table_first_provider_persists_fallback_value() -> None:
    from database.macro_indicators import (
        get_macro_indicators_daily_table,
        load_macro_indicator_daily_asof,
    )

    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)

        class _FallbackProvider:
            source_name = "fred"

            def get_vix_close(self, trade_date):
                return None

            def get_vix_short_term_close(self, trade_date):
                return None

            def get_us10y_history(self, trade_date, lookback_days):
                return [4.20, 4.25, 4.40, 4.50]

        provider = TableFirstMacroProvider(_FallbackProvider(), engine=engine)

        assert provider.get_us10y_history(date(2025, 4, 15), lookback_days=4) == pytest.approx([4.20, 4.25, 4.40, 4.50])
        row = load_macro_indicator_daily_asof(trade_date=date(2025, 4, 15), engine=engine)
        assert row is not None
        assert row["trade_date"] == date(2025, 4, 15)
        assert row["vix"] is None
        assert row["vix9d"] is None
        assert row["ten_y"] == 4.5
        assert row["mode"] is None
        assert row["risk_multiplier"] is None
        assert row["effective_max_positions"] is None
        assert row["allow_new_entries"] is None
        assert row["vix_curve_inverted"] is None
        assert row["yield_10y_5d_pct"] is None
        assert row["sentiment_score"] is None
        assert row["sentiment_level"] is None
        assert row["sentiment_source"] is None
        assert provider.get_macro_source_summary() == {
            "source_effective": "fred",
            "source_by_signal": {"yield_10y": "fred"},
        }
    finally:
        engine.dispose()


def test_table_first_provider_uses_previous_session_in_strict_j_minus_1(monkeypatch) -> None:
    from database.macro_indicators import get_macro_indicators_daily_table, load_macro_indicator_daily_asof

    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)
        requested_dates: list[date] = []

        class _FallbackProvider:
            source_name = "eodhd"

            def get_vix_close(self, trade_date):
                requested_dates.append(trade_date)
                return 18.25

            def get_vix_short_term_close(self, trade_date):
                return None

            def get_us10y_history(self, trade_date, lookback_days):
                return None

        monkeypatch.setattr("service.market.macro_providers.getLastDateMarche", lambda ref_date: date(2025, 4, 14))
        provider = TableFirstMacroProvider(_FallbackProvider(), engine=engine, strict_before=True)

        assert provider.get_vix_close(date(2025, 4, 15)) == pytest.approx(18.25)
        assert requested_dates == [date(2025, 4, 14)]
        row = load_macro_indicator_daily_asof(
            trade_date=date(2025, 4, 15),
            engine=engine,
            strict_before=True,
        )
        assert row is not None
        assert row["trade_date"] == date(2025, 4, 14)
        assert row["vix"] == 18.25
        assert row["vix9d"] is None
        assert row["ten_y"] is None
        assert row["mode"] is None
        assert row["risk_multiplier"] is None
        assert row["effective_max_positions"] is None
        assert row["allow_new_entries"] is None
        assert row["vix_curve_inverted"] is None
        assert row["yield_10y_5d_pct"] is None
        assert row["sentiment_score"] is None
        assert row["sentiment_level"] is None
        assert row["sentiment_source"] is None
    finally:
        engine.dispose()


def test_populate_macro_indicators_table_imports_date_range(monkeypatch) -> None:
    from database.macro_indicators import get_macro_indicators_daily_table, load_macro_indicator_daily_asof
    from service.market.sentiment_provider import MarketSentimentReading

    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)
        sentiment_trade_date = date(2025, 4, 15)

        def fake_eodhd_fetch(symbol, *, start=None, end=None, **kwargs):
            if symbol == "VIX.INDX":
                return [{"date": "2025-04-15", "close": 22.4}]
            if symbol == "VIX9D.INDX":
                return [{"date": "2025-04-15", "close": 14.15}]
            return []

        def fake_fred_fetch(series_id, *, start=None, end=None, api_key_env="KEY_FRED", **kwargs):
            return [
                {"date": "2025-04-14", "value": "4.40"},
                {"date": "2025-04-15", "value": "4.50"},
            ]

        def fake_sentiment_provider(lookback_days):
            return MarketSentimentReading(
                score=-0.2,
                source="ticker_daily_sentiment_features",
                lookback_days=lookback_days,
                total_news_count=12,
                row_count=3,
                covered_days=3,
                latest_trade_date=sentiment_trade_date,
                data_quality="ok",
            )

        def fake_build_snapshot(trade_date, *, config, equity=None, execution_context="live", macro_provider=None, sentiment_score_provider=None, earnings_lookup=None, previous_state=None, use_cache=True):
            class _Snap:
                def to_dict(self):
                    return {
                        "trade_date": trade_date.isoformat(),
                        "mode": "capital_preservation",
                        "risk_multiplier": 0.7,
                        "effective_max_positions": 2,
                        "allow_new_entries": True,
                        "macro": {
                            "vix": 22.4,
                            "vix_short": 14.15,
                            "yield_10y": 4.50,
                            "vix_curve_inverted": True,
                            "yield_10y_5d_pct": 0.03,
                        },
                        "sentiment": {
                            "score": -0.2,
                            "level": "warning",
                            "source": "ticker_daily_sentiment_features",
                        },
                        "reasons": ["demo"],
                    }

            return _Snap()

        monkeypatch.setattr("service.market.macro_providers.nyse_session_dates", lambda start, end: [date(2025, 4, 15)])
        monkeypatch.setattr("service.eodhd.clientEodhd.fetch_eod", fake_eodhd_fetch)
        monkeypatch.setattr("service.fred.clientFred.fetch_series_observations", fake_fred_fetch)
        monkeypatch.setattr("service.market.macro_providers.build_snapshot", fake_build_snapshot)

        summary = populate_macro_indicators_table(
            start_date=date(2025, 4, 15),
            end_date=date(2025, 4, 15),
            yaml_cfg={
                "market_regimes": {
                    "macro_provider": "eodhd",
                    "vix": {"symbol": "VIX.INDX", "short_symbol": "VIX9D.INDX"},
                    "yields": {"provider": "fred", "fred_series_10y": "DGS10", "lookback_days": 5},
                },
                "fred": {"api_key_env": "KEY_FRED", "series_10y": "DGS10"},
            },
            equity=2000.0,
            engine=engine,
        )

        assert summary["sessions_total"] == 1
        assert summary["persisted_rows"] == 1
        row = load_macro_indicator_daily_asof(trade_date=date(2025, 4, 15), engine=engine)
        assert row is not None
        assert row["trade_date"] == date(2025, 4, 15)
        assert row["vix"] == 22.4
        assert row["vix9d"] == 14.15
        assert row["ten_y"] == 4.5
        assert row["mode"] == "capital_preservation"
        assert row["risk_multiplier"] == 0.7
        assert row["effective_max_positions"] == 2
        assert row["allow_new_entries"] is True
        assert row["vix_curve_inverted"] is True
        assert row["yield_10y_5d_pct"] == 0.03
        assert row["sentiment_score"] == -0.2
        assert row["sentiment_level"] == "warning"
        assert row["sentiment_source"] == "ticker_daily_sentiment_features"
    finally:
        engine.dispose()


def test_populate_macro_indicators_table_threads_previous_state_between_sessions(monkeypatch) -> None:
    from service.market.models import MarketRegimeState

    calls: list[str | None] = []

    class _FakeSnapshot:
        def __init__(self, trade_date: date, current_mode: str) -> None:
            self.next_state = MarketRegimeState(trade_date=trade_date, current_mode=current_mode)
            self._trade_date = trade_date
            self._current_mode = current_mode

        def to_dict(self):
            return {
                "trade_date": self._trade_date.isoformat(),
                "mode": self._current_mode,
                "risk_multiplier": 1.0,
                "effective_max_positions": None,
                "allow_new_entries": True,
                "macro": {},
                "sentiment": {},
                "next_state": self.next_state.to_dict(),
            }

    def fake_build_snapshot(trade_date, *, previous_state=None, **kwargs):
        calls.append(previous_state.current_mode if previous_state is not None else None)
        current_mode = "capital_preservation" if previous_state is None else "normal"
        return _FakeSnapshot(trade_date, current_mode)

    monkeypatch.setattr("service.market.macro_providers._build_network_macro_provider", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("service.market.macro_providers.build_snapshot", fake_build_snapshot)
    monkeypatch.setattr(
        "service.market.macro_providers.nyse_session_dates",
        lambda start, end: [date(2025, 4, 14), date(2025, 4, 15)],
    )
    monkeypatch.setattr(
        "service.market.macro_providers.persist_market_macro_snapshot_daily",
        lambda **kwargs: 1,
    )

    summary = populate_macro_indicators_table(
        start_date=date(2025, 4, 14),
        end_date=date(2025, 4, 15),
        yaml_cfg={"market_regimes": {"enabled": True}},
    )

    assert summary["sessions_total"] == 2
    assert calls == [None, "capital_preservation"]


# ---------------------------------------------------------------------------
# Sprint S4 / A-019 — Stooq fonctionne sans clé API
# ---------------------------------------------------------------------------


def test_stooq_provider_works_without_api_key(monkeypatch):
    """StooqMacroProvider doit retourner des données sans variable STOOQ_API_KEY (A-019).

    Stooq est gratuit sans inscription ni clé. Ce test vérifie que le client
    ne transmet PAS le paramètre 'apikey' quand la variable est absente, et
    que le provider retourne les données mockées normalement.
    """
    import urllib.request

    monkeypatch.delenv("STOOQ_API_KEY", raising=False)
    monkeypatch.delenv("STOOQ_APIKEY", raising=False)

    captured_urls: list[str] = []

    class _FakeResponse:
        def __init__(self, content: str) -> None:
            self._content = content.encode("utf-8")

        def read(self):
            return self._content

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    def fake_urlopen(req, timeout=10):
        captured_urls.append(req.full_url)
        csv_content = "Date,Open,High,Low,Close,Volume\n2025-04-15,17.0,18.5,16.5,22.5,0\n"
        return _FakeResponse(csv_content)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    p = StooqMacroProvider()
    result = p.get_vix_close(date(2025, 4, 15))

    assert result == pytest.approx(22.5)
    assert captured_urls, "Au moins une URL doit avoir été appelée"
    assert "apikey" not in captured_urls[0], (
        "Sans STOOQ_API_KEY, le paramètre 'apikey' ne doit PAS être transmis à Stooq (A-019)."
    )


def test_recompute_macro_regime_table_reuses_cached_macro_values(monkeypatch):
    from database.macro_indicators import (
        get_macro_indicators_daily_table,
        load_macro_indicator_daily_asof,
        persist_macro_indicator_daily,
    )

    engine = create_engine("sqlite:///:memory:")
    try:
        get_macro_indicators_daily_table().metadata.create_all(engine)
        for trade_date, vix, vix9d, ten_y in [
            (date(2025, 4, 9), 18.0, 17.0, 4.00),
            (date(2025, 4, 10), 19.0, 18.5, 4.05),
            (date(2025, 4, 11), 20.0, 19.5, 4.10),
            (date(2025, 4, 14), 21.0, 22.0, 4.20),
            (date(2025, 4, 15), 22.0, 24.0, 4.30),
        ]:
            persist_macro_indicator_daily(
                trade_date=trade_date,
                vix=vix,
                vix9d=vix9d,
                ten_y=ten_y,
                engine=engine,
            )

        class _FakeSentimentProvider:
            def __init__(self, trade_date, *, engine=None):
                self.trade_date = trade_date
                self.engine = engine
                self.last_reading = None

            def __call__(self, lookback_days: int) -> float | None:
                return -0.25

        def fake_build_snapshot(
            trade_date,
            *,
            equity=None,
            macro_provider=None,
            sentiment_score_provider=None,
            **kwargs,
        ):
            vix = macro_provider.get_vix_close(trade_date)
            vix_short = macro_provider.get_vix_short_term_close(trade_date)
            history = macro_provider.get_us10y_history(trade_date, 5)
            sentiment_score = sentiment_score_provider(5) if callable(sentiment_score_provider) else None

            class _Snap:
                def to_dict(self):
                    return {
                        "mode": "capital_preservation",
                        "risk_multiplier": 0.85,
                        "effective_max_positions": 2 if equity else None,
                        "allow_new_entries": True,
                        "macro": {
                            "vix_curve_inverted": bool(vix_short is not None and vix is not None and vix_short > vix),
                            "yield_10y_5d_pct": ((history[-1] - history[0]) / history[0]) if history else None,
                        },
                        "sentiment": {
                            "score": sentiment_score,
                            "level": "warning",
                            "source": "test_sentiment",
                        },
                    }

            return _Snap()

        monkeypatch.setattr("service.market.macro_providers.DbSentimentScoreProvider", _FakeSentimentProvider)
        monkeypatch.setattr("service.market.macro_providers.build_snapshot", fake_build_snapshot)
        monkeypatch.setattr("service.market.macro_providers.nyse_session_dates", lambda start, end: [date(2025, 4, 15)])

        summary = recompute_macro_regime_table(
            start_date=date(2025, 4, 15),
            end_date=date(2025, 4, 15),
            yaml_cfg={"market_regimes": {"enabled": True, "vix": {"enabled": True}, "yields": {"enabled": True}}},
            equity=2_000.0,
            engine=engine,
        )

        assert summary["sessions_total"] == 1
        assert summary["persisted_rows"] == 1
        assert summary["missing_rows"] == 0
        row = load_macro_indicator_daily_asof(trade_date=date(2025, 4, 15), engine=engine)
        assert row is not None
        assert row["vix"] == 22.0
        assert row["vix9d"] == 24.0
        assert row["ten_y"] == 4.30
        assert row["mode"] == "capital_preservation"
        assert row["risk_multiplier"] == 0.85
        assert row["effective_max_positions"] == 2
        assert row["allow_new_entries"] is True
        assert row["vix_curve_inverted"] is True
        assert row["yield_10y_5d_pct"] == pytest.approx((4.30 - 4.00) / 4.00)
        assert row["sentiment_score"] == -0.25
        assert row["sentiment_level"] == "warning"
        assert row["sentiment_source"] == "test_sentiment"
        assert summary["rows"][0]["source_effective"] == "db_cache"
    finally:
        engine.dispose()


def test_recompute_macro_regime_table_threads_previous_state_between_sessions(monkeypatch) -> None:
    from database.macro_indicators import get_macro_indicators_daily_table, persist_macro_indicator_daily
    from service.market.models import MarketRegimeState

    engine = create_engine("sqlite:///:memory:")
    calls: list[str | None] = []
    try:
        get_macro_indicators_daily_table().metadata.create_all(engine)
        for trade_date in [date(2025, 4, 14), date(2025, 4, 15)]:
            persist_macro_indicator_daily(trade_date=trade_date, vix=22.0, vix9d=21.0, ten_y=4.2, engine=engine)

        class _FakeSentimentProvider:
            def __init__(self, trade_date, *, engine=None):
                self.trade_date = trade_date
                self.engine = engine
                self.last_reading = None

            def __call__(self, lookback_days: int) -> float | None:
                return None

        class _FakeSnapshot:
            def __init__(self, trade_date: date, current_mode: str) -> None:
                self.next_state = MarketRegimeState(trade_date=trade_date, current_mode=current_mode)
                self._trade_date = trade_date
                self._current_mode = current_mode

            def to_dict(self):
                return {
                    "trade_date": self._trade_date.isoformat(),
                    "mode": self._current_mode,
                    "risk_multiplier": 1.0,
                    "effective_max_positions": None,
                    "allow_new_entries": True,
                    "macro": {},
                    "sentiment": {},
                    "next_state": self.next_state.to_dict(),
                }

        def fake_build_snapshot(trade_date, *, previous_state=None, **kwargs):
            calls.append(previous_state.current_mode if previous_state is not None else None)
            current_mode = "capital_preservation" if previous_state is None else "normal"
            return _FakeSnapshot(trade_date, current_mode)

        monkeypatch.setattr("service.market.macro_providers.DbSentimentScoreProvider", _FakeSentimentProvider)
        monkeypatch.setattr("service.market.macro_providers.build_snapshot", fake_build_snapshot)
        monkeypatch.setattr(
            "service.market.macro_providers.nyse_session_dates",
            lambda start, end: [date(2025, 4, 14), date(2025, 4, 15)],
        )

        summary = recompute_macro_regime_table(
            start_date=date(2025, 4, 14),
            end_date=date(2025, 4, 15),
            yaml_cfg={"market_regimes": {"enabled": True}},
            engine=engine,
        )

        assert summary["sessions_total"] == 2
        assert calls == [None, "capital_preservation"]
    finally:
        engine.dispose()


