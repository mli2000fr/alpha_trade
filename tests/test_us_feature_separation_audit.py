import pandas as pd
import pytest

from scripts.research.us_feature_separation_audit import auc, describe


def test_auc_ties_and_perfect_order():
    assert auc([False, True], [1, 1]) == .5
    assert auc([False, True], [1, 2]) == 1
    assert auc([False, True], [2, 1]) == 0


def test_daily_rank_must_precede_future_extreme_selection():
    pool = pd.DataFrame({"date": pd.to_datetime(["2025-01-02"] * 3 + ["2025-07-02"] * 3),
                         "feature": [1, 2, 3, 1, 2, 3], "oracle_decile": [1, 5, 10, 1, 5, 10]})
    ranks = pool.feature.groupby(pool.date).rank(pct=True)
    extreme = pool[pool.oracle_decile.isin([1, 10])]
    with pytest.raises(ValueError, match="pre-label"):
        describe(extreme, "feature")
    result = describe(extreme, "feature", ranks)
    assert result["auc_daily_rank"] == 1
    assert result["h2_auc_h1_direction"] == 1
