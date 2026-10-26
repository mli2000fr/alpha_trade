import numpy as np
import pandas as pd
import pytest
from scripts.research import fr_p0_p1_equal_mix_20261026 as s


def candidates():
    return pd.DataFrame([dict(symbol=name,entry_day='2026-10-12',momentum_5=i,momentum_20=3-i,
        amf_common_holder_change_score=i,feature_available_at='2026-10-09T20:00Z',entry_at='2026-10-12T07:00Z',
        horizon=5,status='DIAGNOSTIC_LABEL',dominant_direction='LONG' if i%2 else 'SHORT')
        for i,name in enumerate(['A','B','C','D'])])


def test_equal_weights_and_ties_are_exact_neutral():
    f=candidates();f.loc[:,'momentum_5']=0;f.loc[:,'momentum_20']=0
    scores,_=s.score_asof_candidates(f)
    assert scores.price_score.eq(.5).all()
    np.testing.assert_allclose(scores.combined_score,.5*scores.price_score+.5*scores.amf_score)
    assert s.centered_rank(pd.Series([0,0,0])).eq(.5).all()


def test_labels_maturity_and_future_excursions_cannot_change_scores():
    f=candidates();old,_=s.score_asof_candidates(f)
    f['status']='NOT_MATURE';f['dominant_direction']='SHORT';f['long_lower_pct']=99999.
    new,_=s.score_asof_candidates(f)
    pd.testing.assert_frame_equal(old,new)


def test_incomplete_candidates_not_zero_filled_and_future_source_refused():
    f=candidates();f.loc[0,'momentum_20']=np.nan
    scores,coverage=s.score_asof_candidates(f)
    assert len(scores)==3 and coverage.complete_symbols.iloc[0]==3
    f.loc[1,'feature_available_at']='2026-10-12T08:00Z'
    with pytest.raises(ValueError,match='Future'):s.score_asof_candidates(f)


def test_same_feature_cohort_is_scored_before_any_outcome_gate():
    f=candidates();f.loc[3,'status']='NOT_MATURE'
    scores,_=s.score_asof_candidates(f)
    assert len(scores)==4 and scores.amf_score.max()==.875


def test_identical_features_across_horizons_required():
    f=candidates();other=f.copy();other.horizon=10
    assert len(s.score_asof_candidates(pd.concat([f,other]))[0])==4
    other.loc[0,'momentum_5']=9
    with pytest.raises(ValueError,match='Horizon'):s.score_asof_candidates(pd.concat([f,other]))


def test_constant_amf_keeps_same_dates_and_counts_as_chance():
    f=candidates();f['amf_common_holder_change_score']=0
    scored,_=s.score_asof_candidates(f)
    g=f.merge(scored[s.KEY+s.SCORES],on=s.KEY)
    m=s.metrics(g)
    assert m['scores']['amf_score']['mean_daily_auc']==.5
    assert len(m['paired'])==1 and all(v['daily'][0]['n']==4 for v in m['scores'].values())


def test_calendar_nonoverlap_not_calendar_days():
    days=['2026-10-12','2026-10-13','2026-10-14','2026-10-15','2026-10-16','2026-10-19']
    assert s.nonoverlap_dates(days,5,days)==['2026-10-12','2026-10-19']


def test_h20_empty_remains_unavailable_and_no_duplicate_outcome():
    f=candidates();f.horizon=20;f.status='NOT_MATURE'
    scored,_=s.score_asof_candidates(f)
    results,_=s.evaluate(f,scored,['2026-10-12'])
    assert results['20']['status']=='NO_MATURE_H20_LABELS'
    with pytest.raises(ValueError,match='Duplicate'):s.evaluate(pd.concat([f,f]),scored,['2026-10-12'])
