import pytest

from modelFactory import config

def test_config_importable():
    assert hasattr(config, "__doc__")


def test_data_config_accepts_swing_cash_mode() -> None:
    cfg = config.DataConfig(target_mode="swing_cash", target_up_threshold=0.02, target_down_threshold=-0.01)

    assert cfg.target_mode == "swing_cash"
    assert cfg.target_up_threshold == 0.02


def test_data_config_rejects_invalid_threshold_order() -> None:
    with pytest.raises(ValueError, match="target_down_threshold"):
        config.DataConfig(target_mode="swing_cash", target_up_threshold=-0.01, target_down_threshold=0.02)


def test_calibration_config_rejects_unknown_method() -> None:
    with pytest.raises(ValueError, match="calibration.method"):
        config.CalibrationConfig(method="isotonic")


def test_data_config_accepts_expert_feature_set() -> None:
    cfg = config.DataConfig(feature_set="expert", benchmark_symbol="SPY")

    assert cfg.feature_set == "expert"
    assert cfg.benchmark_symbol == "SPY"


def test_baseline_config_defaults_to_lightgbm() -> None:
    cfg = config.BaselineConfig(enabled=True)

    assert cfg.model_name == "lightgbm"


def test_target_optimization_requires_candidate_horizons() -> None:
    with pytest.raises(ValueError, match="candidate_horizons"):
        config.TargetOptimizationConfig(candidate_horizons=())


def test_target_optimization_accepts_partially_valid_threshold_grid() -> None:
    cfg = config.TargetOptimizationConfig(
        candidate_horizons=(3, 5),
        candidate_up_thresholds=(0.0, 0.02),
        candidate_down_thresholds=(-0.01, 0.01),
    )

    assert cfg.candidate_up_thresholds == (0.0, 0.02)


def test_threshold_optimization_rejects_invalid_candidate_decision_threshold() -> None:
    with pytest.raises(ValueError, match="candidate_decision_thresholds"):
        config.ThresholdOptimizationConfig(candidate_decision_thresholds=(0.0, 0.5))


def test_threshold_optimization_rejects_invalid_action_rate_bounds() -> None:
    with pytest.raises(ValueError, match="min_action_rate"):
        config.ThresholdOptimizationConfig(min_action_rate=0.40, max_action_rate=0.20)


