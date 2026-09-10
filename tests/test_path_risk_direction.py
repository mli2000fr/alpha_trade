from __future__ import annotations

import pandas as pd
import pytest

from modelFactory import path_risk_direction as direction
from modelFactory.path_aware_directional import LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL
from modelFactory.path_aware_utility import LONG_TAIL_RISK_COL, SHORT_TAIL_RISK_COL


def _frame(dates: int = 3, symbols: int = 10) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date in pd.date_range("2024-01-02", periods=dates, freq="B"):
        for index in range(symbols):
            long_safer = index < symbols // 2
            rows.append({
                "date": date, "symbol": f"S{index:02d}", "fold_index": 0,
                LONG_NET_RETURN_COL: 0.05 if long_safer else -0.05,
                SHORT_NET_RETURN_COL: -0.05 if long_safer else 0.05,
                LONG_TAIL_RISK_COL: index / symbols,
                SHORT_TAIL_RISK_COL: (symbols - 1 - index) / symbols,
            })
    return pd.DataFrame(rows)


def test_risk_direction_config_validates_margin() -> None:
    assert direction.RiskDirectionConfig().primary_margin == pytest.approx(0.20)
    with pytest.raises(ValueError, match="primary_margin"):
        direction.RiskDirectionConfig(primary_margin=1.0)


def test_daily_risk_asymmetry_prefers_safer_side() -> None:
    scored = direction.add_daily_risk_asymmetry(_frame(dates=1))
    first = scored.loc[scored["symbol"].eq("S00")].iloc[0]
    last = scored.loc[scored["symbol"].eq("S09")].iloc[0]
    assert first[direction.RISK_DIRECTION_SCORE_COL] > 0
    assert last[direction.RISK_DIRECTION_SCORE_COL] < 0


def test_direction_policy_abstains_inside_margin_and_uses_correct_return() -> None:
    scored = direction.add_daily_risk_asymmetry(_frame(dates=1))
    policy = direction.apply_direction_policy(scored, 0.20)
    selected = policy.loc[policy[direction.DECISION_COL].ne("ABSTAIN")]
    assert not selected.empty
    assert set(selected[direction.DECISION_COL]) == {"LONG", "SHORT"}
    assert bool(selected[direction.CHOSEN_RETURN_COL].eq(0.05).all())


def test_evaluation_compares_same_events_to_random_and_static_sides() -> None:
    result = direction.evaluate_risk_direction(_frame(), margins=(0.20,))
    primary = result["policies"]["0.20"]
    assert 0 < primary["coverage"] < 1
    assert primary["long_share"] == pytest.approx(0.5)
    assert primary["short_share"] == pytest.approx(0.5)
    assert primary["mean_net_return"] == pytest.approx(0.05)
    assert primary["random_50_50_expected_return"] == pytest.approx(0.0)
    assert primary["lift_vs_random_50_50"] == pytest.approx(0.05)
    assert primary["lift_vs_best_static_side"] == pytest.approx(0.05)


def test_equal_risks_produce_abstention_even_at_zero_margin() -> None:
    frame = _frame(dates=1)
    frame[SHORT_TAIL_RISK_COL] = frame[LONG_TAIL_RISK_COL]
    scored = direction.add_daily_risk_asymmetry(frame)
    policy = direction.apply_direction_policy(scored, 0.0)
    assert bool(policy[direction.DECISION_COL].eq("ABSTAIN").all())


def test_gates_require_repeated_oos_improvement() -> None:
    primary = {
        "coverage": 0.5, "long_share": 0.5, "short_share": 0.5,
        "mean_net_return": 0.01, "lift_vs_random_50_50": 0.005,
        "lift_vs_best_static_side": 0.003, "cvar_delta_vs_random": 0.01,
        "concentration": {"top1_positive_contribution_share": 0.1},
    }
    stability = {
        "positive_lift_folds": 7, "positive_return_folds": 7,
        "beats_best_static_folds": 7, "tail_risk_not_worse_folds": 7,
    }
    assert direction._gates(
        primary, stability, direction.RiskDirectionConfig()
    )["all_gates_passed"]
