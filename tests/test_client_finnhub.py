from __future__ import annotations

from typing import Any

import pytest
import requests

from service.finnhub import clientFinnhub


class _FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400 and self.status_code != 429:
            raise requests.exceptions.HTTPError(response=self)


class _FakeSession:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def request(self, method, url, params=None, timeout=None, **_kwargs):
        # Phase 2.3 : ``service._http_retry.request_with_retry`` appelle
        # ``session.request(method, url, ...)`` (API standard requests).
        return self.get(url, params=params, timeout=timeout)

    def close(self) -> None:
        self.closed = True


def test_get_finnhub_token_raises_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("CLE_FINNHUB", raising=False)

    with pytest.raises(RuntimeError, match="FINNHUB_API_KEY"):
        clientFinnhub.get_finnhub_token()


def test_fetch_company_profile_returns_payload(monkeypatch) -> None:
    monkeypatch.delenv("CLE_FINNHUB", raising=False)
    monkeypatch.setenv("FINNHUB_API_KEY", "demo-token")
    session = _FakeSession([_FakeResponse({"ticker": "AAPL", "finnhubIndustry": "Technology"})])

    profile = clientFinnhub.fetch_company_profile("aapl", session=session)

    assert profile["ticker"] == "AAPL"
    assert profile["finnhubIndustry"] == "Technology"
    assert session.calls[0]["params"]["symbol"] == "AAPL"
    assert session.calls[0]["params"]["token"] == "demo-token"
    assert session.calls[0]["timeout"] == clientFinnhub.DEFAULT_TIMEOUT_SECONDS


def test_fetch_symbol_sector_returns_none_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("CLE_FINNHUB", raising=False)
    monkeypatch.setenv("FINNHUB_API_KEY", "demo-token")
    session = _FakeSession([_FakeResponse({"ticker": "AAPL"})])

    sector = clientFinnhub.fetch_symbol_sector("AAPL", session=session)

    assert sector is None


def test_fetch_company_profile_retries_after_timeout(monkeypatch) -> None:
    monkeypatch.delenv("CLE_FINNHUB", raising=False)
    monkeypatch.setenv("FINNHUB_API_KEY", "demo-token")
    sleep_calls: list[float] = []
    monkeypatch.setattr(clientFinnhub.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    session = _FakeSession(
        [
            requests.exceptions.Timeout(),
            _FakeResponse({"ticker": "MSFT", "finnhubIndustry": "Technology"}),
        ]
    )

    profile = clientFinnhub.fetch_company_profile("MSFT", session=session)

    assert profile["ticker"] == "MSFT"
    # Phase 2.3 : la politique de retry est maintenant jittered exponentielle
    # via service/_http_retry.py (audit_service §retry helper). On vérifie
    # juste qu'un sleep a bien été émis entre les deux tentatives, sans
    # contrainte stricte sur la valeur (jitter 0.5x-1.5x).
    assert len(sleep_calls) == 1
    assert 0 < sleep_calls[0] <= clientFinnhub._FINNHUB_RETRY_POLICY.max_delay_seconds
    assert len(session.calls) == 2


def test_fetch_multiple_symbol_sector_records_continues_on_error(monkeypatch) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(clientFinnhub.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    session = _FakeSession([])

    def _fake_fetch_symbol_sector_record(symbol: str, session=None):
        if symbol == "MSFT":
            raise RuntimeError("temporary failure")
        return {
            "symbol": symbol,
            "sector": "Technology" if symbol == "AAPL" else "Banks",
            "source": "Finnhub",
            "raw_profile": {"ticker": symbol},
        }

    monkeypatch.setattr(clientFinnhub, "fetch_symbol_sector_record", _fake_fetch_symbol_sector_record)

    records = clientFinnhub.fetch_multiple_symbol_sector_records(
        ["AAPL", "MSFT", "JPM"],
        sleep_seconds=0.25,
        session=session,
    )

    assert records == [
        {
            "symbol": "AAPL",
            "sector": "Technology",
            "source": "Finnhub",
            "raw_profile": {"ticker": "AAPL"},
        },
        {
            "symbol": "JPM",
            "sector": "Banks",
            "source": "Finnhub",
            "raw_profile": {"ticker": "JPM"},
        },
    ]
    assert sleep_calls == [0.25, 0.25]



