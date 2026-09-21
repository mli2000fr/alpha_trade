from __future__ import annotations

from typing import Any

import pytest
import requests

from service.tushare.accounts import load_account
from service.tushare.client import TushareClient
from service.tushare.errors import (
    TushareAuthenticationError,
    TushareQuotaError,
    TushareResponseError,
)
from service.tushare.quota import QuotaBudget
from service.tushare.retry import RetryPolicy


class FakeResponse:
    def __init__(self, status: int, payload: Any) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def post(self, _url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _client(responses: list[FakeResponse | Exception]) -> tuple[TushareClient, FakeSession]:
    session = FakeSession(responses)
    client = TushareClient(
        "secret-token",
        session=session,  # type: ignore[arg-type]
        quota=QuotaBudget(max_calls_per_minute=100, max_calls_per_run=20),
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0),
        sleeper=lambda _delay: None,
    )
    return client, session


def test_successful_response_is_mapped_and_token_is_redacted() -> None:
    client, session = _client(
        [FakeResponse(200, {"code": 0, "msg": None, "data": {"fields": ["ts_code", "name"], "items": [["000001.SZ", "平安银行"]]}})]
    )
    page = client.query("stock_basic", params={"list_status": "L"}, fields=("ts_code", "name"))
    assert page.rows == ({"ts_code": "000001.SZ", "name": "平安银行"},)
    assert page.request_payload["token"] == "***"
    assert session.calls[0]["json"]["token"] == "secret-token"


def test_http_429_is_retried_then_succeeds() -> None:
    client, session = _client(
        [
            FakeResponse(429, {}),
            FakeResponse(200, {"code": 0, "data": {"fields": [], "items": []}}),
        ]
    )
    assert client.query("daily").rows == ()
    assert len(session.calls) == 2


def test_repeated_quota_error_remains_a_quota_error() -> None:
    client, _ = _client([FakeResponse(429, {}), FakeResponse(429, {}), FakeResponse(429, {})])
    with pytest.raises(TushareQuotaError):
        client.query("daily")


def test_provider_token_error_is_blocking_without_retry() -> None:
    client, session = _client(
        [FakeResponse(200, {"code": -2001, "msg": "token不对", "data": None})]
    )
    with pytest.raises(TushareAuthenticationError):
        client.query("daily")
    assert len(session.calls) == 1


def test_5xx_exhaustion_is_a_response_error() -> None:
    client, _ = _client(
        [requests.ConnectionError("offline"), FakeResponse(503, {}), FakeResponse(503, {})]
    )
    with pytest.raises(TushareResponseError, match="retry"):
        client.query("daily")


def test_malformed_row_is_rejected() -> None:
    client, _ = _client(
        [FakeResponse(200, {"code": 0, "data": {"fields": ["a", "b"], "items": [[1]]}})]
    )
    with pytest.raises(TushareResponseError, match="incompatible"):
        client.query("daily")


def test_missing_token_is_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    with pytest.raises(TushareAuthenticationError, match="TUSHARE_TOKEN"):
        load_account()
