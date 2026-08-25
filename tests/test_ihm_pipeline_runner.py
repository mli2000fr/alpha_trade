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
    get_pipeline_workflow_steps,
    is_canonical_pipeline_step_number,
    is_workflow_core_step_number,
    parse_pipeline_step_number,
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
        "publish_tradable_universe",
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


def test_execution_step_depends_on_risk_management_contract_name() -> None:
    execution_step = next(step for step in get_pipeline_steps() if step.key == "execution")
    assert execution_step.deps == "risk_management"


def test_publish_tradable_universe_command_uses_trade_date_and_equity_preset() -> None:
    options = PipelineLaunchOptions(risk_account_equity=100_000.0, trade_date="2026-07-10")
    command = build_pipeline_command("publish_tradable_universe", options)
    preset = pipeline_runner.resolve_capital_preset_for_equity(options.risk_account_equity)

    assert command[:4] == [command[0], "-u", "-m", "common.publish_tradable_universe"]
    assert command[command.index("--trade-date") + 1] == "2026-07-10"
    assert command[command.index("--capital-preset-key") + 1] == preset.key


def test_pipeline_step_number_helpers_handle_main_suffixes_and_auxiliary_prefixes() -> None:
    assert parse_pipeline_step_number("7") == 7
    assert parse_pipeline_step_number("7bis") == 7
    assert parse_pipeline_step_number(" 10-ter ") == 10
    assert parse_pipeline_step_number("B1") is None

    assert is_canonical_pipeline_step_number("1") is True
    assert is_canonical_pipeline_step_number("12") is True
    assert is_canonical_pipeline_step_number("7bis") is False
    assert is_canonical_pipeline_step_number("B1") is False
    assert is_workflow_core_step_number("7bis") is False


def test_get_pipeline_workflow_steps_ignores_removed_7bis_when_explicitly_selected() -> None:
    keys = [
        step.key
        for step in get_pipeline_workflow_steps(
            selected_step_keys=("relevance_backfill", "signal_aggregator", "execution"),
        )
    ]

    assert keys == ["signal_aggregator", "execution"]


def test_get_pipeline_auxiliary_steps_contains_expected_keys() -> None:
    keys = [step.key for step in get_pipeline_auxiliary_steps()]
    assert keys == ["import_alpaca_assets", "update_sector", "eodhd_backfill_history"]


def test_get_pipeline_workflow_steps_defaults_to_live_ml_first_without_training() -> None:
    keys = [step.key for step in get_pipeline_workflow_steps()]

    assert keys == [
        "import_alpaca_bar",
        "data_sanitizer_daily",
        "stock_screener",
        "sync_latest_quotes",
        "sync_earnings_calendar",
        "publish_tradable_universe",
        "sentiment_pipeline",
        "signal_aggregator",
        "ml_predict",
        "risk_management",
        "execution",
    ]


def test_get_pipeline_workflow_steps_can_start_at_3_and_append_corporate_actions() -> None:
    keys = [
        step.key
        for step in get_pipeline_workflow_steps(
            start_step="3",
            include_ml_train=False,
            include_corporate_actions_sync=False,
            include_corporate_actions_apply=True,
        )
    ]

    assert keys == [
        "stock_screener",
        "sync_latest_quotes",
        "sync_earnings_calendar",
        "publish_tradable_universe",
        "sentiment_pipeline",
        "signal_aggregator",
        "ml_predict",
        "risk_management",
        "execution",
        "corporate_actions_sync",
        "corporate_actions_apply",
    ]


def test_get_pipeline_workflow_steps_can_use_explicit_selected_step_keys_in_canonical_order() -> None:
    keys = [
        step.key
        for step in get_pipeline_workflow_steps(
            selected_step_keys=("execution", "stock_screener", "import_alpaca_bar", "relevance_backfill", "ml_predict"),
        )
    ]

    assert keys == [
        "import_alpaca_bar",
        "stock_screener",
        "ml_predict",
        "execution",
    ]



def test_build_pipeline_command_injects_account_for_account_aware_steps() -> None:
    options = PipelineLaunchOptions(
        account_id="test1",
        trade_date="2026-04-19",
        risk_account_equity=125000.0,
        risk_min_position_notional=150.0,
        risk_max_sector_weight=0.27,
        execution_mode="paper",
        execution_run_id="risk-123",
        allow_outside_rth=True,
        auto_rebalance=True,
        execution_account_type="cash",
        execution_swing_only=True,
        execution_take_profit_pct=0.065,
        execution_trailing_stop_pct=0.04,
        execution_max_entry_gap_pct=0.03,
    )

    risk_command = build_pipeline_command("risk_management", options)
    execution_command = build_pipeline_command("execution", options)
    ca_apply_command = build_pipeline_command("corporate_actions_apply", options)

    assert risk_command[:4] == [risk_command[0], "-u", "-m", "risk_management"]
    assert risk_command[-2:] == ["--account", "test1"]
    assert "--trade-date" in risk_command
    assert "125000.0" in risk_command
    assert "--min-position-notional" in risk_command
    assert risk_command[risk_command.index("--min-position-notional") + 1] == "150.0"
    assert "--max-sector-weight" in risk_command
    assert risk_command[risk_command.index("--max-sector-weight") + 1] == "0.27"
    assert "--filter-no-ml" not in risk_command

    assert execution_command[:3] == [execution_command[0], "-u", str(PROJECT_ROOT / "run_execution.py")]
    assert execution_command[3] == "paper"
    assert execution_command[-2:] == ["--account", "test1"]
    assert "--allow-outside-rth" in execution_command
    assert "--auto-rebalance" in execution_command
    assert "--account-type" in execution_command
    assert execution_command[execution_command.index("--account-type") + 1] == "cash"
    assert "--swing-only" in execution_command
    assert "--profit-taker-pct" in execution_command
    assert execution_command[execution_command.index("--profit-taker-pct") + 1] == "0.065"
    assert "--trailing-stop-pct" in execution_command
    assert execution_command[execution_command.index("--trailing-stop-pct") + 1] == "0.04"
    assert "--max-entry-gap-pct" in execution_command
    assert execution_command[execution_command.index("--max-entry-gap-pct") + 1] == "0.03"
    assert "risk-123" in execution_command

    assert ca_apply_command[-2:] == ["--account", "test1"]
    assert "--as-of" in ca_apply_command


def test_build_pipeline_command_propagates_live_approval_controls() -> None:
    options = PipelineLaunchOptions(
        account_id="live1",
        trade_date="2026-05-22",
        execution_mode="live",
        execution_live_approval_token="approved-token",
        execution_run_plan_file="artifacts/execution_run_plans/live1.json",
    )

    execution_command = build_pipeline_command("execution", options)

    assert execution_command[:3] == [execution_command[0], "-u", str(PROJECT_ROOT / "run_execution.py")]
    assert execution_command[3] == "live"
    assert "--approval-token" in execution_command
    assert execution_command[execution_command.index("--approval-token") + 1] == "approved-token"
    assert "--run-plan-file" in execution_command
    assert execution_command[execution_command.index("--run-plan-file") + 1].endswith("live1.json")


def test_build_pipeline_command_propagates_risk_shadow_compare_options() -> None:
    options = PipelineLaunchOptions(
        trade_date="2026-04-19",
        risk_enable_shadow_compare=True,
        risk_shadow_compare_run_id="risk-ref-001",
    )

    risk_command = build_pipeline_command("risk_management", options)

    assert "--enable-shadow-compare" in risk_command
    assert "--shadow-compare-run-id" in risk_command
    assert risk_command[risk_command.index("--shadow-compare-run-id") + 1] == "risk-ref-001"


def test_build_pipeline_command_propagates_allow_fractional_shares_to_risk_and_execution() -> None:
    options = PipelineLaunchOptions(
        trade_date="2026-06-09",
        execution_mode="paper",
        allow_fractional_shares=True,
    )

    risk_command = build_pipeline_command("risk_management", options)
    execution_command = build_pipeline_command("execution", options)

    assert "--allow-fractional-shares" in risk_command
    assert "--allow-fractional-shares" in execution_command


def test_build_pipeline_command_omits_allow_fractional_shares_when_disabled() -> None:
    options = PipelineLaunchOptions(
        trade_date="2026-06-09",
        execution_mode="paper",
        allow_fractional_shares=False,
    )

    risk_command = build_pipeline_command("risk_management", options)
    execution_command = build_pipeline_command("execution", options)

    assert "--allow-fractional-shares" not in risk_command
    assert "--allow-fractional-shares" not in execution_command


def test_build_pipeline_command_propagates_live_risk_guard_options() -> None:
    options = PipelineLaunchOptions(
        trade_date="2026-04-19",
        risk_max_portfolio_drawdown_pct=0.12,
        risk_max_daily_loss_pct=0.025,
        risk_target_annual_vol=0.13,
        risk_vol_target_lookback_days=45,
        risk_min_ml_coverage_ratio=0.80,
    )

    risk_command = build_pipeline_command("risk_management", options)

    assert "--max-portfolio-drawdown-pct" in risk_command
    assert risk_command[risk_command.index("--max-portfolio-drawdown-pct") + 1] == "0.12"
    assert "--max-daily-loss-pct" in risk_command
    assert risk_command[risk_command.index("--max-daily-loss-pct") + 1] == "0.025"
    assert "--target-annual-vol" in risk_command
    assert risk_command[risk_command.index("--target-annual-vol") + 1] == "0.13"
    assert "--vol-target-lookback-days" in risk_command
    assert risk_command[risk_command.index("--vol-target-lookback-days") + 1] == "45"
    assert "--min-ml-coverage-ratio" in risk_command
    assert risk_command[risk_command.index("--min-ml-coverage-ratio") + 1] == "0.8"



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
        "30000000.0",
        "--min-relative-strength-index",
        "100.0",
        "--historical-range-lookback-days",
        "504",
        "--min-historical-range-score",
        "70.0",
        "--first-pass-window-days",
        "400",
        "--trade-date",
        "2026-04-19",
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
        "0.8",
        "--max-spread-bps",
        "40.0",
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


def test_pipeline_launch_options_defaults_to_alpaca_for_sentiment_news_provider() -> None:
    options = PipelineLaunchOptions()

    assert options.sentiment_news_provider == "eodhd"


def test_build_pipeline_command_sentiment_pipeline_uses_backend_cli_contract() -> None:
    """Step 7 génère une commande PowerShell chaînée incluant désormais le contextual."""
    command = build_pipeline_command("sentiment_pipeline", PipelineLaunchOptions())

    assert command[0] == "powershell.exe", f"Step 7 doit lancer via powershell.exe, got {command[0]}"
    ps_script = command[-1]
    # Les 5 étapes chaînées doivent être présentes dans le script PS
    assert "event_sentiment.importe_news" in ps_script
    assert "--news-provider" in ps_script
    assert "eodhd" in ps_script
    assert "event_sentiment.relevance_backfill" in ps_script
    assert "event_sentiment.history_backfill" in ps_script
    assert "--skip-features" in ps_script
    assert "--scoring-mode contextual_only" in ps_script
    assert "--skip-ingestion" in ps_script
    assert "--symbol-source stock_scores_all" in ps_script
    assert "--symbol-source tradable-universe" in ps_script
    assert "--ticker-symbol-source tradable-universe" in ps_script
    assert ps_script.index("Calcul relevance_score (scope univers tradable / override CSV)") < ps_script.index(
        "Scoring FinBERT standard (scope univers tradable / override CSV)"
    )
    assert ps_script.index("Scoring FinBERT contextuel (scope univers tradable / override CSV)") < ps_script.index(
        "Agregation features : ticker=univers tradable, secteur=scope large importe"
    )


def test_build_pipeline_command_sentiment_pipeline_exposes_supported_backend_options() -> None:
    """Step 7 injecte les options sentiment dans le script PS fusionné."""
    command = build_pipeline_command(
        "sentiment_pipeline",
        PipelineLaunchOptions(
            sentiment_start_utc="2026-04-01T00:00:00Z",
            sentiment_end_utc="2026-04-30T23:59:59Z",
            sentiment_symbols="msft, aapl,MSFT,nvda",
            sentiment_news_provider="alpaca",
            sentiment_ticker_relevance_mode="strict",
            sentiment_scoring_mode="standard_and_contextual",
            sentiment_enable_contextual_scoring=True,
            sentiment_contextual_min_relevance=0.25,
            sentiment_contextual_max_pairs=2000,
            sentiment_pending_limit=5000,
            sentiment_pending_max_batches_per_run=10,
            sentiment_finbert_batch_size=32,
        ),
    )

    assert command[0] == "powershell.exe"
    ps_script = command[-1]
    assert "--news-provider" in ps_script
    assert "alpaca" in ps_script
    assert "--ticker-relevance-mode" in ps_script
    assert "strict" in ps_script
    assert "--sentiment-pending-limit" in ps_script
    assert "5000" in ps_script
    assert "--sentiment-pending-max-batches" in ps_script
    assert "10" in ps_script
    assert "--finbert-batch-size" in ps_script
    assert "32" in ps_script
    assert "--contextual-min-relevance" in ps_script
    assert "0.25" in ps_script
    assert "--contextual-max-pairs" in ps_script
    assert "2000" in ps_script
    assert "--start-utc" in ps_script
    assert "2026-04-01T00:00:00Z" in ps_script
    assert "--end-utc" in ps_script
    assert "2026-04-30T23:59:59Z" in ps_script
    assert "--start-date 2026-04-01" in ps_script
    assert "--end-date 2026-04-30" in ps_script
    assert "AAPL,MSFT,NVDA" in ps_script
    assert "--symbol-source stock_scores_all" in ps_script
    assert "--ticker-symbols AAPL,MSFT,NVDA" in ps_script
    # Les étapes relevance, history et contextual doivent toutes être présentes
    assert "event_sentiment.relevance_backfill" in ps_script
    assert "event_sentiment.history_backfill" in ps_script
    assert "--scoring-mode contextual_only" in ps_script
    assert ps_script.index("Calcul relevance_score (scope univers tradable / override CSV)") < ps_script.index(
        "Scoring FinBERT standard (scope univers tradable / override CSV)"
    )
    assert ps_script.index("Scoring FinBERT contextuel (scope univers tradable / override CSV)") < ps_script.index(
        "Agregation features : ticker=univers tradable, secteur=scope large importe"
    )


def test_build_pipeline_command_sentiment_pipeline_supports_contextual_phase_with_explicit_thresholds() -> None:
    command = build_pipeline_command(
        "sentiment_pipeline",
        PipelineLaunchOptions(
            sentiment_start_utc="2026-04-01T00:00:00Z",
            sentiment_end_utc="2026-04-30T23:59:59Z",
            sentiment_symbols="aapl",
            sentiment_news_provider="eodhd",
            sentiment_scoring_mode="standard_and_contextual",
            sentiment_enable_contextual_scoring=True,
            sentiment_contextual_min_relevance=0.25,
            sentiment_contextual_max_pairs=2000,
            sentiment_feature_flush_every_n_batches=3,
        ),
    )

    assert command[0] == "powershell.exe"
    ps_script = command[-1]
    # Le step 7 canonique importe large, calcule relevance_score avant le scoring standard,
    # puis reconstruit les features ticker filtrées.
    assert "--symbol-source stock_scores_all" in ps_script
    assert "--skip-features" in ps_script
    assert "--scoring-mode contextual_only" in ps_script
    assert "--contextual-min-relevance 0.25" in ps_script
    assert "--contextual-max-pairs 2000" in ps_script
    assert "event_sentiment.relevance_backfill" in ps_script
    assert "event_sentiment.history_backfill" in ps_script
    assert "AAPL" in ps_script
    assert "--ticker-symbols AAPL" in ps_script
    assert ps_script.index("Calcul relevance_score (scope univers tradable / override CSV)") < ps_script.index(
        "Scoring FinBERT standard (scope univers tradable / override CSV)"
    )
    assert ps_script.index("Scoring FinBERT contextuel (scope univers tradable / override CSV)") < ps_script.index(
        "Agregation features : ticker=univers tradable, secteur=scope large importe"
    )


def test_build_pipeline_command_rebuild_daily_sentiment_features_only_reuses_manual_scope_and_provider() -> None:
    command = build_pipeline_command(
        "rebuild_daily_sentiment_features_only",
        PipelineLaunchOptions(
            news_import_start_date="2022-01-01",
            news_import_end_date="2022-01-31",
            news_import_symbol_source="tradable-universe",
            news_import_max_symbols=25,
            sentiment_news_provider="eodhd",
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "event_sentiment.history_backfill",
        "--start-date",
        "2022-01-01",
        "--end-date",
        "2022-01-31",
        "--ingestion-source",
        "eodhd",
        "--ticker-symbol-source",
        "tradable-universe",
        "--ticker-max-symbols",
        "25",
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


def test_build_pipeline_command_sync_latest_quotes_accepts_historical_period() -> None:
    command = build_pipeline_command(
        "sync_latest_quotes",
        PipelineLaunchOptions(
            data_integrity_quotes_symbol_source="active_tradable",
            data_integrity_quotes_from_date="2026-04-01",
            data_integrity_quotes_to_date="2026-04-30",
            data_integrity_quotes_start_symbol=" aag ",
            data_integrity_quotes_batch_size=60,
            data_integrity_quotes_limit=25,
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "dataIntegrityEngine.sync_latest_quotes",
        "--batch-size",
        "60",
        "--symbol-source",
        "active-tradable",
        "--from-date",
        "2026-04-01",
        "--to-date",
        "2026-04-30",
        "--start-symbol",
        "AAG",
        "--limit",
        "25",
    ]


def test_build_pipeline_command_sync_earnings_calendar_accepts_symbol_scope() -> None:
    command = build_pipeline_command(
        "sync_earnings_calendar",
        PipelineLaunchOptions(
            data_integrity_earnings_symbol_source="stock_scores_history",
            data_integrity_earnings_from_date="2026-04-01",
            data_integrity_earnings_to_date="2026-04-30",
            data_integrity_earnings_batch_size=75,
            data_integrity_earnings_resume=True,
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "dataIntegrityEngine.sync_earnings_calendar",
        "--sleep-seconds",
        str(PipelineLaunchOptions().data_integrity_earnings_sleep_seconds),
        "--log-every",
        str(PipelineLaunchOptions().data_integrity_earnings_log_every),
        "--batch-size",
        "75",
        "--symbol-source",
        "stock-scores-history",
        "--from-date",
        "2026-04-01",
        "--to-date",
        "2026-04-30",
        "--resume",
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
            data_integrity_fundamentals_provider="finnhub",
            data_integrity_fundamentals_overwrite_existing=True,
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
        "--provider",
        "finnhub",
        "--sleep-seconds",
        "1.2",
        "--log-every",
        "10",
        "--limit",
        "40",
        "--overwrite-existing",
    ]


def test_build_pipeline_command_update_sector_uses_yahoo_finance_by_default() -> None:
    command = build_pipeline_command("update_sector", PipelineLaunchOptions())

    assert command == [
        command[0],
        "-u",
        "-m",
        "dataIntegrityEngine.update_sector",
        "--provider",
        "yahoo_finance",
        "--sleep-seconds",
        str(PipelineLaunchOptions().data_integrity_fundamentals_sleep_seconds),
        "--log-every",
        str(PipelineLaunchOptions().data_integrity_fundamentals_log_every),
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
    assert "--ml-mode" not in train_cmd
    assert train_cmd[train_cmd.index("--training-start-date") + 1] == pipeline_runner.DEFAULT_ML_TRAINING_START_DATE
    assert train_cmd[train_cmd.index("--symbol-source") + 1] == "tradable-universe"
    assert train_cmd[train_cmd.index("--wf-min-train-size") + 1] == "504"
    assert train_cmd[train_cmd.index("--wf-val-size") + 1] == "126"
    assert train_cmd[train_cmd.index("--wf-test-size") + 1] == "126"
    assert train_cmd[train_cmd.index("--wf-step-size") + 1] == "126"
    assert train_cmd[train_cmd.index("--wf-max-splits") + 1] == "11"

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
        "--heartbeat-interval-seconds",
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
    assert predict_cmd[predict_cmd.index("--symbol-source") + 1] == "tradable-universe"
    assert "--artifacts-dir" in predict_cmd
    assert "--batch-id" not in predict_cmd


def test_build_pipeline_command_ml_predict_uses_selected_batch() -> None:
    command = build_pipeline_command(
        "ml_predict",
        PipelineLaunchOptions(ml_predict_batch_id="model-factory-20260716-expert"),
    )

    assert command[command.index("--batch-id") + 1] == "model-factory-20260716-expert"


def test_build_pipeline_command_ml_train_can_disable_or_enable_advanced_options() -> None:
    options = PipelineLaunchOptions(
        ml_accelerator="cpu",
        ml_debug_train=True,
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
        ml_training_start_date="2018-06-01",
        ml_heartbeat_interval_seconds=30.0,
        ml_watchdog_timeout_seconds=600,
    )

    train_cmd = build_pipeline_command("ml_train", options)

    assert train_cmd[train_cmd.index("--accelerator") + 1] == "cpu"
    assert "--ml-mode" not in train_cmd
    assert train_cmd[train_cmd.index("--training-start-date") + 1] == "2018-06-01"

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
        "--debug-train",
        "--enable-global-model",
        "--enable-cross-sectional",
        "--optimize-target",
        "--candidate-horizons",
        "--candidate-up-thresholds",
        "--candidate-down-thresholds",
        "--min-trades-fraction",
        "--watchdog-timeout-seconds",
    ):
        assert flag in train_cmd, f"Flag attendu manquant : {flag}"

    assert train_cmd[train_cmd.index("--global-model-name") + 1] == "lightgbm"
    assert train_cmd[train_cmd.index("--heartbeat-interval-seconds") + 1] == "30.0"
    assert train_cmd[train_cmd.index("--watchdog-timeout-seconds") + 1] == "600"


def test_build_pipeline_command_ml_train_xgboost_champion_three_candidates() -> None:
    """P3-3 : champion auto → 3 candidats côté core (flag unique --global-champion)."""
    options = PipelineLaunchOptions(
        ml_enable_global_model=True,
        ml_global_champion=True,
        ml_global_model_name="xgboost",
    )

    train_cmd = build_pipeline_command("ml_train", options)

    # P3-3 : champion auto → 3 candidats ; --global-model-name redondant et omis.
    assert "--global-model-name" not in train_cmd
    assert "--global-champion" in train_cmd
    assert "--ranking-include-xgboost" not in train_cmd


def test_build_pipeline_command_ml_train_xgboost_single_without_champion() -> None:
    """P3-3 : backend XGBoost sans champion → candidat unique XGBoost."""
    options = PipelineLaunchOptions(
        ml_enable_global_model=True,
        ml_global_champion=False,
        ml_global_model_name="xgboost",
    )

    train_cmd = build_pipeline_command("ml_train", options)

    assert train_cmd[train_cmd.index("--global-model-name") + 1] == "xgboost"
    assert "--global-champion" not in train_cmd


def test_build_pipeline_command_ml_train_champion_ignores_selected_backend() -> None:
    """P3-3 : champion auto quel que soit le backend du dropdown → 3 candidats."""
    options = PipelineLaunchOptions(
        ml_enable_global_model=True,
        ml_global_champion=True,
        ml_global_model_name="catboost",
    )

    train_cmd = build_pipeline_command("ml_train", options)

    assert "--global-champion" in train_cmd
    # P3-3 : champion → backend du dropdown ignoré, --global-model-name non émis.
    assert "--global-model-name" not in train_cmd


def test_build_pipeline_command_ml_train_global_model_only_no_duplicate() -> None:
    """Régression : global-model-only n'émet qu'une fois (voire zéro fois) --enable-global-model
    (implicite côté cli) et omet --global-model-name en mode champion."""
    options = PipelineLaunchOptions(
        ml_global_model_only=True,
        ml_enable_global_model=True,
        ml_global_champion=True,
        ml_global_model_name="catboost",
    )

    train_cmd = build_pipeline_command("ml_train", options)

    assert train_cmd.count("--enable-global-model") == 0  # implicite via --global-model-only
    assert "--global-model-only" in train_cmd
    assert "--global-champion" in train_cmd
    assert "--global-model-name" not in train_cmd


def test_build_pipeline_command_ml_train_propagates_training_end_date() -> None:
    command = build_pipeline_command(
        "ml_train",
        PipelineLaunchOptions(
            ml_training_start_date="2021-01-01",
            ml_training_end_date="2021-12-31",
        ),
    )

    assert command[command.index("--training-start-date") + 1] == "2021-01-01"
    assert command[command.index("--training-end-date") + 1] == "2021-12-31"


def test_build_pipeline_command_ml_train_include_volume_features() -> None:
    """P3-5 : checkbox volume → --include-volume-features dans la commande."""
    options = PipelineLaunchOptions(ml_include_volume_features=True)
    train_cmd = build_pipeline_command("ml_train", options)
    assert "--include-volume-features" in train_cmd


def test_build_pipeline_command_ml_train_volume_features_off_by_default() -> None:
    """P3-5 : off par défaut → pas de --include-volume-features."""
    options = PipelineLaunchOptions()
    train_cmd = build_pipeline_command("ml_train", options)
    assert "--include-volume-features" not in train_cmd


def test_build_pipeline_command_ml_predict_scoped_historical_uses_period_and_tradable_universe() -> None:
    command = build_pipeline_command(
        "ml_predict",
        PipelineLaunchOptions(
            ml_accelerator="cpu",
            ml_predict_symbol_source="stock_scores_history",
            ml_predict_use_historical_range=True,
            ml_training_start_date="2022-01-01",
            ml_training_end_date="2022-02-15",
        ),
    )

    assert command[:6] == [command[0], "-u", "-m", "modelFactory", "--mode", "predict"]
    assert command[command.index("--symbol-source") + 1] == "tradable-universe"
    assert command[command.index("--training-start-date") + 1] == "2022-01-01"
    assert command[command.index("--training-end-date") + 1] == "2022-02-15"
    assert "--selector-universe-signal-modes" not in command
    assert "--selector-universe-max-candidate-rank" not in command
    assert "--selector-universe-exclude-earnings-blackout" not in command


def test_build_pipeline_command_ml_predict_respects_selected_symbol_source() -> None:
    """Le bouton `10. ML Predict` doit refléter le choix "Univers de symboles".

    Régression : `ml_predict_symbol_source` était codé en dur à
    `tradable-universe` dans build_pipeline_command — sélectionner
    "Tickets recherche" (ticket-recherche) dans la liste déroulante ne
    changeait jamais la commande affichée.
    """
    command = build_pipeline_command(
        "ml_predict",
        PipelineLaunchOptions(
            ml_accelerator="cpu",
            ml_predict_symbol_source="ticket-recherche",
        ),
    )
    assert command[command.index("--symbol-source") + 1] == "ticket-recherche"

    command = build_pipeline_command(
        "ml_predict",
        PipelineLaunchOptions(
            ml_accelerator="cpu",
            ml_predict_symbol_source="stock-bars-daily",
        ),
    )
    assert command[command.index("--symbol-source") + 1] == "stock-bars-daily"

    # Source inconnue/héritée -> fallback canonique tradable-universe (inchangé).
    command = build_pipeline_command(
        "ml_predict",
        PipelineLaunchOptions(
            ml_accelerator="cpu",
            ml_predict_symbol_source="stock_scores_all",
        ),
    )
    assert command[command.index("--symbol-source") + 1] == "tradable-universe"


def test_build_pipeline_command_ml_train_forces_tradable_universe_over_legacy_source() -> None:
    options = PipelineLaunchOptions(ml_train_symbol_source="stock_bars_daily")

    train_cmd = build_pipeline_command("ml_train", options)

    assert train_cmd[train_cmd.index("--symbol-source") + 1] == "tradable-universe"


def test_build_pipeline_command_ml_train_rejects_legacy_score_scope_by_forcing_tradable_universe() -> None:
    options = PipelineLaunchOptions(ml_train_symbol_source="stock_scores_all")

    train_cmd = build_pipeline_command("ml_train", options)

    assert train_cmd[train_cmd.index("--symbol-source") + 1] == "tradable-universe"


def test_build_pipeline_command_ml_train_exposes_score_context_without_selector_filters() -> None:
    command = build_pipeline_command(
        "ml_train",
        PipelineLaunchOptions(
            ml_include_screener_scores=True,
        ),
    )

    assert "--include-screener-scores" in command
    assert "--include-selector-context" not in command
    assert "--selector-universe-signal-modes" not in command
    assert "--selector-universe-max-candidate-rank" not in command
    assert "--selector-universe-exclude-earnings-blackout" not in command


def test_build_pipeline_command_import_news() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        sentiment_news_provider="finnhub",
        sentiment_ticker_relevance_mode="scored",
        sentiment_min_relevance_score=0.35,
    )

    command = build_pipeline_command("import_news", options)

    assert command[:3] == [command[0], "-u", str(PROJECT_ROOT / "event_sentiment" / "importe_news.py")]
    assert "--start-date" in command
    assert command[command.index("--start-date") + 1] == "2026-04-01"
    assert "--end-date" in command
    assert command[command.index("--end-date") + 1] == "2026-04-15"
    assert command[command.index("--news-provider") + 1] == "finnhub"
    assert command[command.index("--ticker-relevance-mode") + 1] == "scored"
    assert command[command.index("--min-relevance-score") + 1] == "0.35"
    assert "--enable-contextual-scoring" not in command


def test_build_pipeline_command_import_news_does_not_forward_scoring_only_flags() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        sentiment_news_provider="eodhd",
        sentiment_enable_contextual_scoring=True,
        sentiment_contextual_min_relevance=0.3,
        sentiment_contextual_max_pairs=4000,
        sentiment_pending_limit=5000,
        sentiment_pending_max_batches_per_run=10,
        sentiment_feature_flush_every_n_batches=2,
        sentiment_finbert_batch_size=32,
    )

    command = build_pipeline_command("import_news", options)

    assert "--news-provider" in command
    assert "--enable-contextual-scoring" not in command
    assert "--scoring-mode" not in command
    assert "--contextual-min-relevance" not in command
    assert "--contextual-max-pairs" not in command
    assert "--sentiment-pending-limit" not in command
    assert "--sentiment-pending-max-batches" not in command
    assert "--feature-flush-every-n-batches" not in command
    assert "--finbert-batch-size" not in command


def test_build_pipeline_command_import_news_exposes_symbol_scope_options() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        news_import_symbol_source="stock_bars_daily",
        news_import_symbols="msft, aapl,MSFT,nvda",
        news_import_max_symbols=250,
    )

    command = build_pipeline_command("import_news", options)

    assert command[command.index("--symbols") + 1] == "AAPL,MSFT,NVDA"
    assert "--symbol-source" not in command
    assert command[command.index("--max-symbols") + 1] == "250"


def test_build_pipeline_command_import_news_accepts_stock_scores_all_symbol_source() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        news_import_symbol_source="stock_scores_all",
        news_import_max_symbols=300,
    )

    command = build_pipeline_command("import_news", options)

    assert "--symbol-source" not in command
    assert command[command.index("--max-symbols") + 1] == "300"


def test_build_pipeline_command_import_news_emits_stock_scores_when_explicitly_requested() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        news_import_symbol_source="stock_scores",
        news_import_max_symbols=300,
    )

    command = build_pipeline_command("import_news", options)

    assert command[command.index("--symbol-source") + 1] == "stock_scores"
    assert command[command.index("--max-symbols") + 1] == "300"


def test_build_pipeline_command_import_news_can_resume_from_checkpoints() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        news_import_resume_from_checkpoint=True,
    )

    command = build_pipeline_command("import_news", options)

    assert "--resume-checkpoints" in command


def test_build_pipeline_command_import_news_pending_loop() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        sentiment_news_provider="finnhub",
        sentiment_ticker_relevance_mode="scored",
        sentiment_min_relevance_score=0.35,
        sentiment_enable_contextual_scoring=True,
        sentiment_contextual_min_relevance=0.3,
        sentiment_contextual_max_pairs=5000,
        sentiment_pending_limit=5000,
        sentiment_pending_max_batches_per_run=10,
        sentiment_finbert_batch_size=32,
        backfill_relevance_dry_run=True,
        backfill_relevance_rescore_all=True,
        backfill_relevance_batch_size=750,
        backfill_relevance_purge_below=0.2,
        backfill_relevance_contextual_min_relevance=0.4,
        backfill_relevance_contextual_max_pairs=2500,
    )

    command = build_pipeline_command("import_news_pending_loop", options)

    assert command[:5] == [
        "powershell.exe" if sys.platform.startswith("win") else "pwsh",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
    ]
    assert command[5] == str(PROJECT_ROOT / "scripts" / "windows" / "import_news_and_score_pending.ps1")
    assert "-ProjectRoot" in command
    assert command[command.index("-ProjectRoot") + 1] == str(PROJECT_ROOT)
    assert "-PythonExe" in command
    assert command[command.index("-PythonExe") + 1] == sys.executable
    assert command[command.index("-StartDate") + 1] == "2026-04-01"
    assert command[command.index("-EndDate") + 1] == "2026-04-15"
    assert command[command.index("-NewsProvider") + 1] == "finnhub"
    assert command[command.index("-TickerRelevanceMode") + 1] == "scored"
    assert command[command.index("-MinRelevanceScore") + 1] == "0.35"
    assert "-EnableContextualScoring" in command
    assert command[command.index("-ContextualMinRelevance") + 1] == "0.3"
    assert command[command.index("-ContextualMaxPairs") + 1] == "5000"
    assert command[command.index("-SentimentPendingLimit") + 1] == "5000"
    assert command[command.index("-SentimentPendingMaxBatches") + 1] == "10"
    assert command[command.index("-FinBertBatchSize") + 1] == "32"
    assert command[command.index("-RelevanceBackfillBatchSize") + 1] == "750"
    assert "-RelevanceBackfillDryRun" in command
    assert "-RelevanceBackfillRescoreAll" in command
    assert command[command.index("-RelevanceBackfillPurgeBelow") + 1] == "0.2"
    assert command[command.index("-RelevanceBackfillContextualMinRelevance") + 1] == "0.4"
    assert command[command.index("-RelevanceBackfillContextualMaxPairs") + 1] == "2500"


def test_build_pipeline_command_import_news_pending_loop_can_resume_import_from_checkpoints() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        news_import_resume_from_checkpoint=True,
    )

    command = build_pipeline_command("import_news_pending_loop", options)

    assert "-ResumeCheckpoints" in command


def test_build_pipeline_command_import_news_pending_loop_defaults_to_unlimited_pending_batches() -> None:
    command = build_pipeline_command(
        "import_news_pending_loop",
        PipelineLaunchOptions(
            news_import_start_date="2026-04-01",
            news_import_end_date="2026-04-15",
        ),
    )

    assert "-SentimentPendingMaxBatches" in command
    assert command[command.index("-SentimentPendingMaxBatches") + 1] == "0"


def test_build_pipeline_command_import_news_pending_loop_supports_contextual_only_mode() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        sentiment_scoring_mode="contextual_only",
        sentiment_contextual_min_relevance=0.3,
        sentiment_contextual_max_pairs=4000,
        sentiment_feature_flush_every_n_batches=2,
    )

    command = build_pipeline_command("import_news_pending_loop", options)

    assert command[command.index("-ScoringMode") + 1] == "contextual_only"
    assert command[command.index("-ContextualMinRelevance") + 1] == "0.3"
    assert command[command.index("-ContextualMaxPairs") + 1] == "4000"
    assert command[command.index("-FeatureFlushEveryNBatches") + 1] == "2"
    assert "-EnableContextualScoring" not in command


def test_build_pipeline_command_import_news_pending_loop_exposes_symbol_scope_options() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        news_import_symbol_source="tradable-universe",
        news_import_max_symbols=500,
    )

    command = build_pipeline_command("import_news_pending_loop", options)

    assert command[command.index("-SymbolSource") + 1] == "tradable-universe"
    assert command[command.index("-MaxSymbols") + 1] == "500"
    assert "-Symbols" not in command


def test_build_pipeline_command_score_sentiment_only_uses_manual_scope_and_selected_scoring_mode() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        news_import_symbol_source="stock_scores_history",
        news_import_max_symbols=500,
        sentiment_news_provider="eodhd",
        sentiment_scoring_mode="contextual_only",
        sentiment_contextual_min_relevance=0.3,
        sentiment_contextual_max_pairs=4000,
        sentiment_pending_limit=5000,
        sentiment_pending_max_batches_per_run=10,
        sentiment_feature_flush_every_n_batches=2,
        sentiment_finbert_batch_size=32,
    )

    command = build_pipeline_command("score_sentiment_only", options)

    assert command == [
        command[0],
        "-u",
        "-m",
        "event_sentiment",
        "--skip-ingestion",
        "--news-provider",
        "eodhd",
        "--scoring-mode",
        "contextual_only",
        "--contextual-min-relevance",
        "0.3",
        "--contextual-max-pairs",
        "4000",
        "--sentiment-pending-limit",
        "5000",
        "--sentiment-pending-max-batches",
        "10",
        "--feature-flush-every-n-batches",
        "2",
        "--finbert-batch-size",
        "32",
        "--start-utc",
        "2026-04-01T00:00:00Z",
        "--end-utc",
        "2026-04-15T23:59:59Z",
        "--symbol-source",
        "stock_scores_history",
        "--max-symbols",
        "500",
    ]


def test_build_pipeline_command_score_history_relevance_backfill_auto_skips_import() -> None:
    options = PipelineLaunchOptions(
        news_import_start_date="2026-04-01",
        news_import_end_date="2026-04-15",
        news_import_symbol_source="stock_scores_history",
        news_import_max_symbols=500,
        sentiment_enable_contextual_scoring=True,
    )

    command = build_pipeline_command("score_history_relevance_backfill_auto", options)

    assert command[5] == str(PROJECT_ROOT / "scripts" / "windows" / "import_news_and_score_pending.ps1")
    assert command[command.index("-SymbolSource") + 1] == "stock_scores_history"
    assert command[command.index("-MaxSymbols") + 1] == "500"
    assert "-SkipImport" in command


def test_build_pipeline_command_sentiment_standard_scoring_forces_standard_only_without_features() -> None:
    command = build_pipeline_command(
        "sentiment_standard_scoring",
        PipelineLaunchOptions(
            news_import_start_date="2026-04-01",
            news_import_end_date="2026-04-15",
            news_import_symbols="msft, aapl",
            sentiment_news_provider="eodhd",
            sentiment_contextual_min_relevance=0.4,
            sentiment_contextual_max_pairs=2500,
            sentiment_pending_limit=5000,
            sentiment_pending_max_batches_per_run=10,
            sentiment_finbert_batch_size=32,
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "event_sentiment",
        "--skip-ingestion",
        "--skip-features",
        "--scoring-mode",
        "standard_only",
        "--news-provider",
        "eodhd",
        "--sentiment-pending-limit",
        "5000",
        "--sentiment-pending-max-batches",
        "10",
        "--finbert-batch-size",
        "32",
        "--start-utc",
        "2026-04-01T00:00:00Z",
        "--end-utc",
        "2026-04-15T23:59:59Z",
        "--symbols",
        "AAPL,MSFT",
    ]


def test_build_pipeline_command_sentiment_standard_scoring_defaults_to_unlimited_pending_batches() -> None:
    command = build_pipeline_command(
        "sentiment_standard_scoring",
        PipelineLaunchOptions(
            news_import_start_date="2026-04-01",
            news_import_end_date="2026-04-15",
            sentiment_news_provider="eodhd",
        ),
    )

    assert "--sentiment-pending-max-batches" in command
    assert command[command.index("--sentiment-pending-max-batches") + 1] == "0"


def test_build_pipeline_command_sentiment_standard_scoring_keeps_zero_pending_max_batches_for_unlimited_mode() -> None:
    command = build_pipeline_command(
        "sentiment_standard_scoring",
        PipelineLaunchOptions(
            news_import_start_date="2026-04-01",
            news_import_end_date="2026-04-15",
            sentiment_news_provider="eodhd",
            sentiment_pending_limit=5000,
            sentiment_pending_max_batches_per_run=0,
        ),
    )

    assert "--sentiment-pending-max-batches" in command
    assert command[command.index("--sentiment-pending-max-batches") + 1] == "0"


def test_build_pipeline_command_sentiment_relevance_backfill_uses_manual_scope() -> None:
    command = build_pipeline_command(
        "sentiment_relevance_backfill",
        PipelineLaunchOptions(
            news_import_start_date="2026-04-01",
            news_import_end_date="2026-04-15",
            news_import_symbols="msft, aapl",
            backfill_relevance_batch_size=750,
            backfill_relevance_purge_below=0.2,
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "event_sentiment.relevance_backfill",
        "--news-provider",
        "eodhd",
        "--batch-size",
        "750",
        "--start-date",
        "2026-04-01",
        "--end-date",
        "2026-04-15",
        "--symbols",
        "AAPL,MSFT",
        "--purge-below",
        "0.2",
    ]


def test_build_pipeline_command_sentiment_contextual_scoring_forces_contextual_only() -> None:
    command = build_pipeline_command(
        "sentiment_contextual_scoring",
        PipelineLaunchOptions(
            news_import_start_date="2026-04-01",
            news_import_end_date="2026-04-15",
            news_import_symbols="msft, aapl",
            sentiment_news_provider="eodhd",
            sentiment_contextual_min_relevance=0.4,
            sentiment_contextual_max_pairs=2500,
            sentiment_pending_limit=5000,
            sentiment_pending_max_batches_per_run=10,
            sentiment_finbert_batch_size=32,
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "event_sentiment",
        "--skip-ingestion",
        "--skip-features",
        "--scoring-mode",
        "contextual_only",
        "--news-provider",
        "eodhd",
        "--contextual-min-relevance",
        "0.4",
        "--contextual-max-pairs",
        "2500",
        "--sentiment-pending-limit",
        "5000",
        "--sentiment-pending-max-batches",
        "10",
        "--finbert-batch-size",
        "32",
        "--start-utc",
        "2026-04-01T00:00:00Z",
        "--end-utc",
        "2026-04-15T23:59:59Z",
        "--symbols",
        "AAPL,MSFT",
    ]


def test_build_pipeline_command_relevance_backfill_exposes_contextual_options() -> None:
    """Step 7bis : --contextual-only et --rescore-contextual toujours présents ; pas de --dry-run/--rescore-all."""
    command = build_pipeline_command(
        "relevance_backfill",
        PipelineLaunchOptions(
            sentiment_start_utc="2026-04-01T00:00:00Z",
            sentiment_end_utc="2026-04-15T23:59:59Z",
            sentiment_symbols="msft, aapl,MSFT,nvda",
            backfill_relevance_dry_run=True,
            backfill_relevance_rescore_all=True,
            backfill_relevance_batch_size=750,
            backfill_relevance_purge_below=0.2,
            backfill_relevance_contextual_min_relevance=0.4,
            backfill_relevance_contextual_max_pairs=2500,
        ),
    )

    # La commande est maintenant wrappée dans PowerShell (_build_chained_ps_commands).
    assert command[0] in ("powershell.exe", "pwsh")
    assert "-NoProfile" in command
    assert "-Command" in command
    ps_script = command[-1]
    assert "--contextual-only" in ps_script
    assert "--rescore-contextual" in ps_script
    assert "--batch-size" in ps_script
    assert "750" in ps_script
    assert "--news-provider" in ps_script
    assert "eodhd" in ps_script
    assert "2026-04-01" in ps_script
    assert "2026-04-15" in ps_script
    assert "AAPL,MSFT,NVDA" in ps_script
    assert "--purge-below" in ps_script
    assert "0.2" in ps_script
    assert "--contextual-min-relevance" in ps_script
    assert "0.4" in ps_script
    assert "--contextual-max-pairs" in ps_script
    assert "2500" in ps_script
    assert "--dry-run" not in ps_script
    assert "--rescore-all" not in ps_script


def test_build_pipeline_command_rebuild_daily_sentiment_features_only() -> None:
    command = build_pipeline_command(
        "rebuild_daily_sentiment_features_only",
        PipelineLaunchOptions(
            news_import_start_date="2026-04-01",
            news_import_end_date="2026-04-15",
        ),
    )

    assert command == [
        command[0],
        "-u",
        "-m",
        "event_sentiment.history_backfill",
        "--start-date",
        "2026-04-01",
        "--end-date",
        "2026-04-15",
        "--ingestion-source",
        "eodhd",
        "--ticker-symbol-source",
        "stock_scores_all",
    ]


def test_build_pipeline_command_import_bars_eodhd_disables_stooq_cross_check_by_default(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_runner, "_resolve_bars_provider_for_ihm", lambda: "eodhd")

    command = build_pipeline_command("import_alpaca_bar", PipelineLaunchOptions())

    assert command[:4] == [command[0], "-u", "-m", "dataIntegrityEngine.import_eodhd_bar"]
    assert "--write" in command
    assert "--no-stooq-cross-check" in command


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

