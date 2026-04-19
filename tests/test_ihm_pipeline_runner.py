from __future__ import annotations

from ihm.services.pipeline_runner import (
    PROJECT_ROOT,
    PipelineLaunchOptions,
    build_pipeline_command,
    build_subprocess_env,
    format_command_for_display,
    get_pipeline_steps,
)


def test_get_pipeline_steps_contains_expected_keys() -> None:
    keys = [step.key for step in get_pipeline_steps()]
    assert keys == [
        "import_alpaca_bar",
        "corporate_actions_sync",
        "data_sanitizer_daily",
        "stock_screener",
        "alpha_scanner",
        "sentiment_pipeline",
        "signal_aggregator",
        "risk_management",
        "execution",
        "corporate_actions_apply",
    ]



def test_build_pipeline_command_injects_account_for_account_aware_steps() -> None:
    options = PipelineLaunchOptions(
        account_id="test1",
        trade_date="2026-04-19",
        risk_account_equity=125000.0,
        execution_mode="paper",
        execution_run_id="risk-123",
        allow_outside_rth=True,
        auto_rebalance=True,
    )

    risk_command = build_pipeline_command("risk_management", options)
    execution_command = build_pipeline_command("execution", options)
    ca_apply_command = build_pipeline_command("corporate_actions_apply", options)

    assert risk_command[-2:] == ["--account", "test1"]
    assert "--trade-date" in risk_command
    assert "125000.0" in risk_command

    assert execution_command[1] == str(PROJECT_ROOT / "run_execution.py")
    assert execution_command[2] == "paper"
    assert execution_command[-2:] == ["--account", "test1"]
    assert "--allow-outside-rth" in execution_command
    assert "--auto-rebalance" in execution_command
    assert "risk-123" in execution_command

    assert ca_apply_command[-2:] == ["--account", "test1"]
    assert "--as-of" in ca_apply_command



def test_build_pipeline_command_omits_account_for_global_steps() -> None:
    options = PipelineLaunchOptions(account_id="test2", trade_date="2026-04-19")

    command = build_pipeline_command("stock_screener", options)

    assert command == [command[0], "-m", "screener.stock_screener"]



def test_build_subprocess_env_propagates_db_config_and_pythonpath() -> None:
    env = build_subprocess_env(
        db_config={
            "host": "localhost",
            "name": "alpha_trade",
            "user": "user1",
            "password": "secret1",
        },
        base_env={"PATH": "dummy", "PYTHONPATH": "existing_path"},
    )

    assert env["DB_HOST"] == "localhost"
    assert env["DB_NAME"] == "alpha_trade"
    assert env["LOGIN_DB"] == "user1"
    assert env["PASSWORD_DB"] == "secret1"
    assert str(PROJECT_ROOT) in env["PYTHONPATH"]
    assert "existing_path" in env["PYTHONPATH"]



def test_format_command_for_display_is_non_empty() -> None:
    rendered = format_command_for_display(["python", "-m", "corporate_actions", "sync", "--account", "test1"])
    assert rendered
    assert "corporate_actions" in rendered

