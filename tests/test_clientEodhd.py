"""Tests unitaires du client HTTP EODHD (Phase 2 plan §5.2 + §7.1 T-EOD-1)."""
from __future__ import annotations

from typing import Any
from pathlib import Path

import pytest
import requests

from service.eodhd import accounts as eodhd_accounts
from service.eodhd import clientEodhd
from service.eodhd import quota as eodhd_quota


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: Any = None, status_code: int = 200) -> None:
        self._payload = payload if payload is not None else []
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            err = requests.exceptions.HTTPError(f"status={self.status_code}")
            err.response = self  # type: ignore[attr-defined]
            raise err

    def json(self) -> Any:
        return self._payload


class _FakeSession:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        return self.request("GET", url, **kwargs)

    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _force_token(monkeypatch, tmp_path: Path):
    """Force un token de test + tracker isolé pour chaque test."""
    monkeypatch.setenv("EODHD_API_TOKEN", "TEST_TOKEN")
    eodhd_accounts.EodhdAccountRegistry.reset()
    eodhd_quota.reset_default_tracker()
    # Tracker isolé sur tmp_path pour ne pas polluer artifacts/
    tracker = eodhd_quota.EodhdQuotaTracker(cache_dir=tmp_path)
    monkeypatch.setattr(
        eodhd_quota, "_DEFAULT_TRACKER", tracker, raising=False
    )
    monkeypatch.setattr(clientEodhd, "_retry_policy", lambda: clientEodhd.RetryPolicy(
        max_attempts=2, base_delay_seconds=0.0, max_delay_seconds=0.0, timeout_seconds=1.0
    ))
    # neutralise time.sleep pendant les retries
    import service._http_retry as _retry
    monkeypatch.setattr(_retry.time, "sleep", lambda s: None)
    yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fetch_eod_bulk_uses_correct_url_and_token():
    payload = [{"code": "AAPL.US", "close": 192.0, "volume": 12345}]
    session = _FakeSession([_FakeResponse(payload)])

    result = clientEodhd.fetch_eod_bulk(date="2026-04-28", session=session)

    assert result == payload
    call = session.calls[0]
    assert call["url"].endswith("/eod-bulk-last-day/US")
    assert call["params"]["api_token"] == "TEST_TOKEN"
    assert call["params"]["fmt"] == "json"
    assert call["params"]["date"] == "2026-04-28"


def test_fetch_eod_maps_symbol_class_share():
    session = _FakeSession([_FakeResponse([
        {"date": "2026-04-28", "open": 1, "high": 1, "low": 1, "close": 1, "adjusted_close": 1, "volume": 1}
    ])])

    rows = clientEodhd.fetch_eod("BRK.B", start="2026-04-01", end="2026-04-28", session=session)

    assert len(rows) == 1
    call = session.calls[0]
    assert "/eod/BRK-B.US" in call["url"]
    assert call["params"]["from"] == "2026-04-01"
    assert call["params"]["to"] == "2026-04-28"


def test_fetch_eod_bulk_payload_must_be_list():
    session = _FakeSession([_FakeResponse({"unexpected": "object"})])
    with pytest.raises(clientEodhd.EodhdBarsFetchError):
        clientEodhd.fetch_eod_bulk(session=session)


def test_fetch_eod_http_error_records_failure(tmp_path: Path):
    tracker = eodhd_quota.EodhdQuotaTracker(cache_dir=tmp_path, failure_threshold=99)
    session = _FakeSession([_FakeResponse(payload=[], status_code=403)])

    with pytest.raises(clientEodhd.EodhdBarsFetchError):
        clientEodhd.fetch_splits("NVDA", session=session, tracker=tracker)

    snap = tracker.snapshot()
    assert snap["calls_failed"] == 1


def test_fetch_eod_quota_exceeded(tmp_path: Path):
    tracker = eodhd_quota.EodhdQuotaTracker(cache_dir=tmp_path, daily_quota=0)
    session = _FakeSession([_FakeResponse([])])
    with pytest.raises(eodhd_quota.EodhdQuotaExceeded):
        clientEodhd.fetch_eod("AAPL", session=session, tracker=tracker)


def test_fetch_eod_circuit_breaker_open(tmp_path: Path):
    tracker = eodhd_quota.EodhdQuotaTracker(cache_dir=tmp_path, failure_threshold=1)
    session = _FakeSession([
        _FakeResponse(payload=[], status_code=500),
        _FakeResponse(payload=[], status_code=500),
        _FakeResponse([]),
    ])
    # Premier appel : 500 (retry consommé puis échec)
    with pytest.raises(clientEodhd.EodhdBarsFetchError):
        clientEodhd.fetch_eod("AAPL", session=session, tracker=tracker)

    # Circuit ouvert -> reserve() doit lever
    assert tracker.is_circuit_open()
    with pytest.raises(clientEodhd.EodhdCircuitOpen):
        clientEodhd.fetch_eod("AAPL", session=session, tracker=tracker)


def test_fetch_eod_404_does_not_open_circuit_breaker(tmp_path: Path):
    tracker = eodhd_quota.EodhdQuotaTracker(cache_dir=tmp_path, failure_threshold=1)
    session = _FakeSession([_FakeResponse(payload=[], status_code=404)])

    with pytest.raises(clientEodhd.EodhdSymbolNotFound):
        clientEodhd.fetch_eod("ABR.PRD", session=session, tracker=tracker)

    assert tracker.is_circuit_open() is False


def test_fetch_dividends_uses_div_endpoint():
    session = _FakeSession([_FakeResponse([{"date": "2026-02-15", "value": 0.24}])])
    rows = clientEodhd.fetch_dividends("AAPL", session=session)
    assert rows[0]["value"] == 0.24
    assert "/div/AAPL.US" in session.calls[0]["url"]

