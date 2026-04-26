"""Politique de retry HTTP unifiée pour les clients du module ``service``.

Phase 1 du refactor (`prompt/refactor/plan.md`).

Centralise :
- Le backoff exponentiel (avec plafond et jitter optionnel).
- Un *circuit breaker* simple en mémoire processus (par hôte).
- La distinction entre erreurs réseau / 5xx (retry) et 4xx (non-retry sauf 408/429).

Tous les nouveaux appels HTTP des clients (Alpaca, Finnhub, news...) doivent
utiliser :func:`request_with_retry` au lieu de réimplémenter une boucle.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable

import requests

LOGGER = logging.getLogger(__name__)

#: Codes HTTP transients qui méritent un retry.
RETRYABLE_HTTP_STATUS: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RetryPolicy:
    """Paramétrage d'une boucle de retry exponentiel."""

    max_attempts: int = 5
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 30.0
    jitter: bool = True
    timeout_seconds: float = 10.0


@dataclass
class _CircuitState:
    consecutive_failures: int = 0
    open_until: float = 0.0


@dataclass
class CircuitBreaker:
    """Circuit breaker minimal *par hôte*.

    Ouvre après ``failure_threshold`` échecs consécutifs ; reste ouvert
    pendant ``open_seconds`` (les appels lèvent immédiatement
    :class:`CircuitOpenError`).
    """

    failure_threshold: int = 6
    open_seconds: float = 60.0
    _states: dict[str, _CircuitState] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def _state(self, host: str) -> _CircuitState:
        with self._lock:
            return self._states.setdefault(host, _CircuitState())

    def check(self, host: str) -> None:
        state = self._state(host)
        if state.open_until and time.monotonic() < state.open_until:
            raise CircuitOpenError(
                f"Circuit ouvert pour '{host}' jusqu'à {state.open_until:.0f}s"
            )

    def record_success(self, host: str) -> None:
        state = self._state(host)
        state.consecutive_failures = 0
        state.open_until = 0.0

    def record_failure(self, host: str) -> None:
        state = self._state(host)
        state.consecutive_failures += 1
        if state.consecutive_failures >= self.failure_threshold:
            state.open_until = time.monotonic() + self.open_seconds
            LOGGER.warning(
                "Circuit breaker OPEN pour host=%s (%s échecs consécutifs, %ss)",
                host,
                state.consecutive_failures,
                self.open_seconds,
            )


class CircuitOpenError(RuntimeError):
    """Levée quand le circuit breaker refuse un appel."""


# Singleton par défaut, partagé par tous les clients qui n'en fournissent pas.
DEFAULT_CIRCUIT_BREAKER = CircuitBreaker()


def _backoff_delay(policy: RetryPolicy, attempt: int) -> float:
    base = policy.base_delay_seconds * (2 ** max(attempt - 1, 0))
    delay = min(base, policy.max_delay_seconds)
    if policy.jitter:
        delay *= 0.5 + random.random()  # [0.5x, 1.5x]
    return min(delay, policy.max_delay_seconds)


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    policy: RetryPolicy | None = None,
    breaker: CircuitBreaker | None = DEFAULT_CIRCUIT_BREAKER,
    **request_kwargs: Any,
) -> requests.Response:
    """Effectue une requête HTTP avec retry exponentiel + circuit breaker.

    - 4xx (hors :data:`RETRYABLE_HTTP_STATUS`) : pas de retry, l'exception
      ``HTTPError`` est levée immédiatement.
    - 5xx, timeouts, erreurs réseau : retry selon ``policy``.
    - Le circuit breaker est interrogé *avant* chaque tentative et alimenté
      par les succès / échecs.
    """
    pol = policy or RetryPolicy()
    request_kwargs.setdefault("timeout", pol.timeout_seconds)
    host = _extract_host(url)

    last_exc: Exception | None = None
    method_lower = method.lower()
    for attempt in range(1, pol.max_attempts + 1):
        if breaker is not None:
            breaker.check(host)
        try:
            # API standard requests : préfère ``session.request(method, url, ...)``.
            # Fallback sur ``session.<method>(url, ...)`` pour les fakes minimalistes
            # qui n'implémentent que ``.get()`` / ``.post()`` (rétrocompat tests legacy).
            session_request = getattr(session, "request", None)
            if callable(session_request):
                response = session_request(method, url, **request_kwargs)
            else:
                http_call = getattr(session, method_lower)
                response = http_call(url, **request_kwargs)
            if response.status_code in RETRYABLE_HTTP_STATUS:
                raise _RetryableHttpError(response)
            response.raise_for_status()
            if breaker is not None:
                breaker.record_success(host)
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
        except _RetryableHttpError as exc:
            last_exc = exc.as_http_error()
        except requests.exceptions.HTTPError:
            # 4xx non transient : pas de retry.
            if breaker is not None:
                breaker.record_failure(host)
            raise

        if breaker is not None:
            breaker.record_failure(host)
        if attempt >= pol.max_attempts:
            break
        delay = _backoff_delay(pol, attempt)
        LOGGER.warning(
            "HTTP retry | host=%s attempt=%d/%d sleep=%.2fs cause=%s",
            host, attempt, pol.max_attempts, delay, last_exc,
        )
        time.sleep(delay)

    assert last_exc is not None  # pragma: no cover
    raise last_exc


def _extract_host(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc or url
    except Exception:  # pragma: no cover
        return url


class _RetryableHttpError(Exception):
    def __init__(self, response: requests.Response) -> None:
        super().__init__(f"HTTP {response.status_code}")
        self.response = response

    def as_http_error(self) -> requests.exceptions.HTTPError:
        try:
            self.response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            return err
        return requests.exceptions.HTTPError(  # pragma: no cover
            f"HTTP {self.response.status_code}", response=self.response
        )


__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "DEFAULT_CIRCUIT_BREAKER",
    "RetryPolicy",
    "RETRYABLE_HTTP_STATUS",
    "request_with_retry",
]

