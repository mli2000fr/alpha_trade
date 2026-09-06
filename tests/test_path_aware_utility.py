from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory import path_aware_utility as utility


def test_economic_utility_config_validates_tail_contract() -> None:
    config = utility.EconomicUtilityConfig()
    assert config.catastrophic_loss_threshold == pytest.approx(-0.20)
    assert config.risk_penalty_return == pytest.approx(0.20)
    with pytest.raises(ValueError, match="doit être négatif"):
        utility.EconomicUtilityConfig(catastrophic_loss_threshold=0.0)


def test_winsor_bounds_use_train_only() -> None:
    train = pd.DataFrame({"target": [-100.0, 0.0, 1.0, 2.0, 100.0]})
    config = utility.EconomicUtilityConfig(
        target_winsor_lower=0.20, target_winsor_upper=0.80
    )
    before = utility.target_winsor_bounds(train, "target", config)
    unrelated_test = pd.DataFrame({"target": [-1_000_000.0, 1_000_000.0]})
    after = utility.target_winsor_bounds(train, "target", config)
    assert unrelated_test["target"].abs().max() > 100
    assert before == after
    assert before == pytest.approx((-20.0, 21.6))


def test_add_economic_scores_penalizes_tail_risk_and_ranks_per_date() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02"] * 3 + ["2024-01-03"] * 2),
        utility.LONG_EXPECTED_RETURN_COL: [0.04, 0.03, 0.02, 10.0, 9.0],
        utility.SHORT_EXPECTED_RETURN_COL: [0.01, 0.01, 0.01, 1.0, 2.0],
        utility.LONG_TAIL_RISK_COL: [0.50, 0.00, 0.00, 0.00, 0.00],
        utility.SHORT_TAIL_RISK_COL: [0.00, 0.00, 0.00, 0.00, 0.00],
    })
    scored = utility.add_economic_scores(
        frame, utility.EconomicUtilityConfig(risk_penalty_return=0.20)
    )
    first_day = scored.iloc[:3]
    assert first_day.iloc[0][utility.LONG_UTILITY_RAW_COL] < first_day.iloc[1][utility.LONG_UTILITY_RAW_COL]
    assert first_day.iloc[1][utility.LONG_UTILITY_RANK_COL] == pytest.approx(1.0)
    assert scored.iloc[3][utility.LONG_UTILITY_RANK_COL] == pytest.approx(1.0)


def test_evaluate_economic_oos_uses_side_specific_returns_and_tail_metrics() -> None:
    rows: list[dict[str, object]] = []
    for date in pd.date_range("2024-01-02", periods=5, freq="B"):
        for index in range(20):
            long_return = -0.25 + index * 0.02
            short_return = 0.13 - index * 0.02
            rows.append({
                "date": date,
                "symbol": f"S{index:02d}",
                utility.LONG_NET_RETURN_COL: long_return,
                utility.SHORT_NET_RETURN_COL: short_return,
                utility.LONG_EXPECTED_RETURN_COL: long_return,
                utility.SHORT_EXPECTED_RETURN_COL: short_return,
                utility.LONG_TAIL_RISK_COL: float(long_return <= -0.20),
                utility.SHORT_TAIL_RISK_COL: float(short_return <= -0.20),
            })
    metrics = utility.evaluate_economic_oos(pd.DataFrame(rows))
    assert metrics["long"]["mean_net_return"] > 0
    assert metrics["short"]["mean_net_return"] > 0
    assert metrics["long"]["return_lift_vs_matched"] > 0
    assert metrics["short"]["return_lift_vs_matched"] > 0
    assert metrics["long"]["mean_daily_ic"] == pytest.approx(1.0)
    assert metrics["short"]["mean_daily_ic"] == pytest.approx(1.0)
    assert metrics["long"]["catastrophic_loss_rate"] == pytest.approx(0.0)
    assert np.isfinite(metrics["short"]["cvar_05"])


def test_fold_stability_requires_economic_and_tail_risk_gates() -> None:
    side = {
        "mean_daily_ic": 0.05,
        "return_lift_vs_matched": 0.004,
        "mean_net_return": 0.01,
        "catastrophic_loss_rate": 0.01,
        "matched_catastrophic_loss_rate": 0.02,
        "cvar_lift_vs_matched": 0.01,
        "concentration": {"top1_positive_contribution_share": 0.10},
    }
    folds = [{"long": side, "short": side} for _ in range(7)]
    result = utility._fold_stability(folds, {"long": side, "short": side})
    assert result["long"]["all_gates_passed"]
    assert result["short"]["all_gates_passed"]
