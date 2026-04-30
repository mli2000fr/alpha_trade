from datetime import date, datetime

import json
import pytest

from database.bar_metadata import TimeFrame
from dataIntegrityEngine import import_alpaca_bar
from dataIntegrityEngine.import_alpaca_bar import (
    RUN_SUMMARY_PREFIX,
    _assess_staleness,
    _build_bar_records,
    import_alpaca_bars,
    main,
)
from service.alpaca.clientAlpaca import AlpacaBarsFetchError


class _FakeSession:
    def close(self) -> None:
        return None


def test_import_alpaca_bars_rejects_non_daily_timeframe() -> None:
    with pytest.raises(ValueError, match="daily"):
        import_alpaca_bars(TimeFrame.THIRTY_MINS, symbols=["AAPL"])


def test_import_alpaca_bars_accepts_targeted_symbols(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []
    history_calls: list[str] = []

    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.get_active_tradable_symbols",
        lambda session: (_ for _ in ()).throw(AssertionError("ne doit pas charger l'univers complet")),
    )
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.get_last_bar_timestamp", lambda session, symbol, time_frame: None)
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.fetch_bars",
        lambda symbol, api_value, start: calls.append((symbol, api_value, start)) or [],
    )
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.symbol_exists_in_stock_bars", lambda session, symbol: True)
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.update_bars_available_false",
        lambda symbol: (_ for _ in ()).throw(AssertionError("ne doit pas marquer bars_available à false")),
    )
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.mark_symbol_history_ready", lambda symbol: history_calls.append(symbol) or 1)

    summary = import_alpaca_bars(TimeFrame.ONE_DAY, symbols=[" spy "])

    assert calls == [("SPY", "1Day", None)]
    assert history_calls == []
    assert summary["targeted_symbols"] == 1
    assert summary["first_import_symbols"] == 1
    assert summary["existing_history_symbols"] == 0
    assert summary["successful_symbols"] == 0
    assert summary["skipped_symbols"] == 1
    assert summary["up_to_date_symbols"] == 0
    assert summary["failed_symbols"] == 0


def test_import_alpaca_bars_keeps_bars_available_on_technical_error(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []
    status_calls: list[tuple[str, str]] = []

    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.get_last_bar_timestamp", lambda session, symbol, time_frame: None)
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.fetch_bars",
        lambda symbol, api_value, start: calls.append((symbol, api_value, start)) or (_ for _ in ()).throw(AlpacaBarsFetchError("timeout")),
    )
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.update_bars_available_false",
        lambda symbol: (_ for _ in ()).throw(AssertionError("incident technique: bars_available ne doit pas basculer a false")),
    )
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.update_symbol_history_status",
        lambda symbol, status: status_calls.append((symbol, status)) or 1,
    )

    summary = import_alpaca_bars(TimeFrame.ONE_DAY, symbols=["aapl"])

    assert calls == [("AAPL", "1Day", None)]
    assert status_calls == [("AAPL", "provider_error")]
    assert summary["targeted_symbols"] == 1
    assert summary["failed_symbols"] == 1
    assert summary["provider_error_symbols"] == 1
    assert summary["successful_symbols"] == 0
    assert summary["history_status_counts"]["provider_error"] == 1


def test_import_alpaca_bars_marks_symbol_ready_after_success(monkeypatch) -> None:
    history_calls: list[str] = []

    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.get_last_bar_timestamp", lambda session, symbol, time_frame: None)
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.fetch_bars",
        lambda symbol, api_value, start: [
            {"t": "2026-01-02T21:00:00Z", "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 1_000, "n": 10, "vw": 100.1}
        ] if start is None else [],
    )
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.insert_bars", lambda session, symbol, bars, timeframe: len(bars))
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.symbol_exists_in_stock_bars", lambda session, symbol: True)
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.mark_symbol_history_ready", lambda symbol: history_calls.append(symbol) or 1)

    summary = import_alpaca_bars(TimeFrame.ONE_DAY, symbols=["aapl"])

    assert history_calls == ["AAPL"]
    assert summary["successful_symbols"] == 1
    assert summary["inserted_bars"] == 1
    assert summary["history_status_counts"]["ready"] == 1


def test_import_alpaca_bars_marks_stale_symbol_when_existing_history_is_too_old(monkeypatch) -> None:
    status_calls: list[tuple[str, str]] = []

    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.get_last_bar_timestamp",
        lambda session, symbol, time_frame: datetime(2026, 1, 2, 0, 0, 0),
    )
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.getLastDateMarche", lambda: date(2026, 1, 15))
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.fetch_bars", lambda symbol, api_value, start: [])
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.symbol_exists_in_stock_bars", lambda session, symbol: True)
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.update_symbol_history_status",
        lambda symbol, status: status_calls.append((symbol, status)) or 1,
    )

    summary = import_alpaca_bars(TimeFrame.ONE_DAY, symbols=["aapl"])

    assert status_calls == [("AAPL", "suspended_or_stale")]
    assert summary["stale_symbols"] == 1
    assert summary["skipped_symbols"] == 0
    assert summary["existing_history_symbols"] == 1
    assert summary["max_calendar_gap_days"] >= 13
    assert summary["max_trading_gap_days"] >= 8
    assert summary["history_status_counts"]["suspended_or_stale"] == 1


def test_import_alpaca_bars_reports_no_history_breakdown(monkeypatch) -> None:
    no_history_calls: list[str] = []

    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.getLastDateMarche", lambda: date(2026, 1, 15))
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.get_last_bar_timestamp", lambda session, symbol, time_frame: None)
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.fetch_bars", lambda symbol, api_value, start: [])
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.symbol_exists_in_stock_bars", lambda session, symbol: False)
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.update_bars_available_false",
        lambda symbol: no_history_calls.append(symbol),
    )

    summary = import_alpaca_bars(TimeFrame.ONE_DAY, symbols=["aapl"])

    assert no_history_calls == ["AAPL"]
    assert summary["market_date"] == "2026-01-15"
    assert summary["first_import_symbols"] == 1
    assert summary["no_data_symbols"] == 1
    assert summary["history_status_counts"]["no_history"] == 1


def test_assess_staleness_uses_trading_days_instead_of_simple_calendar_gap(monkeypatch) -> None:
    thanksgiving = date(2026, 11, 26)
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.is_trading_day",
        lambda value: value.weekday() < 5 and value != thanksgiving,
    )

    staleness = _assess_staleness(datetime(2026, 11, 25, 0, 0, 0), date(2026, 12, 3))

    assert staleness["calendar_days"] == 8
    assert staleness["trading_days"] == 5
    assert staleness["is_stale"] is False


def test_build_bar_records_rejects_inconsistent_ohlc_bar() -> None:
    records = _build_bar_records(
        "AAPL",
        [
            {
                "t": "2026-01-02T21:00:00Z",
                "o": 100.0,
                "h": 99.0,
                "l": 98.0,
                "c": 100.5,
                "v": 1_000,
                "n": 10,
                "vw": 100.1,
            }
        ],
        "1D",
    )

    assert records == []


def test_build_bar_records_rejects_negative_volume_and_preserves_nullable_vwap() -> None:
    rejected = _build_bar_records(
        "AAPL",
        [
            {
                "t": "2026-01-02T21:00:00Z",
                "o": 100.0,
                "h": 101.0,
                "l": 99.0,
                "c": 100.5,
                "v": -1,
                "n": 10,
                "vw": 100.1,
            }
        ],
        "1D",
    )
    accepted = _build_bar_records(
        "AAPL",
        [
            {
                "t": "2026-01-03T21:00:00Z",
                "o": 100.0,
                "h": 101.0,
                "l": 99.0,
                "c": 100.5,
                "v": 1_000,
                "n": 10,
                "vw": None,
            }
        ],
        "1D",
    )

    assert rejected == []
    assert len(accepted) == 1
    assert accepted[0]["vwa_price"] is None



def test_import_alpaca_bars_computes_success_ratio_for_attempted_symbols(monkeypatch) -> None:
    """Le ratio succès doit ignorer les symboles up_to_date du dénominateur."""
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.getLastDateMarche", lambda: date(2026, 1, 15))

    # AAPL : up_to_date (ne doit pas compter dans attempted)
    # MSFT : succès (1 barre insérée)
    # GOOG : provider error
    def _last_ts(session, symbol, time_frame):
        if symbol == "AAPL":
            return datetime(2026, 1, 15, 0, 0, 0)
        return None

    def _fetch(symbol, api_value, start):
        if symbol == "GOOG":
            raise AlpacaBarsFetchError("boom")
        if symbol == "MSFT" and start is None:
            return [
                {"t": "2026-01-15T21:00:00Z", "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 1_000, "n": 10, "vw": 100.1}
            ]
        return []

    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.get_last_bar_timestamp", _last_ts)
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.fetch_bars", _fetch)
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.insert_bars", lambda session, symbol, bars, timeframe: len(bars))
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.symbol_exists_in_stock_bars", lambda session, symbol: True)
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.mark_symbol_history_ready", lambda symbol: None)
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.update_symbol_history_status", lambda symbol, status: None)

    summary = import_alpaca_bars(TimeFrame.ONE_DAY, symbols=["aapl", "msft", "goog"])

    assert summary["targeted_symbols"] == 3
    assert summary["up_to_date_symbols"] == 1
    assert summary["attempted_symbols"] == 2
    assert summary["successful_symbols"] == 1
    assert summary["provider_error_symbols"] == 1
    assert summary["success_ratio"] == pytest.approx(0.5)
    assert summary["provider_error_ratio"] == pytest.approx(0.5)


def test_import_alpaca_bars_success_ratio_none_when_all_up_to_date(monkeypatch) -> None:
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr("dataIntegrityEngine.import_alpaca_bar.getLastDateMarche", lambda: date(2026, 1, 15))
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.get_last_bar_timestamp",
        lambda session, symbol, time_frame: datetime(2026, 1, 15, 0, 0, 0),
    )
    monkeypatch.setattr(
        "dataIntegrityEngine.import_alpaca_bar.fetch_bars",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ne doit pas être appelé")),
    )

    summary = import_alpaca_bars(TimeFrame.ONE_DAY, symbols=["aapl"])

    assert summary["attempted_symbols"] == 0
    assert summary["success_ratio"] is None
    assert summary["provider_error_ratio"] is None


def _payload_from_capsys(capsys) -> dict:
    output = capsys.readouterr().out.strip()
    assert output.startswith(RUN_SUMMARY_PREFIX)
    return json.loads(output[len(RUN_SUMMARY_PREFIX):])


def test_main_returns_zero_when_universe_meets_threshold(monkeypatch, capsys) -> None:
    monkeypatch.setattr(import_alpaca_bar, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(import_alpaca_bar, "_resolve_bars_provider", lambda: "alpaca")
    monkeypatch.setattr(
        import_alpaca_bar,
        "import_alpaca_bars",
        lambda time_frame, symbols=None: {
            "targeted_symbols": 100,
            "up_to_date_symbols": 0,
            "successful_symbols": 95,
            "provider_error_symbols": 5,
            "success_ratio": 0.95,
            "provider_error_ratio": 0.05,
            "attempted_symbols": 100,
        },
    )

    exit_code = main([])

    assert exit_code == 0
    payload = _payload_from_capsys(capsys)
    assert payload["schema_version"] == 1
    assert payload["success_ratio_threshold"] == pytest.approx(0.80)
    assert payload["target_mode"] == "universe"


def test_main_returns_one_when_universe_below_threshold(monkeypatch, capsys) -> None:
    monkeypatch.setattr(import_alpaca_bar, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(import_alpaca_bar, "_resolve_bars_provider", lambda: "alpaca")
    monkeypatch.setattr(
        import_alpaca_bar,
        "import_alpaca_bars",
        lambda time_frame, symbols=None: {
            "targeted_symbols": 100,
            "up_to_date_symbols": 0,
            "successful_symbols": 50,
            "provider_error_symbols": 50,
            "success_ratio": 0.50,
            "provider_error_ratio": 0.50,
            "attempted_symbols": 100,
        },
    )

    exit_code = main(["--min-success-ratio", "0.80"])

    assert exit_code == 1
    payload = _payload_from_capsys(capsys)
    assert payload["success_ratio"] == pytest.approx(0.50)


def test_main_returns_zero_when_explicit_symbols_even_if_below_threshold(monkeypatch, capsys) -> None:
    monkeypatch.setattr(import_alpaca_bar, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(import_alpaca_bar, "_resolve_bars_provider", lambda: "alpaca")
    monkeypatch.setattr(
        import_alpaca_bar,
        "import_alpaca_bars",
        lambda time_frame, symbols=None: {
            "targeted_symbols": 1,
            "up_to_date_symbols": 0,
            "successful_symbols": 0,
            "provider_error_symbols": 1,
            "success_ratio": 0.0,
            "provider_error_ratio": 1.0,
            "attempted_symbols": 1,
        },
    )

    exit_code = main(["--symbols", "AAPL"])

    assert exit_code == 0
    payload = _payload_from_capsys(capsys)
    assert payload["target_mode"] == "explicit"



