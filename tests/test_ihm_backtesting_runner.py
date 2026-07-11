from __future__ import annotations


def test_build_backtesting_run_command_includes_account_constraint_mode():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			end="2025-01-31",
			equity=2_000,
			account_type="cash",
			swing_only=True,
			output_dir="artifacts/ihm_backtesting_runs/run_001/artifacts",
		),
	)

	assert "--account-type" in command
	account_type_index = command.index("--account-type")
	assert command[account_type_index + 1] == "cash"
	assert "--swing-only" in command
	assert "--output-dir" in command


def test_build_backtesting_run_command_defaults_to_standard_mode():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command("run", BacktestRunOptions(start="2025-01-01"))

	account_type_index = command.index("--account-type")
	assert command[account_type_index + 1] == "margin"
	score_column_index = command.index("--score-column")
	assert command[score_column_index + 1] == "auto"
	engine_mode_index = command.index("--engine-mode")
	assert command[engine_mode_index + 1] == "research"
	ml_pit_strategy_index = command.index("--ml-pit-strategy")
	assert command[ml_pit_strategy_index + 1] == "auto"
	scores_pit_mode_index = command.index("--scores-pit-mode")
	assert command[scores_pit_mode_index + 1] == "exact"
	macro_pit_mode_index = command.index("--macro-pit-mode")
	assert command[macro_pit_mode_index + 1] == "yaml_default"
	phase2_mode_index = command.index("--phase2-mode")
	assert command[phase2_mode_index + 1] == "off"
	phase3_mode_index = command.index("--phase3-mode")
	assert command[phase3_mode_index + 1] == "off"
	phase4_mode_index = command.index("--phase4-mode")
	assert command[phase4_mode_index + 1] == "off"
	phase5_mode_index = command.index("--phase5-mode")
	assert command[phase5_mode_index + 1] == "off"
	phase7_mode_index = command.index("--phase7-mode")
	assert command[phase7_mode_index + 1] == "off"
	assert "--capital-preset-key" not in command
	assert "--use-live-protection-logic" in command
	assert "--use-fixed-protection-logic" not in command
	assert "--tp" not in command
	assert "--ts" not in command
	assert "--swing-only" not in command
	assert "--walk-forward-artifacts-dir" not in command
	assert "--fail-on-missing-macro-data" in command
	assert "--allow-neutral-fallback-on-missing-macro-data" not in command
	assert "--filter-no-ml" not in command


def test_build_backtesting_run_command_includes_capital_preset_key():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(start="2025-01-01", equity=2_000, capital_preset_key="capital_2001_5000"),
	)

	assert "--capital-preset-key" in command
	assert command[command.index("--capital-preset-key") + 1] == "capital_2001_5000"


def test_build_backtesting_run_command_includes_walk_forward_options():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			score_column="final_score_walk_forward",
			walk_forward_artifacts_dir="artifacts/sentiment_walk_forward/run_001",
		),
	)

	assert "--score-column" in command
	assert command[command.index("--score-column") + 1] == "final_score_walk_forward"
	assert "--walk-forward-artifacts-dir" in command
	assert command[command.index("--walk-forward-artifacts-dir") + 1] == "artifacts/sentiment_walk_forward/run_001"


def test_build_backtesting_run_command_includes_phase1_pipeline_flags():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			engine_mode="pipeline",
			scores_pit_mode="asof_latest",
			ml_pit_strategy="use-persisted",
		),
	)

	assert "--engine-mode" in command
	assert command[command.index("--engine-mode") + 1] == "pipeline"
	assert "--scores-pit-mode" in command
	assert command[command.index("--scores-pit-mode") + 1] == "asof_latest"
	assert "--ml-pit-strategy" in command
	assert command[command.index("--ml-pit-strategy") + 1] == "use-persisted"


def test_build_backtesting_run_command_includes_macro_pit_mode_override():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			macro_pit_mode="j_minus_1_strict",
		),
	)

	assert "--macro-pit-mode" in command
	assert command[command.index("--macro-pit-mode") + 1] == "j_minus_1_strict"


def test_build_backtesting_run_command_can_allow_missing_macro_fallback():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			allow_neutral_fallback_on_missing_macro_data=True,
		),
	)

	assert "--allow-neutral-fallback-on-missing-macro-data" in command
	assert "--fail-on-missing-macro-data" not in command


def test_build_backtesting_run_command_includes_phase2_flags():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			phase2_mode="risk_execution",
		),
	)

	assert "--phase2-mode" in command
	assert command[command.index("--phase2-mode") + 1] == "risk_execution"


def test_build_backtesting_run_command_includes_phase3_flags():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			phase2_mode="risk_execution",
			phase3_mode="execution_replay",
		),
	)

	assert "--phase3-mode" in command
	assert command[command.index("--phase3-mode") + 1] == "execution_replay"


def test_build_backtesting_run_command_includes_phase4_flags():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			phase2_mode="risk_execution",
			phase3_mode="execution_replay",
			phase4_mode="protection_replay",
		),
	)

	assert "--phase4-mode" in command
	assert command[command.index("--phase4-mode") + 1] == "protection_replay"


def test_build_backtesting_run_command_includes_phase5_flags():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			phase2_mode="risk_execution",
			phase3_mode="execution_replay",
			phase4_mode="protection_replay",
			phase5_mode="watcher_replay",
		),
	)

	assert "--phase5-mode" in command
	assert command[command.index("--phase5-mode") + 1] == "watcher_replay"


def test_build_backtesting_run_command_includes_phase7_flags():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			phase2_mode="risk_execution",
			phase3_mode="execution_replay",
			phase4_mode="protection_replay",
			phase5_mode="watcher_replay",
			phase7_mode="exit_lifecycle_replay",
		),
	)

	assert "--phase7-mode" in command
	assert command[command.index("--phase7-mode") + 1] == "exit_lifecycle_replay"


def test_build_backtesting_run_command_includes_allow_fractional_shares_flag():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			allow_fractional_shares=True,
		),
	)

	assert "--allow-fractional-shares" in command


def test_build_backtesting_run_command_omits_allow_fractional_shares_flag_when_disabled():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			allow_fractional_shares=False,
		),
	)

	assert "--allow-fractional-shares" not in command


def test_build_backtesting_run_command_includes_fixed_protection_flags_when_live_like_disabled():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			use_live_protection_logic=False,
			tp=0.11,
			ts=0.06,
			initial_stop_pct=0.04,
		),
	)

	assert "--use-fixed-protection-logic" in command
	assert "--use-live-protection-logic" not in command
	assert "--tp" in command and command[command.index("--tp") + 1] == "0.11"
	assert "--ts" in command and command[command.index("--ts") + 1] == "0.06"
	assert "--initial-stop-pct" in command and command[command.index("--initial-stop-pct") + 1] == "0.04"


def test_build_backtesting_run_command_matches_pipeline_live_like_replay_preset():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			end="2025-03-31",
			engine_mode="pipeline",
			ml_pit_strategy="use-persisted",
			phase2_mode="risk_execution",
			phase3_mode="execution_replay",
			phase4_mode="protection_replay",
			phase5_mode="watcher_replay",
			phase7_mode="exit_lifecycle_replay",
		),
	)

	assert command[:5] == [command[0], "-u", "-m", "backtesting", "run"]
	assert "--start" in command and command[command.index("--start") + 1] == "2025-01-01"
	assert "--end" in command and command[command.index("--end") + 1] == "2025-03-31"
	assert "--engine-mode" in command and command[command.index("--engine-mode") + 1] == "pipeline"
	assert "--ml-pit-strategy" in command and command[command.index("--ml-pit-strategy") + 1] == "use-persisted"
	assert "--phase2-mode" in command and command[command.index("--phase2-mode") + 1] == "risk_execution"
	assert "--phase3-mode" in command and command[command.index("--phase3-mode") + 1] == "execution_replay"
	assert "--phase4-mode" in command and command[command.index("--phase4-mode") + 1] == "protection_replay"
	assert "--phase5-mode" in command and command[command.index("--phase5-mode") + 1] == "watcher_replay"
	assert "--phase7-mode" in command and command[command.index("--phase7-mode") + 1] == "exit_lifecycle_replay"


def test_build_backtesting_run_command_includes_pipeline_defensive_overlays():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			engine_mode="pipeline",
			max_portfolio_dd_pct=0.12,
			dd_recovery_pct=0.98,
			target_annual_vol=0.12,
			min_ml_coverage_ratio=0.80,
		),
	)

	assert "--max-portfolio-dd-pct" in command
	assert command[command.index("--max-portfolio-dd-pct") + 1] == "0.12"
	assert "--dd-recovery-pct" in command
	assert command[command.index("--dd-recovery-pct") + 1] == "0.98"
	assert "--target-annual-vol" in command
	assert command[command.index("--target-annual-vol") + 1] == "0.12"
	assert "--min-ml-coverage-ratio" in command
	assert command[command.index("--min-ml-coverage-ratio") + 1] == "0.8"


def test_build_backtesting_run_command_includes_fidelity_baseline_flags():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			fidelity_baseline_id="pipeline_live_like_smoke",
			fidelity_baseline_catalog="config/fidelity_baseline_catalog.json",
		),
	)

	assert "--fidelity-baseline-id" in command
	assert command[command.index("--fidelity-baseline-id") + 1] == "pipeline_live_like_smoke"
	assert "--fidelity-baseline-catalog" in command
	assert command[command.index("--fidelity-baseline-catalog") + 1] == "config/fidelity_baseline_catalog.json"


def test_build_backtesting_diagnose_screener_command_includes_grid_parameters():
	from ihm.services.backtesting_runner import DiagnoseScreenerOptions, build_backtesting_command

	command = build_backtesting_command(
		"diagnose-screener",
		DiagnoseScreenerOptions(
			start="2025-01-01",
			end="2025-03-31",
			limit_days=15,
			mode="grid",
			chunk_size=250,
			selection_size=80,
			max_positions=12,
			screener_workers=3,
			max_scenarios=24,
			rs_values="100,104",
			output_dir="artifacts/screener_diagnostics/run_1",
		),
	)

	assert command[:5] == [command[0], "-u", "-m", "backtesting", "diagnose-screener"]
	assert "--mode" in command and command[command.index("--mode") + 1] == "grid"
	assert "--limit-days" in command and command[command.index("--limit-days") + 1] == "15"
	assert "--max-scenarios" in command and command[command.index("--max-scenarios") + 1] == "24"
	assert "--rs-values" in command and command[command.index("--rs-values") + 1] == "100,104"
	assert "--output-dir" in command and command[command.index("--output-dir") + 1] == "artifacts/screener_diagnostics/run_1"


def test_build_backtesting_recommend_screener_command_includes_target_horizon_and_paths():
	from ihm.services.backtesting_runner import RecommendScreenerOptions, build_backtesting_command

	command = build_backtesting_command(
		"recommend-screener",
		RecommendScreenerOptions(
			input_dir="artifacts/screener_diagnostics/run_1",
			summary_csv="artifacts/screener_diagnostics/run_1/summary_metrics.csv",
			daily_csv="artifacts/screener_diagnostics/run_1/daily_metrics.csv",
			output_dir="artifacts/screener_diagnostics/run_1",
			baseline_name="baseline",
			target_horizon=10,
		),
	)

	assert command[:5] == [command[0], "-u", "-m", "backtesting", "recommend-screener"]
	assert "--input-dir" in command and command[command.index("--input-dir") + 1] == "artifacts/screener_diagnostics/run_1"
	assert "--summary-csv" in command
	assert "--daily-csv" in command
	assert "--baseline-name" in command and command[command.index("--baseline-name") + 1] == "baseline"
	assert "--target-horizon" in command and command[command.index("--target-horizon") + 1] == "10"


def test_build_backtesting_backfill_command_includes_capital_and_preset():
	from ihm.services.backtesting_runner import BackfillScoresHistoryOptions, build_backtesting_command

	command = build_backtesting_command(
		"backfill-scores-history",
		BackfillScoresHistoryOptions(
			start="2025-01-01",
			end="2025-01-31",
			capital=2_000,
			capital_preset_key="capital_2001_5000",
		),
	)

	assert "--capital" in command
	assert command[command.index("--capital") + 1] == "2000"
	assert "--capital-preset-key" in command
	assert command[command.index("--capital-preset-key") + 1] == "capital_2001_5000"


def test_backfill_options_defaults_to_optimized_chunk_and_workers():
	from ihm.services.backtesting_runner import BackfillScoresHistoryOptions

	options = BackfillScoresHistoryOptions(start="2025-01-01")

	assert options.chunk_size == 1000
	assert options.screener_workers == 4


def test_build_calibrate_conviction_command_includes_directional_top_n():
	from ihm.services.backtesting_runner import CalibrateConvictionWeightsOptions, build_backtesting_command

	command = build_backtesting_command(
		"calibrate-conviction-weights",
		CalibrateConvictionWeightsOptions(
			start="2025-01-01",
			end="2025-03-31",
			top_n=20,
			top_n_long=30,
			top_n_short=15,
			backtest_kelly=True,
		),
	)

	assert "--backtest-kelly" in command
	assert "--top-n-long" in command
	assert command[command.index("--top-n-long") + 1] == "30"
	assert "--top-n-short" in command
	assert command[command.index("--top-n-short") + 1] == "15"


def test_build_walk_forward_conviction_command_includes_market_neutral_flags():
	from ihm.services.backtesting_runner import WalkForwardConvictionOptions, build_backtesting_command

	command = build_backtesting_command(
		"walk-forward-conviction",
		WalkForwardConvictionOptions(
			start="2025-01-01",
			end="2025-03-31",
			top_n=20,
			symmetric_grid="80/80",
			top_n_long=80,
			top_n_short=80,
			enforce_net_exposure=True,
			net_exposure_target=0.0,
			backtest_kelly=True,
		),
	)

	assert "--symmetric-grid" in command
	assert command[command.index("--symmetric-grid") + 1] == "80/80"
	assert "--top-n-long" in command
	assert command[command.index("--top-n-long") + 1] == "80"
	assert "--top-n-short" in command
	assert command[command.index("--top-n-short") + 1] == "80"
	assert "--enforce-net-exposure" in command
	assert "--net-exposure-target" in command
	assert command[command.index("--net-exposure-target") + 1] == "0.0"


