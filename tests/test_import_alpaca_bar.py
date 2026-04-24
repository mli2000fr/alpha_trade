from database.bar_metadata import TimeFrame
from dataIntegrityEngine.import_alpaca_bar import _build_bar_records, import_alpaca_bars
from service.alpaca.clientAlpaca import AlpacaBarsFetchError


class _FakeSession:
    def close(self) -> None:
        return None


def test_import_alpaca_bars_accepts_targeted_symbols(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []

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

    import_alpaca_bars(TimeFrame.ONE_DAY, symbols=[" spy "])

    assert calls == [("SPY", "1Day", None)]


def test_import_alpaca_bars_keeps_bars_available_on_technical_error(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []

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

    import_alpaca_bars(TimeFrame.ONE_DAY, symbols=["aapl"])

    assert calls == [("AAPL", "1Day", None)]


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


