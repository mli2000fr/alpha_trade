from datetime import date
from dataclasses import replace

import pandas as pd
import pytest

from ihm.pages import pipeline
from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
from modelFactory.oracle_path.predict import first_causal_date


def folds():
    return {'2021-07-02':dict(metrics=dict(fold_start='2021-07-02',
        train_available_max='2020-12-30',val_available_max='2021-07-01'))}


def test_first_date_observes_all_three_clocks():
    assert first_causal_date(folds())==pd.Timestamp('2021-07-02')
    f=folds();f['2021-07-02']['metrics']['train_available_max']='2021-07-05'
    assert first_causal_date(f)==pd.Timestamp('2021-07-06')
    with pytest.raises(ValueError,match='disponibilité qualifiée'):
        first_causal_date({})


def ui(monkeypatch):
    state={};messages=[]
    monkeypatch.setattr(pipeline.st,'session_state',state)
    monkeypatch.setattr(pipeline.st,'caption',lambda value:messages.append(value))
    monkeypatch.setattr(pipeline.st,'error',lambda value:messages.append(value))
    monkeypatch.setattr(pipeline.st,'date_input',lambda label,**kwargs:state[kwargs['key']])
    monkeypatch.setattr('modelFactory.oracle_path.train.is_path_batch',lambda *a:True)
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *a:
        (None,{'horizon':10},None,folds()))
    return state,messages


def test_training_dates_not_reused_and_command_explicit(monkeypatch):
    state,messages=ui(monkeypatch)
    original=PipelineLaunchOptions(ml_training_start_date='2019-01-01',ml_training_end_date='2026-10-29',
        ml_predict_batch_id='new-h10',ml_predict_use_historical_range=True)
    predicted=pipeline._path_prediction_date_options(original,'new-h10')
    assert original.ml_training_start_date=='2019-01-01'
    assert predicted.ml_training_start_date=='2021-07-02'
    assert predicted.ml_training_end_date=='2026-10-29'
    command=build_pipeline_command('ml_predict',predicted)
    assert command[command.index('--training-start-date')+1]=='2021-07-02'
    assert any('2021-07-02' in m for m in messages)
    state['pipeline_ml_path_predict_start_new-h10']=date(2025,1,1)
    predicted=pipeline._path_prediction_date_options(replace(original,ml_training_start_date='2016-01-01'),'new-h10')
    assert predicted.ml_training_start_date=='2025-01-01'


def test_bad_manual_range_blocks_button_scope(monkeypatch):
    state,_=ui(monkeypatch)
    state['pipeline_ml_path_predict_start_new-h10']=date(2019,1,1)
    assert pipeline._path_prediction_date_options(PipelineLaunchOptions(),'new-h10') is None
    state['pipeline_ml_path_predict_start_new-h10']=date(2025,1,1)
    state['pipeline_ml_path_predict_end_new-h10']=date(2024,1,1)
    assert pipeline._path_prediction_date_options(PipelineLaunchOptions(),'new-h10') is None


def test_invalid_contract_not_replaced_by_training_period(monkeypatch):
    _,messages=ui(monkeypatch)
    def broken(*a):raise ValueError('bad hash')
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',broken)
    assert pipeline._path_prediction_date_options(PipelineLaunchOptions(),'new-h10') is None
    assert any('bad hash' in m for m in messages)


def test_auto_batch_is_resolved_before_proposing_dates_and_pinned(monkeypatch):
    ui(monkeypatch)
    monkeypatch.setattr('modelFactory.cli._resolve_predict_batch_id',lambda *a,**kw:'new-h10')
    options=PipelineLaunchOptions(ml_predict_batch_id=None,ml_live_predict_batch_id=None,
        ml_training_start_date='2019-01-01',ml_training_end_date='2026-10-29')
    result=pipeline._path_prediction_date_options(options,'')
    assert result.ml_predict_batch_id=='new-h10'
    assert result.ml_training_start_date=='2021-07-02'


def test_real_date_widgets_keep_training_dates_separate(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr('modelFactory.oracle_path.train.is_path_batch',lambda *a:True)
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *a:
        (None,{'horizon':10},None,folds()))
    def app():
        import streamlit as st
        from ihm.pages.pipeline import _path_prediction_date_options
        from ihm.services.pipeline_runner import PipelineLaunchOptions
        original=PipelineLaunchOptions(ml_training_start_date='2019-01-01',ml_training_end_date='2026-10-29')
        changed=_path_prediction_date_options(original,'new-h10')
        st.session_state['original_start']=original.ml_training_start_date
        st.session_state['prediction_start']=changed.ml_training_start_date if changed else None
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception
    assert at.session_state['original_start']=='2019-01-01'
    assert at.date_input(key='pipeline_ml_path_predict_start_new-h10').value==date(2021,7,2)
    at.date_input(key='pipeline_ml_path_predict_start_new-h10').set_value(date(2025,1,1)).run(timeout=30)
    assert not at.exception and at.session_state['prediction_start']=='2025-01-01'
