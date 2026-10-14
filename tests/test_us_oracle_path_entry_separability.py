import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_path_entry_separability import (PERIODS,RULES,TARGET,auc,
    causal_fold_contract,daily_aucs,evaluable,frozen_probe,label_input,maxT_block_pvalues,period_dates,tier)
from scripts.research.us_oracle_path_economic_replay import freeze_top


def test_auc_ties_and_single_class():
    assert auc([0,1,0,1],[2,2,2,2])==.5
    assert auc([0,0,1,1],[1,2,3,4])==1.
    assert auc([0,0,0],[1,2,3]) is None
    assert auc([0,1,0,1],[1,4,np.nan,3])==1.


def test_common_date_macro_does_not_become_cross_sectional_signal():
    frame=pd.DataFrame(dict(date=pd.to_datetime(['2020-01-02']*6+['2020-01-03']*6),
        long_tp_before_sl=[0,0,1,1,1,1,0,0,0,0,1,1],context=[10]*6+[1]*6))
    assert auc(frame[TARGET],frame.context)>.5
    assert daily_aucs(frame,['context']).context.eq(.5).all()


def test_sparse_days_report_no_conditional_auc():
    frame=pd.DataFrame(dict(date=pd.to_datetime(['2020-01-02']*4),long_tp_before_sl=[1,0,0,0],x=[1,2,3,4]))
    assert daily_aucs(frame,['x']).x.isna().all()


def test_valid_daily_auc_uses_feature_finite_pairs():
    frame=pd.DataFrame(dict(date=pd.to_datetime(['2020-01-02']*5),long_tp_before_sl=[0,0,1,1,1],x=[1,2,3,4,np.nan]))
    assert daily_aucs(frame,['x']).x.iloc[0]==1.


def test_frozen_top_is_never_replaced_on_future_unknown():
    frame=pd.DataFrame(dict(date=pd.to_datetime(['2020-01-02']*3),symbol=['A','B','C'],score_lightgbm=[.9,.8,.7],
        future_qualified=[False,True,True]))
    selected=freeze_top(frame,2)
    assert selected.symbol.tolist()==['A','B']
    assert 'future_qualified' not in selected


def test_discovery_and_validation_labels_purged_at_boundaries():
    frame=pd.DataFrame(dict(date=pd.to_datetime(['2021-12-01','2021-12-02','2022-12-01','2022-12-02','2024-12-31']),
        selected=True,path_qualified=True,long_tp_before_sl=[1,0,1,0,0],
        oracle_available_date=pd.to_datetime(['2021-12-31','2022-01-01','2022-12-31','2023-01-01','2025-02-01'])))
    frame['period']=period_dates(frame.date)
    assert evaluable(frame).tolist()==[True,False,True,False,True]


def test_missing_or_ambiguous_label_never_assumed_negative():
    frame=pd.DataFrame(dict(selected=[True,True,False],path_qualified=[True,False,True],
        long_tp_before_sl=[np.nan,0,1],oracle_available_date=pd.to_datetime(['2020-02-03']*3),period=PERIODS[0]))
    assert not evaluable(frame).any()


@pytest.mark.parametrize('field', ['train_available_max','val_available_max'])
def test_causal_inference_rejects_future_or_equal_labels(field):
    done=dict(metrics=dict(train_available_max='2020-01-01',val_available_max='2020-02-01'))
    causal_fold_contract(done,'2020-03-01')
    done['metrics'][field]='2020-03-01'
    with pytest.raises(ValueError,match='precede'):
        causal_fold_contract(done,'2020-03-01')


def test_probe_selection_has_no_external_input_and_rejects_lineage_reserved():
    d=dict(daily_auc_oriented=.56,coverage=.95,daily_auc_dates=200)
    v=dict(daily_auc_oriented=.54,coverage=.95,daily_auc_dates=50)
    assert frozen_probe(d,v,tier('momentum_20'),.02)
    assert not frozen_probe(d,v,tier('macro_vix'),.02)
    assert not frozen_probe(d,v,tier('selector_short_score'),.02)
    assert not frozen_probe(d,v,tier('score_lightgbm'),.02)
    assert not frozen_probe(d,v,tier('momentum_20'),.2)
    with pytest.raises(TypeError):
        frozen_probe(d,v,tier('momentum_20'),.02,external=.99)


def test_joint_maxT_sign_flips_repeat_and_reject_insufficient_blocks():
    days=pd.bdate_range('2018-01-01',periods=10*63)
    daily=pd.DataFrame({'signal':.65,'neutral':.5},index=days)
    a=maxT_block_pvalues(daily,['signal','neutral'],days)
    assert a==maxT_block_pvalues(daily,['signal','neutral'],days)
    assert a['signal']['p_maxT']<.05
    assert a['neutral']['p_maxT']==1.
    assert maxT_block_pvalues(daily.iloc[:63],['signal'],days)['signal']['p_maxT'] is None


def test_rule_and_primary_scope_frozen_before_external_inspection():
    assert RULES['primary_top']==10
    assert RULES['robustness_tops']==[20,50]
    assert RULES['discovery_daily_auc']==.55
    assert RULES['validation_daily_auc']==.53
    assert RULES['external_daily_auc']==.52


def test_nullable_string_identity_is_numeric_or_unknown_never_fake():
    frame=pd.DataFrame(dict(instrument_id=pd.Series(['321',pd.NA,'CUSIP:889110201'],dtype='string')))
    normal=label_input(frame)
    assert normal.instrument_id.dtype==np.dtype('float64')
    assert normal.instrument_id.iloc[0]==321
    assert normal.instrument_id.iloc[1:].isna().all()
    assert frame.instrument_id.dtype==pd.StringDtype()
    mask=np.array([True,True,True])
    mask &= normal.instrument_id.gt(0).to_numpy()
    assert mask.tolist()==[True,False,False]
