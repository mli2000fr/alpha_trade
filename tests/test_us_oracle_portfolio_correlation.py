import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_portfolio_correlation import prior_returns, evaluate_pair


def frame():
    rng = np.random.default_rng(48)
    a = rng.normal(0, .02, 50)
    return pd.DataFrame(dict(A=a, B=a*2, C=-a, D=rng.normal(0, .02, 50)),
                        index=pd.bdate_range('2025-01-01', periods=50))


@pytest.mark.parametrize('side', ['buy', 'sell'])
def test_same_bet_is_rejected_and_anticorrelation_not_treated_as_same_bet(side):
    g = frame()
    assert evaluate_pair(g, 'A', 'B', side, side)['status'] == 'CORRELATED'
    assert evaluate_pair(g, 'A', 'C', side, side)['status'] == 'PASS'
    assert evaluate_pair(g, 'A', 'D', side, side)['status'] == 'PASS'


def test_missing_and_flat_history_are_not_mistaken_for_low_correlation():
    g = frame(); g.loc[g.index[:30], 'B'] = np.nan
    assert evaluate_pair(g, 'A', 'B', 'buy', 'buy')['status'] == 'MISSING_PAIR'
    g['B'] = 0.
    assert evaluate_pair(g, 'A', 'B', 'buy', 'buy')['status'] == 'MISSING_PAIR'
    assert evaluate_pair(g, 'A', 'UNKNOWN', 'buy', 'buy')['status'] == 'MISSING_PAIR'


def prices():
    days = pd.bdate_range('2025-01-01', periods=80)
    c = 100*np.exp(np.arange(80)*.001)
    return pd.DataFrame(dict(date=days, symbol='A', open=c, close=c, high=c*1.01,
                             low=c*.99, volume=1000., is_filled=0, data_adjustment='split'))


@pytest.mark.parametrize('kind', ['missing', 'filled', 'unqualified_adjustment'])
def test_no_synthetic_zero_returns_across_a_missing_price(kind):
    g = prices(); days = pd.DatetimeIndex(g.date)
    if kind == 'missing':
        g = g[g.date.ne(days[20])]
    elif kind == 'filled':
        g.loc[20, 'is_filled'] = 1
    else:
        g.loc[20, 'data_adjustment'] = None
    r = prior_returns(g, days)
    assert pd.isna(r.at[days[20], 'A']) and pd.isna(r.at[days[21], 'A'])
    assert np.isfinite(r.at[days[22], 'A'])


def test_future_daily_changes_do_not_change_past_returns():
    g = prices(); days = pd.DatetimeIndex(g.date)
    before = prior_returns(g, days)
    g.loc[60:, ['close', 'open', 'high', 'low']] *= 7
    pd.testing.assert_frame_equal(before.iloc[:60], prior_returns(g, days).iloc[:60])


def test_duplicate_price_identity_rejected():
    g = prices()
    with pytest.raises(ValueError, match='Duplicate'):
        prior_returns(pd.concat([g, g.iloc[:1]]), pd.DatetimeIndex(g.date))


def test_held_prefix_priority_cannot_be_removed_by_another_existing_position():
    g = frame()
    for blocker in ['A', 'B']:
        candidate = 'B' if blocker == 'A' else 'A'
        r = evaluate_pair(g, candidate, blocker, 'buy', 'buy')
        assert r['status'] == 'CORRELATED' and r['held_symbol'] == blocker
