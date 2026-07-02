from __future__ import annotations

import pandas as pd

from selector.short_score import enrich_with_short_score, resolve_regime_adaptive_short_params


def test_enrich_with_short_score_marks_partial_when_sma_inputs_missing() -> None:
    day_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "trend_score": 0.20,
                "relative_strength_index": 30.0,
            }
        ]
    )

    result = enrich_with_short_score(day_df)

    assert result.loc[0, "short_score_quality"] == "partial_missing_sma"
    assert result.loc[0, "short_score"] == 0.30 * (1 - 0.20) + 0.25 * (1 - 0.30)


def test_enrich_with_short_score_marks_full_when_sma_inputs_available() -> None:
    trade_day = pd.Timestamp("2026-05-01")
    idx = pd.date_range(end=trade_day, periods=60, freq="D")
    close_df = pd.DataFrame({"AAPL": [100.0] * 59 + [90.0]}, index=idx)
    day_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "trend_score": 0.20,
                "relative_strength_index": 30.0,
            }
        ]
    )

    result = enrich_with_short_score(day_df, close_df=close_df, trade_day=trade_day)

    assert result.loc[0, "short_score_quality"] == "full"
    assert result.loc[0, "sma_50"] is not None
    assert result.loc[0, "last_close"] == 90.0
    assert result.loc[0, "short_score"] > 0.0


def test_resolve_regime_adaptive_short_params_boosts_capital_preservation() -> None:
    class _Cfg:
        short_max_positions = 2
        short_min_score = 0.30

    boosted_max, boosted_min = resolve_regime_adaptive_short_params(_Cfg(), True)
    normal_max, normal_min = resolve_regime_adaptive_short_params(_Cfg(), False)

    assert (normal_max, normal_min) == (2, 0.30)
    assert (boosted_max, boosted_min) == (4, 0.20)