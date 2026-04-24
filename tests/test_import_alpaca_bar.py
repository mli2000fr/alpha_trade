from datetime import date, datetime

import pytest

from database.bar_metadata import TimeFrame
from dataIntegrityEngine.import_alpaca_bar import _build_bar_records, import_alpaca_bars
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
    assert summary["successful_symbols"] == 0
    assert summary["skipped_symbols"] == 1
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
    assert summary["successful_symbols"] == 0


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


