import logging

import pytest

from dataIntegrityEngine import update_sector


class _FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_update_missing_sectors_updates_symbols_and_logs_progress(monkeypatch, caplog) -> None:
    fake_session = _FakeSession()
    sleep_calls: list[float] = []
    updates: list[tuple[str, str | None, float | None]] = []

    monkeypatch.setattr(update_sector, "get_symbols_missing_sector", lambda limit=None: ["AAPL", "MSFT", "JPM"])
    monkeypatch.setattr(update_sector, "get_stock_metadata_fundamentals_map", lambda symbols: {})
    monkeypatch.setattr(update_sector.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(update_sector.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    records = {
        "AAPL": {"sector": "Technology", "market_cap": None},
        "MSFT": {},
        "JPM": {"sector": "Banks", "market_cap": None},
    }
    monkeypatch.setattr(update_sector, "fetch_finnhub_fundamentals_record", lambda symbol, session=None: records[symbol])
    monkeypatch.setattr(
        update_sector,
        "update_stock_metadata_fundamentals",
        lambda symbol, **kwargs: updates.append((symbol, kwargs.get("sector"), kwargs.get("market_cap"))) or 1,
    )

    caplog.set_level(logging.INFO)
    summary = update_sector.update_missing_sectors(limit=3, sleep_seconds=0.25, log_every=2, provider="finnhub")

    assert summary["total"] == 3
    assert summary["updated"] == 2
    assert summary["skipped"] == 1
    assert summary["failed"] == 0
    assert summary["missing_fundamentals_targets"] == 3
    assert summary["stale_market_cap_targets"] == 0
    assert summary["refresh_stale_days"] is None
    assert summary["provider"] == "finnhub"
    assert updates == [("AAPL", "Technology", None), ("JPM", "Banks", None)]
    assert sleep_calls == [0.25, 0.25]
    assert fake_session.closed is True
    assert ("Debut mise a jour sector stock_metadata" in caplog.text or "Début mise à jour sector stock_metadata" in caplog.text)
    assert "Progression sector | current=2/3 updated=1 skipped=1 failed=0" in caplog.text
    assert ("Fin mise a jour sector stock_metadata" in caplog.text or "Fin mise à jour sector stock_metadata" in caplog.text)


def test_update_missing_sectors_continues_after_error(monkeypatch, caplog) -> None:
    fake_session = _FakeSession()
    updates: list[tuple[str, str | None, float | None]] = []

    monkeypatch.setattr(update_sector, "get_symbols_missing_sector", lambda limit=None: ["AAA", "BBB"])
    monkeypatch.setattr(update_sector, "get_stock_metadata_fundamentals_map", lambda symbols: {})
    monkeypatch.setattr(update_sector.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(update_sector.time, "sleep", lambda seconds: None)

    def _fake_fetch_fundamentals(symbol: str, session=None):
        if symbol == "AAA":
            raise RuntimeError("boom")
        return {"sector": "Energy", "market_cap": None}

    monkeypatch.setattr(update_sector, "fetch_finnhub_fundamentals_record", _fake_fetch_fundamentals)
    monkeypatch.setattr(
        update_sector,
        "update_stock_metadata_fundamentals",
        lambda symbol, **kwargs: updates.append((symbol, kwargs.get("sector"), kwargs.get("market_cap"))) or 1,
    )

    caplog.set_level(logging.INFO)
    summary = update_sector.update_missing_sectors(sleep_seconds=0.0, log_every=1, provider="finnhub")

    assert summary["total"] == 2
    assert summary["updated"] == 1
    assert summary["skipped"] == 0
    assert summary["failed"] == 1
    assert summary["missing_fundamentals_targets"] == 2
    assert summary["stale_market_cap_targets"] == 0
    assert updates == [("BBB", "Energy", None)]
    assert fake_session.closed is True
    # Recherche large de la chaîne d'erreur dans caplog.text
    assert "Erreur mise" in caplog.text and "symbol=AAA" in caplog.text and "progress=1/2" in caplog.text and "failed=1" in caplog.text


@pytest.mark.parametrize(
    ("sleep_seconds", "log_every", "expected_message"),
    [(-0.1, 1, "sleep_seconds"), (0.0, 0, "log_every")],
)
def test_update_missing_sectors_validates_arguments(
    monkeypatch,
    sleep_seconds: float,
    log_every: int,
    expected_message: str,
) -> None:
    monkeypatch.setattr(update_sector, "get_symbols_missing_sector", lambda limit=None: [])

    with pytest.raises(ValueError, match=expected_message):
        update_sector.update_missing_sectors(sleep_seconds=sleep_seconds, log_every=log_every)


def test_update_missing_sectors_merges_stale_market_cap_targets(monkeypatch) -> None:
    """Phase 3.1.e — refresh_stale_days fusionne les symboles périmés avec les missing."""
    fake_session = _FakeSession()

    monkeypatch.setattr(update_sector, "get_symbols_missing_sector", lambda limit=None: ["AAA"])
    monkeypatch.setattr(update_sector, "get_stock_metadata_fundamentals_map", lambda symbols: {symbol: {"sector": None, "market_cap": None} for symbol in symbols})
    monkeypatch.setattr(
        update_sector,
        "get_symbols_with_stale_market_cap",
        lambda max_age_days, limit=None: ["AAA", "BBB", "CCC"],
    )
    monkeypatch.setattr(update_sector.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(update_sector.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        update_sector,
        "fetch_finnhub_fundamentals_record",
        lambda symbol, session=None: {"sector": "Tech", "market_cap": 1234.0},
    )
    monkeypatch.setattr(update_sector, "update_stock_metadata_fundamentals", lambda symbol, **kwargs: 1)

    summary = update_sector.update_missing_sectors(
	        sleep_seconds=0.0, log_every=10, refresh_stale_days=30, provider="finnhub",
    )

    # Total = 3 (AAA dédupliqué entre les deux sources).
    assert summary["total"] == 3
    assert summary["missing_fundamentals_targets"] == 1
    assert summary["stale_market_cap_targets"] == 3
    assert summary["refresh_stale_days"] == 30
    assert summary["updated"] == 3


def test_update_missing_sectors_does_not_overwrite_existing_values_by_default(monkeypatch) -> None:
    fake_session = _FakeSession()
    updates: list[tuple[str, str | None, float | None]] = []

    monkeypatch.setattr(update_sector, "get_symbols_missing_sector", lambda limit=None: ["AAA"])
    monkeypatch.setattr(
        update_sector,
        "get_stock_metadata_fundamentals_map",
        lambda symbols: {"AAA": {"sector": "Legacy", "market_cap": 10.0}},
    )
    monkeypatch.setattr(update_sector.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(update_sector.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        update_sector,
        "fetch_finnhub_fundamentals_record",
        lambda symbol, session=None: {"sector": "NewSector", "market_cap": 20.0},
    )
    monkeypatch.setattr(
        update_sector,
        "update_stock_metadata_fundamentals",
        lambda symbol, **kwargs: updates.append((symbol, kwargs.get("sector"), kwargs.get("market_cap"))) or 1,
    )

    summary = update_sector.update_missing_sectors(sleep_seconds=0.0, provider="finnhub")

    assert summary["updated"] == 0
    assert summary["skipped"] == 1
    assert updates == []


def test_update_missing_sectors_overwrite_existing_targets_all_eligible_symbols(monkeypatch) -> None:
    fake_session = _FakeSession()
    updates: list[tuple[str, str | None, float | None]] = []

    monkeypatch.setattr(update_sector, "get_symbols_missing_sector", lambda limit=None: ["AAA"])
    monkeypatch.setattr(update_sector, "list_eligible_stock_symbols", lambda limit=None: ["AAA", "BBB"])
    monkeypatch.setattr(update_sector, "get_stock_metadata_fundamentals_map", lambda symbols: {symbol: {"sector": "Legacy", "market_cap": 10.0} for symbol in symbols})
    monkeypatch.setattr(update_sector.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(update_sector.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        update_sector,
        "fetch_eodhd_fundamentals_record",
        lambda symbol, session=None: {"sector": f"Sector-{symbol}", "market_cap": 99.0},
    )
    monkeypatch.setattr(
        update_sector,
        "update_stock_metadata_fundamentals",
        lambda symbol, **kwargs: updates.append((symbol, kwargs.get("sector"), kwargs.get("market_cap"))) or 1,
    )

    summary = update_sector.update_missing_sectors(sleep_seconds=0.0, overwrite_existing=True)

    assert summary["provider"] == "eodhd"
    assert summary["overwrite_existing"] is True
    assert summary["total"] == 2
    assert summary["updated"] == 2
    assert updates == [("AAA", "Sector-AAA", 99.0), ("BBB", "Sector-BBB", 99.0)]


def test_update_missing_sectors_falls_back_to_finnhub_after_eodhd_permission_error(monkeypatch) -> None:
    fake_session = _FakeSession()
    updates: list[tuple[str, str | None, float | None]] = []
    eodhd_calls: list[str] = []
    finnhub_calls: list[str] = []

    monkeypatch.setattr(update_sector, "get_symbols_missing_sector", lambda limit=None: ["A", "AA"])
    monkeypatch.setattr(update_sector, "get_stock_metadata_fundamentals_map", lambda symbols: {})
    monkeypatch.setattr(update_sector.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(update_sector.time, "sleep", lambda seconds: None)

    def _fake_eodhd(symbol: str, session=None):
        eodhd_calls.append(symbol)
        raise update_sector.EodhdPermissionError("HTTP 403 sur fundamentals")

    def _fake_finnhub(symbol: str, session=None):
        finnhub_calls.append(symbol)
        return {"sector": f"Sector-{symbol}", "market_cap": 42.0}

    monkeypatch.setattr(update_sector, "fetch_eodhd_fundamentals_record", _fake_eodhd)
    monkeypatch.setattr(update_sector, "fetch_finnhub_fundamentals_record", _fake_finnhub)
    monkeypatch.setattr(
        update_sector,
        "update_stock_metadata_fundamentals",
        lambda symbol, **kwargs: updates.append((symbol, kwargs.get("sector"), kwargs.get("market_cap"))) or 1,
    )

    summary = update_sector.update_missing_sectors(sleep_seconds=0.0, provider="eodhd")

    assert summary["provider"] == "eodhd"
    assert summary["provider_effective"] == "finnhub"
    assert summary["provider_fallback_triggered"] is True
    assert summary["provider_fallback_count"] == 1
    assert summary["provider_fallback_from"] == "eodhd"
    assert summary["provider_fallback_to"] == "finnhub"
    assert summary["updated"] == 2
    assert summary["failed"] == 0
    assert eodhd_calls == ["A"]
    assert finnhub_calls == ["A", "AA"]
    assert updates == [("A", "Sector-A", 42.0), ("AA", "Sector-AA", 42.0)]


