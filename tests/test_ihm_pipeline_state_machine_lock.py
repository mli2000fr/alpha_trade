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


def test_standalone_predict_does_not_require_aggregation_or_optional_training() -> None:
    for latest in ({}, {'signal_aggregator':{'status':'failed'}},
                   {'ml_train':{'status':'failed'}},
                   {'signal_aggregator':{'status':'failed'},'ml_train':{'status':'running'}}):
        assert pipeline._pipeline_state_machine_lock_reason('ml_predict',latest) is None


def test_predict_unlock_does_not_unlock_risk_or_execution() -> None:
    assert pipeline._pipeline_state_machine_lock_reason('risk_management',{}) is not None
    assert pipeline._pipeline_state_machine_lock_reason('execution',{}) is not None

