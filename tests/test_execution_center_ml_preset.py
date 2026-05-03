from __future__ import annotations

from types import SimpleNamespace

import ihm.pages._execution_center as execution_center
from ihm.services.pipeline_runner import (
    RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS,
    RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL,
    RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS,
    RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS,
    RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS,
)


def test_build_ml_train_preset_session_state_values_for_debug_preset() -> None:
    values = execution_center._build_ml_train_preset_session_state_values(execution_center.ML_TRAIN_PRESET_DEBUG)

    assert values == {
        "pipeline_ml_log_level": RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL,
        "pipeline_ml_debug_train": True,
        "pipeline_ml_max_workers": RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS,
        "pipeline_ml_walkforward": False,
        "pipeline_ml_max_epochs": RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS,
        "pipeline_ml_heartbeat_interval_seconds": RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS,
        "pipeline_ml_watchdog_timeout_seconds": RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS,
    }


def test_apply_selected_ml_train_preset_updates_session_once(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.ML_TRAIN_PRESET_KEY: execution_center.ML_TRAIN_PRESET_DEBUG,
        "pipeline_ml_max_workers": 8,
    }
    monkeypatch.setattr(execution_center, "st", SimpleNamespace(session_state=session_state))

    execution_center._apply_selected_ml_train_preset()

    assert session_state["pipeline_ml_log_level"] == RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL
    assert session_state["pipeline_ml_debug_train"] is True
    assert session_state["pipeline_ml_max_workers"] == RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS
    assert session_state["pipeline_ml_walkforward"] is False
    assert session_state["pipeline_ml_max_epochs"] == RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS
    assert session_state["pipeline_ml_heartbeat_interval_seconds"] == RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS
    assert session_state["pipeline_ml_watchdog_timeout_seconds"] == RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS

    session_state["pipeline_ml_max_workers"] = 7
    execution_center._apply_selected_ml_train_preset()

    assert session_state["pipeline_ml_max_workers"] == 7


def test_apply_selected_ml_train_preset_custom_does_not_override_values(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.ML_TRAIN_PRESET_KEY: execution_center.ML_TRAIN_PRESET_CUSTOM,
        "pipeline_ml_max_workers": 3,
        execution_center.ML_TRAIN_PRESET_APPLIED_SIGNATURE_KEY: "older",
    }
    monkeypatch.setattr(execution_center, "st", SimpleNamespace(session_state=session_state))

    execution_center._apply_selected_ml_train_preset()

    assert session_state["pipeline_ml_max_workers"] == 3
    assert session_state[execution_center.ML_TRAIN_PRESET_APPLIED_SIGNATURE_KEY] == (
        f"{execution_center.ML_TRAIN_PRESET_CUSTOM}|{execution_center.ML_TRAIN_PRESET_VERSION}"
    )

