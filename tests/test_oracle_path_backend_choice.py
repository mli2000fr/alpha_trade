from dataclasses import replace
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from modelFactory.config import TrainingConfig,load_oracle_path_training_backend
from modelFactory.oracle_path.backend import resolve_backend,candidates_for,DECLARATIONS,NAMES
from modelFactory.oracle_path import train as trainer,predict as serving
from tests.test_oracle_path import config,bars


def test_explicit_choice_overrides_legacy_flags_and_bad_choices_fail():
    assert resolve_backend(None)=='lightgbm'
    assert resolve_backend(None,enable_catboost=True)=='auto'
    assert resolve_backend('lightgbm',enable_catboost=True)=='lightgbm'
    assert resolve_backend('catboost')=='catboost'
    assert candidates_for('catboost')==('catboost',)
    assert candidates_for('auto')==('lightgbm','catboost')
    with pytest.raises(ValueError,match='backend'):
        resolve_backend('lstm')
    with pytest.raises(ValueError,match='réservé'):
        TrainingConfig(oracle_path_backend='catboost')


def test_yaml_default_and_validation(monkeypatch):
    monkeypatch.setattr('common.config_loader.load_config',lambda p: {'oracle_path':{'training_backend':'catboost','direction_policy':'long_only'}})
    assert load_oracle_path_training_backend()=='catboost'
    monkeypatch.setattr('common.config_loader.load_config',lambda p: {})
    assert load_oracle_path_training_backend()=='auto'
    monkeypatch.setattr('common.config_loader.load_config',lambda p: {'oracle_path':{'training_backend':'unknown'}})
    with pytest.raises(ValueError,match='backend'):
        load_oracle_path_training_backend()


@pytest.mark.parametrize('backend',['lightgbm','catboost','auto'])
def test_ihm_command_cli_backend_not_generic_champion(backend):
    from modelFactory.cli import build_arg_parser
    from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
    opts=PipelineLaunchOptions(ml_oracle_path_model_only=True,ml_oracle_path_backend=backend,
        ml_walkforward=True,ml_enable_lightgbm=False,ml_enable_catboost=False)
    command=build_pipeline_command('ml_train',opts)
    parsed=build_arg_parser().parse_args(command[4:])
    assert parsed.oracle_path_backend==backend
    assert parsed.enable_catboost==(backend in ('catboost','auto'))
    assert parsed.compare_lightgbm==(backend in ('lightgbm','auto'))
    assert parsed.default_champion==('catboost' if backend=='catboost' else 'lightgbm')
    other=build_pipeline_command('ml_train',replace(opts,ml_oracle_path_model_only=False))
    assert '--oracle-path-backend' not in other


def test_cli_choice_threads_to_config_before_any_sql(monkeypatch):
    from modelFactory import cli
    class Seen(Exception):pass
    def capture(**kwargs):
        assert kwargs['oracle_path_backend']=='catboost'
        raise Seen()
    monkeypatch.setattr(cli,'TrainingConfig',capture)
    monkeypatch.setattr(cli,'get_sqlalchemy_engine',lambda:pytest.fail('SQL must not be reached'))
    with pytest.raises(Seen):
        cli.main(['--mode','train','--market-code','US_EQ','--oracle-path-model-only',
                  '--oracle-path-backend','catboost','--walkforward','--training-end-date','2023-12-31'])
    with pytest.raises(SystemExit):
        cli.main(['--mode','train','--market-code','US_EQ','--oracle-path-backend','catboost'])


@pytest.mark.parametrize('backend',['lightgbm','catboost','auto'])
def test_real_tiny_training_serving_resume_and_corruption(tmp_path,monkeypatch,backend):
    symbols=[f'S{i:02d}' for i in range(20)]
    frames=[]
    for i,symbol in enumerate(symbols):
        f=bars(symbol,n=200);f['high']=101+i;f['instrument_id']=i+1;frames.append(f)
    panel=pd.concat(frames,ignore_index=True)
    cfg=config(tmp_path/'batch')
    cfg=replace(cfg,oracle_path_backend=backend,walk_forward=replace(cfg.walk_forward,max_splits=1),
        baseline=replace(cfg.baseline,enable_catboost=backend=='lightgbm',catboost_iterations=10,
                         catboost_depth=2,catboost_border_count=32))
    monkeypatch.setattr(trainer,'nyse_sessions',lambda *a:pd.DatetimeIndex(frames[0].date))
    monkeypatch.setattr(trainer,'load_security_discontinuities',lambda:{})
    monkeypatch.setattr(trainer,'load_bars',lambda *a:panel.copy())
    def features(*a,**kw):
        f=panel[['date','symbol']].copy();f['momentum_20']=f.symbol.str[1:].astype(float);return f
    monkeypatch.setattr(trainer,'build_feature_matrix',features)
    if backend=='catboost':monkeypatch.setattr(trainer,'train_model',lambda *a:pytest.fail('No LightGBM fit requested'))
    if backend=='lightgbm':monkeypatch.setattr(trainer,'train_catboost',lambda *a:pytest.fail('No CatBoost fit requested'))
    result=trainer.train_oracle_path(cfg,object(),'batch',symbols)
    root,protocol,profile,folds=serving.load_contract(tmp_path,'batch')
    assert protocol['training_backend']==backend==profile['training_backend']==result['training_backend']
    assert protocol['backend']==DECLARATIONS[backend]
    assert set(result['comparison_oof'])==set(candidates_for(backend))
    fold=next(iter(folds));folder=root/'folds'/fold
    done=json.loads((folder/'done.json').read_text())
    assert set(done['files'])=={NAMES[b] for b in candidates_for(backend)}|{'oof.parquet'}
    if backend!='auto':
        assert done['champion']['backend']==backend
        assert done['champion']['selection']=='explicit_backend'
        assert all(x['selected_backend']==backend for x in result['folds'])
    monkeypatch.setattr('modelFactory.oracle.build_labels.nyse_sessions',lambda *a:pd.DatetimeIndex([fold]))
    columns=profile['feature_columns']
    f=pd.DataFrame({'date':pd.Timestamp(fold),'symbol':symbols,'momentum_20':np.arange(20,dtype=float)})
    f=trainer.restore_ranks(f,profile['generator_options'])
    monkeypatch.setattr(serving,'build_inference_features',lambda *a:f[['date','symbol',*columns]].copy())
    saved=[]
    monkeypatch.setattr(serving,'write_path_predictions',lambda e,f,b:saved.append(f.copy()) or len(f))
    out=serving.predict_oracle_path_history(SimpleNamespace(url=SimpleNamespace(database='alpha_trade')),
        'batch',fold,fold,artifacts_dir=tmp_path)
    assert out['n_rows']==20
    assert saved[0].model_sha256.iloc[0]==done['files'][done['champion']['model_file']]
    from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
    predict_command=build_pipeline_command('ml_predict',PipelineLaunchOptions(
        ml_oracle_path_backend='lightgbm' if backend=='catboost' else 'catboost',
        ml_live_predict_batch_id='batch',ml_artifacts_dir=str(tmp_path),llm_filter_enabled=False))
    assert '--oracle-path-backend' not in predict_command  # inference uses only the archived model contract
    monkeypatch.setattr(trainer,'train_model',lambda *a:pytest.fail('Resume must not refit'))
    monkeypatch.setattr(trainer,'train_catboost',lambda *a:pytest.fail('Resume must not refit'))
    assert trainer.train_oracle_path(cfg,object(),'batch',symbols)['overall']==result['overall']
    with pytest.raises(ValueError,match='protocole différent'):
        trainer.train_oracle_path(replace(cfg,oracle_path_backend='auto' if backend!='auto' else 'catboost'),object(),'batch',symbols)
    forged=json.loads(json.dumps(done))
    other='lightgbm' if done['champion']['backend']=='catboost' else 'catboost'
    forged['champion'].update(backend=other,model_file=NAMES[other])
    trainer.atomic_json(folder/'done.json',forged)
    with pytest.raises(ValueError,match='choix explicite|automatique'):
        serving.load_contract(tmp_path,'batch')
    trainer.atomic_json(folder/'done.json',done)
    (folder/done['champion']['model_file']).write_bytes(b'broken')
    with pytest.raises(ValueError,match='absents/corrompus|corrompus'):
        serving.load_contract(tmp_path,'batch')


def test_full_widget_all_three_choices_and_non_path_restores_legacy_checkboxes():
    from streamlit.testing.v1 import AppTest
    def app():
        import streamlit as st
        from ihm.pages._execution_center import _build_launch_options
        from ihm.services.pipeline_runner import build_pipeline_command
        options,_=_build_launch_options()
        st.session_state['backend_command']=build_pipeline_command('ml_train',options)
    at=AppTest.from_function(app);at.session_state['pipeline_ml_oracle_path_model_only']=True
    at.session_state['pipeline_ml_oracle_barrier_model_only']=False
    at.run(timeout=30)
    assert not at.exception
    for backend in ['catboost','lightgbm','auto']:
        at.selectbox(key='pipeline_ml_oracle_path_backend').select(backend).run(timeout=30)
        assert not at.exception
        command=at.session_state['backend_command']
        assert command[command.index('--oracle-path-backend')+1]==backend
    at.checkbox(key='pipeline_ml_oracle_path_model_only').uncheck().run(timeout=30)
    assert not at.exception
    assert '--oracle-path-backend' not in at.session_state['backend_command']
    assert at.checkbox(key='pipeline_ml_enable_catboost').label=='Entraîner aussi CatBoost (challenger)'
