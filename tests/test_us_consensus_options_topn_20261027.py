from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import pytest

from service.eodhd.consensus_snapshot import parse
from scripts.research import us_consensus_options_topn_20261027 as audit


def fixture(up=8,down=2,current=1.2,prior=1.,new_time=None):
    old_time=datetime(2026,10,15,21,tzinfo=timezone.utc)
    new_time=new_time or datetime(2026,10,16,21,tzinfo=timezone.utc)
    records=[];runs={}
    for i,(stamp,revenue) in enumerate([(old_time,100.),(new_time,110.)],1):
        run=f'run-{i}'
        item=dict(code='AAA.US',period='0q',date='2026-09-30',
            earningsEstimateAvg=1.2,earningsEstimateLow=1.,earningsEstimateHigh=2.,
            earningsEstimateNumberOfAnalysts=3,revenueEstimateAvg=revenue,
            revenueEstimateLow=90.,revenueEstimateHigh=120.,revenueEstimateNumberOfAnalysts=3,
            epsRevisionsUpLast30days=up,epsRevisionsDownLast30days=down,
            epsTrendCurrent=current,epsTrend30daysAgo=prior)
        row=parse({'trends':[[item]]},['AAA'],stamp,run)['AAA'][0]
        row.update(id=i,ingestion_at=stamp+timedelta(minutes=2));records.append(row)
        runs[run]=dict(status='COMPLETED',finished_at=stamp+timedelta(minutes=1))
    pairs=pd.DataFrame([dict(symbol='AAA',entry_date=pd.Timestamp('2026-10-19'),old_id=1,new_id=2,
        prior_open=pd.Timestamp('2026-10-16T13:30Z'),old_revenue=100.,new_revenue=110.,
        revenue_count_group='UNCHANGED_COUNT')])
    top=pd.DataFrame([dict(symbol='AAA',entry_day='2026-10-19',decision_at=pd.Timestamp('2026-10-19T13:25Z'))])
    return pairs,pd.DataFrame(records),runs,top


def test_valid_same_period_observed_features_are_research_only():
    f=audit.consensus_features(*fixture())
    assert f.iloc[0].revisions30 == pytest.approx(.6)
    assert f.iloc[0].eps30 == pytest.approx(.2)
    assert f.iloc[0].revenue_observed == pytest.approx(.1)
    assert bool(f.iloc[0].consensus_receipts_qualified)
    assert not bool(f.iloc[0].production_qualified)


def test_missing_down_counter_not_imputed_as_zero():
    f=audit.consensus_features(*fixture(down=None))
    assert pd.isna(f.iloc[0].revisions30)


def test_two_explicit_zero_counters_are_neutral_not_missing():
    assert audit.consensus_features(*fixture(up=0,down=0)).iloc[0].revisions30 == 0.


@pytest.mark.parametrize('prior', [0.,None])
def test_zero_or_missing_eps_reference_not_invented(prior):
    assert pd.isna(audit.consensus_features(*fixture(prior=prior)).iloc[0].eps30)


def test_receipt_between_decision_and_open_is_future():
    f=audit.consensus_features(*fixture(new_time=datetime(2026,10,19,13,26,tzinfo=timezone.utc)))
    assert not bool(f.iloc[0].consensus_receipts_qualified)
    assert f[audit.FEATURES].isna().all().all()


def test_changed_contributors_reserve_revenue_but_not_revision_counts():
    pairs,raw,runs,top=fixture();pairs['revenue_count_group']='CHANGED_COUNT'
    f=audit.consensus_features(pairs,raw,runs,top)
    assert pd.isna(f.iloc[0].revenue_observed) and f.iloc[0].revisions30 == pytest.approx(.6)


def test_incomplete_run_or_corrupted_payload_cannot_supply_signal():
    pairs,raw,runs,top=fixture();runs['run-2']['status']='RUNNING'
    assert audit.consensus_features(pairs,raw,runs,top)[audit.FEATURES].isna().all().all()
    pairs,raw,runs,top=fixture();raw.loc[1,'raw_hash']='bad'
    assert audit.consensus_features(pairs,raw,runs,top)[audit.FEATURES].isna().all().all()


def test_ranks_do_not_impute_missing_or_look_at_labels():
    f=pd.DataFrame(dict(entry_day=['d']*3,revisions30=[-1,np.nan,1],eps30=[0,0,0],
                       revenue_observed=[3,2,1],future_label=['LONG','SHORT','LONG']))
    out=audit.ranks(f)
    assert out.revisions30_score.iloc[[0,2]].tolist() == [.25,.75]
    assert pd.isna(out.revisions30_score.iloc[1])
    changed=audit.ranks(f.assign(future_label='OTHER'))
    pd.testing.assert_series_equal(out.revisions30_score,changed.revisions30_score)


def test_auc_uses_common_covered_labels_and_reports_one_date_not_three():
    f=pd.DataFrame(dict(symbol=['A','B','C'],entry_day=['d']*3,status=['LABEL']*3,
        dominant_direction=['SHORT','LONG','LONG'],score=[.2,.8,np.nan]))
    m=audit.metrics(f,['score'])
    assert m['valid_n']==2 and m['valid_dates']==1
    assert m['scores']['score']['mean_daily_auc']==1.


def test_original_top_rank_is_reproduced_before_any_coverage_filter():
    raw=pd.DataFrame(dict(signal_day=pd.to_datetime(['2026-10-16']*2),symbol=['AAA','BBB'],
        batch_id=['b']*2,proba_extreme=[.9,.8]))
    ranked=raw.assign(oracle_rank=[1,2])
    protocol=dict(batch_policy={'2026-10':'b'},minimum_daily_coverage=.95)
    assert audit.verify_ranks(ranked,raw,protocol,['AAA','BBB'])==2
    with pytest.raises(AssertionError):
        audit.verify_ranks(ranked.assign(oracle_rank=[2,1]),raw,protocol,['AAA','BBB'])
