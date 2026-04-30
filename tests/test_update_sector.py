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
    updates: list[tuple[str, str]] = []

    monkeypatch.setattr(update_sector, "get_symbols_missing_sector", lambda limit=None: ["AAPL", "MSFT", "JPM"])
    monkeypatch.setattr(update_sector.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(update_sector.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    profiles = {
        "AAPL": {"finnhubIndustry": "Technology"},
        "MSFT": {},
        "JPM": {"finnhubIndustry": "Banks"},
    }
    monkeypatch.setattr(update_sector, "fetch_company_profile", lambda symbol, session=None: profiles[symbol])
    monkeypatch.setattr(update_sector, "update_stock_metadata_sector", lambda symbol, sector: updates.append((symbol, sector)) or 1)

    caplog.set_level(logging.INFO)
    summary = update_sector.update_missing_sectors(limit=3, sleep_seconds=0.25, log_every=2)

    assert summary["total"] == 3
    assert summary["updated"] == 2
    assert summary["skipped"] == 1
    assert summary["failed"] == 0
    assert summary["missing_fundamentals_targets"] == 3
    assert summary["stale_market_cap_targets"] == 0
    assert summary["refresh_stale_days"] is None
    assert updates == [("AAPL", "Technology"), ("JPM", "Banks")]
    assert sleep_calls == [0.25, 0.25]
    assert fake_session.closed is True
    assert ("Debut mise a jour sector stock_metadata" in caplog.text or "Début mise à jour sector stock_metadata" in caplog.text)
    assert "Progression sector | current=2/3 updated=1 skipped=1 failed=0" in caplog.text
    assert ("Fin mise a jour sector stock_metadata" in caplog.text or "Fin mise à jour sector stock_metadata" in caplog.text)


def test_update_missing_sectors_continues_after_error(monkeypatch, caplog) -> None:
    fake_session = _FakeSession()
    updates: list[tuple[str, str]] = []

    monkeypatch.setattr(update_sector, "get_symbols_missing_sector", lambda limit=None: ["AAA", "BBB"])
    monkeypatch.setattr(update_sector.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(update_sector.time, "sleep", lambda seconds: None)

    def _fake_fetch_company_profile(symbol: str, session=None):
        if symbol == "AAA":
            raise RuntimeError("boom")
        return {"finnhubIndustry": "Energy"}

    monkeypatch.setattr(update_sector, "fetch_company_profile", _fake_fetch_company_profile)
    monkeypatch.setattr(update_sector, "update_stock_metadata_sector", lambda symbol, sector: updates.append((symbol, sector)) or 1)

    caplog.set_level(logging.INFO)
    summary = update_sector.update_missing_sectors(sleep_seconds=0.0, log_every=1)

    assert summary["total"] == 2
    assert summary["updated"] == 1
    assert summary["skipped"] == 0
    assert summary["failed"] == 1
    assert summary["missing_fundamentals_targets"] == 2
    assert summary["stale_market_cap_targets"] == 0
    assert updates == [("BBB", "Energy")]
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
    monkeypatch.setattr(
        update_sector,
        "get_symbols_with_stale_market_cap",
        lambda max_age_days, limit=None: ["AAA", "BBB", "CCC"],
    )
    monkeypatch.setattr(update_sector.requests, "Session", lambda: fake_session)
    monkeypatch.setattr(update_sector.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        update_sector,
        "fetch_company_profile",
        lambda symbol, session=None: {"finnhubIndustry": "Tech", "marketCapitalization": 1234.0},
    )
    monkeypatch.setattr(update_sector, "update_stock_metadata_fundamentals", lambda symbol, **kwargs: 1)
    monkeypatch.setattr(update_sector, "update_stock_metadata_sector", lambda symbol, sector: 1)

    summary = update_sector.update_missing_sectors(
        sleep_seconds=0.0, log_every=10, refresh_stale_days=30,
    )

    # Total = 3 (AAA dédupliqué entre les deux sources).
    assert summary["total"] == 3
    assert summary["missing_fundamentals_targets"] == 1
    assert summary["stale_market_cap_targets"] == 3
    assert summary["refresh_stale_days"] == 30
    assert summary["updated"] == 3

