import pandas as pd

from modelFactory.oracle_universe_p0e_compare import daily_top_metrics


def test_daily_top_metrics_uses_cross_sectional_top_fraction() -> None:
    frame = pd.DataFrame({
        "date": ["2025-01-02"] * 20,
        "proba_extreme": list(range(20)),
        "oracle_extreme10": [0] * 18 + [1, 1],
        "future_return": [0.01] * 18 + [-0.10, 0.12],
    })
    result = daily_top_metrics(frame, 0.10).iloc[0]
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["selected_abs_return"] == 0.11
