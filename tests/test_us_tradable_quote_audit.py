import pandas as pd
import pytest

from scripts.research.us_tradable_quote_audit import select_sample, spread_bps, stats


@pytest.mark.parametrize("bid,ask", [(None,1),(0,1),(-1,2),(2,1),(float('nan'),2),(1,float('inf'))])
def test_invalid_two_sided_quote(bid, ask):
    assert spread_bps(bid, ask) is None


def test_basis_points_not_percent():
    assert spread_bps(99.7, 100.3) == pytest.approx(60)
    assert spread_bps(10, 10) == 0


def test_empty_stats():
    result = stats(pd.Series([], dtype=float))
    assert result['count'] == 0
    assert result['median'] is None


def test_sample_bounded_deterministic_unique_and_no_outcome():
    frame = pd.DataFrame([
        dict(symbol=f'S{i:02}', tradability_reason_code='spread_above_maximum',
             selected_spread_bps=100+i, is_tradable=0, quote_date='2026-10-16')
        for i in range(20)] + [
        dict(symbol=f'G{i:02}', tradability_reason_code='tradable',
             selected_spread_bps=10, is_tradable=1, quote_date='2026-10-16')
        for i in range(10)])
    result = select_sample(frame)
    assert len(result) <= 12
    assert len(result) == len(set(result))
    assert result == select_sample(frame.sample(frac=1, random_state=17))
