"""Tests Phase 1 — chargement et validation des secrets (`core/secrets.py`)."""
from __future__ import annotations

import pytest

from core.secrets import (
    SecretConfigurationError,
    assert_no_plaintext_secrets,
    assert_required_env_vars,
    resolve_env_placeholders,
)


def test_resolve_env_placeholders_simple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TOKEN", "abc123")
    assert resolve_env_placeholders("Bearer ${MY_TOKEN}") == "Bearer abc123"


def test_resolve_env_placeholders_strict_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_VAR", raising=False)
    with pytest.raises(SecretConfigurationError):
        resolve_env_placeholders("${MISSING_VAR}")


def test_resolve_env_placeholders_lenient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_VAR", raising=False)
    assert resolve_env_placeholders("${MISSING_VAR}", strict=False) == "${MISSING_VAR}"


def test_resolve_env_placeholders_nested(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USR", "alice")
    monkeypatch.setenv("PWD", "s3cret")
    cfg = {
        "database": {"user": "${USR}", "password": "${PWD}"},
        "list": ["${USR}", "literal"],
    }
    out = resolve_env_placeholders(cfg)
    assert out == {
        "database": {"user": "alice", "password": "s3cret"},
        "list": ["alice", "literal"],
    }


def test_assert_no_plaintext_secrets_rejects_sentinel() -> None:
    cfg = {"database": {"user": "user", "password": "pass"}}
    with pytest.raises(SecretConfigurationError):
        assert_no_plaintext_secrets(cfg)


def test_assert_no_plaintext_secrets_accepts_placeholders() -> None:
    cfg = {"database": {"user": "${LOGIN_DB}", "password": "${PASSWORD_DB}"}}
    # Ne doit rien lever : ce sont des placeholders, pas des secrets en clair.
    assert_no_plaintext_secrets(cfg)


def test_assert_no_plaintext_secrets_accepts_real_value() -> None:
    cfg = {"database": {"user": "alice_prod", "password": "S3cr3tP@ssw0rd!"}}
    assert_no_plaintext_secrets(cfg)


def test_assert_required_env_vars_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REQUIRED_FOO", raising=False)
    monkeypatch.delenv("REQUIRED_BAR", raising=False)
    with pytest.raises(SecretConfigurationError) as excinfo:
        assert_required_env_vars(["REQUIRED_FOO", "REQUIRED_BAR"])
    assert "REQUIRED_FOO" in str(excinfo.value)
    assert "REQUIRED_BAR" in str(excinfo.value)


def test_assert_required_env_vars_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENT_VAR", "x")
    assert_required_env_vars(["PRESENT_VAR"])

