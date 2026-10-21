import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_campaign import admit_campaigns,fresh_signals,exit_trade,simulate_campaign


def path(values,offsets=None):
    f=pd.DataFrame(values,columns=['open','high','low','close'],dtype=float)
    t=pd.date_range('2025-01-02 14:30Z',periods=len(f),freq='5min')
    return f.assign(bar_timestamp=t,bar_end_timestamp=t+pd.Timedelta(minutes=5),
        previous_high=101.,previous_low=99.,previous_close=100.,session_offset=offsets if offsets is not None else 5)


def test_first_two_completed_closes_then_next_open():
    f=path([[101,103,100,102],[102,104,101,103],[104,105,103,104],[104,105,103,104]])
    assert fresh_signals(f)==[(2,1)]
    s,t=simulate_campaign(f,[(2,1)],5,'ONE_FULL','BOTH')
    assert t[0]['entry_price']==104 and t[0]['signal_bar']==1
    assert t[0]['signal_time']==f.bar_end_timestamp.iloc[1]


def test_touch_or_last_bar_does_not_enter():
    assert fresh_signals(path([[100,102,99,101],[101,103,100,102],[102,104,101,103]]))==[]


def test_fresh_cross_required_not_repeated_above_range():
    f=path([[102,103,101,102],[102,104,101,103],[103,104,102,103],[103,104,102,103],[103,104,102,103]])
    assert fresh_signals(f)==[(2,1)]


def test_short_confirmation():
    f=path([[98,99,97,98],[98,99,96,97],[96,98,95,96],[96,98,95,96]])
    assert fresh_signals(f)==[(2,-1)]


def test_no_current_high_lookahead_in_trailing():
    a=np.array([[100,130,99,120],[120,121,110,115],[115,116,114,115]],float)
    i,price,reason,stop,gap=exit_trade(a,0,2,1)
    # Initial stop95 cannot become110.5 inside the first bar.
    assert i==1 and reason=='STOP' and price==pytest.approx(110.5) and not gap


def test_future_high_cannot_change_earlier_exit():
    a=np.array([[100,101,94,95],[100,1000,90,99],[99,100,98,99]],float)
    assert exit_trade(a,0,2,1)[:3]==(0,95.,'STOP')
    a[1,1]=2000
    assert exit_trade(a,0,2,1)[:3]==(0,95.,'STOP')


@pytest.mark.parametrize('side,a,expected',[
    (1,[[100,101,99,100],[80,85,75,81],[81,82,80,81]],80),
    (-1,[[100,101,99,100],[120,125,119,121],[121,122,120,121]],120)])
def test_gap_loss_not_capped(side,a,expected):
    result=exit_trade(np.array(a,float),0,2,side)
    assert result[1]==expected and result[2]=='GAP_STOP'


def test_expiry_at_final_open_no_final_high_low():
    a=np.array([[100,101,99,100],[101,150,50,120]],float)
    assert exit_trade(a,0,1,1)[:3]==(1,101.,'EXPIRY')


def test_confirmation_after_exit_and_max_two_attempts():
    f=path([[100,101,99,100],[100,101,94,95],[95,96,94,95],
        [100,101,99,100],[100,101,99,100],[100,101,94,95],
        [100,101,99,100],[100,101,99,100],[100,101,99,100],[100,101,99,100]])
    events=[(0,1),(2,1),(4,1),(8,1)]
    s,t=simulate_campaign(f,events,5,'TWO_SPLIT','BOTH')
    assert len(t)==2 and [r['entry_bar'] for r in t]==[0,4]
    assert t[1]['planned_risk']<=10 and t[1]['stop_and_cost_reserve']<=t[1]['planned_risk']
    assert t[0]['net']<0 and t[1]['net']<0
    assert s['final_balance']==pytest.approx(1000+sum(r['net'] for r in t))


def test_same_first_trade_for_half_control():
    f=path([[100,101,99,100]]*6)
    _,a=simulate_campaign(f,[(0,1)],5,'ONE_HALF_CONTROL','BOTH')
    _,b=simulate_campaign(f,[(0,1)],5,'TWO_SPLIT','BOTH')
    assert a==b


def test_gap_budget_exhaustion_prevents_second_trade():
    f=path([[100,101,99,100],[50,51,49,50]]+[[100,101,99,100]]*8)
    s,t=simulate_campaign(f,[(0,1),(4,-1)],5,'TWO_SPLIT','BOTH')
    assert len(t)==1 and s['status']=='RISK_BUDGET_EXHAUSTED'
    assert t[0]['net'] < -20


def test_long_only_abstains_short_and_whole_shares_can_be_zero():
    f=path([[100,101,99,100]]*6)
    s,t=simulate_campaign(f,[(0,-1)],5,'ONE_FULL','LONG_ONLY')
    assert s['net']==0 and not t and s['status']=='NO_SIGNAL'
    f[['open','high','low','close']]*=100
    s,t=simulate_campaign(f,[(0,1)],5,'ONE_FULL','BOTH')
    assert not t and s['status']=='ABSTAIN_ZERO_WHOLE_SHARES'


def test_waiting_counts_and_no_entry_at_expiry():
    f=path([[100,101,99,100]]*8,offsets=[1,1,1,5,5,10,10,10])
    s,t=simulate_campaign(f,[(4,1),(6,1)],5,'ONE_FULL','BOTH')
    assert not t and s['net']==0
    s,t=simulate_campaign(f,[(4,1)],10,'ONE_FULL','BOTH')
    assert t[0]['exit_bar']==7


def test_admission_before_quality_and_common20_across_years():
    days=pd.bdate_range('2024-12-01',periods=50)
    f=pd.DataFrame(dict(date=days[[0,5,20,21,40]],symbol='A',rank=1,score=.8))
    selected=admit_campaigns(f,days)
    assert selected.admitted.tolist()==[True,False,True,False,True]


def test_short_initial_quantity_identical_across_horizons():
    f=path([[100,101,99,100]]*12,offsets=[1]*3+[5]*3+[10]*3+[20]*3)
    _,a=simulate_campaign(f,[(0,-1)],5,'ONE_FULL','BOTH')
    _,b=simulate_campaign(f,[(0,-1)],20,'ONE_FULL','BOTH')
    assert a[0]['quantity']==b[0]['quantity']


def test_scalar_trailing_matches_separate_vector_formula_random_paths():
    from scripts.research.us_oracle_campaign_audit import vector_exit
    rng=np.random.default_rng(20261020)
    for side in [-1,1]:
        for _ in range(100):
            op=100*np.exp(np.cumsum(rng.normal(0,.02,30)))
            close=op*np.exp(rng.normal(0,.01,30))
            hi=np.maximum(op,close)*(1+rng.uniform(0,.03,30))
            lo=np.minimum(op,close)*(1-rng.uniform(0,.03,30))
            a=np.c_[op,hi,lo,close]
            left=exit_trade(a,0,29,side);right=vector_exit(a,0,29,side)
            assert left[0]==right[0] and left[2:]==right[2:]
            assert left[1]==pytest.approx(right[1])
