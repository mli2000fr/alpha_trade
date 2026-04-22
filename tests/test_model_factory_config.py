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


