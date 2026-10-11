import pandas as pd
import numpy as np
from scripts.research.options_downloaded_directional_audit import paired_features, FEATURE


def test_pair_keeps_orientation_and_never_imputes_missing_put():
    spots = pd.DataFrame([dict(symbol='ABC', day=pd.Timestamp('2024-02-01'), spot=100)])
    rows = [dict(symbol='ABC', contract_symbol='C', bar_timestamp='2024-02-01T05:00:00Z',
        expiration_date='2024-02-23', strike=100, volume=100, option_type='CALL'),
        dict(symbol='ABC', contract_symbol='P', bar_timestamp='2024-02-01T05:00:00Z',
        expiration_date='2024-02-23', strike=100, volume=10, option_type='PUT')]
    pairs = paired_features(pd.DataFrame(rows), spots)
    assert len(pairs) == 1 and np.isclose(pairs.iloc[0][FEATURE], np.log1p(100)-np.log1p(10))
    assert paired_features(pd.DataFrame(rows[:1]), spots).empty


def test_far_strike_cannot_be_used_for_direction():
    spots = pd.DataFrame([dict(symbol='ABC', day=pd.Timestamp('2024-02-01'), spot=100)])
    rows = [dict(symbol='ABC', contract_symbol=t, bar_timestamp='2024-02-01T05:00:00Z',
        expiration_date='2024-02-23', strike=110, volume=10, option_type=t) for t in ('CALL', 'PUT')]
    assert paired_features(pd.DataFrame(rows), spots).empty


def test_oracle_selection_precedes_options_and_uses_stable_score_order():
    from scripts.research.options_oracle_top20_directional_audit import select_top20
    scores = pd.DataFrame([dict(day='2024-02-01', symbol=s, proba_extreme=p,
        fold_start='2024-01-08') for s,p in [('Z', .9), ('A', .9), ('B', .8), ('C', .7), ('D', .6)]])
    top, coverage = select_top20(scores, 5)
    assert top.symbol.tolist() == ['A']
    assert coverage[0]['qualified']
    scores.loc[0, 'fold_start'] = '2024-02-02'
    import pytest
    with pytest.raises(ValueError, match='lineage'):
        select_top20(scores, 5)
