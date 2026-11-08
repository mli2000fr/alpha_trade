from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_path import directional as d


def prices(n=40):
    days=pd.bdate_range('2020-01-01',periods=n)
    a=pd.DataFrame(dict(date=days,symbol='ABC',open=100.,high=101.,low=99.,close=100.,
        adj_close=100.,volume=100000.,is_filled=0,instrument_id=1,data_source='alpaca_sip',data_adjustment='raw'))
    return a,days


def test_profit_labels_follow_stop_before_later_peak_and_short_is_separate():
    a,days=prices()
    a.loc[2,'low']=94.
    a.loc[3,'high']=130.
    a.loc[11,['open','high','low','close','adj_close']]=[120,121,119,120,120]
    result=d.labels(a,days,d.Settings())
    assert result.iloc[0]['long']==0  # later gain cannot undo the earlier stop
    assert result.iloc[0]['short']==0  # later upward stop before open11
    assert result.iloc[0].available==days[11]
    a.loc[2,'low']=99.
    assert d.labels(a,days,d.Settings()).iloc[0]['long']==1
    before=d.labels(a,days,d.Settings()).iloc[0]
    a.loc[30,'low']=1.
    pd.testing.assert_series_equal(before,d.labels(a,days,d.Settings()).iloc[0])


def test_missing_or_changed_provider_rejects_window_even_with_early_stop():
    a,days=prices();a.loc[1,'low']=90.
    a.loc[9,'data_source']='eodhd_eod'
    assert pd.isna(d.labels(a,days,d.Settings()).iloc[0]['long'])
    a,days=prices();a.loc[11,'open']=np.nan
    assert pd.isna(d.labels(a,days,d.Settings()).iloc[0]['short'])


def test_split_purges_outcomes_at_both_boundaries():
    p=pd.DataFrame(dict(date=pd.to_datetime(['2022-12-01','2022-12-28','2023-01-03','2023-12-27']),
        available=pd.to_datetime(['2022-12-19','2023-01-12','2023-01-20','2024-01-12']),long=1.))
    fit,cal=d.split(p,2024,'long')
    assert fit.date.tolist()==[pd.Timestamp('2022-12-01')]
    assert cal.date.tolist()==[pd.Timestamp('2023-01-03')]


def test_fixed_oracle_pool_before_long_ranking_no_short_or_refill():
    names=[f'S{i:02}' for i in range(25)]
    a=pd.DataFrame(dict(date=pd.Timestamp('2025-01-02'),symbol=names,proba_extreme=np.linspace(1,0,25)))
    p=pd.DataFrame(dict(date=a.date,symbol=names,long_probability=np.linspace(.1,.9,25),short_probability=1.))
    out=d.rank(a,p,d.Settings())
    assert out[out.selected].symbol.tolist()==['S15','S16','S17','S18','S19']
    assert out[out.selected].sort_values('long_rank').symbol.tolist()==['S19','S18','S17','S16','S15']
    p.loc[:19,'long_probability']=np.nan
    assert not d.rank(a,p,d.Settings()).selected.any()  # no substitution from rank21


def test_same_probability_tie_breaks_on_original_oracle_rank():
    a=pd.DataFrame(dict(date=pd.Timestamp('2025-01-02'),symbol=['B','A','C'],proba_extreme=[.9,.8,.7]))
    p=a[['date','symbol']].assign(long_probability=.4,short_probability=.99)
    out=d.rank(a,p,d.Settings(selected_n=1))
    assert out[out.selected].symbol.tolist()==['B']  # relative selection below .5 allowed


def test_prediction_coverage_93_percent_allows_30_of_32_but_not_29():
    from modelFactory.oracle_path.predict import validate_prediction_coverage
    names=[f'S{i:02}' for i in range(32)];day=pd.Timestamp('2026-07-16')
    frame=pd.DataFrame(dict(date=day,symbol=names[:30]))
    protocol=dict(min_daily_universe=20,directional_contract=dict(oracle_top_n=20))
    validate_prediction_coverage(frame,names,[day],protocol,.93)
    with pytest.raises(ValueError,match=r'2026-07-16.*30/32.*minimum 31.*S30,S31'):
        validate_prediction_coverage(frame,names,[day],protocol,.95)
    with pytest.raises(ValueError,match=r'29/32.*minimum 30'):
        validate_prediction_coverage(frame.iloc[:-1],names,[day],protocol,.93)
    with pytest.raises(ValueError,match='minimum 20'):
        validate_prediction_coverage(frame.iloc[:19],names,[day],protocol,.5)


@pytest.mark.parametrize('value',[0,1.1,True,'0.93',float('nan')])
def test_prediction_coverage_setting_validation(monkeypatch,value):
    from modelFactory.oracle_path.predict import prediction_coverage_ratio
    monkeypatch.setattr('common.config_loader.load_config',lambda:dict(oracle_path=dict(min_prediction_coverage_ratio=value)))
    with pytest.raises(ValueError,match='min_prediction_coverage_ratio'):
        prediction_coverage_ratio()


@pytest.mark.parametrize('horizon',[10,15,20])
def test_flag_requires_path_and_pipeline_emits_matching_horizon(horizon):
    from datetime import date
    from modelFactory.config import TrainingConfig,DataConfig,WalkForwardConfig
    from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
    with pytest.raises(ValueError,match='H10'):
        TrainingConfig(oracle_path_directional_enabled=True)
    cfg=TrainingConfig(data=DataConfig(oracle_path_model_only=True,training_start_date=date(2016,1,1),training_end_date=date(2023,12,31)),
        walk_forward=WalkForwardConfig(enabled=True),oracle_horizon=horizon,oracle_path_directional_enabled=True)
    assert cfg.oracle_path_directional_enabled
    opts=PipelineLaunchOptions(ml_oracle_path_model_only=True,ml_oracle_path_directional_enabled=True,
        ml_oracle_horizon=horizon,ml_training_start_date='2016-01-01',ml_training_end_date='2023-12-31')
    command=build_pipeline_command('ml_train',opts)
    assert '--oracle-path-model-only' in command and '--oracle-path-directional' in command
    assert '--directional-feature-profiles' not in command
    assert command[command.index('--oracle-horizon')+1]==str(horizon)


def test_bundle_routes_directly_without_options_llm_or_batch_substitution(tmp_path):
    from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command,path_directional_options
    from service.forward_pit.us_pipeline import options_filter_options,llm_options
    folder=tmp_path/'batch/oracle_path';folder.mkdir(parents=True)
    (folder/'protocol.json').write_text(json.dumps(dict(training_config=dict(oracle_path_directional_enabled=True))))
    opts=PipelineLaunchOptions(ml_artifacts_dir=str(tmp_path),ml_live_predict_batch_id='batch',
        llm_filter_enabled=True,options_filter_enabled=True,trade_date='2026-11-03')
    normalized=path_directional_options(opts)
    assert not normalized.options_filter_enabled and not normalized.llm_filter_enabled
    assert normalized.ml_live_predict_batch_id=='batch'
    command=build_pipeline_command('ml_predict',opts)
    assert command[3]=='modelFactory' and 'batch' in command
    for bind in [llm_options,options_filter_options]:
        result=bind(opts,[SimpleNamespace(num='10')])
        assert result.ml_live_predict_batch_id=='batch' and not result.options_filter_enabled and not result.llm_filter_enabled


def test_probability_storage_and_synthetic_projection_is_long_only(monkeypatch):
    from contextlib import contextmanager
    from modelFactory import synthesize_oracle_predictions as synth
    from modelFactory.oracle_path import predict
    from modelFactory.oracle import predictions_store
    from database import connection
    calls=[]
    class Engine:
        @contextmanager
        def connect(self):yield self
        begin=connect
        def execute(self,sql,params=None):calls.append((str(sql),params))
    engine=Engine()
    oracle=pd.DataFrame(dict(date=pd.to_datetime(['2024-01-02']*2),symbol=['A','B'],proba_extreme=[.9,.8]))
    ranked=oracle.assign(long_probability=[.4,.9],short_probability=[.99,.01],selected=[True,False])
    monkeypatch.setattr(connection,'get_sqlalchemy_engine',lambda:engine)
    monkeypatch.setattr(synth,'get_sqlalchemy_engine',lambda:engine)
    monkeypatch.setattr(predict,'load_contract',lambda *a:(Path('.'),dict(training_config=dict(oracle_path_directional_enabled=True)),None,None))
    from modelFactory.oracle_path import train
    monkeypatch.setattr(train,'is_path_batch',lambda *a:True)
    monkeypatch.setattr(predictions_store,'load_oracle_predictions',lambda *a,**kw:oracle)
    monkeypatch.setattr(pd,'read_sql',lambda *a,**kw:oracle.rename(columns={'date':'prediction_date'}))
    monkeypatch.setattr(d,'read_predictions',lambda *a:ranked)
    monkeypatch.setattr(synth,'ensure_synthetic_run',lambda *a,**kw:None)
    result=synth.synthesize('batch')
    writes=[params for sql,params in calls if sql.startswith('INSERT INTO alpha_trade.model_predictions')]
    assert result['long_count']==1 and len(writes[0])==2
    a,b=writes[0]
    assert a['predicted_side']=='long' and a['proba_long']==.4  # no artificial .5 threshold
    assert b['predicted_side']=='flat' and a['proba_short']==b['proba_short']==0
    assert a['source']==d.SOURCE


@pytest.mark.filterwarnings('error:.*does not have valid feature names.*:UserWarning')
@pytest.mark.parametrize('horizon',[10,15,20])
def test_real_annual_training_both_branches_reload_and_own_history(tmp_path,monkeypatch,horizon):
    from modelFactory import data_loader
    from modelFactory.oracle_path.train import atomic_json,digest
    from modelFactory.oracle.build_labels import nyse_sessions
    days=nyse_sessions(pd.Timestamp('2016-01-01').date(),pd.Timestamp('2024-01-05').date())
    rng=np.random.default_rng(27);close=100*np.exp(np.cumsum(rng.normal(.0002,.025,len(days))))
    a=pd.DataFrame(dict(date=days,symbol='ABC',open=close,close=close,adj_close=close,
        high=close*1.02,low=close*.98,volume=100000+rng.integers(0,100000,len(days)),
        is_filled=0,instrument_id=1,data_source='alpaca_sip',data_adjustment='raw',vwap=close))
    bench=a.assign(symbol='SPY')
    monkeypatch.setattr(data_loader,'load_benchmark_bars',lambda *args,**kw:bench[bench.date.le(pd.Timestamp(kw['end_date']))])
    root=tmp_path/'oracle_path';chunk=root/'chunks/0000';chunk.mkdir(parents=True)
    a[a.date.le('2023-12-31')].to_parquet(chunk/'bars.parquet',index=False)
    atomic_json(root/'protocol.json',dict(universe=['ABC'],horizon=horizon,directional_contract=vars(d.Settings(horizon_sessions=horizon)),
        training_config=dict(oracle_path_directional_enabled=True,data=dict(benchmark_symbol='SPY',
            training_start_date='2016-01-01',training_end_date='2023-12-31'))))
    cfg=SimpleNamespace(data=SimpleNamespace(training_start_date='2016-01-01',training_end_date='2023-12-31',
        benchmark_symbol='SPY'),reproducibility=SimpleNamespace(seed=42))
    result=d.train(cfg,None,root,lambda *a:None)
    assert {(r['side'],r['year']) for r in result['models']} >= {('long',2024),('short',2024)}
    assert all(pd.Timestamp(r['available'])<pd.Timestamp(f"{r['year']}-01-01") for r in result['models'])
    assert d.load_manifest(root)[0]==result
    assert all('calibration' in r['metrics'] and 'oos' in r['metrics'] for r in result['models'])
    from modelFactory.oracle_path.evaluate_directional import evaluate
    diagnostics=evaluate(root,output=tmp_path/'diagnostics')
    assert diagnostics['status']=='COMPLETED' and not diagnostics['benchmark_reconstructed_from_SQL']
    assert diagnostics['nonoverlap_phase']==f'global calendar index modulo{horizon+1} ==0'
    assert diagnostics['training_launched'] is diagnostics['SQL_writes'] is False
    expected={(r['symbol'],r['year'],r['side']):r['metrics'] for r in result['models']}
    assert all(r['metrics']==expected[(r['symbol'],r['year'],r['side'])] for r in diagnostics['models'])
    from modelFactory.oracle_path import labels as mod
    monkeypatch.setattr(mod,'load_bars',lambda *args:a[a.date.le(pd.Timestamp(args[-1]))])
    scores=pd.DataFrame(dict(date=pd.to_datetime(['2024-01-02']),symbol=['ABC'],proba_extreme=[.9]))
    out=d.infer(None,root,scores)
    assert out.selected.all() and out.long_probability.between(0,1).all() and out.short_probability.between(0,1).all()
    saved=out.rename(columns={'date':'prediction_date'})
    d.validate_saved(root,scores,saved)
    with pytest.raises(ValueError,match='classement|Classement'):
        d.validate_saved(root,scores,saved.assign(selected=False))
    with (root/result['models'][0]['file']).open('ab') as stream:stream.write(b'corrupt')
    with pytest.raises(ValueError,match='corrompu'):
        d.load_manifest(root)


@pytest.mark.parametrize('horizon',[10,15,20])
def test_configured_horizon_follows_selected_oracle_without_changing_defaults(monkeypatch,horizon):
    configured=dict(enabled=True,oracle_top_n=40,selected_n=8,stop_loss_pct=.06,
        horizon_sessions=10,fee_per_leg=.001)
    monkeypatch.setattr('common.config_loader.load_config',lambda:dict(oracle_path=dict(directional=configured)))
    contract=d.settings(horizon=horizon)
    assert contract.horizon_sessions==horizon
    assert contract.stop_loss_pct==.06 and contract.oracle_top_n==40
    assert configured['horizon_sessions']==10 and d.settings().horizon_sessions==10


@pytest.mark.parametrize('horizon',[10,15,20])
def test_label_maturity_and_open_exit_follow_horizon(horizon):
    a,days=prices(50)
    a.loc[horizon+1,['open','high','low','close','adj_close']]=[110,111,109,110,110]
    contract=d.Settings(horizon_sessions=horizon)
    result=d.labels(a,days,contract)
    assert result.iloc[0].available==days[horizon+1]
    assert result.iloc[0]['long']==1 and result.iloc[0]['short']==0
    a.loc[horizon,'low']=94.
    assert d.labels(a,days,contract).iloc[0]['long']==0  # final-session SL still observed


def test_mismatched_bundle_and_oracle_horizons_are_rejected_even_with_updated_hash(tmp_path):
    from modelFactory.oracle_path.train import atomic_json,digest
    root=tmp_path/'oracle_path';(root/'directional').mkdir(parents=True)
    contract=vars(d.Settings(horizon_sessions=10))
    atomic_json(root/'protocol.json',dict(horizon=20,universe=['ABC'],directional_contract=contract,
        training_config=dict(oracle_path_directional_enabled=True)))
    atomic_json(root/'directional/manifest.json',dict(status='COMPLETED',contract=contract,
        features=d.INPUTS,serving_side='long',oracle_protocol_sha256=digest(root/'protocol.json'),models=[]))
    with pytest.raises(ValueError,match='incompatible'):d.load_manifest(root)


def test_pipeline_widget_enables_bundle_and_matches_h15_h20():
    from streamlit.testing.v1 import AppTest
    def app():
        import streamlit as st
        from ihm.pages._execution_center import _build_launch_options
        from ihm.services.pipeline_runner import build_pipeline_command
        options,_=_build_launch_options()
        st.session_state['bundle_command']=build_pipeline_command('ml_train',options)
    at=AppTest.from_function(app)
    at.session_state['pipeline_ml_oracle_path_model_only']=True
    at.session_state['pipeline_ml_oracle_barrier_model_only']=False
    at.session_state['pipeline_ml_directional_profiles_enabled']=True
    at.run(timeout=30)
    for horizon in [15,20,10]:
        at.selectbox(key='pipeline_ml_oracle_path_horizon').select(horizon).run(timeout=30)
        assert not at.exception
        checkbox=at.checkbox(key='pipeline_ml_directional_profiles_enabled')
        assert checkbox.value and not checkbox.disabled
        cmd=at.session_state['bundle_command']
        assert '--oracle-path-directional' in cmd
        assert cmd[cmd.index('--oracle-horizon')+1]==str(horizon)
        assert any(f'sortie open{horizon+1}' in message.value for message in at.info)
