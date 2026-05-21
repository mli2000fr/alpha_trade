import pytest
import requests
from typing import cast

from service.alpaca import clientAlpaca


class _FakeResponse:
    def __init__(self, payload=None, status_code: int = 200) -> None:
        self._payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            http_error = requests.exceptions.HTTPError(f"status={self.status_code}")
            http_error.response = self
            raise http_error

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def get(self, endpoint, headers=None, params=None, timeout=None):
        self.calls.append({"endpoint": endpoint, "headers": headers, "params": params, "timeout": timeout})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def request(self, method, endpoint, headers=None, params=None, timeout=None, **_kwargs):
        # Phase 2.3 : ``service._http_retry.request_with_retry`` appelle
        # ``session.request(method, url, ...)`` (API standard requests).
        return self.get(endpoint, headers=headers, params=params, timeout=timeout)

    def close(self) -> None:
        return None


def test_clientAlpaca_importable() -> None:
    assert hasattr(clientAlpaca, "__doc__")


def test_fetch_bars_requests_split_adjustment(monkeypatch) -> None:
    session = _FakeSession([
        _FakeResponse({"bars": [{"t": "2026-01-02T21:00:00Z", "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 1}], "next_page_token": None})
    ])

    monkeypatch.setattr(clientAlpaca, "_build_headers", lambda account_id=None: {"X": "Y"})
    monkeypatch.setattr(clientAlpaca.time, "sleep", lambda seconds: None)

    bars = clientAlpaca.fetch_bars("AAPL", "1Day", session=cast(requests.Session, cast(object, session)))

    assert len(bars) == 1
    assert session.calls[0]["params"]["adjustment"] == "split"


def test_fetch_bars_uses_rolling_default_start_date(monkeypatch) -> None:
    session = _FakeSession([
        _FakeResponse({"bars": [{"t": "2026-01-02T21:00:00Z", "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 1}], "next_page_token": None})
    ])

    monkeypatch.setattr(clientAlpaca, "_build_headers", lambda account_id=None: {"X": "Y"})
    monkeypatch.setattr(clientAlpaca, "_default_start_date", lambda: "2015-04-24")
    monkeypatch.setattr(clientAlpaca.time, "sleep", lambda seconds: None)

    clientAlpaca.fetch_bars("AAPL", "1Day", session=cast(requests.Session, cast(object, session)))

    assert session.calls[0]["params"]["start"] == "2015-04-24"


def test_fetch_bars_raises_technical_error_after_timeout_exhaustion(monkeypatch) -> None:
    session = _FakeSession([requests.exceptions.Timeout(), requests.exceptions.Timeout()])

    monkeypatch.setattr(clientAlpaca, "_build_headers", lambda account_id=None: {"X": "Y"})
    monkeypatch.setattr(clientAlpaca.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(clientAlpaca, "MAX_TIMEOUT_RETRIES", 2)

    with pytest.raises(clientAlpaca.AlpacaBarsFetchError, match="Timeout Alpaca epuise"):
        clientAlpaca.fetch_bars("AAPL", "1Day", session=cast(requests.Session, cast(object, session)))


def test_iter_historical_quotes_pages_yields_page_metadata(monkeypatch) -> None:
    session = _FakeSession([
        _FakeResponse({
            "quotes": [{"t": "2026-04-29T20:00:00Z", "bp": 100.0, "ap": 100.5}],
            "next_page_token": "NEXT",
        }),
        _FakeResponse({
            "quotes": [{"t": "2026-04-30T20:00:00Z", "bp": 101.0, "ap": 101.5}],
            "next_page_token": None,
        }),
    ])

    monkeypatch.setattr(clientAlpaca, "_build_headers", lambda account_id=None: {"X": "Y"})
    monkeypatch.setattr(clientAlpaca.time, "sleep", lambda seconds: None)

    pages = list(
        clientAlpaca.iter_historical_quotes_pages(
            "AAPL",
            start="2026-04-29",
            end="2026-04-30",
            session=cast(requests.Session, cast(object, session)),
        )
    )

    assert len(pages) == 2
    assert pages[0]["page"] == 1
    assert pages[0]["page_count"] == 1
    assert pages[0]["total_count"] == 1
    assert pages[0]["has_next"] is True
    assert pages[0]["last_quote_timestamp"] == "2026-04-29T20:00:00Z"
    assert pages[1]["page"] == 2
    assert pages[1]["total_count"] == 2
    assert pages[1]["has_next"] is False


def test_fetch_latest_historical_quote_in_window_requests_desc_limit_one(monkeypatch) -> None:
    session = _FakeSession([
        _FakeResponse({
            "quotes": [{"t": "2026-04-29T19:59:00Z", "bp": 100.0, "ap": 100.5}],
        }),
    ])

    monkeypatch.setattr(clientAlpaca, "_build_headers", lambda account_id=None: {"X": "Y"})
    monkeypatch.setattr(clientAlpaca.time, "sleep", lambda seconds: None)

    quote = clientAlpaca.fetch_latest_historical_quote_in_window(
        "AAPL",
        start="2026-04-29T19:50:00Z",
        end="2026-04-29T20:00:00Z",
        session=cast(requests.Session, cast(object, session)),
    )

    assert quote is not None
    assert quote["t"] == "2026-04-29T19:59:00Z"
    assert session.calls[0]["params"]["sort"] == "desc"
    assert session.calls[0]["params"]["limit"] == 1


