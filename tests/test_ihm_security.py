"""Tests Phase 6.2 — sécurité IHM (auth, exposition réseau)."""
from __future__ import annotations

import pytest

from ihm.services import security


def test_auth_token_required_false_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(security.AUTH_TOKEN_ENV, raising=False)
    assert security.auth_token_required() is False


def test_auth_token_required_true_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(security.AUTH_TOKEN_ENV, "supersecret")
    assert security.auth_token_required() is True


def test_auth_token_required_false_for_blank_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(security.AUTH_TOKEN_ENV, "   ")
    assert security.auth_token_required() is False


def test_is_localhost_required_truthy_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv(security.REQUIRE_LOCALHOST_ENV, raw)
        assert security.is_localhost_required() is True
    monkeypatch.setenv(security.REQUIRE_LOCALHOST_ENV, "0")
    assert security.is_localhost_required() is False


def test_is_listening_on_localhost_only_default_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STREAMLIT_SERVER_ADDRESS", raising=False)
    assert security.is_listening_on_localhost_only() is True


@pytest.mark.parametrize("addr", ["localhost", "127.0.0.1", "::1"])
def test_is_listening_on_localhost_only_recognizes_loopback(monkeypatch: pytest.MonkeyPatch, addr: str) -> None:
    monkeypatch.setenv("STREAMLIT_SERVER_ADDRESS", addr)
    assert security.is_listening_on_localhost_only() is True


def test_is_listening_on_localhost_only_rejects_public_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMLIT_SERVER_ADDRESS", "0.0.0.0")
    # 0.0.0.0 résolu n'appartient pas au loopback.
    assert security.is_listening_on_localhost_only() is False

