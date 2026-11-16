from dataclasses import asdict
from types import SimpleNamespace
import json

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_path import directional as d
from modelFactory.oracle_path.directional_features import compact_columns,input_columns
from modelFactory.oracle_path.train import atomic_json


def market():
    from modelFactory.oracle.build_labels import nyse_sessions
    days=nyse_sessions(pd.Timestamp('2016-01-01').date(),pd.Timestamp('2024-01-05').date())
    rng=np.random.default_rng(37)
    close=100*np.exp(np.cumsum(rng.normal(.0001,.025,len(days))))
    spy=100*np.exp(np.cumsum(rng.normal(.0002,.012,len(days))))
    bars=pd.DataFrame(dict(date=days,symbol='ABC',open=close,close=close,adj_close=close,
        high=close*1.02,low=close*.98,volume=100000+rng.integers(0,100000,len(days)),
        is_filled=0,instrument_id=1,data_source='alpaca_sip',data_adjustment='raw',vwap=close))
    bench=bars.assign(symbol='SPY',open=spy,close=spy,adj_close=spy,high=spy*1.01,low=spy*.99,vwap=spy)
    return days,bars,bench


def test_b_panels_match_frozen_experiment_and_are_past_only():
    from scripts.research.us_q051_feature_groups_20261116 import common_panel
    days,bars,bench=market()
    native=d.panels(bars,bench,days,feature_mode='compact_volatility')
    expected=common_panel(bars,bench,days)[['date',*compact_columns('compact_volatility'),'symbol']]
    pd.testing.assert_frame_equal(native.reset_index(drop=True),expected.reset_index(drop=True))
    changed=bars.copy();changed.loc[changed.date.gt('2023-01-03'),['open','high','low','close','adj_close']]*=1.3
    after=d.panels(changed,bench,days,feature_mode='compact_volatility')
    pd.testing.assert_frame_equal(native[native.date.le('2023-01-03')],after[after.date.le('2023-01-03')])
    assert len(compact_columns())==24 and len(compact_columns('compact_volatility'))==29


@pytest.mark.filterwarnings('error:.*does not have valid feature names.*:UserWarning')
def test_b_real_long_short_training_reload_and_prediction(tmp_path,monkeypatch):
    import joblib
    from modelFactory.oracle_path.directional_metrics import predict
    days,bars,bench=market();root=tmp_path/'oracle_path';chunk=root/'chunks/0000';chunk.mkdir(parents=True)
    training=bars[bars.date.le('2023-12-31')];training.to_parquet(chunk/'bars.parquet',index=False)
    contract=asdict(d.Settings(feature_mode='compact_volatility'))
    atomic_json(root/'protocol.json',dict(universe=['ABC'],horizon=10,directional_contract=contract,
        training_config=dict(oracle_path_directional_enabled=True,data=dict(benchmark_symbol='SPY',
            training_start_date='2016-01-01',training_end_date='2023-12-31'))))
    cfg=SimpleNamespace(data=SimpleNamespace(training_start_date='2016-01-01',training_end_date='2023-12-31',
        benchmark_symbol='SPY'),reproducibility=SimpleNamespace(seed=42))
    m=d.train(cfg,None,root,lambda *a:None,benchmark=bench[bench.date.le('2023-12-31')],years=[2024])
    assert len(m['models'])==2 and m['features']==compact_columns('compact_volatility')
    assert {r['side'] for r in m['models']}=={'long','short'}
    assert d.load_manifest(root)[0]['features']==input_columns(root)
    for record in m['models']:
        w=joblib.load(root/record['file'])
        assert w['model'][-1].n_features_in_==29
        assert list(w['model'][-1].feature_names_in_)==compact_columns('compact_volatility')
    monkeypatch.setattr('modelFactory.data_loader.load_benchmark_bars',lambda *a,**kw:bench)
    scores=pd.DataFrame(dict(date=pd.to_datetime(['2024-01-02']),symbol='ABC',proba_extreme=.9))
    result=d.infer(None,root,scores,bar_frame=bars)
    assert result.long_probability.between(0,1).all() and result.short_probability.between(0,1).all()
    d.validate_saved(root,scores,result.rename(columns={'date':'prediction_date'}))
    saved=d.panels(bars,bench,days,feature_mode='compact_volatility')
    w=joblib.load(root/next(r['file'] for r in m['models'] if r['side']=='long'))
    assert result.long_probability.iloc[0]==pytest.approx(predict(w,saved[saved.date.eq('2024-01-02')])[0])
    from modelFactory.oracle_path.evaluate_directional import evaluate
    diagnostics=evaluate(root,output=tmp_path/'diagnostics')
    assert diagnostics['status']=='COMPLETED' and len(diagnostics['models'])==2
    assert not diagnostics['training_launched'] and not diagnostics['benchmark_reconstructed_from_SQL']


def test_pipeline_checkbox_default_opt_out_and_command():
    from streamlit.testing.v1 import AppTest
    def app():
        import streamlit as st
        from ihm.components.oracle_path_training_features import render_volatility_features
        from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
        mode=render_volatility_features(True)
        options=PipelineLaunchOptions(ml_oracle_path_model_only=True,ml_oracle_path_directional_enabled=True,
            ml_oracle_path_directional_feature_mode=mode,ml_oracle_horizon=10,
            ml_training_start_date='2016-01-01',ml_training_end_date='2023-12-31')
        st.session_state['command']=build_pipeline_command('ml_train',options)
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception and at.checkbox(key='pipeline_ml_path_directional_volatility').value
    command=at.session_state['command']
    assert command[command.index('--oracle-path-directional-features')+1]=='compact_volatility'
    from modelFactory.cli import build_arg_parser
    parsed=build_arg_parser().parse_args(command[4:])
    assert parsed.oracle_path_directional_features=='compact_volatility'
    at.checkbox(key='pipeline_ml_path_directional_volatility').uncheck().run(timeout=30)
    assert not at.exception and '--oracle-path-directional-features' not in at.session_state['command']


def test_compact_without_mode_stays_24(tmp_path):
    atomic_json(tmp_path/'protocol.json',dict(directional_contract={}))
    assert input_columns(tmp_path)==d.INPUTS


def test_b_profile_rejects_non_b_models():
    from ihm.components.winner_backtest_profiles import validate_profile_model
    with pytest.raises(ValueError,match='29 variables'):validate_profile_model('q051_b',{},None,False)
    with pytest.raises(ValueError,match='29 variables'):
        validate_profile_model('q051_b',{'directional_contract':{'feature_mode':'compact'}},{'features':d.INPUTS},True)
    validate_profile_model('q051_b',{'directional_contract':{'feature_mode':'compact_volatility'}},
        {'features':compact_columns('compact_volatility')},True)


def test_model_config_accepts_b_and_requires_bundle():
    from modelFactory.config import TrainingConfig,DataConfig,WalkForwardConfig
    with pytest.raises(ValueError,match='activer le bundle'):
        TrainingConfig(oracle_path_directional_feature_mode='compact_volatility')
    from datetime import date
    cfg=TrainingConfig(data=DataConfig(oracle_path_model_only=True,training_start_date=date(2016,1,1),
        training_end_date=date(2023,12,31)),oracle_path_directional_enabled=True,
        oracle_path_directional_feature_mode='compact_volatility',oracle_horizon=20,
        walk_forward=WalkForwardConfig(enabled=True))
    assert cfg.oracle_path_directional_feature_mode=='compact_volatility'
