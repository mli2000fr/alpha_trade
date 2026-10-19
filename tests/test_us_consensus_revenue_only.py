import copy
from datetime import date
import json
import pandas as pd
import pytest
from scripts.research import us_consensus_revenue_only as s


def row():
    raw=dict(code='DOCN.US',date='2026-09-30',period='0q',revenueEstimateAvg='100',revenueEstimateLow='90',revenueEstimateHigh='110',revenueEstimateNumberOfAnalysts='5',earningsEstimateAvg='bad EPS irrelevant')
    r=dict(provider='eodhd',symbol='DOCN',fiscal_period_end=date(2026,9,30),horizon_raw='0q',raw_payload_json=json.dumps(raw),raw_hash=s.payload_hash(raw),
        revenue_avg=100.,revenue_low=90.,revenue_high=110.,revenue_analyst_count=5,run_id='R',observed_at='2026-10-15 20:15:00',available_at='2026-10-15 20:15:00',ingestion_at='2026-10-15 20:15:01')
    runs={'R':dict(status='COMPLETED',finished_at='2026-10-15 20:20:00')}
    return r,runs


def test_eps_invalid_or_changed_does_not_affect_revenue_check():
    r,runs=row();assert s.check_row(r,runs)['reasons']==[]
    assert s.check_row(r,runs)['available_at']==pd.Timestamp('2026-10-15T20:20Z')


@pytest.mark.parametrize('field,value',[('provider','other'),('symbol','FUN'),('fiscal_period_end',date(2026,12,31)),('horizon_raw','+1q')])
def test_no_bridge_across_fiscal_provider_symbol_or_horizon(field,value):
    a,_=row();b=copy.deepcopy(a);b[field]=value
    assert s.revision(a,b)['pattern']=='ABSTAIN'
    assert 'NO_PERIOD_OR_HORIZON_BRIDGE' in s.revision(a,b)['reasons']


@pytest.mark.parametrize('new,side',[(101,'LONG'),(99,'SHORT'),(100,'ABSTAIN'),(None,'ABSTAIN'),(0,'ABSTAIN')])
def test_revenue_sign_no_eps_requirement(new,side):
    a,_=row();b=dict(a,revenue_avg=new)
    assert s.revision(a,b)['pattern']==side


def test_changed_counts_separate_not_pooled_as_same_analysts():
    a,_=row();b=dict(a,revenue_avg=110,revenue_analyst_count=6)
    r=s.revision(a,b);assert r['pattern']=='LONG' and r['count_group']=='CHANGED_COUNT'
    assert s.revision(a,dict(b,revenue_analyst_count=2))['count_group']=='MISSING_OR_LT3'


def test_support_does_not_assume_every_us_stock_usd_or_all_periods_current():
    assert s.known_metadata('FUN','2026-09-30')['currency']=='USD'
    assert not s.known_metadata('FUN','2026-09-30')['actual_fiscal_end_known']
    assert not s.known_metadata('FMC','2026-09-30')['currency_supported']
    assert not s.known_metadata('DOCN','2025-09-30')['period_supported']


@pytest.mark.parametrize('mode',['raw_hash','normal_value','early_available','run_failed','bad_revenue_range'])
def test_revenue_source_errors_are_not_ignored(mode):
    r,runs=row()
    if mode=='raw_hash':r['raw_hash']='0'*64
    if mode=='normal_value':r['revenue_avg']=99
    if mode=='early_available':r['available_at']='2026-10-15 20:00:00'
    if mode=='run_failed':runs['R']['status']='FAILED'
    if mode=='bad_revenue_range':r['revenue_high']=50
    assert s.check_row(r,runs)['reasons']


def scores():
    return pd.DataFrame([dict(symbol=f'S{i}',prediction_date=pd.Timestamp('2026-10-16'),created_at=pd.Timestamp('2026-10-17T20:00Z'),
        model_available_date=pd.Timestamp('2026-01-01'),target_name='oracle_path_extreme20',target_horizon=20,proba_extreme=i/20) for i in range(20)])


def test_oct16_scores_not_reused_for_prior_or_next_session_membership():
    f=scores()
    assert s.top10_for_entry(f,pd.Timestamp('2026-10-15'),pd.Timestamp('2026-10-16T13:30Z')).empty
    assert s.top10_for_entry(f,pd.Timestamp('2026-10-19'),pd.Timestamp('2026-10-20T13:30Z')).empty
    assert len(s.top10_for_entry(f,pd.Timestamp('2026-10-16'),pd.Timestamp('2026-10-19T13:30Z')))==10


def test_scores_created_after_entry_cannot_select_top10():
    f=scores()
    assert s.top10_for_entry(f,pd.Timestamp('2026-10-16'),pd.Timestamp('2026-10-17T19:00Z')).empty


def test_completed_run_timestamp_controls_full_availability_not_only_item_time():
    r,runs=row();runs['R']['finished_at']='2026-10-16 15:00:00'
    assert s.check_row(r,runs)['available_at']==pd.Timestamp('2026-10-16T15:00Z')
