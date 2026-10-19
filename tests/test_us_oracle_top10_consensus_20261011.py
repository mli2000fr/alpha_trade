from datetime import date
import pytest
from scripts.research.us_oracle_top10_consensus_20261011 import signals,outcome,summarize


@pytest.mark.parametrize('value,expected',[
    ({'eps_current':-1,'eps_7d_ago':-2},'UP'),
    ({'eps_current':-2,'eps_7d_ago':-1},'DOWN'),
    ({'eps_current':1,'eps_7d_ago':1},'UNCHANGED'),
    ({'eps_current':1,'eps_7d_ago':None},'MISSING'),
])
def test_eps_improvement_is_not_positive_eps_level(value,expected):
    assert signals(value)['eps_7d_direction']==expected


def test_missing_down_not_assumed_zero():
    value=signals({'eps_current':1,'eps_7d_ago':0,'revisions_up_30d':3})
    assert value['revisions_30d_direction']=='MISSING' and value['eps_7d_change_pct'] is None


def bars():
    return [dict(date=d,open=100,close=c,high=112,low=90,is_filled=0,data_source='alpaca_sip',data_adjustment='split')
        for d,c in [('2026-10-09',110),('2026-10-12',105),('2026-10-13',108)]]


def test_forward_return_starts_after_snapshot_not_before():
    result=outcome(bars(),date(2026,10,9),date(2026,10,12),[date(2026,10,12),date(2026,10,13)])
    assert result['status']=='AVAILABLE'
    assert result['entry_to_latest_pct']==pytest.approx(8)
    assert result['close_to_close_pct']==pytest.approx((108/110-1)*100)
    assert result['max_up_from_entry_pct']==pytest.approx(12)
    assert result['max_down_from_entry_pct']==pytest.approx(-10)


@pytest.mark.parametrize('fault',['gap','filled','mixed','invalid'])
def test_unqualified_bars_cannot_enter_accuracy_summary(fault):
    values=bars()
    if fault=='gap':values.pop()
    if fault=='filled':values[-1]['is_filled']=1
    if fault=='mixed':values[-1]['data_source']='alpaca_iex'
    if fault=='invalid':values[-1]['high']=1
    result=outcome(values,date(2026,10,9),date(2026,10,12),[date(2026,10,12),date(2026,10,13)])
    summary=summarize([{'prices':result,'signals':{'eps_7d_direction':'UP'}}],'eps_7d_direction')
    assert summary['active_n']==0


def test_neutral_and_missing_not_successes():
    rows=[{'prices':{'status':'AVAILABLE','entry_to_latest_pct':1},'signals':{'eps_7d_direction':d}}
          for d in ('UP','DOWN','UNCHANGED','MISSING')]
    summary=summarize(rows,'eps_7d_direction')
    assert summary['active_n']==2 and summary['same_direction_n']==1
