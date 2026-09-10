from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory import oracle_daily_regime as daily
from modelFactory.first_touch_directional import DOWN_FIRST, UP_FIRST
from modelFactory.oracle.dataset import GUARD_COL
from modelFactory.path_aware_directional import LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL
from modelFactory.shared_directional import ORACLE_GATE_SCORE_COL


def _events(dates: int = 3, symbols: int = 20) -> pd.DataFrame:
    rows = []
    for date_index, date in enumerate(pd.date_range("2024-01-02", periods=dates, freq="B")):
        for symbol_index in range(symbols):
            up = symbol_index < (14 if date_index % 2 == 0 else 6)
            rows.append({
                "date": date, "symbol": f"S{symbol_index:02d}",
                GUARD_COL: date + pd.offsets.BDay(20),
                "first_touch_target": UP_FIRST if up else DOWN_FIRST,
                LONG_NET_RETURN_COL: 0.04 if up else -0.03,
                SHORT_NET_RETURN_COL: -0.04 if up else 0.03,
                ORACLE_GATE_SCORE_COL: 0.8 + symbol_index / 1000,
                "market_return_20": 0.02 if date_index % 2 == 0 else -0.02,
                "market_trend_strength_50": 0.03 if date_index % 2 == 0 else -0.03,
                "regime_bull_market": float(date_index % 2 == 0),
                "regime_risk_off": float(date_index % 2 == 1),
                "daily_return": 0.01 if up else -0.01,
                "momentum_5": 0.02 if up else -0.02,
                "momentum_20": 0.03 if up else -0.03,
                "momentum_60": 0.04 if up else -0.04,
                "relative_strength_20": 0.01 if up else -0.01,
                "sma20_distance": 0.02 if up else -0.02,
                "rsi_14": 60.0 if up else 40.0,
                "range_position_20": 0.7 if up else 0.3,
            })
    return pd.DataFrame(rows)


def test_daily_panel_has_one_row_per_date_and_continuous_target() -> None:
    panel, features, diagnostics = daily.build_daily_regime_panel(_events())
    assert len(panel) == 3
    assert panel["date"].is_unique
    assert panel[daily.UP_RATE_COL].tolist() == pytest.approx([0.7, 0.3, 0.7])
    assert panel[daily.DAILY_TARGET_COL].tolist() == pytest.approx([0.4, -0.4, 0.4])
    assert panel[daily.LONG_BASKET_RETURN_COL].iloc[0] == pytest.approx(0.019)
    assert panel[daily.SHORT_BASKET_RETURN_COL].iloc[0] == pytest.approx(-0.019)
    assert "breadth_positive_momentum_20" in features
    assert "median_momentum_20" in features
    assert diagnostics["feature_count"] == len(features)
    assert len(features) <= 26


def test_daily_panel_excludes_rare_classes_from_target_denominator() -> None:
    events = _events(dates=1)
    events.loc[:4, "first_touch_target"] = 0
    panel, _, _ = daily.build_daily_regime_panel(events, min_daily_candidates=10)
    # 9 UP et 6 DOWN restent après les cinq exclusions.
    assert panel.iloc[0][daily.UP_RATE_COL] == pytest.approx(9 / 15)
    assert panel.iloc[0]["daily_directional_count"] == 15


def test_daily_panel_rejects_dates_with_too_few_directional_candidates() -> None:
    events = _events(dates=1)
    events.loc[:10, "first_touch_target"] = np.nan
    with pytest.raises(ValueError, match="vide"):
        daily.build_daily_regime_panel(events, min_daily_candidates=10)


def _scored() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("2024-01-02", periods=4, freq="B"),
        daily.DAILY_TARGET_COL: [0.6, -0.6, 0.1, -0.1],
        daily.UP_RATE_COL: [0.8, 0.2, 0.55, 0.45],
        daily.PREDICTION_COL: [0.5, -0.5, 0.05, -0.05],
        daily.LONG_BASKET_RETURN_COL: [0.04, -0.04, 0.01, -0.01],
        daily.SHORT_BASKET_RETURN_COL: [-0.04, 0.04, -0.01, 0.01],
    })


def test_primary_policy_abstains_inside_neutral_band() -> None:
    policy = daily.apply_daily_policy(_scored(), 0.20)
    assert policy[daily.DECISION_COL].tolist() == [
        "LONG_DAY", "SHORT_DAY", "ABSTAIN", "ABSTAIN",
    ]
    assert policy[daily.CHOSEN_RETURN_COL].dropna().tolist() == pytest.approx([0.04, 0.04])


def test_evaluation_of_perfect_daily_direction() -> None:
    metrics = daily.evaluate_daily_predictions(_scored())
    primary = metrics["policies"][f"{daily.PRIMARY_THRESHOLD:.2f}"]
    assert metrics["pearson_ic"] > 0.99
    assert metrics["spearman_ic"] > 0.99
    assert primary["coverage"] == pytest.approx(0.5)
    assert primary["direction_accuracy"] == pytest.approx(1.0)
    assert primary["mean_chosen_basket_return"] == pytest.approx(0.04)
    assert primary["lift_vs_random_50_50"] == pytest.approx(0.04)


def test_daily_config_rejects_invalid_contract() -> None:
    with pytest.raises(ValueError):
        daily.DailyRegimeConfig(min_daily_candidates=1)
    with pytest.raises(ValueError):
        daily.DailyRegimeConfig(primary_threshold=1.0)
