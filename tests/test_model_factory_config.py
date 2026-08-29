import pytest
from datetime import date

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


def test_data_config_rejects_ternary_positive_down_threshold() -> None:
    with pytest.raises(ValueError, match="target_mode='ternary'"):
        config.DataConfig(target_mode="ternary", target_up_threshold=0.01, target_down_threshold=0.01)


def test_calibration_config_rejects_unknown_method() -> None:
    with pytest.raises(ValueError, match="calibration.method"):
        config.CalibrationConfig(method="isotonic")


def test_walk_forward_config_defaults_to_eight_non_overlapping_splits() -> None:
    cfg = config.WalkForwardConfig()

    assert cfg.min_train_size == 504
    assert cfg.val_size == 126
    assert cfg.test_size == 126
    assert cfg.step_size == 252
    assert cfg.max_splits == 8


def test_data_config_accepts_expert_feature_set() -> None:
    cfg = config.DataConfig(feature_set="expert", benchmark_symbol="SPY")

    assert cfg.feature_set == "expert"
    assert cfg.benchmark_symbol == "SPY"


def test_data_config_defaults_to_training_start_date_2020_01_01() -> None:
    cfg = config.DataConfig()

    assert cfg.training_start_date == date(2020, 1, 1)


def test_data_config_rejects_invalid_training_start_date_type() -> None:
    with pytest.raises(ValueError, match="training_start_date"):
        config.DataConfig(training_start_date="2020-01-01")  # type: ignore[arg-type]


def test_data_config_accepts_training_end_date() -> None:
    cfg = config.DataConfig(training_start_date=date(2020, 1, 1), training_end_date=date(2020, 12, 31))

    assert cfg.training_end_date == date(2020, 12, 31)


def test_data_config_rejects_training_end_date_before_start_date() -> None:
    with pytest.raises(ValueError, match="training_end_date"):
        config.DataConfig(training_start_date=date(2020, 12, 31), training_end_date=date(2020, 1, 1))


def test_data_config_accepts_cross_sectional_fields() -> None:
    cfg = config.DataConfig(enable_cross_sectional_features=True, cross_sectional_min_universe=10)

    assert cfg.enable_cross_sectional_features is True
    assert cfg.cross_sectional_min_universe == 10


def test_data_config_rejects_removed_selector_universe_fields() -> None:
    with pytest.raises(TypeError, match="selector_universe"):
        config.DataConfig(selector_universe_max_candidate_rank=25)  # type: ignore[call-arg]


def test_data_config_rejects_cross_sectional_min_universe_below_two() -> None:
    with pytest.raises(ValueError, match="cross_sectional_min_universe"):
        config.DataConfig(cross_sectional_min_universe=1)


def test_baseline_config_defaults_to_lightgbm() -> None:
    cfg = config.BaselineConfig(enabled=True)

    assert cfg.model_name == "lightgbm"


def test_baseline_config_accepts_catboost_model_name() -> None:
    cfg = config.BaselineConfig(enabled=True, model_name="catboost")

    assert cfg.model_name == "catboost"


def test_global_model_config_accepts_lightgbm() -> None:
    cfg = config.GlobalModelConfig(enabled=True, model_name="lightgbm", artifact_symbol="__GLOBAL__")

    assert cfg.model_name == "lightgbm"


def test_champion_selection_config_accepts_business_score() -> None:
    cfg = config.ChampionSelectionConfig(enabled=True, allow_auto_selection=True, selection_metric="business_score")

    assert cfg.selection_metric == "business_score"


def test_champion_selection_config_rejects_unknown_metric() -> None:
    with pytest.raises(ValueError, match="selection_metric"):
        config.ChampionSelectionConfig(selection_metric="sharpe")


def test_target_optimization_requires_candidate_horizons() -> None:
    """candidate_horizons vide est accepté si des candidats triple-barrier sont fournis,
    mais rejeté si aucun candidat (ni horizon ni triple-barrier) n'est présent."""
    # Avec triple-barrier candidates → OK (pas d'erreur)
    cfg = config.TargetOptimizationConfig(
        candidate_horizons=(),
        candidate_stop_atr_mults=(2.0,),
        candidate_tp_atr_mults=(3.0,),
        candidate_max_sessions=(20,),
    )
    assert cfg.candidate_horizons == ()

    # Sans aucun candidat → doit lever
    with pytest.raises(ValueError, match="candidate_horizons"):
        config.TargetOptimizationConfig(
            candidate_horizons=(),
            candidate_stop_atr_mults=(),
            candidate_tp_atr_mults=(),
            candidate_max_sessions=(),
        )


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


def test_reproducibility_config_defaults_to_seed_42_and_deterministic() -> None:
    cfg = config.ReproducibilityConfig()

    assert cfg.seed == 42
    assert cfg.deterministic is True


def test_reproducibility_config_rejects_negative_seed() -> None:
    with pytest.raises(ValueError, match="reproducibility.seed"):
        config.ReproducibilityConfig(seed=-1)


