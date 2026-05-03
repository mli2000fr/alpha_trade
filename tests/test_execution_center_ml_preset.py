from __future__ import annotations

from types import SimpleNamespace

import ihm.pages._execution_center as execution_center
from ihm.services.pipeline_runner import (
    RECOMMENDED_ML_DEBUG_GPU_ACCELERATOR,
    RECOMMENDED_ML_DEBUG_GPU_HEARTBEAT_INTERVAL_SECONDS,
    RECOMMENDED_ML_DEBUG_GPU_LOG_LEVEL,
    RECOMMENDED_ML_DEBUG_GPU_MAX_EPOCHS,
    RECOMMENDED_ML_DEBUG_GPU_MAX_WORKERS,
    RECOMMENDED_ML_DEBUG_GPU_WALKFORWARD,
    RECOMMENDED_ML_DEBUG_GPU_WATCHDOG_TIMEOUT_SECONDS,
    RECOMMENDED_ML_DEBUG_RAPIDE_ACCELERATOR,
    RECOMMENDED_ML_DEBUG_TRAIN_DEBUG_TRAIN,
    RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS,
    RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL,
    RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS,
    RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS,
    RECOMMENDED_ML_DEBUG_TRAIN_WALKFORWARD,
    RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS,
    RECOMMENDED_ML_PROD_SWING_ACCELERATOR,
    RECOMMENDED_ML_PROD_SWING_DEBUG_TRAIN,
    RECOMMENDED_ML_PROD_SWING_HEARTBEAT_INTERVAL_SECONDS,
    RECOMMENDED_ML_PROD_SWING_LOG_LEVEL,
    RECOMMENDED_ML_PROD_SWING_MAX_EPOCHS,
    RECOMMENDED_ML_PROD_SWING_MAX_WORKERS,
    RECOMMENDED_ML_PROD_SWING_WALKFORWARD,
    RECOMMENDED_ML_PROD_SWING_WATCHDOG_TIMEOUT_SECONDS,
)


def test_build_ml_train_preset_session_state_values_for_prod_swing_preset() -> None:
    values = execution_center._build_ml_train_preset_session_state_values(execution_center.ML_TRAIN_PRESET_PROD_SWING)

    assert values == {
        "pipeline_ml_accelerator": RECOMMENDED_ML_PROD_SWING_ACCELERATOR,
        "pipeline_ml_log_level": RECOMMENDED_ML_PROD_SWING_LOG_LEVEL,
        "pipeline_ml_debug_train": RECOMMENDED_ML_PROD_SWING_DEBUG_TRAIN,
        "pipeline_ml_max_workers": RECOMMENDED_ML_PROD_SWING_MAX_WORKERS,
        "pipeline_ml_walkforward": RECOMMENDED_ML_PROD_SWING_WALKFORWARD,
        "pipeline_ml_max_epochs": RECOMMENDED_ML_PROD_SWING_MAX_EPOCHS,
        "pipeline_ml_heartbeat_interval_seconds": RECOMMENDED_ML_PROD_SWING_HEARTBEAT_INTERVAL_SECONDS,
        "pipeline_ml_watchdog_timeout_seconds": RECOMMENDED_ML_PROD_SWING_WATCHDOG_TIMEOUT_SECONDS,
    }


def test_build_ml_train_preset_session_state_values_for_debug_rapide_preset() -> None:
    values = execution_center._build_ml_train_preset_session_state_values(execution_center.ML_TRAIN_PRESET_DEBUG_FAST)

    assert values == {
        "pipeline_ml_accelerator": RECOMMENDED_ML_DEBUG_RAPIDE_ACCELERATOR,
        "pipeline_ml_log_level": RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL,
        "pipeline_ml_debug_train": RECOMMENDED_ML_DEBUG_TRAIN_DEBUG_TRAIN,
        "pipeline_ml_max_workers": RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS,
        "pipeline_ml_walkforward": RECOMMENDED_ML_DEBUG_TRAIN_WALKFORWARD,
        "pipeline_ml_max_epochs": RECOMMENDED_ML_DEBUG_TRAIN_MAX_EPOCHS,
        "pipeline_ml_heartbeat_interval_seconds": RECOMMENDED_ML_DEBUG_TRAIN_HEARTBEAT_INTERVAL_SECONDS,
        "pipeline_ml_watchdog_timeout_seconds": RECOMMENDED_ML_DEBUG_TRAIN_WATCHDOG_TIMEOUT_SECONDS,
    }


def test_build_ml_train_preset_session_state_values_for_debug_gpu_preset() -> None:
    values = execution_center._build_ml_train_preset_session_state_values(execution_center.ML_TRAIN_PRESET_DEBUG_GPU)

    assert values == {
        "pipeline_ml_accelerator": RECOMMENDED_ML_DEBUG_GPU_ACCELERATOR,
        "pipeline_ml_log_level": RECOMMENDED_ML_DEBUG_GPU_LOG_LEVEL,
        "pipeline_ml_debug_train": True,
        "pipeline_ml_max_workers": RECOMMENDED_ML_DEBUG_GPU_MAX_WORKERS,
        "pipeline_ml_walkforward": RECOMMENDED_ML_DEBUG_GPU_WALKFORWARD,
        "pipeline_ml_max_epochs": RECOMMENDED_ML_DEBUG_GPU_MAX_EPOCHS,
        "pipeline_ml_heartbeat_interval_seconds": RECOMMENDED_ML_DEBUG_GPU_HEARTBEAT_INTERVAL_SECONDS,
        "pipeline_ml_watchdog_timeout_seconds": RECOMMENDED_ML_DEBUG_GPU_WATCHDOG_TIMEOUT_SECONDS,
    }


def test_apply_selected_ml_train_preset_updates_session_once(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.ML_TRAIN_PRESET_KEY: execution_center.ML_TRAIN_PRESET_DEBUG_FAST,
        "pipeline_ml_max_workers": 8,
    }
    monkeypatch.setattr(execution_center, "st", SimpleNamespace(session_state=session_state))

    execution_center._apply_selected_ml_train_preset()

    assert session_state["pipeline_ml_accelerator"] == RECOMMENDED_ML_DEBUG_RAPIDE_ACCELERATOR
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


def test_apply_selected_ml_train_preset_force_reapplies_values(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.ML_TRAIN_PRESET_KEY: execution_center.ML_TRAIN_PRESET_DEBUG_FAST,
    }
    monkeypatch.setattr(execution_center, "st", SimpleNamespace(session_state=session_state))

    execution_center._apply_selected_ml_train_preset()
    session_state["pipeline_ml_max_workers"] = 7

    execution_center._apply_selected_ml_train_preset(force=True)

    assert session_state["pipeline_ml_max_workers"] == RECOMMENDED_ML_DEBUG_TRAIN_MAX_WORKERS
    assert session_state[execution_center.ML_TRAIN_PRESET_APPLIED_SIGNATURE_KEY] == (
        f"{execution_center.ML_TRAIN_PRESET_DEBUG_FAST}|{execution_center.ML_TRAIN_PRESET_VERSION}"
    )


def test_apply_selected_ml_train_preset_normalizes_legacy_debug_key(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.ML_TRAIN_PRESET_KEY: execution_center.ML_TRAIN_PRESET_DEBUG,
    }
    monkeypatch.setattr(execution_center, "st", SimpleNamespace(session_state=session_state))

    execution_center._apply_selected_ml_train_preset()

    assert session_state[execution_center.ML_TRAIN_PRESET_KEY] == execution_center.ML_TRAIN_PRESET_DEBUG_FAST
    assert session_state["pipeline_ml_accelerator"] == RECOMMENDED_ML_DEBUG_RAPIDE_ACCELERATOR
    assert session_state["pipeline_ml_log_level"] == RECOMMENDED_ML_DEBUG_TRAIN_LOG_LEVEL


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


def test_is_selected_ml_train_preset_dirty_detects_manual_overrides() -> None:
    session_state: dict[str, object] = {
        execution_center.ML_TRAIN_PRESET_KEY: execution_center.ML_TRAIN_PRESET_PROD_SWING,
        **execution_center._build_ml_train_preset_session_state_values(execution_center.ML_TRAIN_PRESET_PROD_SWING),
    }

    assert execution_center._is_selected_ml_train_preset_dirty(session_state) is False

    session_state["pipeline_ml_max_epochs"] = 123

    assert execution_center._is_selected_ml_train_preset_dirty(session_state) is True


def test_build_ml_train_preset_summary_contains_key_values() -> None:
    summary = execution_center._build_ml_train_preset_summary(execution_center.ML_TRAIN_PRESET_DEBUG_GPU)

    assert "Debug GPU" in summary
    assert f"accélérateur `{RECOMMENDED_ML_DEBUG_GPU_ACCELERATOR}`" in summary
    assert f"logs `{RECOMMENDED_ML_DEBUG_GPU_LOG_LEVEL}`" in summary
    assert f"epochs `{RECOMMENDED_ML_DEBUG_GPU_MAX_EPOCHS}`" in summary


def test_build_ml_train_preset_summary_for_custom_mentions_manual_mode() -> None:
    summary = execution_center._build_ml_train_preset_summary(execution_center.ML_TRAIN_PRESET_CUSTOM)

    assert "manuel" in summary.lower()
    assert "Personnalisé" in summary


