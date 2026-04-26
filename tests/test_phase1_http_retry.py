"""Tests Phase 1 — politique de retry HTTP unifiée (`service/_http_retry.py`)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from service._http_retry import (
    RETRYABLE_HTTP_STATUS,
    CircuitBreaker,
    CircuitOpenError,
    RetryPolicy,
    request_with_retry,
)


def _mock_session_with_responses(responses: list) -> MagicMock:
    """responses = list de Response mock OU exceptions à lever."""
    session = MagicMock(spec=requests.Session)
    iter_resp = iter(responses)

    def _request(method, url, **kwargs):
        nxt = next(iter_resp)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    session.request.side_effect = _request
    return session


def _ok_response(status: int = 200) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.raise_for_status = MagicMock(return_value=None)
    return resp


def _http_error_response(status: int) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    err = requests.exceptions.HTTPError(f"HTTP {status}", response=resp)
    resp.raise_for_status = MagicMock(side_effect=err)
    return resp


def test_request_with_retry_success_first_try() -> None:
    session = _mock_session_with_responses([_ok_response(200)])
    resp = request_with_retry(
        session, "GET", "https://api.example.com/x",
        policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.0, jitter=False),
        breaker=None,
    )
    assert resp.status_code == 200
    assert session.request.call_count == 1


def test_request_with_retry_retries_on_5xx_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("service._http_retry.time.sleep", lambda *_: None)
    session = _mock_session_with_responses([_http_error_response(503), _ok_response(200)])
    resp = request_with_retry(
        session, "GET", "https://api.example.com/x",
        policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.0, jitter=False),
        breaker=None,
    )
    assert resp.status_code == 200
    assert session.request.call_count == 2


def test_request_with_retry_4xx_no_retry() -> None:
    session = _mock_session_with_responses([_http_error_response(404)])
    with pytest.raises(requests.exceptions.HTTPError):
        request_with_retry(
            session, "GET", "https://api.example.com/x",
            policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.0, jitter=False),
            breaker=None,
        )
    assert session.request.call_count == 1


def test_request_with_retry_429_is_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("service._http_retry.time.sleep", lambda *_: None)
    assert 429 in RETRYABLE_HTTP_STATUS
    session = _mock_session_with_responses([_http_error_response(429), _ok_response(200)])
    resp = request_with_retry(
        session, "GET", "https://api.example.com/x",
        policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.0, jitter=False),
        breaker=None,
    )
    assert resp.status_code == 200


def test_request_with_retry_exhausts_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("service._http_retry.time.sleep", lambda *_: None)
    session = _mock_session_with_responses([
        _http_error_response(500),
        _http_error_response(500),
        _http_error_response(500),
    ])
    with pytest.raises(requests.exceptions.HTTPError):
        request_with_retry(
            session, "GET", "https://api.example.com/x",
            policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.0, jitter=False),
            breaker=None,
        )
    assert session.request.call_count == 3


def test_circuit_breaker_opens_after_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("service._http_retry.time.sleep", lambda *_: None)
    breaker = CircuitBreaker(failure_threshold=2, open_seconds=60.0)
    session = _mock_session_with_responses([
        _http_error_response(500),
        _http_error_response(500),
    ])
    with pytest.raises(requests.exceptions.HTTPError):
        request_with_retry(
            session, "GET", "https://api.example.com/x",
            policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.0, jitter=False),
            breaker=breaker,
        )
    # Le 3e appel doit lever CircuitOpenError directement, sans appeler la session.
    session2 = _mock_session_with_responses([_ok_response(200)])
    with pytest.raises(CircuitOpenError):
        request_with_retry(
            session2, "GET", "https://api.example.com/x",
            policy=RetryPolicy(max_attempts=1, base_delay_seconds=0.0, jitter=False),
            breaker=breaker,
        )
    assert session2.request.call_count == 0


def test_circuit_breaker_resets_on_success() -> None:
    breaker = CircuitBreaker(failure_threshold=3, open_seconds=60.0)
    breaker.record_failure("api.example.com")
    breaker.record_failure("api.example.com")
    breaker.record_success("api.example.com")
    # Doit pouvoir échouer encore 3 fois avant ouverture.
    breaker.record_failure("api.example.com")
    breaker.record_failure("api.example.com")
    breaker.check("api.example.com")  # toujours ok

