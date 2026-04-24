import pytest
import requests

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

    bars = clientAlpaca.fetch_bars("AAPL", "1Day", session=session)

    assert len(bars) == 1
    assert session.calls[0]["params"]["adjustment"] == "split"


def test_fetch_bars_raises_technical_error_after_timeout_exhaustion(monkeypatch) -> None:
    session = _FakeSession([requests.exceptions.Timeout(), requests.exceptions.Timeout()])

    monkeypatch.setattr(clientAlpaca, "_build_headers", lambda account_id=None: {"X": "Y"})
    monkeypatch.setattr(clientAlpaca.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(clientAlpaca, "MAX_TIMEOUT_RETRIES", 2)

    with pytest.raises(clientAlpaca.AlpacaBarsFetchError, match="Timeout Alpaca epuise"):
        clientAlpaca.fetch_bars("AAPL", "1Day", session=session)


