from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_weak_topn_2020_2024_experiments as exp


def panel(days=2):
    return pd.DataFrame([dict(date=day,symbol=f'S{rank}',oracle_rank=rank,
        oracle_decile=10 if rank%2 else 1,score=float(rank),target=float(rank%2))
        for day in pd.date_range('2020-01-01',periods=days) for rank in range(1,51)])


def test_top_selection_happens_before_outcome_missingness():
    source=panel();source.loc[source.oracle_rank.le(4),'oracle_decile']=np.nan
    twenty=exp.select_top(source,20)
    assert len(twenty)==40 and set(twenty.oracle_rank)==set(range(1,21))
    assert twenty.loc[twenty.oracle_rank.le(4),'oracle_decile'].isna().all()


def test_missing_original_rank_cannot_be_replaced_by_rank_21():
    source=panel();source=source.loc[~source.oracle_rank.eq(3)]
    with pytest.raises(ValueError,match='Incomplete'):exp.select_top(source,20)


@pytest.mark.parametrize('change',['symbol','rank'])
def test_duplicate_candidates_or_ranks_fail(change):
    source=panel()
    key='symbol' if change=='symbol' else 'oracle_rank'
    source.loc[1,key]=source.loc[0,key]
    with pytest.raises(ValueError,match='Duplicate'):exp.select_top(source,20)


def test_task_labels_do_not_turn_unknowns_into_negatives():
    source=pd.DataFrame(dict(oracle_decile=[1,5,10,np.nan]))
    assert exp.task_target(source,'D1_VS_REST').iloc[:3].tolist()==[1.,0.,0.]
    assert np.isnan(exp.task_target(source,'D1_VS_REST').iloc[3])
    tails=exp.task_target(source,'D1_VS_D10')
    assert tails.iloc[[0,2]].tolist()==[0.,1.] and tails.iloc[[1,3]].isna().all()
    with pytest.raises(ValueError):exp.task_target(pd.DataFrame(dict(oracle_decile=[11])),'D1_VS_REST')


def test_training_and_validation_are_purged_by_actual_label_availability():
    source=pd.DataFrame(dict(date=pd.bdate_range('2018-01-01','2020-12-31')))
    source['symbol']='A';source['target']=np.arange(len(source))%2
    source['available']=source.date+pd.Timedelta(days=25)
    train,valid,mature,proof=exp.causal_split(source,2020,'target','available')
    assert (pd.to_datetime(train.available)<valid.date.min()).all()
    assert (pd.to_datetime(valid.available)<pd.Timestamp('2020-01-01')).all()
    assert (pd.to_datetime(mature.available)<pd.Timestamp('2020-01-01')).all()
    assert proof['validation_dates']==63 and train.date.nunique()>=252


def test_future_label_changes_cannot_change_training_split():
    source=pd.DataFrame(dict(date=pd.bdate_range('2017-01-01','2020-12-31')))
    source['symbol']='A';source['target']=np.arange(len(source))%2
    source['available']=source.date+pd.Timedelta(days=30)
    before=exp.causal_split(source,2020,'target','available')
    source.loc[source.available.ge('2020-01-01'),'target']=1-source.target
    after=exp.causal_split(source,2020,'target','available')
    for a,b in zip(before[:3],after[:3]):pd.testing.assert_frame_equal(a,b)


def test_insufficient_warmup_is_explicit():
    source=pd.DataFrame(dict(date=pd.bdate_range('2019-01-01','2019-12-31')))
    source['symbol']='A';source['target']=np.arange(len(source))%2;source['available']=source.date
    with pytest.raises(ValueError,match='Insufficient'):exp.causal_split(source,2020,'target','available')


def test_daily_auc_reserves_dates_without_two_of_each_class():
    f=panel(1).head(20)
    f['target']=0.;f.loc[f.index[0],'target']=1.
    result=exp.metrics(f,probability=False)
    assert result['auc_daily_mean'] is None and result['auc_daily_dates']==0
    assert result['auc_pooled_descriptive'] is not None


def test_head_selection_is_frozen_before_label_filtering():
    f=panel(1).head(20)
    f['score']=np.arange(20)/20
    f.loc[f.index[-2:],'target']=np.nan
    report=exp.metrics(f)
    assert report['selected_original_rows']==2 and report['selected_known_rows']==0
    assert report['selected_target_rate'] is None and report['target_coverage']==.9


def test_constant_probability_has_auc_half_but_not_a_trade_win_rate():
    f=panel(1).head(20);f['score']=.5
    result=exp.metrics(f,prior=.5)
    assert result['auc_daily_mean']==.5 and result['auc_pooled_descriptive']==.5
    assert result['brier']==.25 and result['brier_train_prior']==.25
    assert result['selected_rate_is_not_portfolio_win_rate']


def test_h_spaced_dates_are_anchored_to_shared_calendar_not_label_survivors():
    f=panel(5).head(250);f['score']=f.target
    f.loc[f.date.eq(pd.Timestamp('2020-01-01')),'target']=np.nan
    result=exp.metrics(f,probability=True,horizon=2,calendar=pd.date_range('2020-01-01',periods=5))
    assert result['auc_h_spaced_dates']==2


def test_probability_out_of_range_is_rejected():
    with pytest.raises(ValueError,match='Invalid probability'):exp.metrics(panel(1))


def test_reconstructed_e3_is_never_routed_to_terminal_h3_or_pmath_tasks():
    source=pd.DataFrame(dict(e3_long_target=[1.,0.,np.nan],terminal_return_h3=[-.2,.1,.2]))
    e3,tasks=exp.attach_method_targets(source,'E3')
    assert tasks==[('LONG_NET_POSITIVE','available_e3',20)]
    assert e3.target.iloc[:2].tolist()==[1.,0.] and np.isnan(e3.target.iloc[2])
    e2,tasks=exp.attach_method_targets(source,'E2')
    assert tasks==[('LONG_H3','available_h3',3)] and e2.target.tolist()==[0.,1.,1.]
    with pytest.raises(ValueError):exp.attach_method_targets(source,'E3_CAUSAL_CORRECTED')
