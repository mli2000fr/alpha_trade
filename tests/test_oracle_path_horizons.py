"""Real tiny path training/inference; no production SQL, broker or provider calls."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from modelFactory.config import load_oracle_path_horizon
from modelFactory.oracle_path import target_name, mode_name, validate_horizon
from modelFactory.oracle_path.labels import symbol_paths, classify
from modelFactory.oracle_path import train as trainer, predict as serving
from tests.test_oracle_path import bars, config


@pytest.mark.parametrize('horizon',[10,15,20])
def test_labels_use_peak_in_selected_window_and_conservative_maturity(horizon):
    f=bars(n=60)
    f.loc[5,'high']=120
    f.loc[horizon+1,'high']=180
    labels,_=symbol_paths(f,pd.DatetimeIndex(f.date),start=f.date.min(),end=f.date.max(),
                          registry={},horizon=horizon)
    first=labels.iloc[0]
    assert first.path_amplitude==pytest.approx(.2)
    assert first.oracle_exit_date==f.date.iloc[horizon]
    assert first.oracle_available_date==f.date.iloc[horizon+1]
    short,_=symbol_paths(f,pd.DatetimeIndex(f.date),start=f.date.min(),end=f.date.iloc[horizon],
                        registry={},horizon=horizon)
    assert short.iloc[0].path_quality_reason=='IMMATURE_WINDOW'
    panel=pd.concat([labels.iloc[:1].assign(symbol=str(i),path_amplitude=i/100) for i in range(20)])
    assert classify(panel,horizon=horizon)[target_name(horizon)].sum()==4


@pytest.mark.parametrize('horizon',[10,15,20])
def test_ihm_command_passes_selected_horizon_to_cli(horizon):
    from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
    from modelFactory.cli import build_arg_parser
    opts=PipelineLaunchOptions(ml_oracle_path_model_only=True,ml_oracle_path_backend='lightgbm',
                              ml_oracle_horizon=horizon,ml_walkforward=True)
    parsed=build_arg_parser().parse_args(build_pipeline_command('ml_train',opts)[4:])
    assert parsed.oracle_path_model_only and parsed.oracle_horizon==horizon


def test_config_default_and_reject_non_supported_values(monkeypatch):
    monkeypatch.setattr('common.config_loader.load_config',lambda path: {})
    assert load_oracle_path_horizon()==20
    monkeypatch.setattr('common.config_loader.load_config',lambda path: {'oracle_path':{'horizon':15}})
    assert load_oracle_path_horizon()==15
    for bad in [5,0,True,10.,'10',None]:
        with pytest.raises(ValueError):validate_horizon(bad)


@pytest.mark.parametrize('horizon',[10,15,20])
def test_real_training_contract_prediction_and_no_cross_horizon_resume(tmp_path,monkeypatch,horizon):
    from modelFactory.oracle.artifact_contract import resolve_oracle_artifact_horizon
    symbols=[f'S{i:02d}' for i in range(20)]
    frames=[bars(s,n=200).assign(high=101+i,instrument_id=i+1) for i,s in enumerate(symbols)]
    panel=pd.concat(frames,ignore_index=True)
    cfg=config(tmp_path/'batch',oracle_horizon=horizon,oracle_path_backend='lightgbm')
    cfg=replace(cfg,walk_forward=replace(cfg.walk_forward,max_splits=1))
    monkeypatch.setattr(trainer,'nyse_sessions',lambda *a:pd.DatetimeIndex(frames[0].date))
    monkeypatch.setattr(trainer,'load_security_discontinuities',lambda:{})
    monkeypatch.setattr(trainer,'load_bars',lambda *a:panel.copy())
    def features(*a,**kw):
        f=panel[['date','symbol']].copy();f['momentum_20']=f.symbol.str[1:].astype(float);return f
    monkeypatch.setattr(trainer,'build_feature_matrix',features)
    result=trainer.train_oracle_path(cfg,object(),'batch',symbols)
    root,protocol,profile,folds=serving.load_contract(tmp_path,'batch')
    assert protocol['horizon']==result['horizon']==horizon
    assert protocol['mode']==profile['mode']==mode_name(horizon)
    assert protocol['target']==profile['target']==target_name(horizon)
    assert resolve_oracle_artifact_horizon('batch',tmp_path)==horizon
    from ihm.services.oracle_path_diagnostics import load_path_artifacts
    assert load_path_artifacts('batch',tmp_path)['ready']
    oof=pd.read_parquet(root/'oof_predictions.parquet')
    assert target_name(horizon) in oof
    for item in result['folds']:
        assert pd.Timestamp(item['train_available_max'])<pd.Timestamp(item['val_start'])
        assert pd.Timestamp(item['val_available_max'])<pd.Timestamp(item['test_start'])
    chosen=next(iter(folds));day=folds[chosen]['metrics']['test_start']
    monkeypatch.setattr(serving,'build_inference_features',lambda *a:
        trainer.restore_ranks(features(),profile['generator_options']))
    real_write=serving.write_path_predictions
    saved=[]
    def write(engine,frame,batch,**kw):
        assert kw['horizon']==horizon
        saved.append(frame.copy());return len(frame)
    monkeypatch.setattr(serving,'write_path_predictions',write)
    engine=SimpleNamespace(url=SimpleNamespace(database='alpha_trade'))
    prediction=serving.predict_oracle_path_history(engine,'batch',day,day,artifacts_dir=tmp_path)
    assert prediction['horizon']==horizon and prediction['target']==target_name(horizon)
    assert len(saved)==1 and saved[0].proba_extreme.between(0,1).all()
    from tests.test_oracle_path_serving import Engine
    fake=Engine()
    assert real_write(fake,saved[0],'batch',horizon=horizon)==len(symbols)
    inserts=[(str(sql),params) for sql,params in fake.calls if 'INSERT' in str(sql)]
    assert inserts[-1][1][0]['target_horizon']==horizon
    assert inserts[-1][1][0]['target_name']==target_name(horizon)
    assert all(r['future_return'] is None and r['oracle_extreme10'] is None for r in inserts[0][1])
    from backtesting.winner_campaign_replay import validate_scores
    lineage=saved[0].rename(columns={'date':'trade_date'}).assign(
        lineage_fold_start=chosen,target_name=target_name(horizon),target_horizon=horizon)
    ranked=validate_scores(lineage,profile_hash=trainer.digest(root/'feature_profile.json'),
        folds=folds,expected_days=[pd.Timestamp(day).date()],top_n=10,horizon=horizon)
    assert len(ranked)==10
    other=10 if horizon!=10 else 15
    with pytest.raises(ValueError,match='lineage'):
        validate_scores(lineage.assign(target_horizon=other),
            profile_hash=trainer.digest(root/'feature_profile.json'),folds=folds,
            expected_days=[pd.Timestamp(day).date()],top_n=10,horizon=horizon)
    with pytest.raises(ValueError,match='incompatible'):
        serving.predict_oracle_path_history(engine,'batch',day,day,artifacts_dir=tmp_path,horizon=other)
    with pytest.raises(ValueError,match='protocole différent'):
        trainer.train_oracle_path(replace(cfg,oracle_horizon=other),object(),'batch',symbols)


def test_full_widget_horizon_changes_training_command():
    from streamlit.testing.v1 import AppTest
    def app():
        import streamlit as st
        from ihm.pages._execution_center import _build_launch_options
        from ihm.services.pipeline_runner import build_pipeline_command
        options,_=_build_launch_options()
        st.session_state['horizon_command']=build_pipeline_command('ml_train',options)
    at=AppTest.from_function(app)
    at.session_state['pipeline_ml_oracle_path_model_only']=True
    at.session_state['pipeline_ml_oracle_barrier_model_only']=False
    at.run(timeout=40)
    assert not at.exception
    for h in [10,15,20]:
        at.selectbox(key='pipeline_ml_oracle_path_horizon').select(h).run(timeout=40)
        assert not at.exception
        command=at.session_state['horizon_command']
        assert command[command.index('--oracle-horizon')+1]==str(h)
