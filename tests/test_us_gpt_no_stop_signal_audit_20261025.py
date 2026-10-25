import pandas as pd
import pytest
from types import SimpleNamespace

from scripts.research.us_gpt_no_stop_signal_audit_20261025 import outcome,statistics


def fixture():
    days=pd.bdate_range('2026-01-01',periods=21)
    sessions=[SimpleNamespace(session_date=d.date(),open_at_utc=d.tz_localize('UTC')+pd.Timedelta(hours=14),
        close_at_utc=d.tz_localize('UTC')+pd.Timedelta(hours=14,minutes=5)) for d in days]
    rows=[dict(bar_timestamp=s.open_at_utc,bar_end_timestamp=s.close_at_utc,open=100.,high=125.,low=50.,close=101.) for s in sessions]
    rows[-1].update(open=110.,high=120.,low=100.,close=110.)
    return pd.DataFrame(rows),sessions


def test_no_stop_keeps_deep_adverse_excursion_and_uses_open21_not_peak():
    path,sessions=fixture();r=outcome(path,path.iloc[0],sessions)
    assert r['status']=='WIN' and r['exit_price']==110
    assert r['max_down_pct']==-50 and r['max_up_pct']==25
    assert r['net_return_pct']==pytest.approx(9.832)
    assert r['h20_close_return_pct']==pytest.approx(1.)


def test_missing_due_or_window_not_classified_as_loss():
    path,sessions=fixture()
    assert outcome(path.iloc[:-1],path.iloc[0],sessions)['status']=='CENSORED_OR_INCOMPLETE'
    assert outcome(path.drop(index=5),path.iloc[0],sessions)['status']=='CENSORED_OR_INCOMPLETE'


def test_entry_mid_session_does_not_require_bars_before_entry():
    path,sessions=fixture()
    sessions[0].close_at_utc+=pd.Timedelta(minutes=5)
    later=path.iloc[0].to_dict()
    later.update(bar_timestamp=later['bar_timestamp']+pd.Timedelta(minutes=5),
        bar_end_timestamp=later['bar_end_timestamp']+pd.Timedelta(minutes=5))
    path=pd.concat([path,pd.DataFrame([later])]).sort_values('bar_timestamp').reset_index(drop=True)
    r=outcome(path,path.iloc[1],sessions)
    assert r['status']=='WIN' and r['exit_price']==110


def test_stats_exclude_censored_and_no_entry_from_wins_losses():
    f=pd.DataFrame(dict(symbol=list('ABCD'),status=['WIN','LOSS','NO_ENTRY','CENSORED_OR_INCOMPLETE'],
        net_return_pct=[10.,-20.,None,None],max_up_pct=[25.,10.,None,None],max_down_pct=[-20.,-30.,None,None]))
    r=statistics(f)
    assert r['signals']==4 and r['mature']==2 and r['win_pct']==50.
    assert r['mean_net_return_pct']==-5.
