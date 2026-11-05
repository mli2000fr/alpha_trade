"""Backtest-only re-ranking of verified scores; never revises serving archives."""
import numpy as np
import pandas as pd
import pytest

from backtesting.per_symbol_selection import PerSymbolSelection,select_per_symbol


def scores():
    return pd.DataFrame([
        dict(date='2022-01-03',symbol=s,proba_extreme=o,long_probability=l,short_probability=p)
        for s,o,l,p in [('A',.9,.7,.2),('B',.8,.8,.9),('C',.7,.9,.8),('D',.6,.99,.99)]])


def selected(frame):
    return frame.loc[frame.selected].sort_values('rank')[['symbol','side']].values.tolist()


def test_pool_then_branch_ranking_not_branch_then_oracle():
    a=scores();before=a.copy(deep=True)
    result=select_per_symbol(a,PerSymbolSelection(3,True,False,2,1))
    assert selected(result)==[['C','long'],['B','long']]
    assert result.set_index('symbol').loc['D','reason']=='OUTSIDE_ORACLE_POOL'
    assert result.loc[result.selected,'rank'].tolist()==[2,1]
    pd.testing.assert_frame_equal(a,before)
    assert selected(select_per_symbol(a,PerSymbolSelection(2,True,False,1,1)))==[['B','long']]
    assert selected(select_per_symbol(a,PerSymbolSelection(4,True,False,1,1)))==[['D','long']]


def test_short_only_and_different_counts():
    result=select_per_symbol(scores(),PerSymbolSelection(3,False,True,1,2))
    assert selected(result)==[['B','short'],['C','short']]
    assert not result.retain_long.any()
    assert PerSymbolSelection(3,False,True,1,2).describe()=='TOP3 Oracle -> TOP2 SHORT per-symbol'


def test_conflicts_keep_higher_branch_no_refill_or_hedged_duplicate():
    result=select_per_symbol(scores(),PerSymbolSelection(3,True,True,2,1))
    assert selected(result)==[['B','short'],['C','long']]
    assert result.set_index('symbol').loc['B','reason']=='DIRECTION_CONFLICT_KEEP_HIGHER_PROBABILITY'
    # B was also top2 LONG; A is not promoted after the conflict.
    assert not result.set_index('symbol').loc['A','selected']
    assert result.loc[result.selected,'symbol'].is_unique


def test_equal_direction_scores_abstain_no_refill():
    result=select_per_symbol(scores(),PerSymbolSelection(4,True,True,1,1))
    assert not result.selected.any()
    assert result.set_index('symbol').loc['D','reason']=='DIRECTION_TIE_ABSTAIN'


def test_missing_branch_does_not_invent_scores_or_leave_oracle_pool():
    a=scores();a.loc[a.symbol.eq('C'),'long_probability']=None
    a.loc[a.symbol.eq('B'),'long_probability']=None
    result=select_per_symbol(a,PerSymbolSelection(3,True,False,3,1))
    assert selected(result)==[['A','long']]
    assert result.loc[result.symbol.eq('B'),'long_probability'].isna().all()


def test_numeric_strings_ties_and_dates_do_not_leak_between_sessions():
    a=scores().astype({'long_probability':str,'short_probability':str})
    b=scores().assign(date='2022-01-04',long_probability=[.95,.1,.2,.3])
    result=select_per_symbol(pd.concat([a,b],ignore_index=True),PerSymbolSelection(3,True,False,1,1))
    assert result.loc[result.selected].symbol.tolist()==['C','A']
    a=scores();a['long_probability']=.8
    result=select_per_symbol(a.sample(frac=1,random_state=5),PerSymbolSelection(3,True,False,1,1))
    assert selected(result)==[['A','long']]


@pytest.mark.parametrize('changes',[
    dict(allow_long=False,allow_short=False),dict(oracle_top_n=0),dict(long_top_n=0),
    dict(short_top_n=-1),dict(oracle_top_n=True),dict(allow_short=1),
    dict(oracle_top_n=3,long_top_n=4),dict(oracle_top_n=3,allow_short=True,short_top_n=4),
])
def test_invalid_settings_rejected(changes):
    with pytest.raises(ValueError):PerSymbolSelection(**changes)


@pytest.mark.parametrize('column,value',[
    ('long_probability',1.1),('short_probability','bad'),('proba_extreme',np.nan),('date',None),('symbol',None)])
def test_invalid_input_rejected(column,value):
    a=scores();a.loc[0,column]=value
    with pytest.raises(ValueError):select_per_symbol(a,PerSymbolSelection())


def test_duplicate_identity_rejected():
    a=scores()
    with pytest.raises(ValueError):select_per_symbol(pd.concat([a,a.iloc[:1]]),PerSymbolSelection())


def test_minimum_long_score_strict_boundary_and_no_refill():
    a=scores();a['long_probability']=[.60,.600001,.4,.99]
    result=select_per_symbol(a,PerSymbolSelection(3,True,False,2,1,min_long_probability=.6))
    assert selected(result)==[['B','long']]
    assert result.set_index('symbol').loc['A','reason']=='LONG_SCORE_NOT_ABOVE_THRESHOLD'
    assert result.set_index('symbol').loc['C','long_rank']==3
    assert not result.set_index('symbol').loc['D','selected']  # Never leave the Oracle pool.
    assert result.long_selected_before_threshold.sum()==2
    assert result.long_score_threshold.eq(.6).all()


def test_high_long_threshold_can_legitimately_select_nothing():
    result=select_per_symbol(scores(),PerSymbolSelection(min_long_probability=1.))
    assert not result.selected.any() and result['rank'].isna().all()
    assert result.reason.eq('LONG_SCORE_NOT_ABOVE_THRESHOLD').sum()==4


def test_long_threshold_does_not_change_short_or_resurrect_losing_branch():
    a=scores();a.loc[a.symbol.eq('B'),'long_probability']=.95
    result=select_per_symbol(a,PerSymbolSelection(3,True,True,2,1,min_long_probability=.96))
    assert not result.selected.any()  # B's SHORT lost the collision, do not restore it.
    short=select_per_symbol(scores(),PerSymbolSelection(3,False,True,1,2,min_long_probability=1.))
    assert selected(short)==[['B','short'],['C','short']]


@pytest.mark.parametrize('value',[-.01,1.01,float('nan'),float('inf'),True,'0.6'])
def test_invalid_long_threshold_is_rejected(value):
    with pytest.raises(ValueError,match='Seuil LONG'):PerSymbolSelection(min_long_probability=value)
