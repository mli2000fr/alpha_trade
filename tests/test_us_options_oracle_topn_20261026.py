import pandas as pd
import pytest
from scripts.research import us_options_oracle_topn_20261026 as s
from scripts.research import us_options_equal_mix_20261026 as b


def fixture_scores(n=100):
    batch=s.BATCHES['2026-09'];symbols=[f'S{i:03}' for i in range(n)]
    frame=pd.DataFrame([dict(signal_day='2026-09-14',symbol=sym,proba_extreme=1-i/(n+1),
        fold_start='2025-12-10',lineage_fold_start='2025-12-10',batch_id=batch,
        model_available_date='2025-12-09',target_name='oracle_path_extreme20',target_horizon=20,
        model_sha256='model',feature_profile_sha256='profile',prediction_created_at='2026-10-15T00:00Z',
        lineage_created_at='2026-10-15T00:00Z') for i,sym in enumerate(symbols)])
    models={batch:dict(profile_sha256='profile',folds={'2025-12-10':dict(model_sha256='model',
        metrics=dict(train_available_max='2025-06-10',val_available_max='2025-12-09'))})}
    cal=pd.DataFrame(dict(day=pd.to_datetime(['2026-09-14','2026-09-15']),
        opened=pd.to_datetime(['2026-09-14T13:30Z','2026-09-15T13:30Z'])))
    return frame,symbols,models,cal


def test_rank_is_original_before_options_and_no_top11_substitute():
    scores,symbols,models,cal=fixture_scores()
    ranked,c=s.rank_oracle(scores.sample(frac=1,random_state=1),symbols,models,cal)
    top=ranked[ranked.oracle_rank.le(10)]
    assert top.symbol.tolist()==symbols[:10]
    assert symbols[10] not in top.symbol.tolist()


def test_topn_is_title_count_not_twenty_percent():
    f,u,m,c=fixture_scores()
    ranked,_=s.rank_oracle(f,u,m,c)
    assert [len(ranked[ranked.oracle_rank.le(n)]) for n in [10,20,50]]==[10,20,50]


def test_model_future_maturity_or_terminal_target_rejected():
    f,u,m,c=fixture_scores();f.loc[0,'target_name']='terminal_h5'
    with pytest.raises(ValueError,match='Incompatible'):s.rank_oracle(f,u,m,c)
    f,u,m,c=fixture_scores();f.loc[0,'model_available_date']='2026-09-15'
    with pytest.raises(ValueError,match='Incompatible'):s.rank_oracle(f,u,m,c)


def test_missing_underlying_universe_scores_not_hidden_by_options_filter():
    f,u,m,c=fixture_scores()
    ranked,coverage=s.rank_oracle(f.iloc[:50],u,m,c)
    assert ranked.empty and not coverage.qualified.any()


def test_strict_creation_is_not_backdated_to_fold_availability():
    f,u,m,c=fixture_scores();ranked,_=s.rank_oracle(f,u,m,c)
    assert not ranked.physically_observed_before_decision.any()
    f['prediction_created_at']='2026-09-15T12:00Z';f['lineage_created_at']='2026-09-15T12:00Z'
    ranked,_=s.rank_oracle(f,u,m,c)
    assert ranked.physically_observed_before_decision.all()


def test_duplicate_and_nan_scores_fail_closed():
    f,u,m,c=fixture_scores()
    with pytest.raises(ValueError,match='Duplicate'):s.rank_oracle(pd.concat([f,f.iloc[:1]]),u,m,c)
    f.loc[0,'proba_extreme']=float('nan')
    with pytest.raises(ValueError,match='Bad Oracle'):s.rank_oracle(f,u,m,c)


def test_tied_oracle_score_has_symbol_tiebreak():
    f,u,m,c=fixture_scores();f.proba_extreme=.5
    ranked,_=s.rank_oracle(f.iloc[::-1],u,m,c)
    assert ranked.symbol.tolist()==u


def test_conditional_ranks_exclude_top11_but_include_immature_top10():
    f,u,m,c=fixture_scores();ranked,_=s.rank_oracle(f,u,m,c);top=ranked[ranked.oracle_rank.le(10)]
    features=pd.DataFrame([dict(entry_day='2026-09-15',symbol=sym,
        volume_call_minus_put_log=float(i),oi_call_minus_put_log=float(-i),
        entry_at=pd.Timestamp('2026-09-15T13:30Z'),decision_at=pd.Timestamp('2026-09-15T13:25Z'),
        feature_available_at=pd.Timestamp('2026-09-14T22:00Z')) for i,sym in enumerate(u[:11])])
    labels=pd.DataFrame([dict(entry_day='2026-09-15',symbol=sym,horizon=h,status='NOT_MATURE',
        dominant_direction=None,volume_score=999,oi_score=999,combined_score=999) for sym in u[:11] for h in [5,10,20]])
    scores,panel=s.cohort(top,features,labels)
    assert len(scores)==10 and len(panel)==30
    assert scores.symbol.tolist()==u[:10]
    assert scores.volume_score.tolist()==pytest.approx([(.5+i)/10 for i in range(10)])
    assert panel.combined_score.tolist()==pytest.approx([.5]*30)
