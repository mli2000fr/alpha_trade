"""S8 — live execution requires an approval token."""
from __future__ import annotations

import pytest

import run_execution


@pytest.fixture(autouse=True)
def _clean_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        run_execution.LIVE_APPROVAL_TOKEN_ENV,
        "ALPHA_TRADE_LIVE_SECRET_POLICY",
        "ALPHA_TRADE_VAULT_ADDR",
        "ALPHA_TRADE_VAULT_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


def test_validate_live_approval_token_rejects_missing_expected_token() -> None:
    with pytest.raises(RuntimeError, match="aucun token d'approbation configuré"):
        run_execution._validate_live_approval_token("abc")


def test_validate_live_approval_token_rejects_missing_cli_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(run_execution.LIVE_APPROVAL_TOKEN_ENV, "approved-token")

    with pytest.raises(RuntimeError, match="manquant"):
        run_execution._validate_live_approval_token(None)


def test_validate_live_approval_token_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(run_execution.LIVE_APPROVAL_TOKEN_ENV, "approved-token")

    with pytest.raises(RuntimeError, match="invalide"):
        run_execution._validate_live_approval_token("wrong-token")


def test_validate_live_approval_token_accepts_matching_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(run_execution.LIVE_APPROVAL_TOKEN_ENV, "approved-token")

    token = run_execution._validate_live_approval_token("approved-token")

    assert token == "approved-token"


def test_parser_accepts_live_approval_flags() -> None:
    parser = run_execution.build_parser()

    args = parser.parse_args([
        "live",
        "--approval-token", "approved-token",
        "--run-plan-file", "artifacts/execution_run_plans/live.json",
    ])

    assert args.approval_token == "approved-token"
    assert args.run_plan_file.endswith("live.json")

