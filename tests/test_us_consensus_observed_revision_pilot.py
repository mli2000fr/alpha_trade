from datetime import date
import json
import numpy as np
import pandas as pd
import pytest

from scripts.research import us_consensus_observed_revision_pilot as study
from service.eodhd.consensus_snapshot import FIELDS


def rows():
    out = []
    for i, value in enumerate([1., 1.1]):
        stamp = pd.Timestamp('2026-10-11T13:00Z')+pd.Timedelta(days=i)
        raw = {native: None for native in FIELDS.values()}
        raw.update(code='AAPL.US', date='2026-12-31', period='0q', earningsEstimateAvg=str(value),
            earningsEstimateLow='.5', earningsEstimateHigh='2', earningsEstimateNumberOfAnalysts='5',
            revenueEstimateAvg=str(value*1000), revenueEstimateLow='500', revenueEstimateHigh='2000',
            revenueEstimateNumberOfAnalysts='6')
        r = dict(id=i+1,provider='eodhd',symbol='AAPL',snapshot_date=stamp.date(),fiscal_period_end=date(2026,12,31),horizon_raw='0q',
            observed_at=stamp,available_at=stamp,ingestion_at=stamp+pd.Timedelta(seconds=2),run_id='run'+str(i),
            raw_hash=study.payload_hash(raw),raw_payload_json=json.dumps(raw),currency='USD',
            fiscal_identity_qualified=True,units_qualified=True,historical_pit_qualified=False,qualification_status='PROSPECTIVE_QUALIFIED')
        r.update({key: None if raw.get(native) is None else float(raw[native]) for key,native in FIELDS.items()})
        out.append(r)
    runs = {r['run_id']:dict(status='COMPLETED',finished_at=r['observed_at']+pd.Timedelta(minutes=15)) for r in out}
    return out, runs


def test_actual_pairs_qualified_prospectively_without_backdating():
    r, runs = rows(); pairs, checks = study.pair_rows(pd.DataFrame(r), runs)
    p = pairs.iloc[0]
    assert p.direction == 'LONG' and p.qualified_before_receipt_check
    assert p.eps_delta == pytest.approx(.1) and p.eps_change_ratio == pytest.approx(.1)
    assert p.available_at == runs['run1']['finished_at']
    assert p.old_snapshot_date == date(2026,10,11)
    # False historical_PIT is correct for a received current snapshot, not a rejection by itself.
    assert not r[0]['historical_pit_qualified']


@pytest.mark.parametrize('field,reason', [
    ('units_qualified','UNITS_UNQUALIFIED'),('fiscal_identity_qualified','FISCAL_IDENTITY_UNQUALIFIED')])
def test_false_qualifications_abstain_even_when_both_values_rise(field, reason):
    r, runs = rows(); r[1][field] = False
    p = study.pair_rows(pd.DataFrame(r), runs)[0].iloc[0]
    assert p.numeric_pattern == 'LONG' and p.direction == 'ABSTAIN'
    assert reason in p.qualification_reasons


@pytest.mark.parametrize('mode,reason', [
    ('currency_missing','CURRENCY_UNKNOWN'),('currency_changed','CURRENCY_CHANGED'),
    ('research_only','UPSTREAM_RESEARCH_ONLY'),('run_failed','RUN_NOT_COMPLETED'),
    ('low_analysts','ANALYST_COUNTS_MISSING_OR_LT3'),('bad_raw','RAW_HASH_MISMATCH'),
    ('different_code','RAW_IDENTITY_MISMATCH'),('normalized_changed','NORMALIZED_VALUE_MISMATCH:eps_avg'),
    ('long_gap','SNAPSHOT_GAP_OVER_72H_OR_NONCAUSAL'),('backdated','INVALID_RECEIPT_TIMESTAMPS')])
def test_bad_evidence_never_becomes_direction(mode, reason):
    r, runs = rows()
    if mode=='currency_missing': r[1]['currency']=None
    if mode=='currency_changed': r[1]['currency']='EUR'
    if mode=='research_only': r[1]['qualification_status']='RESEARCH_ONLY'
    if mode=='run_failed': runs['run1']['status']='FAILED'
    if mode=='low_analysts': r[1]['eps_analyst_count']=2
    if mode=='bad_raw': r[1]['raw_hash']='0'*64
    if mode=='normalized_changed': r[1]['eps_avg']=8
    if mode=='different_code':
        raw=json.loads(r[1]['raw_payload_json']); raw['code']='MSFT.US'
        r[1]['raw_payload_json']=json.dumps(raw); r[1]['raw_hash']=study.payload_hash(raw)
    if mode=='long_gap':
        for k in ['observed_at','available_at','ingestion_at']: r[1][k]+=pd.Timedelta(days=4)
        r[1]['snapshot_date']=r[1]['observed_at'].date(); runs['run1']['finished_at']+=pd.Timedelta(days=4)
    if mode=='backdated': r[1]['available_at']-=pd.Timedelta(seconds=1)
    p=study.pair_rows(pd.DataFrame(r), runs)[0].iloc[0]
    assert p.direction=='ABSTAIN' and reason in p.qualification_reasons


@pytest.mark.parametrize('field,value', [('fiscal_period_end',date(2027,3,31)),('horizon_raw','+1q'),('symbol','MSFT'),('provider','other')])
def test_no_bridge_across_identity_or_horizon(field,value):
    r,runs=rows();r[1][field]=value
    assert study.pair_rows(pd.DataFrame(r),runs)[0].empty


def test_duplicate_snapshot_rejected_not_latest_wins():
    r,runs=rows();r.append(r[1].copy())
    with pytest.raises(ValueError): study.pair_rows(pd.DataFrame(r),runs)


def test_old_lookback_value_never_treated_as_observed_old_snapshot():
    r,runs=rows();r[1]['eps_7d_ago']=99
    # Raw alignment is required too; this injected inconsistency fails rather than producing a new date.
    p=study.pair_rows(pd.DataFrame(r),runs)[0].iloc[0]
    assert p.old_id==1 and p.eps_delta==pytest.approx(.1)
    assert len(study.pair_rows(pd.DataFrame([r[1]]),runs)[0])==0


def test_zero_denominator_no_infinite_percent():
    assert study.change(0,1)==(1.,None)
    assert study.change(None,1)==(None,None)
    assert study.change(np.nan,1)==(None,None)


def test_known_explicit_gap_is_not_silently_filled():
    r,runs=rows();r[1]['observed_at']+=pd.Timedelta(days=5)
    p=study.pair_rows(pd.DataFrame(r),runs)[0].iloc[0]
    assert not p.technical_pair and p.direction=='ABSTAIN'


def test_missing_down7_not_imputed_to_zero_or_used_as_net_signal():
    r,runs=rows();assert r[0]['revisions_down_7d'] is None
    p=study.pair_rows(pd.DataFrame(r),runs)[0].iloc[0]
    assert p.eps_delta==pytest.approx(.1) and 'revisions_down_7d' not in p.index


def test_query_guard_does_not_accept_dml():
    with pytest.raises(ValueError): study.inventory.query(None,'DELETE FROM anything')
