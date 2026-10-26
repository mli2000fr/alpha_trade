from datetime import date
import numpy as np
import pandas as pd
import pytest
from scripts.research import us_options_equal_mix_20261026 as s


def candidates():
    return pd.DataFrame([dict(entry_day='2026-09-15',symbol=sym,
        volume_call_minus_put_log=v,oi_call_minus_put_log=o,
        feature_available_at=pd.Timestamp('2026-09-14T21:00Z'),
        decision_at=pd.Timestamp('2026-09-15T13:25Z'),entry_at=pd.Timestamp('2026-09-15T13:30Z'))
        for sym,v,o in [('A',1.,3.),('B',2.,2.),('C',3.,1.)]])


def cal():
    days=pd.bdate_range('2026-09-15',periods=25)
    return pd.DataFrame(dict(day=days,opened=days.tz_localize('UTC')+pd.Timedelta(hours=13,minutes=30),
                             closed=days.tz_localize('UTC')+pd.Timedelta(hours=20)))


def prices():
    return pd.DataFrame([dict(symbol='A',date=d,open=100.,high=105.,low=99.,close=103.,volume=1000,
        is_filled=0,instrument_id=42,data_source='alpaca_sip',data_adjustment='split') for d in cal().day])


def test_equal_weights_ranks_and_ties():
    scores=s.score_candidates(candidates())
    assert scores.combined_score.tolist()==pytest.approx([.5,.5,.5])
    assert scores.volume_score.tolist()==pytest.approx([1/6,.5,5/6])


def test_future_outcomes_do_not_affect_rank_cohort():
    f=candidates().assign(status=['NOT_MATURE','LABEL','AMBIGUOUS'],future_return=[np.nan,1.,-1.])
    pd.testing.assert_frame_equal(s.score_candidates(f),s.score_candidates(f.assign(status='LABEL',future_return=100)))
    assert len(s.score_candidates(f))==3


def test_missing_is_not_zero_and_future_features_rejected():
    f=candidates();f.loc[0,s.FEATURES[1]]=np.nan
    assert set(s.score_candidates(f).symbol)=={'B','C'}
    f=candidates();f.loc[0,'feature_available_at']=pd.Timestamp('2026-09-15T14:00Z')
    with pytest.raises(ValueError,match='Future feature'):s.score_candidates(f)


def test_duplicate_candidates_rejected():
    with pytest.raises(ValueError,match='Duplicate'):s.score_candidates(pd.concat([candidates(),candidates()]))


def test_latest_conflicts_not_selected_arbitrarily():
    f=pd.DataFrame([dict(symbol='A',received_at=pd.Timestamp('2026-09-14T21:00Z'),volume=v) for v in [1,2]])
    result,n=s.latest_unambiguous(f,['symbol'],['volume'])
    assert n==2 and result.empty


def test_late_historical_download_not_prospective_volume():
    f=pd.DataFrame([dict(symbol='A',contract_symbol='A261002C00100000',expiration_date='2026-10-02',
        option_type='CALL',available_at='2026-09-14T21:00Z',observed_at='2026-09-14T21:00Z',bar_timestamp=t)
        for t in ['2026-09-14T20:00Z','2024-01-15T20:00Z']])
    assert len(s.standard_rows(f,received_day=True))==1


def test_daily_gap_stop_precedes_rebound_and_ambiguous_direction_reserved():
    path=[dict(date='1',open=100,high=105,low=99,close=102),dict(date='2',open=85,high=150,low=80,close=90)]
    assert s.protected_excursion(path,'LONG')['upper_pct']==pytest.approx(5.)
    a=dict(lower_pct=0,upper_pct=25,ambiguous=True,peak_day=None)
    b=dict(lower_pct=20,upper_pct=20,ambiguous=False,peak_day='1')
    assert s.compare_paths(a,b)[0]=='AMBIGUOUS_OR_TIE'


def test_no_partial_h20_and_missing_identity_blocked():
    score=s.score_candidates(candidates().iloc[:1])
    labels=s.make_labels(score,prices(),cal(),pd.Timestamp('2026-09-22T21:00Z'))
    assert labels.loc[labels.horizon.eq(20),'status'].iloc[0]=='NOT_MATURE'
    p=prices();p.loc[0,'instrument_id']=None
    labels=s.make_labels(score,p,cal(),pd.Timestamp('2026-11-01T21:00Z'))
    assert labels.status.eq('INVALID_OR_INCOMPLETE_PRICE_IDENTITY').all()


def test_constant_scores_chance_not_dropped_date():
    f=s.score_candidates(candidates()).assign(status='LABEL',dominant_direction=['LONG','SHORT','LONG'])
    assert s.metrics(f)['scores']['combined_score']['mean_daily_auc']==.5


def test_spacing_uses_calendar_not_available_label_dates():
    c=cal();days=[str(d.date()) for d in c.day]
    assert s.spaced_dates([days[0],days[3],days[5],days[6]],5,c)==[days[0],days[5]]


def test_same_bar_peak_stop_bounds_and_exact_short_stop():
    r=s.protected_excursion([dict(date='1',open=100,high=125,low=89,close=100)],'LONG')
    assert r['lower_pct']==0 and r['upper_pct']==25 and r['ambiguous']
    r=s.protected_excursion([dict(date='1',open=100,high=110,low=99,close=100),
        dict(date='2',open=100,high=105,low=50,close=60)],'SHORT')
    assert r['stop_day']=='1'
