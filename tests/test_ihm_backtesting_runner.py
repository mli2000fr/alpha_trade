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
			pdt_rule="off",
			swing_only=True,
			output_dir="artifacts/ihm_backtesting_runs/run_001/artifacts",
		),
	)

	assert "--account-type" in command
	account_type_index = command.index("--account-type")
	assert command[account_type_index + 1] == "cash"
	assert "--pdt-rule" in command
	pdt_rule_index = command.index("--pdt-rule")
	assert command[pdt_rule_index + 1] == "off"
	assert "--swing-only" in command
	assert "--output-dir" in command


def test_build_backtesting_run_command_defaults_to_standard_mode():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command("run", BacktestRunOptions(start="2025-01-01"))

	account_type_index = command.index("--account-type")
	assert command[account_type_index + 1] == "margin"
	pdt_rule_index = command.index("--pdt-rule")
	assert command[pdt_rule_index + 1] == "auto"
	assert "--swing-only" not in command


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


