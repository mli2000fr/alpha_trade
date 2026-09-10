from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory import path_risk_veto as veto
from modelFactory.path_aware_directional import LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL
from modelFactory.path_aware_utility import LONG_TAIL_RISK_COL, SHORT_TAIL_RISK_COL
from modelFactory.shared_directional import ORACLE_GATE_SCORE_COL, P_LONG_COL, P_SHORT_COL


def _frame(dates: int = 2, symbols: int = 10) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date in pd.date_range("2024-01-02", periods=dates, freq="B"):
        for index in range(symbols):
            bad = index >= symbols - 2
            rows.append({
                "date": date, "symbol": f"S{index:02d}", "fold_index": 0,
                ORACLE_GATE_SCORE_COL: index / symbols,
                P_LONG_COL: index / symbols, P_SHORT_COL: index / symbols,
                LONG_NET_RETURN_COL: -0.30 if bad else 0.02,
                SHORT_NET_RETURN_COL: -0.35 if bad else 0.01,
                LONG_TAIL_RISK_COL: index / symbols,
                SHORT_TAIL_RISK_COL: index / symbols,
            })
    return pd.DataFrame(rows)


def test_risk_veto_config_rejects_invalid_primary_fraction() -> None:
    with pytest.raises(ValueError, match="primary_veto_fraction"):
        veto.RiskVetoConfig(primary_veto_fraction=0.0)


def test_daily_veto_rejects_exact_highest_risk_fraction() -> None:
    frame = veto.add_daily_risk_vetoes(_frame(), (0.20,))
    rejected = frame.loc[frame["long_veto_0.20"]]
    assert len(rejected) == 4
    assert set(rejected["symbol"]) == {"S08", "S09"}


def test_veto_reduces_catastrophic_losses_without_refill() -> None:
    metrics = veto.evaluate_risk_veto(_frame(), fractions=(0.0, 0.20))
    result = metrics["policies"]["oracle_pool"]["long"]["0.20"]
    assert result["coverage"] == pytest.approx(0.80)
    assert result["after_veto"]["catastrophic_loss_count"] == 0
    assert result["catastrophic_relative_reduction"] == pytest.approx(1.0)
    assert result["return_delta"] > 0


def test_veto_is_applied_after_candidate_selection_without_changing_direction() -> None:
    metrics = veto.evaluate_risk_veto(_frame(), fractions=(0.0, 0.20))
    long_top = metrics["policies"]["path_probability_top"]["long"]["0.20"]
    short_top = metrics["policies"]["path_probability_top"]["short"]["0.20"]
    assert long_top["baseline"]["rows"] == 2
    assert short_top["baseline"]["rows"] == 2
    assert long_top["after_veto"]["rows"] == 0
    assert short_top["after_veto"]["rows"] == 0


def test_primary_gates_pass_for_stable_protective_veto() -> None:
    config = veto.RiskVetoConfig()
    comparison = {
        "coverage": 0.8,
        "return_delta": 0.001,
        "catastrophic_relative_reduction": 0.8,
        "cvar_delta": 0.01,
        "after_veto": {"concentration": {"top1_positive_contribution_share": 0.1}},
    }
    stability = {
        "catastrophic_rate_improved_folds": 7,
        "cvar_improved_folds": 7,
        "return_preserved_folds": 7,
    }
    result = veto._gates(comparison, stability, config)
    assert result["all_gates_passed"]


def test_veto_mask_is_deterministic_when_risk_ties() -> None:
    frame = _frame(dates=1, symbols=10)
    frame[LONG_TAIL_RISK_COL] = 0.5
    marked = veto.add_daily_risk_vetoes(frame, (0.20,))
    assert marked.loc[marked["long_veto_0.20"], "symbol"].tolist() == ["S00", "S01"]
    assert np.isfinite(marked[LONG_NET_RETURN_COL]).all()
