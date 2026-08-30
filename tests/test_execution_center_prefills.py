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
            swing_only=None,
        ),
    )

    execution_center._apply_execution_prefills("paper2")

    assert session_state["pipeline_risk_account_equity"] == 2_000.0
    assert session_state[execution_center.DETECTED_ACCOUNT_TYPE_KEY] == "cash"
    assert "pipeline_detected_legacy_execution_rule" not in session_state
    assert session_state[execution_center.CAPITAL_PRESET_KEY] == "capital_0_2000"
    assert session_state[execution_center.DETECTED_CAPITAL_PRESET_KEY] == "capital_0_2000"


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
            swing_only=None,
        ),
    )

    execution_center._apply_execution_prefills("paper1")

    assert session_state["pipeline_risk_account_equity"] == 3_500.0


def test_apply_selected_capital_preset_for_small_account_sets_expected_values(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.CAPITAL_PRESET_KEY: "capital_2001_5000",
    }
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)

    execution_center._apply_selected_capital_preset(
        PipelineExecutionDefaults(
            account_id="paper-small",
            broker_mode="paper",
            equity=2_000.0,
            account_type="cash",
            swing_only=None,
        ),
        selected_account_id="paper-small",
    )

    assert session_state["pipeline_risk_account_equity"] == 2_000.0
    assert session_state["pipeline_risk_per_trade_pct"] == 0.0125
    assert session_state["pipeline_risk_max_positions"] == 8
    assert session_state["pipeline_risk_max_position_weight"] == 0.25
    assert session_state["pipeline_risk_max_sector_weight"] == 0.50
    assert session_state["pipeline_risk_min_position_notional"] == 155.0
    assert session_state["pipeline_screener_liquidity_threshold_usd"] == 5_000_000.0
    assert session_state["pipeline_screener_min_historical_range_score"] == 60.0
    assert session_state["pipeline_selector_selection_size"] == 20
    assert session_state["pipeline_execution_account_type"] == "cash"
    assert session_state["pipeline_execution_max_entry_gap_pct"] == 0.03
    assert str(session_state[execution_center.CAPITAL_PRESET_APPLIED_SIGNATURE_KEY]).startswith("capital_2001_5000|")


def test_apply_selected_capital_preset_custom_does_not_override_existing_values(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.CAPITAL_PRESET_KEY: execution_center.CAPITAL_PRESET_CUSTOM,
        "pipeline_risk_account_equity": 3_000.0,
        "pipeline_risk_min_position_notional": 180.0,
    }
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)

    execution_center._apply_selected_capital_preset(
        PipelineExecutionDefaults(
            account_id="paper-custom",
            broker_mode="paper",
            equity=2_000.0,
            account_type="cash",
            swing_only=None,
        ),
        selected_account_id="paper-custom",
    )

    assert session_state["pipeline_risk_account_equity"] == 3_000.0
    assert session_state["pipeline_risk_min_position_notional"] == 180.0
    assert str(session_state[execution_center.CAPITAL_PRESET_APPLIED_SIGNATURE_KEY]).startswith("custom|")


def test_apply_selected_capital_preset_can_override_execution_settings_from_bucket(monkeypatch) -> None:
    session_state: dict[str, object] = {
        execution_center.CAPITAL_PRESET_KEY: "capital_50001_100000",
    }
    monkeypatch.setattr(execution_center.st, "session_state", session_state, raising=False)

    execution_center._apply_selected_capital_preset(
        PipelineExecutionDefaults(
            account_id="acct-broker-cash",
            broker_mode="paper",
            equity=60_000.0,
            account_type="cash",
            swing_only=None,
        ),
        selected_account_id="acct-broker-cash",
    )

    assert session_state["pipeline_risk_account_equity"] == 60_000.0
    assert session_state["pipeline_execution_account_type"] == "margin"
    assert "pipeline_execution_legacy_rule" not in session_state
    assert session_state["pipeline_execution_submission_window"] == "both"


def test_build_parameter_rerun_guidance_rows_covers_risk_execution_selector_and_screener() -> None:
    rows = execution_center._build_parameter_rerun_guidance_rows()

    assert {"Paramètres", "Relancer", "Pourquoi"} == set(rows[0].keys())
    assert any(row["Paramètres"] == "risk_*" and row["Relancer"] == "11 → 12" for row in rows)
    assert any(row["Paramètres"] == "execution_*" and row["Relancer"] == "12" for row in rows)
    assert any(row["Paramètres"] == "selector_*" and row["Relancer"] == "6 → 12" for row in rows)
    assert any(row["Paramètres"] == "screener_*" and row["Relancer"] == "3 → 12" for row in rows)
    assert any("Alpha Scanner" in row["Pourquoi"] for row in rows)

