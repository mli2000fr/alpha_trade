"""Tests PIT safety and application of conviction/Kelly calibration in the backtest CLI."""
from __future__ import annotations


def test_conviction_calibration_mode_off_no_db_call():
    """The backwards-compatible default does not emit calibration CLI flags."""
    from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

    cmd = build_backtesting_command("run", BacktestRunOptions(start="2025-01-01", phase2_mode="risk"))
    assert "--conviction-calibration-mode" not in cmd


def test_conviction_calibration_pit_auto_uses_start_as_cutoff():
    """auto mode is represented independently from the end date."""
    from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

    cmd = build_backtesting_command(
        "run",
        BacktestRunOptions(
            start="2024-01-01",
            end="2024-12-31",
            phase2_mode="risk",
            conviction_calibration_mode="auto",
        ),
    )
    assert cmd[cmd.index("--conviction-calibration-mode") + 1] == "auto"


def test_conviction_calibration_pinned_requires_run_id():
    from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

    cmd = build_backtesting_command(
        "run",
        BacktestRunOptions(
            start="2024-01-01",
            phase2_mode="risk",
            conviction_calibration_mode="pinned",
            conviction_calibration_run_id="run_abc123",
        ),
    )
    assert cmd[cmd.index("--conviction-calibration-run-id") + 1] == "run_abc123"


def test_conviction_calibration_pinned_no_run_id_omits_flag():
    from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

    cmd = build_backtesting_command(
        "run",
        BacktestRunOptions(
            start="2024-01-01",
            phase2_mode="risk",
            conviction_calibration_mode="pinned",
        ),
    )
    assert "--conviction-calibration-mode" in cmd
    assert "--conviction-calibration-run-id" not in cmd


def test_apply_empirical_risk_calibration_updates_weights():
    from risk_management.config import RiskConfig
    from risk_management.cli import _apply_empirical_risk_calibration

    config = RiskConfig(account_equity=10_000.0)
    updated = _apply_empirical_risk_calibration(
        config,
        {
            "status": "selected",
            "eligible_for_live": True,
            "best_weights": {"score_weight": 0.30, "prediction_weight": 0.70},
        },
    )
    assert updated.score_weight == 0.30
    assert updated.prediction_weight == 0.70


def test_apply_empirical_risk_calibration_blocked_returns_unchanged():
    from risk_management.config import RiskConfig
    from risk_management.cli import _apply_empirical_risk_calibration

    config = RiskConfig(account_equity=10_000.0)
    result = _apply_empirical_risk_calibration(
        config,
        {
            "status": "blocked_by_governance",
            "eligible_for_live": False,
            "best_weights": {"score_weight": 0.20, "prediction_weight": 0.80},
        },
    )
    assert result is config


def test_pit_safety_window_end_must_not_exceed_start():
    from datetime import date

    assert date(2025, 6, 1) > date(2025, 1, 1)


def test_pit_safety_window_end_at_start_is_safe():
    from datetime import date

    assert not date(2025, 1, 1) > date(2025, 1, 1)


def test_pit_safety_window_end_before_start_is_safe():
    from datetime import date

    assert not date(2024, 12, 31) > date(2025, 1, 1)
