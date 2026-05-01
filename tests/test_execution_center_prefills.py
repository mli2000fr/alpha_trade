from __future__ import annotations

from ihm.pages import _execution_center as execution_center
from ihm.services.account_defaults import PipelineExecutionDefaults


def test_apply_execution_prefills_auto_selects_execution_mode_from_broker_mode(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(
        execution_center,
        "get_pipeline_execution_defaults",
        lambda account_id: PipelineExecutionDefaults(
            account_id=str(account_id),
            broker_mode="live",
            equity=50_000.0,
            account_type="margin",
            pdt_rule=None,
            swing_only=None,
        ),
    )

    defaults = execution_center._apply_execution_prefills("live1")

    assert defaults is not None
    assert session_state[execution_center.DETECTED_BROKER_MODE_KEY] == "live"
    assert session_state[execution_center.DETECTED_BROKER_MODE_ACCOUNT_KEY] == "live1"
    assert session_state[execution_center.DETECTED_ACCOUNT_TYPE_KEY] == "margin"
    assert session_state[execution_center.EXECUTION_DEFAULTS_ACCOUNT_KEY] == "live1"
    assert session_state[execution_center.EXECUTION_MODE_ACCOUNT_KEY] == "live1"
    assert session_state["pipeline_execution_mode"] == "live"
    assert session_state["pipeline_execution_account_type"] == "margin"


def test_apply_execution_prefills_preserves_manual_mode_on_same_account(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.EXECUTION_DEFAULTS_ACCOUNT_KEY: "paper1",
        "pipeline_execution_mode": "simulate",
    }
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(
        execution_center,
        "get_pipeline_execution_defaults",
        lambda account_id: PipelineExecutionDefaults(
            account_id=str(account_id),
            broker_mode="paper",
            equity=12_500.0,
            account_type="cash",
            pdt_rule="off",
            swing_only=None,
        ),
    )

    execution_center._apply_execution_prefills("paper1")

    # Même compte => on respecte un override manuel (`simulate`) déjà choisi.
    assert session_state["pipeline_execution_mode"] == "simulate"
    assert session_state[execution_center.DETECTED_BROKER_MODE_KEY] == "paper"


def test_apply_execution_prefills_overrides_mode_when_switching_account(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.EXECUTION_DEFAULTS_ACCOUNT_KEY: "paper1",
        execution_center.EXECUTION_MODE_ACCOUNT_KEY: "paper1",
        "pipeline_execution_mode": "simulate",
    }
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(
        execution_center,
        "get_pipeline_execution_defaults",
        lambda account_id: PipelineExecutionDefaults(
            account_id=str(account_id),
            broker_mode="paper",
            equity=25_000.0,
            account_type="margin",
            pdt_rule=None,
            swing_only=None,
        ),
    )

    execution_center._apply_execution_prefills("paper2")

    # Switch de compte => on réaligne automatiquement le mode broker paper/live.
    assert session_state["pipeline_execution_mode"] == "paper"
    assert session_state[execution_center.EXECUTION_MODE_ACCOUNT_KEY] == "paper2"


def test_apply_execution_prefills_sets_risk_equity_from_broker_equity_on_account_switch(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.EXECUTION_DEFAULTS_ACCOUNT_KEY: "paper1",
        "pipeline_risk_account_equity": 100_000.0,
    }
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(
        execution_center,
        "get_pipeline_execution_defaults",
        lambda account_id: PipelineExecutionDefaults(
            account_id=str(account_id),
            broker_mode="paper",
            equity=2_000.0,
            account_type="cash",
            pdt_rule="off",
            swing_only=None,
        ),
    )

    execution_center._apply_execution_prefills("paper2")

    assert session_state["pipeline_risk_account_equity"] == 2_000.0
    assert session_state[execution_center.DETECTED_ACCOUNT_TYPE_KEY] == "cash"
    assert session_state[execution_center.DETECTED_PDT_RULE_KEY] == "off"


def test_apply_execution_prefills_preserves_manual_risk_equity_for_same_account(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.EXECUTION_DEFAULTS_ACCOUNT_KEY: "paper1",
        "pipeline_risk_account_equity": 3_500.0,
    }
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(
        execution_center,
        "get_pipeline_execution_defaults",
        lambda account_id: PipelineExecutionDefaults(
            account_id=str(account_id),
            broker_mode="paper",
            equity=2_000.0,
            account_type="cash",
            pdt_rule="off",
            swing_only=None,
        ),
    )

    execution_center._apply_execution_prefills("paper1")

    assert session_state["pipeline_risk_account_equity"] == 3_500.0


def test_apply_selected_risk_preset_for_small_account_sets_expected_values(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.RISK_PRESET_KEY: execution_center.RISK_PRESET_SMALL_ACCOUNT_2000,
    }
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)

    execution_center._apply_selected_risk_preset()

    assert session_state["pipeline_risk_account_equity"] == 2_000.0
    assert session_state["pipeline_risk_per_trade_pct"] == 0.02
    assert session_state["pipeline_risk_max_position_weight"] == 0.15
    assert session_state["pipeline_risk_min_position_notional"] == 150.0
    assert session_state[execution_center.RISK_PRESET_APPLIED_KEY] == execution_center.RISK_PRESET_SMALL_ACCOUNT_2000


def test_apply_selected_risk_preset_custom_does_not_override_existing_values(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.RISK_PRESET_KEY: execution_center.RISK_PRESET_CUSTOM,
        "pipeline_risk_account_equity": 3_000.0,
        "pipeline_risk_min_position_notional": 180.0,
    }
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)

    execution_center._apply_selected_risk_preset()

    assert session_state["pipeline_risk_account_equity"] == 3_000.0
    assert session_state["pipeline_risk_min_position_notional"] == 180.0
    assert session_state[execution_center.RISK_PRESET_APPLIED_KEY] == execution_center.RISK_PRESET_CUSTOM


