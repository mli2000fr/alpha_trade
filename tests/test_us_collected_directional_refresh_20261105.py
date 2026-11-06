import numpy as np
import pandas as pd
import pytest

from scripts.research.us_collected_directional_metrics_20261105 import consensus_for_candidate,score_cohort,signal_metrics


def consensus_frame():
    return pd.DataFrame([dict(id=i,symbol='TEST',raw_ok=True,horizon_raw='0q',
        fiscal_period_end=pd.Timestamp(period),known_at=pd.Timestamp(stamp),
        eps_range_ok=True,revenue_range_ok=True,eps_analyst_count=5,revenue_analyst_count=5,
        eps_avg=eps,revenue_avg=revenue,eps_current=eps,eps_30d_ago=1.,
        revisions_up_30d=3,revisions_down_30d=1)
        for i,period,stamp,eps,revenue in [
            (1,'2026-09-30','2026-10-14T20:00Z',1.,100.),
            (2,'2026-09-30','2026-10-15T20:00Z',1.2,120.),
            (3,'2026-09-30','2026-10-16T14:00Z',2.,200.)]])


def test_future_consensus_receipt_excluded_and_same_period_changes():
    f=consensus_frame();day=pd.Timestamp('2026-10-15');cutoff=pd.Timestamp('2026-10-16T13:25Z')
    r=consensus_for_candidate(f,day,cutoff,cutoff-pd.Timedelta(days=1))
    assert r['consensus_id']==2 and r['consensus_old_id']==1
    assert r['revisions30']==.5 and r['eps30']==pytest.approx(.2)
    assert r['revenue_change']==pytest.approx(.2)
    f.loc[f.id.eq(1),'fiscal_period_end']=pd.Timestamp('2026-06-30')
    assert np.isnan(consensus_for_candidate(f,day,cutoff,cutoff-pd.Timedelta(days=1))['revenue_change'])


def test_contributor_change_and_stale_consensus_do_not_create_revision():
    f=consensus_frame();f.loc[f.id.eq(1),'revenue_analyst_count']=4
    r=consensus_for_candidate(f,pd.Timestamp('2026-10-15'),pd.Timestamp('2026-10-16T13:25Z'),pd.Timestamp('2026-10-15T13:25Z'))
    assert np.isnan(r['revenue_change'])
    assert consensus_for_candidate(f,pd.Timestamp('2026-10-25'),pd.Timestamp('2026-10-26T13:25Z'),pd.Timestamp('2026-10-23T13:25Z'))['consensus_id'] is None


def test_combination_never_imputes_missing_options_or_consensus():
    cols=['revisions30','eps30','revenue_change','eps_change','sentiment1','sentiment3']
    f=pd.DataFrame([dict(signal_day=pd.Timestamp('2026-10-15'),symbol=str(i),volume_feature=float(i),
        oi_feature=float(i) if i<4 else np.nan,**{c:float(i) if i<3 else np.nan for c in cols}) for i in range(5)])
    out=score_cohort(f)
    assert out.options_score.iloc[:4].notna().all() and pd.isna(out.options_score.iloc[4])
    assert out.options_score.iloc[0]==pytest.approx(.125)
    assert pd.isna(out.options_consensus_score.iloc[3])


def test_top_half_selection_does_not_use_future_label_availability():
    day=pd.Timestamp('2026-10-15')
    f=pd.DataFrame(dict(signal_day=[day]*4,symbol=list('ABCD'),oracle_rank=[1,2,3,4],
        score=[.9,.8,.7,.6],status=['NOT_MATURE','LABEL','LABEL','LABEL'],
        dominant_direction=[None,'SHORT','LONG','LONG']))
    cal=pd.DataFrame(dict(day=pd.date_range(day,periods=10)))
    r=signal_metrics(f,'score',cal,5)
    # Buy candidates are A/B, not B/C after silently removing unobserved A.
    assert r['selected_long_share']==0 and r['top_half'][0]['selected_n']==1
    assert r['matched_baseline_long_share']==pytest.approx(2/3)
