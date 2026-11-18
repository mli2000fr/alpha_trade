from dataclasses import asdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
import json

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_path import anti_sl as a
from modelFactory.oracle_path.train import atomic_json,digest


def test_path_and_target_match_research_without_importing_research_in_runtime():
    from scripts.research.us_q051_b_early_sl_20261116 import path_panel,early_labels
    days=pd.bdate_range('2024-01-02',periods=30);rng=np.random.default_rng(2)
    f=pd.DataFrame(rng.normal(size=(len(days),29)),columns=a.columns()[:29]);f['date']=days;f['symbol']='ABC'
    f=f.drop(index=9)
    pd.testing.assert_frame_equal(a.path_features(f,days),path_panel(f,days))
    after=f.copy();after.loc[after.date.gt(days[20]),'return_5d']=1e8
    pd.testing.assert_frame_equal(a.path_features(f,days).query('date<=@days[20]'),a.path_features(after,days).query('date<=@days[20]'))
    bars=pd.DataFrame(dict(date=days,symbol='ABC',open=100.,close=100.,high=110.,low=np.resize([94.,96.],30),
        volume=10000.,is_filled=0,instrument_id=1,data_source='alpaca_sip',data_adjustment='raw'))
    actual=a.labels(bars,days,.05);expected=early_labels(bars,days)
    pd.testing.assert_series_equal(actual.first_session_sl,expected.first_session_sl)
    pd.testing.assert_series_equal(actual.available,expected.event_available,check_names=False)
    assert actual.available.iloc[0]==days[2]


def flags(n=4):
    return dict(anti_sl_probability=[.9,.1,.1,None][:n],anti_sl_threshold=[.8,.8,.8,None][:n],
        anti_sl_model_sha256=['m','m','m',None][:n],anti_sl_manifest_sha256='h',
        anti_sl_available=['2023-12-20']*n,anti_sl_status=['SCORED','SCORED','SCORED','NO_CAUSAL_MODEL'][:n],
        anti_sl_features_sha256=['f','f','f',None][:n])


def test_veto_after_long_top_does_not_promote_next_rank_and_keeps_unknown():
    from backtesting.per_symbol_selection import PerSymbolSelection,select_per_symbol
    f=pd.DataFrame(dict(date=pd.Timestamp('2024-01-02'),symbol=list('ABCD'),proba_extreme=[.9,.8,.7,.6],
        long_probability=[.9,.8,.7,.6],short_probability=np.nan,**flags()))
    got=select_per_symbol(f,PerSymbolSelection(oracle_top_n=4,long_top_n=2))
    assert got[got.selected].symbol.tolist()==['B']
    assert got.loc[got.symbol.eq('A'),'reason'].iloc[0]=='ANTI_SL_FIRST_SESSION_RISK'
    got=select_per_symbol(f,PerSymbolSelection(oracle_top_n=4,long_top_n=4))
    assert 'D' in got[got.selected].symbol.tolist()


def test_legacy_frame_identity_and_short_not_vetoed():
    f=pd.DataFrame({'selected':[True],'side':['short'],'reason':['SELECTED_SHORT']})
    assert a.apply_filter(f) is f
    for name,val in {k:v for k,v in flags(1).items()}.items():f[name]=val
    assert a.apply_filter(f).selected.all()


@pytest.fixture(scope='module')
def trained_head(tmp_path_factory):
    """Real LightGBM/calibration, synthetic causal pool and raw price labels."""
    from modelFactory.oracle.build_labels import nyse_sessions
    from unittest.mock import patch
    days=nyse_sessions(pd.Timestamp('2016-01-01').date(),pd.Timestamp('2023-12-29').date())
    root=tmp_path_factory.mktemp('antihead');(root/'directional').mkdir();(root/'chunks/0000').mkdir(parents=True)
    protocol=dict(horizon=10,universe=[f'X{i:02}' for i in range(30)],anti_sl_contract=asdict(a.Contract()),
        directional_contract=dict(feature_mode='compact_volatility',stop_loss_pct=.05),
        training_config=dict(oracle_path_anti_sl_enabled=True))
    atomic_json(root/'protocol.json',protocol);atomic_json(root/'directional/manifest.json',dict(status='COMPLETED'))
    rng=np.random.default_rng(42);pieces=[]
    for symbol in protocol['universe']:
        low=100*(1-rng.uniform(0,.1,len(days)))
        pieces.append(pd.DataFrame(dict(date=days,symbol=symbol,open=100.,high=110.,low=low,close=100.,
            volume=10000.,is_filled=0,instrument_id=1,data_source='alpaca_sip',data_adjustment='raw')))
    bars=pd.concat(pieces,ignore_index=True);bars.to_parquet(root/'chunks/0000/bars.parquet',index=False)
    pd.DataFrame({'date':days,'close':100.,'symbol':'SPY'}).to_parquet(root/'directional/benchmark.parquet',index=False)
    fold=root/'folds/2016-01-04';fold.mkdir(parents=True)
    from modelFactory.oracle_path import SCORE
    pool=bars[['date','symbol']].copy();pool[SCORE]=.5;pool.to_parquet(fold/'oof.parquet',index=False)
    (fold/'path_model.txt').write_text('fixture Oracle weight')
    atomic_json(fold/'done.json',dict(champion=dict(model_file='path_model.txt'),
        metrics=dict(train_available_max='2015-01-01',val_available_max='2015-12-31'),
        files={n:digest(fold/n) for n in ['oof.parquet','path_model.txt']}))
    cfg=SimpleNamespace(data=SimpleNamespace(training_start_date='2016-01-01',training_end_date='2023-12-29'),
        reproducibility=SimpleNamespace(seed=42))
    def panels(g,bench,calendar,**kwargs):
        f=pd.DataFrame({c:np.sin(np.arange(len(g))*.3)+g.low.to_numpy()/100 for c in a.columns()[:29]})
        f['date']=g.date.to_numpy();f['symbol']=g.symbol.to_numpy();return f
    with patch('modelFactory.oracle_path.directional.panels',panels),patch('modelFactory.oracle.security_continuity.load_security_discontinuities',return_value={}):
        manifest=a.train(cfg,root,lambda *args:None)
    return root,manifest,bars


def test_real_training_uses_causal_oof_pool_and_calibration_only(trained_head):
    import joblib
    from modelFactory.oracle_path.directional_metrics import predict
    root,m,_=trained_head
    assert m['features']==a.columns() and len(a.columns())==44 and m['models']
    gate=pd.read_parquet(root/'anti_sl/oof-pool.parquet')
    assert gate.groupby('date').size().eq(3).all()
    panel=pd.read_parquet(root/'anti_sl/training-panel.parquet')
    for r in m['models']:
        assert pd.Timestamp(r['fit_available_max'])<pd.Timestamp(r['year']-1,1,1)
        assert pd.Timestamp(r['available'])<pd.Timestamp(r['year'],1,1)
        cal=panel[panel.date.dt.year.eq(r['year']-1)&panel.available.lt(pd.Timestamp(r['year'],1,1))&panel.first_session_sl.notna()]
        weights=joblib.load(root/r['file'])
        assert weights['model'][-1].n_features_in_==44
        assert r['threshold']==pytest.approx(np.quantile(predict(weights,cal),.9))
    a.load_manifest(root)


def test_saved_scores_read_only_lineage_cutoff_and_corruption(trained_head,tmp_path):
    import shutil
    from sqlalchemy import create_engine,event
    from modelFactory.oracle_path import anti_sl_store as store
    src,m,_=trained_head;root=tmp_path/'model';shutil.copytree(src,root)
    record=m['models'][-1];year=record['year'];day=pd.Timestamp(year,1,3)
    scores=pd.DataFrame({'date':[day],'symbol':['X00']})
    f=pd.read_parquet(root/'anti_sl/training-panel.parquet').tail(1)[['date','symbol',*a.columns()]].copy()
    f['date']=day;f['symbol']='X00';risk=a.score_features(root,scores,f)
    engine=create_engine('sqlite:///'+str(tmp_path/'scores.db'))
    with engine.begin() as conn:store.write(conn,risk,'batch')
    cutoff=datetime.now(timezone.utc)+timedelta(seconds=2)
    got=store.read(engine,root,scores,'batch',cutoff=cutoff)
    assert got.anti_sl_status.tolist()==['SCORED']
    def readonly(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().split()[0].upper() not in ['SELECT','PRAGMA']:
            pytest.fail('Unexpected write in anti-SL reader: '+statement)
    event.listen(engine,'before_cursor_execute',readonly)
    assert store.read(engine,root,scores,'batch',cutoff=cutoff).shape[0]==1
    event.remove(engine,'before_cursor_execute',readonly)
    with pytest.raises(ValueError,match='manquants'):store.read(engine,root,scores,'batch',cutoff=datetime(2000,1,1,tzinfo=timezone.utc))
    corrupt=got.copy();corrupt.anti_sl_threshold=.999
    with pytest.raises(ValueError,match='contrat'):store.validate(root,scores,corrupt)
    with pytest.raises(ValueError,match='incomplets'):store.validate(root,scores,got.drop(columns='anti_sl_probability'))
    (root/record['file']).write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='corrompus'):a.load_manifest(root)


def test_oof_gate_rejects_future_fold_before_fitting(trained_head,tmp_path):
    import shutil
    src,_,_=trained_head;root=tmp_path/'gate';shutil.copytree(src,root)
    p=next((root/'folds').glob('*/done.json'));v=json.loads(p.read_text());v['metrics']['val_available_max']='2024-01-01';atomic_json(p,v)
    with pytest.raises(ValueError,match='in-sample'):a.oof_pool(root,json.loads((root/'protocol.json').read_text()))


def test_ui_flag_default_on_optout_and_command_validation():
    from streamlit.testing.v1 import AppTest
    def app():
        import streamlit as st
        from ihm.components.oracle_path_training_features import render_anti_sl_features
        from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
        horizon=st.selectbox('Horizon',[10,20],key='test_horizon')
        enabled=render_anti_sl_features(True,'compact_volatility',horizon)
        options=PipelineLaunchOptions(ml_oracle_path_model_only=True,ml_oracle_path_directional_enabled=True,
            ml_oracle_path_directional_feature_mode='compact_volatility',ml_oracle_path_anti_sl_enabled=enabled,
            ml_oracle_horizon=horizon,ml_training_start_date='2016-01-01',ml_training_end_date='2023-12-31')
        st.session_state['command']=build_pipeline_command('ml_train',options)
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception and at.checkbox(key='pipeline_ml_path_anti_sl').value
    assert not at.exception and '--oracle-path-anti-sl' in at.session_state['command']
    from modelFactory.cli import build_arg_parser
    assert build_arg_parser().parse_args(at.session_state['command'][4:]).oracle_path_anti_sl
    at.checkbox(key='pipeline_ml_path_anti_sl').uncheck().run(timeout=30)
    assert not at.exception and '--oracle-path-anti-sl' not in at.session_state['command']
    at.selectbox(key='test_horizon').select(20).run(timeout=30)
    assert not at.exception and at.checkbox(key='pipeline_ml_path_anti_sl').disabled
    assert not at.checkbox(key='pipeline_ml_path_anti_sl').value
    at.selectbox(key='test_horizon').select(10).run(timeout=30)
    assert not at.exception and at.checkbox(key='pipeline_ml_path_anti_sl').value
    assert '--oracle-path-anti-sl' in at.session_state['command']
    from modelFactory.config import TrainingConfig
    with pytest.raises(ValueError,match='B29'):TrainingConfig(oracle_path_anti_sl_enabled=True)


def test_backtest_ui_detects_head_and_keeps_its_required_long_ranking(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ihm.components import winner_backtest as ui
    folder=tmp_path/'batch/oracle_path';folder.mkdir(parents=True)
    atomic_json(folder/'report.json',dict(status='completed',serving_ready=True,horizon=10,directional_models=40,anti_sl_models=3))
    protocol=dict(horizon=10,universe=[f'X{i:02}' for i in range(20)],
        training_config=dict(oracle_path_directional_enabled=True,oracle_path_anti_sl_enabled=True),
        directional_contract=dict(oracle_top_n=20,selected_n=5))
    monkeypatch.setattr(ui,'MODEL_ROOT',tmp_path)
    monkeypatch.setattr('ihm.services.queries.get_ml_training_batch_comments',lambda:{})
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *args:(folder,protocol,None,{}))
    monkeypatch.setattr('modelFactory.oracle_path.directional.load_manifest',lambda *args:({},'hash'))
    def app():
        import streamlit as st
        from ihm.components.winner_backtest import render_model_selection
        st.session_state['active']=render_model_selection()[-2]
    at=AppTest.from_function(app);at.session_state['bt_winner_per_symbol_long_batch']=False
    at.run(timeout=30)
    assert not at.exception and at.session_state['active']
    field=at.checkbox(key='bt_winner_per_symbol_long_batch')
    assert field.value and field.disabled and any('anti-SL' in v.value for v in at.info)


def test_anti_batch_cannot_bypass_per_symbol_selection():
    from modelFactory.oracle_path.directional import use_long_selection
    p=dict(training_config=dict(oracle_path_anti_sl_enabled=True,oracle_path_directional_enabled=True))
    with pytest.raises(ValueError,match='anti-SL'):use_long_selection(p,False)
    with pytest.raises(ValueError,match='anti-SL'):a.require_bundle_route(p)
    assert a.require_bundle_route({}) is None


def test_invalid_non_null_risk_is_not_an_abstention():
    f=pd.DataFrame(dict(selected=True,reason='SELECTED_LONG',**flags()))
    f['anti_sl_probability']=f.anti_sl_probability.astype(object)
    f.loc[3,'anti_sl_probability']='invalid'
    with pytest.raises(ValueError,match='invalide'):a.apply_filter(f)


def test_amplitude_only_external_routes_refuse_anti_head_before_sql(monkeypatch):
    from service.options_directional import runner as options
    from service.llm_directional import runner as llm
    from modelFactory.oracle_path import predict as serving
    protocol=dict(training_config=dict(oracle_path_anti_sl_enabled=True))
    monkeypatch.setattr(serving,'load_contract',lambda *args:(None,protocol,None,None))
    monkeypatch.setattr('modelFactory.db_registry.load_symbols_for_source',lambda *args,**kwargs:['ABC'])
    class NoSQL:
        def connect(self):pytest.fail('This route must refuse before reading raw Oracle or provider data')
    with pytest.raises(ValueError,match='anti-SL'):
        options.load_inputs(NoSQL(),batch_id='batch',trade_date='2024-01-02',symbol_source='file',
            capital_preset_key='auto',artifacts_dir='unused',config=None,cutoff=datetime.now(timezone.utc))
    monkeypatch.setattr('modelFactory.oracle.artifact_contract.resolve_oracle_artifact_horizon',lambda *args:10)
    monkeypatch.setattr('modelFactory.oracle_path.train.is_path_batch',lambda *args:True)
    with pytest.raises(ValueError,match='anti-SL'):
        llm.load_inputs(NoSQL(),'batch','2024-01-02','file',SimpleNamespace(horizon=10),'auto')


@pytest.mark.parametrize('active',[False,True])
def test_outer_training_publishes_optional_head_only_after_directional(tmp_path,monkeypatch,active):
    from dataclasses import replace
    from tests.test_oracle_path import config,bars
    from modelFactory.oracle_path import train as trainer,directional as d
    cfg=replace(config(tmp_path/'batch'),oracle_horizon=10,oracle_path_directional_enabled=True,
        oracle_path_directional_feature_mode='compact_volatility',oracle_path_anti_sl_enabled=active)
    symbols=[f'S{i:02}' for i in range(20)]
    pieces=[]
    for i,symbol in enumerate(symbols):
        f=bars(symbol,n=200);f['high']=101+i;f['instrument_id']=i+1;pieces.append(f)
    panel=pd.concat(pieces,ignore_index=True)
    monkeypatch.setattr(trainer,'nyse_sessions',lambda *args:pd.DatetimeIndex(pieces[0].date))
    monkeypatch.setattr(trainer,'load_security_discontinuities',lambda:{})
    monkeypatch.setattr(trainer,'load_bars',lambda *args:panel.copy())
    monkeypatch.setattr(trainer,'build_feature_matrix',lambda engine,names,**kwargs:
        panel[panel.symbol.isin(names)][['date','symbol']].assign(return_1d=.1))
    monkeypatch.setattr(trainer,'feature_columns',lambda *args:['return_1d'])
    monkeypatch.setattr(trainer,'fit_folds',lambda *args:dict(n_folds=1,folds=[]))
    order=[]
    def directions(cfg,engine,root,progress):
        order.append('directional');assert not (root/'report.json').exists()
        atomic_json(root/'directional/manifest.json',dict(status='COMPLETED'))
        return dict(models=[{}],skipped=[])
    def head(cfg,root,progress):
        order.append('anti_sl');assert (root/'directional/manifest.json').is_file()
        assert not (root/'report.json').exists()
        atomic_json(root/'anti_sl/manifest.json',dict(status='COMPLETED'))
        return dict(models=[{}],skipped=[])
    monkeypatch.setattr(d,'train',directions);monkeypatch.setattr(a,'train',head)
    report=trainer.train_oracle_path(cfg,object(),'batch',symbols)
    root=Path(cfg.artifacts_dir)/'oracle_path';protocol=json.loads((root/'protocol.json').read_text())
    assert order==(['directional','anti_sl'] if active else ['directional'])
    if active:
        assert report['anti_sl_manifest_sha256']==digest(root/'anti_sl/manifest.json')
        assert protocol['anti_sl_contract']==asdict(a.Contract()) and report['anti_sl_auto_filter']
    else:
        assert 'oracle_path_anti_sl_enabled' not in protocol['training_config']
        assert 'anti_sl_contract' not in protocol and 'anti_sl_auto_filter' not in report


def test_native_directional_inference_validation_and_reranking_keep_veto(trained_head,tmp_path,monkeypatch):
    import shutil
    from modelFactory.oracle_path import directional as d
    from tests.test_oracle_path_volatility_b import market
    from backtesting.per_symbol_selection import select_per_symbol,PerSymbolSelection
    src,head,_=trained_head;days,bars,bench=market();root=tmp_path/'native';(root/'chunks/0000').mkdir(parents=True)
    bars[bars.date.le('2023-12-31')].to_parquet(root/'chunks/0000/bars.parquet',index=False)
    p=dict(universe=['ABC'],horizon=10,anti_sl_contract=asdict(a.Contract()),
        directional_contract=asdict(d.Settings(enabled=True,feature_mode='compact_volatility')),
        training_config=dict(oracle_path_directional_enabled=True,oracle_path_anti_sl_enabled=True,
            data=dict(training_start_date='2016-01-01',benchmark_symbol='SPY')))
    atomic_json(root/'protocol.json',p)
    cfg=SimpleNamespace(data=SimpleNamespace(training_start_date='2016-01-01',training_end_date='2023-12-31',benchmark_symbol='SPY'),
        reproducibility=SimpleNamespace(seed=42))
    d.train(cfg,None,root,lambda *unused:None,benchmark=bench[bench.date.le('2023-12-31')],years=[2024])
    m=json.loads(json.dumps(head));record=next(r for r in m['models'] if r['year']==2024);record['threshold']=0.
    (root/'anti_sl').mkdir();shutil.copyfile(src/record['file'],root/record['file'])
    m.update(models=[record],oracle_protocol_sha256=digest(root/'protocol.json'),directional_manifest_sha256=digest(root/'directional/manifest.json'))
    atomic_json(root/'anti_sl/manifest.json',m)
    monkeypatch.setattr('modelFactory.data_loader.load_benchmark_bars',lambda *args,**kwargs:bench)
    oracle=pd.DataFrame(dict(date=pd.to_datetime(['2024-01-02','2024-01-03']),symbol='ABC',proba_extreme=.9))
    result=d.infer(None,root,oracle,bar_frame=bars)
    assert result.anti_sl_probability.between(0,1).all() and result.anti_sl_rejected.all() and not result.selected.any()
    checked=d.validate_saved(root,oracle,result.rename(columns={'date':'prediction_date'}))
    assert not checked.selected.any()
    reranked=select_per_symbol(checked,PerSymbolSelection(oracle_top_n=1,long_top_n=1))
    assert not reranked.selected.any() and reranked.anti_sl_rejected.all()


def test_paper_custom_selection_also_applies_head_after_its_own_top(monkeypatch):
    from service.q051_paper.pipeline import rank_selection
    f=pd.DataFrame(dict(date=pd.Timestamp('2024-01-02'),symbol=list('ABCD'),proba_extreme=[.9,.8,.7,.6],
        long_probability=[.9,.8,.7,.6],short_probability=np.nan,**flags()))
    monkeypatch.setattr('backtesting.per_symbol_selection.attach_calibration_auc',lambda x,r:x)
    monkeypatch.setattr('service.q051_paper.pipeline.reference',lambda:dict(selection=dict(oracle_fraction=1.,long_top_n=2,min_long_probability=.5,min_long_auc=None)))
    result,_=rank_selection(f,None,4)
    assert result[result.selected].symbol.tolist()==['B']
