from __future__ import annotations

from pathlib import Path

from scripts.run_ml_regime_ablation import (
    VariantSpec,
    WindowSpec,
    build_arg_parser,
    build_backtest_command,
    build_decision_summary,
    compute_factorial_effects,
    write_frozen_runtime_configs,
)


def test_write_frozen_runtime_configs_disables_regime_only_for_regime_off(tmp_path: Path) -> None:
    base_config = tmp_path / "config.yaml"
    base_config.write_text(
        """
market_regimes:
  enabled: true
  allow_neutral_fallback_on_missing_macro_data: true
conviction:
  quant_weight: 0.75
""".strip(),
        encoding="utf-8",
    )

    config_paths = write_frozen_runtime_configs(base_config_path=base_config, output_root=tmp_path / "out")

    baseline = config_paths["baseline"].read_text(encoding="utf-8")
    regime_off = config_paths["regime_off"].read_text(encoding="utf-8")

    assert "enabled: true" in baseline
    assert "enabled: false" in regime_off
    assert "quant_weight: 0.75" in baseline
    assert "quant_weight: 0.75" in regime_off


def test_build_backtest_command_includes_frozen_config_and_core_flags(tmp_path: Path) -> None:
    parser = build_arg_parser()
    args = parser.parse_args([
        "--base-config",
        str(tmp_path / "config.yaml"),
        "--output-root",
        str(tmp_path / "ablation"),
    ])
    window = WindowSpec("2020_q1", "2020-01-01", "2020-03-31", "Q1")
    variant = VariantSpec("ml_off", "off", True, "ML OFF + régime ON")
    config_path = tmp_path / "configs" / "baseline.runtime.yaml"
    output_dir = tmp_path / "runs" / "2020_q1" / "ml_off"

    command = build_backtest_command(args, window=window, variant=variant, config_path=config_path, output_dir=output_dir)

    assert "--config-path" in command
    assert str(config_path) in command
    assert "--ml-mode" in command
    assert command[command.index("--ml-mode") + 1] == "off"
    assert "--engine-mode" in command
    assert command[command.index("--engine-mode") + 1] == "pipeline"
    assert "--phase7-mode" in command
    assert command[command.index("--phase7-mode") + 1] == "exit_lifecycle_replay"
    assert "--allow-neutral-fallback-on-missing-macro-data" in command
    assert "--use-cache" in command


def test_compute_factorial_effects_and_decision_summary_detect_ml_is_harmful() -> None:
    rows = [
        {
            "window_id": "w1",
            "variant_id": "control",
            "status": "completed",
            "expected_ml_mode": "rebuild-missing",
            "expected_regime_enabled": True,
            "total_return_pct": -5.0,
            "sharpe_ratio": -1.0,
            "max_drawdown_pct": 8.0,
            "degraded": True,
        },
        {
            "window_id": "w1",
            "variant_id": "ml_off",
            "status": "completed",
            "expected_ml_mode": "off",
            "expected_regime_enabled": True,
            "total_return_pct": 4.0,
            "sharpe_ratio": 0.8,
            "max_drawdown_pct": 5.0,
            "degraded": False,
        },
        {
            "window_id": "w1",
            "variant_id": "regime_off",
            "status": "completed",
            "expected_ml_mode": "rebuild-missing",
            "expected_regime_enabled": False,
            "total_return_pct": -1.0,
            "sharpe_ratio": -0.2,
            "max_drawdown_pct": 10.0,
            "degraded": True,
        },
        {
            "window_id": "w1",
            "variant_id": "ml_off_regime_off",
            "status": "completed",
            "expected_ml_mode": "off",
            "expected_regime_enabled": False,
            "total_return_pct": 2.0,
            "sharpe_ratio": 0.3,
            "max_drawdown_pct": 6.0,
            "degraded": False,
        },
        {
            "window_id": "w2",
            "variant_id": "control",
            "status": "completed",
            "expected_ml_mode": "rebuild-missing",
            "expected_regime_enabled": True,
            "total_return_pct": -3.0,
            "sharpe_ratio": -0.6,
            "max_drawdown_pct": 7.0,
            "degraded": True,
        },
        {
            "window_id": "w2",
            "variant_id": "ml_off",
            "status": "completed",
            "expected_ml_mode": "off",
            "expected_regime_enabled": True,
            "total_return_pct": 3.0,
            "sharpe_ratio": 0.6,
            "max_drawdown_pct": 4.0,
            "degraded": False,
        },
        {
            "window_id": "w2",
            "variant_id": "regime_off",
            "status": "completed",
            "expected_ml_mode": "rebuild-missing",
            "expected_regime_enabled": False,
            "total_return_pct": -2.0,
            "sharpe_ratio": -0.1,
            "max_drawdown_pct": 9.0,
            "degraded": True,
        },
        {
            "window_id": "w2",
            "variant_id": "ml_off_regime_off",
            "status": "completed",
            "expected_ml_mode": "off",
            "expected_regime_enabled": False,
            "total_return_pct": 1.0,
            "sharpe_ratio": 0.2,
            "max_drawdown_pct": 5.0,
            "degraded": False,
        },
    ]

    effects = compute_factorial_effects(rows)
    decision = build_decision_summary(rows, effects)

    assert effects["complete_window_count"] == 2
    assert effects["ml_off_effect"]["total_return_pct"]["positive_windows"] == 2
    assert effects["ml_off_effect"]["sharpe_ratio"]["positive_windows"] == 2
    assert effects["ml_off_effect"]["drawdown_improvement"]["positive_windows"] == 2
    assert decision["degraded_by_ml_state"]["ml_on"] == 4
    assert decision["degraded_by_ml_state"].get("ml_off", 0) == 0
    assert any("ml_mode=off" in recommendation for recommendation in decision["recommendations"])

