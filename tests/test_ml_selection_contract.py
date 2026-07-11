import pytest

from core.ml_selection_contract import (
    LIVE_WORKFLOW_STAGES,
    MLFirstSelectionContract,
    SelectionCapacity,
)
from ihm.services.backtesting_runner import BacktestRunOptions
from ihm.services.pipeline_runner import PipelineLaunchOptions
from risk_management.config import RiskConfig


def test_ml_first_contract_defaults_are_single_path_invariants() -> None:
    contract = MLFirstSelectionContract()

    assert contract.universe_source == "tradable-universe"
    assert contract.prediction_target_mode == "ternary"
    assert contract.score_role == "feature_veto"
    assert contract.feature_scope == "full_tradable_universe"
    assert contract.veto_timing == "post_prediction_ranking"
    assert contract.training_workflow == "separate"
    assert contract.prediction_required is True
    assert contract.separate_side_ranking is True
    assert contract.live_workflow_stages == LIVE_WORKFLOW_STAGES
    assert len(contract.live_workflow_stages) == 12


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"universe_source": "candidates"}, "tradable-universe"),
        ({"prediction_target_mode": "binary"}, "ternaire"),
        ({"score_role": "ranking"}, "feature ou veto"),
        ({"feature_scope": "candidates"}, "tout l'univers tradable"),
        ({"veto_timing": "pre_prediction"}, "après le ranking"),
        ({"training_workflow": "daily_live"}, "séparé"),
        ({"prediction_required": False}, "obligatoire"),
        ({"separate_side_ranking": False}, "séparés"),
        ({"live_workflow_stages": ("ml_predict", "execution")}, "12 étapes"),
    ],
)
def test_ml_first_contract_rejects_legacy_variants(
    override: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        MLFirstSelectionContract(**override)  # type: ignore[arg-type]


def test_selection_capacity_enforces_total_and_side_caps() -> None:
    capacity = SelectionCapacity(
        max_positions=4,
        max_long_positions=3,
        max_short_positions=2,
    )

    assert capacity.max_positions == 4
    assert capacity.max_long_positions == 3
    assert capacity.max_short_positions == 2


@pytest.mark.parametrize(
    "override",
    [
        {"max_positions": 0, "max_long_positions": 0, "max_short_positions": 0},
        {"max_positions": 4, "max_long_positions": 5, "max_short_positions": 0},
        {"max_positions": 4, "max_long_positions": 4, "max_short_positions": 5},
        {"max_positions": 4, "max_long_positions": -1, "max_short_positions": 0},
        {"max_positions": 4, "max_long_positions": 4, "max_short_positions": -1},
    ],
)
def test_selection_capacity_rejects_invalid_limits(override: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        SelectionCapacity(**override)


def test_risk_config_exposes_effective_selection_capacity() -> None:
    config = RiskConfig(
        max_positions=4,
        max_long_positions=3,
        max_short_positions=2,
        effective_max_positions_override=2,
    )

    assert config.selection_capacity == SelectionCapacity(
        max_positions=2,
        max_long_positions=2,
        max_short_positions=2,
    )


def test_launch_surfaces_share_the_ml_first_contract() -> None:
    pipeline_contract = PipelineLaunchOptions(
        risk_max_positions=4,
    ).ml_first_selection_contract
    backtest_contract = BacktestRunOptions(
        start="2025-01-01",
        max_positions=4,
    ).ml_first_selection_contract
    risk_capacity = RiskConfig(
        max_positions=4,
        max_long_positions=4,
        max_short_positions=2,
    ).selection_capacity

    assert pipeline_contract == backtest_contract
    assert pipeline_contract.capacity == risk_capacity