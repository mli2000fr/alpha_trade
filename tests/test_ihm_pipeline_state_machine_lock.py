from __future__ import annotations

from ihm.pages import pipeline


def test_previous_pipeline_step_key_follows_canonical_order() -> None:
    assert pipeline._previous_pipeline_step_key("data_sanitizer_daily") == "import_alpaca_bar"
    assert pipeline._previous_pipeline_step_key("execution") == "risk_management"
    assert pipeline._previous_pipeline_step_key("import_alpaca_bar") is None


def test_pipeline_state_machine_lock_requires_previous_success() -> None:
    latest_by_step = {
        "risk_management": {"status": "failed"},
    }

    reason = pipeline._pipeline_state_machine_lock_reason("execution", latest_by_step)

    assert reason is not None
    assert "risk_management" in reason
    assert "failed" in reason


def test_pipeline_state_machine_lock_is_open_after_completed_previous_step() -> None:
    latest_by_step = {
        "risk_management": {"status": "completed"},
    }

    reason = pipeline._pipeline_state_machine_lock_reason("execution", latest_by_step)

    assert reason is None

