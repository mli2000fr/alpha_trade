import copy
from datetime import date
import json

import pandas as pd
import pytest

from scripts.research import us_consensus_revenue_top20 as s


def scores(n=1743):
    return pd.DataFrame([dict(symbol=f'S{i:04}',prediction_date=pd.Timestamp('2026-10-16'),
        created_at='2026-10-17T12:00Z',model_available_date='2026-10-01',
        batch_id=s.BATCH,target_name='oracle_path_extreme20',target_horizon=20,
        proba_extreme=i/n,model_sha256='a'*64,feature_profile_sha256='b'*64) for i in range(n)])


def rank(f,prior='2026-10-16',cutoff='2026-10-19T13:30Z',universe=None):
    return s.rank_cohort(f,pd.Timestamp(prior),pd.Timestamp(cutoff),set(f.symbol) if universe is None else universe)


@pytest.mark.parametrize('n,expected',[(1743,349),(100,20),(101,21),(20,4)])
def test_fraction_rounding_fixed_before_consensus_filter(n,expected):
    f=scores(n);cohort,denominator=rank(f)
    assert denominator==n and len(cohort)==expected
    assert cohort.oracle_rank.tolist()==list(range(1,expected+1))
    assert cohort.symbol.tolist()==f.sort_values(['proba_extreme','symbol'],ascending=[False,True]).head(expected).symbol.tolist()


def test_top10_and_remaining_disjoint_and_no_replacement():
    cohort,n=rank(scores(100))
    assert len(cohort[cohort.arm.eq('TOP10')])==10
    assert len(cohort[cohort.arm.eq('RANK11_TO_TOP20_PERCENT')])==10
    assert not set(cohort[cohort.arm.eq('TOP10')].symbol)&set(cohort[cohort.arm.ne('TOP10')].symbol)


@pytest.mark.parametrize('prior',['2026-10-15','2026-10-19'])
def test_sole_cohort_not_reused_for_other_dates(prior):
    cohort,n=rank(scores(),prior=prior)
    assert cohort.empty and n==0


def test_late_scores_universe_and_ties_are_causal():
    f=scores(100);f['proba_extreme']=.5
    f.loc[0,'created_at']='2026-10-19T13:30Z'
    cohort,n=rank(f,universe=set(f.symbol)-{'S0001'})
    assert n==98 and len(cohort)==20
    assert cohort.symbol.tolist()==[f'S{i:04}' for i in range(2,22)]


@pytest.mark.parametrize('field,value', [('batch_id','wrong'),('target_name','oracle_extreme20'),
    ('target_horizon',10),('proba_extreme',float('nan')),('proba_extreme',1.1),
    ('model_available_date','2026-10-17'),('model_sha256','different')])
def test_wrong_model_target_lineage_or_score_rejected(field,value):
    f=scores(100);f.loc[0,field]=value
    with pytest.raises(ValueError):
        rank(f)


def test_duplicate_symbol_rejected():
    f=scores(100);f.loc[0,'symbol']=f.loc[1,'symbol']
    with pytest.raises(ValueError,match='Duplicate'):
        rank(f)


def fixture(symbol='DOCN',new_count=5,new_revenue=110):
    records=[];runs={};receipts=[]
    for identifier,(snapshot,revenue,count) in enumerate([('2026-10-15',100,5),('2026-10-18',new_revenue,new_count)],1):
        raw=dict(code=symbol+'.US',date='2026-09-30',period='0q',revenueEstimateAvg=revenue,
            revenueEstimateLow=90,revenueEstimateHigh=120,revenueEstimateNumberOfAnalysts=count,
            earningsEstimateAvg='not used')
        observed=snapshot+' 20:00:00';run='r'+str(identifier)
        item=dict(id=identifier,provider='eodhd',symbol=symbol,fiscal_period_end=date(2026,9,30),horizon_raw='0q',
            revenue_avg=revenue,revenue_low=90,revenue_high=120,revenue_analyst_count=count,
            raw_payload_json=json.dumps(raw),raw_hash=s.payload_hash(raw),run_id=run,
            observed_at=observed,available_at=observed,ingestion_at=snapshot+' 20:00:01')
        records.append(item);runs[run]=dict(status='COMPLETED',finished_at=snapshot+' 20:01:00')
        body={'trends':[[raw]]}
        receipts.append(dict(id=identifier,run_id=run,observed_at=observed,available_at=observed,http_status=200,
            payload_hash=s.payload_hash(body),payload_json=json.dumps(body)))
    frame=pd.DataFrame([dict(symbol=symbol,pair_present=True,old_id=1,new_id=2,
        fiscal_anchor='2026-09-30',prior_entry_open_utc=pd.Timestamp('2026-10-16T13:30Z'),
        entry_open_utc=pd.Timestamp('2026-10-19T13:30Z'),technical_pair=True)])
    return frame,pd.DataFrame(records),runs,receipts


def test_revenue_only_existing_support_and_no_direction_invention():
    args=fixture();q,bad=s.qualify(*args)
    assert not bad and q.iloc[0].qualified_pattern=='LONG' and q.iloc[0].envelope_verified
    assert not q.iloc[0].live_admission and not q.iloc[0].definition_known_before_entry
    q,_=s.qualify(*fixture(new_revenue=90))
    assert q.iloc[0].qualified_pattern=='SHORT'
    q,_=s.qualify(*fixture(new_revenue=100))
    assert q.iloc[0].qualified_pattern=='ABSTAIN'


def test_unknown_currency_or_period_and_changed_counts_reserved():
    q,_=s.qualify(*fixture(symbol='CCOI'))
    assert q.iloc[0].numeric_pattern=='LONG' and q.iloc[0].qualified_pattern=='ABSTAIN'
    assert 'CURRENCY_NOT_VERIFIED' in q.iloc[0].reservation_reasons
    q,_=s.qualify(*fixture(new_count=6))
    assert q.iloc[0].count_group=='CHANGED_COUNT' and q.iloc[0].qualified_pattern=='ABSTAIN'


def test_missing_pair_kept_in_cohort_as_abstention():
    frame,source,runs,raw=fixture()
    frame.loc[0,'pair_present']=False
    q,_=s.qualify(frame,source,runs,raw)
    assert len(q)==1 and q.iloc[0].qualified_pattern=='ABSTAIN'
    assert 'MISSING_COMPARABLE_0Q_PAIR' in q.iloc[0].reservation_reasons


@pytest.mark.parametrize('mode',['tamper','after_cutoff','missing','late_run'])
def test_envelopes_and_receipts_must_be_real_and_before_decision(mode):
    frame,source,runs,raw=fixture()
    if mode=='tamper':
        raw[0]['payload_hash']='invalid'
    elif mode=='after_cutoff':
        raw[1]['available_at']='2026-10-19 14:00:00'
    elif mode=='missing':
        raw=[]
    else:
        runs['r2']['finished_at']='2026-10-19 14:00:00'
    q,bad=s.qualify(frame,source,runs,raw)
    assert q.iloc[0].qualified_pattern=='ABSTAIN'
    assert bool(bad)==(mode=='tamper')
