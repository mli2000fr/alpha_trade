import pandas as pd
import pytest

from backtesting.risk_overlay import RegimeFilterConfig
from scripts.research.us_winner_q051_regime_gross2_20261108 import RegimeEntryGate


def gate_with_last(value, future=None):
    days = pd.bdate_range('2020-01-01', periods=200)
    close = pd.Series([100.]*199+[value], index=days)
    if future is not None:
        close.loc[days[-1]+pd.Timedelta(days=1)] = future
    gate = RegimeEntryGate(close, RegimeFilterConfig(enabled=True))
    cutoff = pd.Timestamp(days[-1]+pd.Timedelta(days=4), tz='UTC')
    return gate, days[-1].date(), cutoff


def test_defensive_regime_blocks_fixed_candidates_and_ignores_future_prices():
    rows = pd.DataFrame({'symbol': ['A','B']})
    for future in (1.,10000.):
        gate, day, cutoff = gate_with_last(95., future)
        assert gate(day, rows, cutoff) == dict(selected=[], incomplete=False)
        assert gate.receipts[0]['blocked_candidates'] == 2
        assert gate.receipts[0]['spy_close'] == 95.


def test_favorable_regime_preserves_candidate_order():
    gate, day, cutoff = gate_with_last(101.)
    rows = pd.DataFrame({'symbol': ['B','A']})
    assert gate(day, rows, cutoff)['selected'] == ['B','A']
    assert gate.receipts[0]['blocked_candidates'] == 0


def test_regime_fails_for_insufficient_history_or_same_day_decision():
    gate, day, cutoff = gate_with_last(100.)
    rows = pd.DataFrame({'symbol': ['A']})
    with pytest.raises(ValueError, match='précédente'):
        gate(day, rows, pd.Timestamp(day, tz='UTC')+pd.Timedelta(hours=18))
    gate.close = gate.close.iloc[1:]
    with pytest.raises(ValueError, match='insuffisant'):
        gate(day, rows, cutoff)
