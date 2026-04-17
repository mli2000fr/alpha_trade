from database.bar_metadata import TimeFrame
from dataIntegrityEngine.import_alpaca_bar import import_alpaca_bars


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

