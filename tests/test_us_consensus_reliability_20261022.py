import json
import numpy as np
import pandas as pd
import pytest

from scripts.research import us_consensus_reliability_20261022 as audit


def row(row_id=1,observed='2026-10-11T18:00Z',revenue=100,count=5,**kw):
    raw=dict(code='A.US',date='2026-09-30',period='0q',
        revenueEstimateAvg=revenue,revenueEstimateLow=90,revenueEstimateHigh=200,
        revenueEstimateNumberOfAnalysts=count,earningsEstimateAvg=1,
        earningsEstimateLow=.5,earningsEstimateHigh=2,earningsEstimateNumberOfAnalysts=5)
    result=dict(id=row_id,symbol='A',provider='eodhd',fiscal_period_end=pd.Timestamp('2026-09-30'),
        horizon_raw='0q',snapshot_date=pd.Timestamp(observed).date(),run_id=f'r{row_id}',
        observed_at=pd.Timestamp(observed),available_at=pd.Timestamp(observed),
        ingestion_at=pd.Timestamp(observed)+pd.Timedelta(minutes=1),raw_payload_json=json.dumps(raw),
        raw_hash=audit.payload_hash(raw))
    for field,native in audit.FIELDS.items():result[field]=raw.get(native)
    result.update(kw)
    return result


def runs(rows):
    return {r['run_id']:dict(status='COMPLETED',finished_at=r['observed_at']+pd.Timedelta(minutes=2)) for r in rows}


def test_revenue_counts_unchanged_changed_and_missing():
    a=row()
    assert audit.changes(a,row(revenue=110))['revenue_sign']==1
    assert audit.changes(a,row(revenue=90))['revenue_sign']==-1
    assert audit.changes(a,row(count=6))['revenue_count_group']=='CHANGED_COUNT'
    assert audit.changes(a,row(count=None))['revenue_count_group']=='MISSING_OR_LT3'
    assert audit.changes(a,row(count=5))['revenue_count_group']=='UNCHANGED_COUNT'


def test_do_not_bridge_horizon_or_fiscal_period():
    for changed in (dict(horizon_raw='+1q'),dict(fiscal_period_end=pd.Timestamp('2026-12-31'))):
        with pytest.raises(ValueError,match='fiscal'):
            audit.changes(row(),row(**changed))


def test_eps_zero_denominator_and_negative_to_positive_not_infinite():
    a=row(eps_avg=0)
    b=row(eps_avg=1)
    assert audit.changes(a,b)['eps_relative'] is None
    a['eps_avg']=-1
    assert audit.changes(a,b)['eps_relative']==2


def test_raw_hash_and_normalized_values_are_checked():
    a=row()
    assert audit.row_quality(a,runs([a]))['raw_normalization_ok']
    a['revenue_avg']=99
    assert 'NORMALIZATION:revenue_avg' in audit.row_quality(a,runs([a]))['errors']
    a['raw_hash']='invalid'
    assert 'RAW_HASH_MISMATCH' in audit.row_quality(a,runs([a]))['errors']


def test_eps_range_does_not_override_revenue_range():
    a=row(eps_avg=3)
    quality=audit.row_quality(a,runs([a]))
    assert quality['revenue_range_ok'] and not quality['eps_range_ok']


def test_incomplete_run_has_no_available_timestamp():
    a=row()
    r=runs([a]);r[a['run_id']]['status']='RUNNING'
    result=audit.row_quality(a,r)
    assert not result['run_receipt_ok'] and pd.isna(result['conservative_available'])


def test_receipt_never_predates_ingestion_or_run_finish():
    a=row()
    result=audit.row_quality(a,runs([a]))
    assert result['conservative_available']==pd.Timestamp('2026-10-11T18:02Z')
    a['available_at']=a['observed_at']-pd.Timedelta(seconds=1)
    assert not audit.row_quality(a,runs([a]))['run_receipt_ok']


def test_unchanged_weekend_copies_are_abstention_not_new_signals():
    rows=[row(1,'2026-10-11T18:00Z'),row(2,'2026-10-12T18:00Z')]
    f,_=audit.decision_features(pd.DataFrame(rows),runs(rows),audit.schedule(),pd.Timestamp('2026-10-14T12:00Z'))
    assert len(f)==1 and f.iloc[0].revenue_sign==0
    assert f.iloc[0].entry_date==pd.Timestamp('2026-10-13')


def test_late_run_finish_cannot_enter_earlier_open():
    rows=[row(1,'2026-10-11T18:00Z'),row(2,'2026-10-12T18:00Z',revenue=110)]
    r=runs(rows);r['r2']['finished_at']=pd.Timestamp('2026-10-13T14:00Z')
    f,_=audit.decision_features(pd.DataFrame(rows),r,audit.schedule(),pd.Timestamp('2026-10-14T12:00Z'))
    assert f.iloc[0].old_id==f.iloc[0].new_id==1
    assert f.iloc[0].revenue_sign==0


def test_future_snapshots_do_not_change_previous_decisions():
    rows=[row(1,'2026-10-11T18:00Z'),row(2,'2026-10-12T18:00Z',revenue=110)]
    cutoff=pd.Timestamp('2026-10-14T12:00Z')
    a,_=audit.decision_features(pd.DataFrame(rows),runs(rows),audit.schedule(),cutoff)
    extra=row(3,'2026-10-14T18:00Z',revenue=1000)
    b,_=audit.decision_features(pd.DataFrame(rows+[extra]),runs(rows+[extra]),audit.schedule(),cutoff)
    pd.testing.assert_frame_equal(a,b)


def test_stale_observations_are_not_carried_forward_forever():
    rows=[row(1,'2026-10-11T18:00Z'),row(2,'2026-10-12T18:00Z',revenue=110)]
    f,_=audit.decision_features(pd.DataFrame(rows),runs(rows),audit.schedule(),pd.Timestamp('2026-10-22T12:00Z'))
    assert f.entry_date.max()<=pd.Timestamp('2026-10-16')


def test_windows_reserve_abstention_and_missing_prices():
    f=pd.DataFrame(dict(symbol=['A']*3,entry_idx=[1,2,4],exit_idx=[3,4,6],return_pct=[np.nan,5,1]))
    assert audit.reserve_windows(f).entry_idx.tolist()==[1,4]


def price_fixture():
    s=audit.schedule()
    f=pd.DataFrame(dict(symbol=['A'],entry_idx=[s[s.day.eq('2026-10-13')].index[0]],
                        entry_date=[pd.Timestamp('2026-10-13')],revenue_sign=[1]))
    prices=[]
    for symbol in ('A','SPY'):
        for i,day in enumerate(pd.to_datetime(['2026-10-13','2026-10-14','2026-10-15'])):
            prices.append(dict(symbol=symbol,date=day,open=100,close=101+i if symbol=='A' else 100,
                high=105,low=95,volume=100,is_filled=0,data_adjustment='split',data_source='alpaca_sip',instrument_id=1))
    return f,pd.DataFrame(prices),s


def test_horizon_maturity_before_price_and_entry_included():
    f,p,s=price_fixture()
    cutoff=pd.Timestamp('2026-10-15T19:59Z')
    r=audit.score_prices(f,p,s,cutoff,3)
    assert not r.iloc[0].mature and pd.isna(r.iloc[0].return_pct)
    r=audit.score_prices(f,p,s,pd.Timestamp('2026-10-15T20:01Z'),3)
    assert r.iloc[0].return_pct==pytest.approx(3)


def test_missing_intermediate_price_is_not_filled():
    f,p,s=price_fixture()
    p=p[~((p.symbol=='A')&(p.date==pd.Timestamp('2026-10-14')))]
    r=audit.score_prices(f,p,s,pd.Timestamp('2026-10-16T21:00Z'),3)
    assert r.iloc[0].price_status=='MISSING_OR_INVALID_BARS' and pd.isna(r.iloc[0].return_pct)


def test_source_identity_or_adjustment_break_reserved():
    f,p,s=price_fixture()
    for key,value in [('data_source','other'),('instrument_id',2),('data_adjustment','raw')]:
        q=p.copy();q.loc[(q.symbol=='A')&(q.date==pd.Timestamp('2026-10-14')),key]=value
        r=audit.score_prices(f,q,s,pd.Timestamp('2026-10-16T21:00Z'),3)
        assert pd.isna(r.iloc[0].return_pct)


def test_equal_date_mean_does_not_count_symbols_as_dates():
    f=pd.DataFrame(dict(symbol=['A','B','C'],entry_date=pd.to_datetime(['2026-10-13','2026-10-13','2026-10-14']),
        revenue_sign=[1,1,-1],return_pct=[10,10,2],spy_return_pct=[0,0,0]))
    result=audit.metric(f,'revenue_sign')
    assert result['dates']==2 and result['n']==3
    assert result['equal_date_signed_mean_pct']==pytest.approx(4)
