"""S8 — immutable run plan for live execution."""
from __future__ import annotations

from pathlib import Path

import pytest

import run_execution


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(run_execution.LIVE_APPROVAL_TOKEN_ENV, "approved-token")
    monkeypatch.setenv("ALPHA_TRADE_LIVE_SECRET_POLICY", "env")


@pytest.fixture()
def live_preset() -> dict[str, object]:
    return run_execution._build_runtime_preset("live", submission_window="both")


def test_ensure_immutable_run_plan_writes_then_accepts_identical_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    live_preset: dict[str, object],
) -> None:
    monkeypatch.setattr(run_execution, "PROJECT_ROOT", tmp_path)
    plan_path = tmp_path / "plans" / "live_plan.json"

    first_path, first_fingerprint = run_execution._ensure_immutable_run_plan(
        mode="live",
        run_id="risk-1",
        trade_date="2026-05-22",
        account_id="live1",
        preset=live_preset,
        approval_token="approved-token",
        run_plan_file=str(plan_path),
    )
    second_path, second_fingerprint = run_execution._ensure_immutable_run_plan(
        mode="live",
        run_id="risk-1",
        trade_date="2026-05-22",
        account_id="live1",
        preset=live_preset,
        approval_token="approved-token",
        run_plan_file=str(plan_path),
    )

    assert first_path == second_path == plan_path
    assert first_fingerprint == second_fingerprint
    assert plan_path.exists()


def test_ensure_immutable_run_plan_rejects_payload_drift_for_same_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    live_preset: dict[str, object],
) -> None:
    monkeypatch.setattr(run_execution, "PROJECT_ROOT", tmp_path)
    plan_path = tmp_path / "plans" / "live_plan.json"

    run_execution._ensure_immutable_run_plan(
        mode="live",
        run_id="risk-1",
        trade_date="2026-05-22",
        account_id="live1",
        preset=live_preset,
        approval_token="approved-token",
        run_plan_file=str(plan_path),
    )

    drifted_preset = dict(live_preset)
    drifted_preset["max_slippage_bps"] = 12

    with pytest.raises(RuntimeError, match="immutable mismatch"):
        run_execution._ensure_immutable_run_plan(
            mode="live",
            run_id="risk-1",
            trade_date="2026-05-22",
            account_id="live1",
            preset=drifted_preset,
            approval_token="approved-token",
            run_plan_file=str(plan_path),
        )

