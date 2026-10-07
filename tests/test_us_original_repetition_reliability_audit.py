import pandas as pd
import pytest

from scripts.research.us_original_repetition_reliability_audit import episode_selection, capped_day_weight, reliability


def test_episode_break_and_calendar_cooldown():
    sessions=pd.bdate_range('2025-01-01',periods=45)
    frame=pd.DataFrame({'symbol':['A']*5,'date':sessions[[0,1,3,20,21]]})
    out=episode_selection(frame,sessions)
    assert out.episode_start.tolist()==[True,False,True,True,False]
    assert out.first_h20_signal.tolist()==[True,False,False,True,False]


def test_cooldown_does_not_restart_at_year_boundary():
    sessions=pd.bdate_range('2025-12-29',periods=25)
    frame=pd.DataFrame({'symbol':['A','A','A'],'date':sessions[[0,5,20]]})
    out=episode_selection(frame,sessions)
    assert out.first_h20_signal.tolist()==[True,False,True]


def test_duplicate_signals_rejected():
    frame=pd.DataFrame({'symbol':['A','A'],'date':pd.to_datetime(['2025-01-01']*2)})
    with pytest.raises(ValueError,match='Duplicate'):
        episode_selection(frame,pd.DatetimeIndex(['2025-01-01']))


def test_cap_leaves_cash_not_reallocation():
    frame=pd.DataFrame({'date':pd.to_datetime(['2025-01-02']*2),'symbol':['A','B'],
                        'future_return':[.1,-.2],'target_quality_valid':[1,1]})
    result=capped_day_weight(frame)
    assert abs(result['mean_cash_fraction']-.8)<1e-9
    assert abs(result['mean_daily_budget_h20_pct']+1)<1e-9


def test_reliability_bins_and_invalid_labels():
    frame=pd.DataFrame({'date':pd.to_datetime(['2025-01-02']*3),'symbol':['A','B','C'],
        'future_return':[.1,-.2,.8],'target_quality_valid':[1,1,0],
        'oracle_decile':[10,1,10],'proba_long':[.55,.8,.95]})
    out=reliability(frame,{'positive':.5,'above_3pct':.5})
    assert out['events']==2
    assert out['events_by_bin'][0]['bin']=='(0.35, 0.55]'
    assert out['metrics']['positive']['auc']==0
