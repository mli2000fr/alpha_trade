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

