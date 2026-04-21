from __future__ import annotations


def test_build_backtesting_run_command_includes_account_constraint_mode():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command(
		"run",
		BacktestRunOptions(
			start="2025-01-01",
			end="2025-01-31",
			equity=2_000,
			account_constraint_mode="pdt",
			output_dir="artifacts/ihm_backtesting_runs/run_001/artifacts",
		),
	)

	assert "--account-constraint-mode" in command
	flag_index = command.index("--account-constraint-mode")
	assert command[flag_index + 1] == "pdt"
	assert "--output-dir" in command


def test_build_backtesting_run_command_defaults_to_standard_mode():
	from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

	command = build_backtesting_command("run", BacktestRunOptions(start="2025-01-01"))

	flag_index = command.index("--account-constraint-mode")
	assert command[flag_index + 1] == "standard"

