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


