import pandas as pd
import pytest
from scripts.research.us_selected_universe_per_symbol_selection_20261104 import select


def sample():
    return pd.DataFrame(dict(date=[pd.Timestamp('2024-01-02')]*25,
        symbol=[f'S{i:02d}' for i in range(25)],score=[1-i*.02 for i in range(25)],
        long_probability=[.1+i*.02 for i in range(25)],future_label=[0]*25))


def test_oracle_pool_frozen_before_long_ranking_no_rank21_refill():
    pool,chosen=select(sample())
    assert chosen.symbol.tolist()==['S19','S18','S17','S16','S15']
    assert chosen.oracle_amplitude_rank.tolist()==[20,19,18,17,16]
    assert chosen.oracle_rank.tolist()==[1,2,3,4,5]
    assert len(pool)==20 and not set(chosen.symbol)&{'S20','S21','S22','S23','S24'}


def test_future_labels_do_not_choose_candidates():
    a=sample();before=select(a)[1].symbol.tolist()
    a.future_label=1
    assert select(a)[1].symbol.tolist()==before


def test_same_long_score_uses_oracle_priority():
    a=sample();a.long_probability=.5
    assert select(a)[1].symbol.tolist()==['S00','S01','S02','S03','S04']


def test_missing_direction_score_in_pool_fails_instead_of_replacing_from_rank21():
    a=sample();a.loc[0,'long_probability']=float('nan')
    with pytest.raises(ValueError,match='Missing/invalid'):select(a)


def test_missing_direction_outside_pool_does_not_change_valid_selection():
    a=sample();a.loc[24,'long_probability']=float('nan')
    assert len(select(a)[1])==5


def test_hindsight_high_long_score_cannot_reenter_oracle_pool():
    a=sample();a.loc[24,'long_probability']=1.
    assert 'S24' not in set(select(a)[1].symbol)
