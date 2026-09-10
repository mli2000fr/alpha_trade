import pandas as pd
import pytest

from modelFactory.oracle_universe_target_audit import _rank, _top_share


def test_top_share_uses_requested_fraction_of_symbols() -> None:
    assert _top_share(pd.Series([40, 30, 20, 10, 0]), 0.20) == pytest.approx(0.40)


def test_rank_is_cross_sectional_within_each_date() -> None:
    frame = pd.DataFrame({
        "date": ["2026-01-02", "2026-01-02", "2026-01-05", "2026-01-05"],
        "score": [1.0, 3.0, 8.0, 2.0],
    })
    assert _rank(frame, "score", ["date"]).tolist() == [0.5, 1.0, 1.0, 0.5]
