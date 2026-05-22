"""S8 — live requires vault or explicit env policy."""
from __future__ import annotations

from pathlib import Path

import pytest

from execution_engine.preflight import PreflightContext, check_live_secret_policy


@pytest.fixture(autouse=True)
def _clean_live_secret_policy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "ALPHA_TRADE_LIVE_SECRET_POLICY",
        "ALPHA_TRADE_VAULT_ADDR",
        "ALPHA_TRADE_VAULT_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


def _ctx(*, broker_mode: str = "live") -> PreflightContext:
    return PreflightContext(
        account_id="live1",
        broker_mode=broker_mode,
        config_path=Path("config.yaml"),
        skip_network=True,
    )


def test_live_secret_policy_fails_without_vault_or_env_override() -> None:
    res = check_live_secret_policy(_ctx(broker_mode="live"))
    assert res.status == "fail"
    assert "ALPHA_TRADE_LIVE_SECRET_POLICY=env" in res.message


def test_live_secret_policy_accepts_explicit_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_TRADE_LIVE_SECRET_POLICY", "env")

    res = check_live_secret_policy(_ctx(broker_mode="live"))

    assert res.status == "ok"
    assert res.details["source"] == "explicit_env_policy"


def test_live_secret_policy_accepts_explicit_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_TRADE_VAULT_ADDR", "http://127.0.0.1:8200")
    monkeypatch.setenv("ALPHA_TRADE_VAULT_TOKEN", "vault-token")

    res = check_live_secret_policy(_ctx(broker_mode="live"))

    assert res.status == "ok"
    assert res.details["source"] == "vault"


def test_live_secret_policy_skips_for_paper() -> None:
    res = check_live_secret_policy(_ctx(broker_mode="paper"))
    assert res.status == "skip"

