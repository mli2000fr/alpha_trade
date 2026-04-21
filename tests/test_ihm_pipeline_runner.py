from __future__ import annotations

import sys

import ihm.services.pipeline_runner as pipeline_runner
from ihm.services.pipeline_runner import (
    PROJECT_ROOT,
    PipelineLaunchOptions,
    build_pipeline_command,
    build_subprocess_env,
    format_command_for_display,
    get_pipeline_steps,
    run_pipeline_step,
)


def test_get_pipeline_steps_contains_expected_keys() -> None:
    keys = [step.key for step in get_pipeline_steps()]
    assert keys == [
        "import_alpaca_bar",
        "data_sanitizer_daily",
        "stock_screener",
        "alpha_scanner",
        "sentiment_pipeline",
        "signal_aggregator",
        "ml_train",
        "ml_predict",
        "risk_management",
        "execution",
        "corporate_actions_sync",
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
        execution_account_type="cash",
        execution_pdt_rule="auto",
        execution_swing_only=True,
    )

    risk_command = build_pipeline_command("risk_management", options)
    execution_command = build_pipeline_command("execution", options)
    ca_apply_command = build_pipeline_command("corporate_actions_apply", options)

    assert risk_command[:4] == [risk_command[0], "-u", "-m", "risk_management"]
    assert risk_command[-2:] == ["--account", "test1"]
    assert "--trade-date" in risk_command
    assert "125000.0" in risk_command

    assert execution_command[:3] == [execution_command[0], "-u", str(PROJECT_ROOT / "run_execution.py")]
    assert execution_command[3] == "paper"
    assert execution_command[-2:] == ["--account", "test1"]
    assert "--allow-outside-rth" in execution_command
    assert "--auto-rebalance" in execution_command
    assert "--account-type" in execution_command
    assert execution_command[execution_command.index("--account-type") + 1] == "cash"
    assert "--pdt-rule" in execution_command
    assert execution_command[execution_command.index("--pdt-rule") + 1] == "auto"
    assert "--swing-only" in execution_command
    assert "risk-123" in execution_command

    assert ca_apply_command[-2:] == ["--account", "test1"]
    assert "--as-of" in ca_apply_command



def test_build_pipeline_command_omits_account_for_global_steps() -> None:
    options = PipelineLaunchOptions(account_id="test2", trade_date="2026-04-19")

    command = build_pipeline_command("stock_screener", options)

    assert command == [command[0], "-u", "-m", "screener.stock_screener"]


def test_build_pipeline_command_alpha_scanner_can_enable_strict_preset() -> None:
    strict_command = build_pipeline_command(
        "alpha_scanner",
        PipelineLaunchOptions(alpha_scanner_use_strict_preset=True),
    )
    default_command = build_pipeline_command(
        "alpha_scanner",
        PipelineLaunchOptions(alpha_scanner_use_strict_preset=False),
    )

    assert strict_command == [strict_command[0], "-u", "-m", "selector.alpha_scanner", "--preset", "strict"]
    assert default_command == [default_command[0], "-u", "-m", "selector.alpha_scanner"]



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



def test_build_pipeline_command_ml_steps() -> None:
    options = PipelineLaunchOptions(ml_accelerator="gpu")

    train_cmd = build_pipeline_command("ml_train", options)
    predict_cmd = build_pipeline_command("ml_predict", options)

    assert train_cmd == [train_cmd[0], "-u", "-m", "modelFactory", "--mode", "train", "--include-sentiment", "--accelerator", "gpu"]
    assert predict_cmd == [predict_cmd[0], "-u", "-m", "modelFactory", "--mode", "predict", "--accelerator", "gpu"]


def test_run_pipeline_step_streams_logs_via_callback(monkeypatch) -> None:
    command = [
        sys.executable,
        "-c",
        (
            "import sys, time; "
            "print('stdout-1', flush=True); "
            "sys.stderr.write('stderr-1\\n'); sys.stderr.flush(); "
            "time.sleep(0.2); "
            "print('stdout-2', flush=True)"
        ),
    ]
    monkeypatch.setattr(pipeline_runner, "build_pipeline_command", lambda step_key, options: command)

    updates: list[tuple[str, str, str]] = []

    result = run_pipeline_step(
        "fake_step",
        PipelineLaunchOptions(),
        on_update=lambda snapshot: updates.append((snapshot.status, snapshot.stdout, snapshot.stderr)),
    )

    assert result.returncode == 0
    assert "stdout-1" in result.stdout
    assert "stdout-2" in result.stdout
    assert "stderr-1" in result.stderr
    assert updates
    assert any("stdout-1" in stdout for _, stdout, _ in updates)
    assert any("stderr-1" in stderr for _, _, stderr in updates)
    assert updates[-1][0] == "completed"



def test_format_command_for_display_is_non_empty() -> None:
    rendered = format_command_for_display(["python", "-m", "corporate_actions", "sync", "--account", "test1"])
    assert rendered
    assert "corporate_actions" in rendered

