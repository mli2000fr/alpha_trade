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
    assert keys == ["import_alpaca_assets", "update_sector", "eodhd_backfill_history"]



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

    assert command == [
        command[0],
        "-u",
        "-m",
        "selector.alpha_scanner",
        "--chunk-size",
        "500",
        "--selection-size",
        "50",
        "--liquidity-threshold",
        "30000000.0",
        "--min-close",
        "10.0",
        "--max-volatility-ratio",
        "0.9",
        "--min-relative-strength-index",
        "100.0",
        "--min-high-52w-proximity",
        "0.75",
        "--min-weekly-trend-score",
        "1.0",
        "--min-atr-pct-20",
        "0.015",
        "--max-atr-pct-20",
        "0.06",
        "--min-market-cap",
        "2000000000.0",
        "--min-beta-126",
        "1.0",
        "--max-spread-bps",
        "25.0",
        "--earnings-blackout-days",
        "3",
        "--max-anomaly-count",
        "20",
        "--sector-cap-ratio",
        "0.3",
        "--log-level",
        "INFO",
        # Défaut swing strict : --require-above-ma200 actif (cf. STRICT_SWING_CASH_FILTERS)
        "--require-above-ma200",
    ]


def test_build_pipeline_command_alpha_scanner_exposes_supported_backend_options() -> None:
    command = build_pipeline_command(
        "alpha_scanner",
        PipelineLaunchOptions(
            selector_chunk_size=300,
            selector_selection_size=80,
            selector_max_workers=6,
            selector_liquidity_threshold=25_000_000.0,
            selector_min_close=12.0,
            selector_max_volatility_ratio=0.8,
            selector_min_relative_strength_index=105.0,
            selector_min_high_52w_proximity=0.8,
            selector_min_weekly_trend_score=0.9,
            selector_min_atr_pct_20=0.02,
            selector_max_atr_pct_20=0.05,
            selector_min_market_cap=3_000_000_000.0,
            selector_min_beta_126=1.2,
            selector_max_spread_bps=18.0,
            selector_earnings_blackout_days=5,
            selector_max_anomaly_count=12,
            selector_sector_cap_ratio=0.25,
            selector_log_level="DEBUG",
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "selector.alpha_scanner",
        "--chunk-size",
        "300",
        "--selection-size",
        "80",
        "--liquidity-threshold",
        "25000000.0",
        "--min-close",
        "12.0",
        "--max-volatility-ratio",
        "0.8",
        "--min-relative-strength-index",
        "105.0",
        "--min-high-52w-proximity",
        "0.8",
        "--min-weekly-trend-score",
        "0.9",
        "--min-atr-pct-20",
        "0.02",
        "--max-atr-pct-20",
        "0.05",
        "--min-market-cap",
        "3000000000.0",
        "--min-beta-126",
        "1.2",
        "--max-spread-bps",
        "18.0",
        "--earnings-blackout-days",
        "5",
        "--max-anomaly-count",
        "12",
        "--sector-cap-ratio",
        "0.25",
        "--log-level",
        "DEBUG",
        "--max-workers",
        "6",
        # Défaut swing strict (selector_require_above_ma200=True par défaut)
        "--require-above-ma200",
    ]


def test_build_pipeline_command_sentiment_pipeline_uses_backend_cli_contract() -> None:
    command = build_pipeline_command("sentiment_pipeline", PipelineLaunchOptions())

    assert command == [command[0], "-u", "-m", "event_sentiment"]


def test_build_pipeline_command_sentiment_pipeline_exposes_supported_backend_options() -> None:
    command = build_pipeline_command(
        "sentiment_pipeline",
        PipelineLaunchOptions(
            sentiment_start_utc="2026-04-01T00:00:00Z",
            sentiment_end_utc="2026-04-30T23:59:59Z",
            sentiment_symbols="msft, aapl,MSFT,nvda",
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "event_sentiment",
        "--start-utc",
        "2026-04-01T00:00:00Z",
        "--end-utc",
        "2026-04-30T23:59:59Z",
        "--symbols",
        "AAPL,MSFT,NVDA",
    ]


def test_build_pipeline_command_signal_aggregator_exposes_default_backend_options() -> None:
    command = build_pipeline_command("signal_aggregator", PipelineLaunchOptions())

    assert command == [
        command[0],
        "-u",
        "-m",
        "event_sentiment.signal_aggregator",
        "--sentiment-weight",
        "0.15",
        "--macro-weight",
        "0.1",
        "--lookback-days",
        "5",
        "--min-news-count",
        "2",
        "--time-decay-half-life-days",
        "2.0",
        "--log-level",
        "INFO",
    ]


def test_build_pipeline_command_signal_aggregator_exposes_supported_backend_options() -> None:
    command = build_pipeline_command(
        "signal_aggregator",
        PipelineLaunchOptions(
            trade_date="2026-04-19",
            signal_aggregator_all_symbols=True,
            signal_aggregator_sentiment_weight=0.2,
            signal_aggregator_macro_weight=0.15,
            signal_aggregator_lookback_days=7,
            signal_aggregator_min_news_count=3,
            signal_aggregator_time_decay_half_life_days=1.5,
            signal_aggregator_log_level="DEBUG",
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "event_sentiment.signal_aggregator",
        "--sentiment-weight",
        "0.2",
        "--macro-weight",
        "0.15",
        "--lookback-days",
        "7",
        "--min-news-count",
        "3",
        "--time-decay-half-life-days",
        "1.5",
        "--log-level",
        "DEBUG",
        "--trade-date",
        "2026-04-19",
        "--all-symbols",
    ]


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
            data_integrity_earnings_log_every=10,
            data_integrity_earnings_batch_size=75,
            data_integrity_earnings_resume=False,
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
        "--log-every",
        "10",
        "--batch-size",
        "75",
        "--from-date",
        "2026-04-01",
        "--to-date",
        "2026-04-30",
        "--limit",
        "90",
        "--no-resume",
    ]


def test_build_pipeline_command_sync_earnings_calendar_defaults_to_resumable_batches() -> None:
    command = build_pipeline_command("sync_earnings_calendar", PipelineLaunchOptions())

    assert command == [
        command[0],
        "-u",
        "-m",
        "dataIntegrityEngine.sync_earnings_calendar",
        "--sleep-seconds",
        "1.1",
        "--log-every",
        "25",
        "--batch-size",
        "50",
        "--resume",
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

    # Structure de base
    assert train_cmd[:6] == [train_cmd[0], "-u", "-m", "modelFactory", "--mode", "train"]
    assert "--accelerator" in train_cmd
    assert train_cmd[train_cmd.index("--accelerator") + 1] == "gpu"

    # Drapeaux booléens activés par défaut (swing prod)
    for flag in (
        "--include-sentiment",
        "--compare-lightgbm",
        "--enable-catboost",
        "--select-champion",
        "--optimize-thresholds",
        "--walkforward",  # walk-forward activé par défaut en swing
    ):
        assert flag in train_cmd, f"Flag attendu manquant : {flag}"
    assert "--champion-selection-metric" in train_cmd
    assert train_cmd[train_cmd.index("--champion-selection-metric") + 1] == "selection_score"

    # Cible swing cash
    assert train_cmd[train_cmd.index("--target-mode") + 1] == "swing_cash"
    assert train_cmd[train_cmd.index("--forecast-horizon") + 1] == "5"
    assert train_cmd[train_cmd.index("--target-up-threshold") + 1] == "0.02"
    assert train_cmd[train_cmd.index("--decision-threshold") + 1] == "0.55"
    assert train_cmd[train_cmd.index("--calibration-method") + 1] == "platt"

    # Hyperparams architecture & boosters désormais explicites (cf. audit)
    for flag in (
        "--sequence-length",
        "--batch-size",
        "--hidden-size",
        "--artifacts-dir",
        "--benchmark-symbol",
        "--lgbm-max-depth",
        "--catboost-depth",
        "--default-champion",
        "--cross-sectional-min-universe",
        "--calibration-min-samples",
        "--calibration-max-iter",
    ):
        assert flag in train_cmd, f"Flag avancé attendu manquant : {flag}"

    # Grille candidate decision thresholds émise quand --optimize-thresholds est actif
    assert "--candidate-decision-thresholds" in train_cmd

    # Predict
    assert predict_cmd[:6] == [predict_cmd[0], "-u", "-m", "modelFactory", "--mode", "predict"]
    assert predict_cmd[predict_cmd.index("--accelerator") + 1] == "gpu"
    assert "--artifacts-dir" in predict_cmd


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
        ml_walkforward=False,
    )

    train_cmd = build_pipeline_command("ml_train", options)

    assert train_cmd[train_cmd.index("--accelerator") + 1] == "cpu"

    # Drapeaux désactivés
    for flag in (
        "--include-sentiment",
        "--compare-lightgbm",
        "--enable-catboost",
        "--select-champion",
        "--optimize-thresholds",
        "--walkforward",
        "--candidate-decision-thresholds",
    ):
        assert flag not in train_cmd, f"Flag inattendu présent : {flag}"

    # Drapeaux activés explicitement
    for flag in (
        "--enable-global-model",
        "--enable-cross-sectional",
        "--optimize-target",
        "--candidate-horizons",
        "--candidate-up-thresholds",
        "--candidate-down-thresholds",
        "--min-trades-fraction",
    ):
        assert flag in train_cmd, f"Flag attendu manquant : {flag}"

    assert train_cmd[train_cmd.index("--global-model-name") + 1] == "lightgbm"


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

