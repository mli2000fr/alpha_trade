from __future__ import annotations

import sys

import ihm.services.pipeline_runner as pipeline_runner
from ihm.services.pipeline_runner import (
    PROJECT_ROOT,
    PipelineLaunchOptions,
    build_pipeline_command,
    build_subprocess_env,
    format_command_for_display,
    get_pipeline_auxiliary_steps,
    get_pipeline_steps,
    run_pipeline_step,
)


def test_get_pipeline_steps_contains_expected_keys() -> None:
    keys = [step.key for step in get_pipeline_steps()]
    assert keys == [
        "import_alpaca_bar",
        "data_sanitizer_daily",
        "stock_screener",
        "sync_latest_quotes",
        "sync_earnings_calendar",
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


def test_get_pipeline_auxiliary_steps_contains_expected_keys() -> None:
    keys = [step.key for step in get_pipeline_auxiliary_steps()]
    assert keys == ["import_alpaca_assets", "update_sector"]



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

    assert command == [
        command[0],
        "-u",
        "-m",
        "screener.stock_screener",
        "--chunk-size",
        "500",
        "--benchmark",
        "SPY",
        "--liquidity-threshold-usd",
        "10000000.0",
        "--min-relative-strength-index",
        "100.0",
        "--historical-range-lookback-days",
        "504",
        "--min-historical-range-score",
        "70.0",
        "--first-pass-window-days",
        "400",
    ]


def test_build_pipeline_command_stock_screener_exposes_all_supported_backend_options() -> None:
    command = build_pipeline_command(
        "stock_screener",
        PipelineLaunchOptions(
            screener_chunk_size=250,
            screener_max_workers=6,
            screener_benchmark_symbol="qqq",
            screener_liquidity_threshold_usd=5_000_000.0,
            screener_min_relative_strength_index=105.0,
            screener_historical_range_lookback_days=252,
            screener_min_historical_range_score=80.0,
            screener_first_pass_window_days=504,
            screener_enable_two_pass_loading=False,
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "screener.stock_screener",
        "--chunk-size",
        "250",
        "--benchmark",
        "QQQ",
        "--liquidity-threshold-usd",
        "5000000.0",
        "--min-relative-strength-index",
        "105.0",
        "--historical-range-lookback-days",
        "252",
        "--min-historical-range-score",
        "80.0",
        "--first-pass-window-days",
        "504",
        "--max-workers",
        "6",
        "--disable-two-pass-loading",
    ]


def test_build_pipeline_command_alpha_scanner_is_always_strict_implicitly() -> None:
    command = build_pipeline_command("alpha_scanner", PipelineLaunchOptions())

    assert command == [command[0], "-u", "-m", "selector.alpha_scanner"]


def test_build_pipeline_command_selector_reference_sync_steps() -> None:
    quotes_command = build_pipeline_command(
        "sync_latest_quotes",
        PipelineLaunchOptions(data_integrity_quotes_limit=120, data_integrity_quotes_batch_size=80),
    )
    earnings_command = build_pipeline_command(
        "sync_earnings_calendar",
        PipelineLaunchOptions(
            data_integrity_earnings_from_date="2026-04-01",
            data_integrity_earnings_to_date="2026-04-30",
            data_integrity_earnings_limit=90,
            data_integrity_earnings_sleep_seconds=1.5,
        ),
    )

    assert quotes_command == [
        quotes_command[0],
        "-u",
        "-m",
        "dataIntegrityEngine.sync_latest_quotes",
        "--batch-size",
        "80",
        "--limit",
        "120",
    ]
    assert earnings_command == [
        earnings_command[0],
        "-u",
        "-m",
        "dataIntegrityEngine.sync_earnings_calendar",
        "--sleep-seconds",
        "1.5",
        "--from-date",
        "2026-04-01",
        "--to-date",
        "2026-04-30",
        "--limit",
        "90",
    ]


def test_build_pipeline_command_data_integrity_auxiliary_steps() -> None:
    assets_command = build_pipeline_command("import_alpaca_assets", PipelineLaunchOptions())
    fundamentals_command = build_pipeline_command(
        "update_sector",
        PipelineLaunchOptions(
            data_integrity_fundamentals_limit=40,
            data_integrity_fundamentals_sleep_seconds=1.2,
            data_integrity_fundamentals_log_every=10,
        ),
    )

    assert assets_command == [assets_command[0], "-u", "-m", "dataIntegrityEngine.import_alpaca_assets"]
    assert fundamentals_command == [
        fundamentals_command[0],
        "-u",
        "-m",
        "dataIntegrityEngine.update_sector",
        "--sleep-seconds",
        "1.2",
        "--log-every",
        "10",
        "--limit",
        "40",
    ]



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

    assert train_cmd == [
        train_cmd[0],
        "-u",
        "-m",
        "modelFactory",
        "--mode",
        "train",
        "--accelerator",
        "gpu",
        "--include-sentiment",
        "--compare-lightgbm",
        "--enable-catboost",
        "--select-champion",
        "--champion-selection-metric",
        "selection_score",
        "--optimize-thresholds",
    ]
    assert predict_cmd == [predict_cmd[0], "-u", "-m", "modelFactory", "--mode", "predict", "--accelerator", "gpu"]


def test_build_pipeline_command_ml_train_can_disable_or_enable_advanced_options() -> None:
    options = PipelineLaunchOptions(
        ml_accelerator="cpu",
        ml_include_sentiment=False,
        ml_enable_lightgbm=False,
        ml_enable_catboost=False,
        ml_enable_global_model=True,
        ml_global_model_name="lightgbm",
        ml_enable_cross_sectional=True,
        ml_select_champion=False,
        ml_optimize_thresholds=False,
        ml_optimize_target=True,
    )

    train_cmd = build_pipeline_command("ml_train", options)

    assert train_cmd == [
        train_cmd[0],
        "-u",
        "-m",
        "modelFactory",
        "--mode",
        "train",
        "--accelerator",
        "cpu",
        "--enable-global-model",
        "--global-model-name",
        "lightgbm",
        "--enable-cross-sectional",
        "--optimize-target",
    ]


def test_build_pipeline_command_import_news() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
    )

    command = build_pipeline_command("import_news", options)

    assert command[:3] == [command[0], "-u", str(PROJECT_ROOT / "event_sentiment" / "importe_news.py")]
    assert command[-4:] == ["--start-date", "2026-04-01", "--end-date", "2026-04-15"]


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

