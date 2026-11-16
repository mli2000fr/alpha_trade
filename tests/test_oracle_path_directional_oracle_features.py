from dataclasses import asdict
from types import SimpleNamespace
import json

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_path import directional as d
from modelFactory.oracle_path.directional_features import input_columns,training_matrix
from modelFactory.oracle_path.train import atomic_json,digest


def test_oracle_feature_profile_rank_population_and_leakage_guard(tmp_path):
    columns=['momentum_5','momentum_5_xs_rank']
    atomic_json(tmp_path/'protocol.json',dict(universe=['A','B'],directional_contract={'feature_mode':'oracle'},
        generator_options={'enable_cross_sectional_ranks':True}))
    atomic_json(tmp_path/'feature_profile.json',dict(feature_columns=columns))
    for i,(symbol,value) in enumerate([('A',1.),('B',3.)]):
        path=tmp_path/'chunks'/str(i)/'features.parquet';path.parent.mkdir(parents=True)
        pd.DataFrame([dict(date=pd.Timestamp('2024-01-02'),symbol=symbol,momentum_5=value)]).to_parquet(path,index=False)
        atomic_json(path.parent/'done.json',dict(files={'features.parquet':digest(path)}))
    result=training_matrix(tmp_path).set_index('symbol')
    assert result.loc['A','momentum_5_xs_rank']==.5
    assert result.loc['B','momentum_5_xs_rank']==1.
    assert input_columns(tmp_path)==columns
    atomic_json(tmp_path/'feature_profile.json',dict(feature_columns=['momentum_5','future_return']))
    with pytest.raises(ValueError,match='leaking'):input_columns(tmp_path)


@pytest.mark.filterwarnings('error:.*does not have valid feature names.*:UserWarning')
def test_real_173_models_both_sides_reload_predict_and_preserve_empty_column(tmp_path,monkeypatch):
    import joblib
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle_path.directional_metrics import predict
    days=nyse_sessions(pd.Timestamp('2016-01-01').date(),pd.Timestamp('2024-01-05').date())
    rng=np.random.default_rng(27);close=100*np.exp(np.cumsum(rng.normal(.0002,.025,len(days))))
    bars=pd.DataFrame(dict(date=days,symbol='ABC',open=close,close=close,adj_close=close,
        high=close*1.02,low=close*.98,volume=100000+rng.integers(0,100000,len(days)),
        is_filled=0,instrument_id=1,data_source='alpaca_sip',data_adjustment='raw',vwap=close))
    columns=[f'feature_{i:03}' for i in range(173)]
    values={c:np.sin(np.arange(len(days))/(i+3)) for i,c in enumerate(columns)}
    values[columns[-1]]=np.full(len(days),np.nan)
    frame=pd.DataFrame(dict(date=days,symbol='ABC',**values))
    root=tmp_path/'oracle_path';chunk=root/'chunks/0000';chunk.mkdir(parents=True)
    train_bars=bars[bars.date.le('2023-12-31')];train_bars.to_parquet(chunk/'bars.parquet',index=False)
    atomic_json(root/'feature_profile.json',dict(feature_columns=columns,generator_options={}))
    atomic_json(root/'protocol.json',dict(universe=['ABC'],horizon=10,
        directional_contract=asdict(d.Settings(feature_mode='oracle')),
        training_config=dict(oracle_path_directional_enabled=True,data=dict(benchmark_symbol='SPY',
            training_start_date='2016-01-01',training_end_date='2023-12-31'))))
    cfg=SimpleNamespace(data=SimpleNamespace(training_start_date='2016-01-01',training_end_date='2023-12-31',
        benchmark_symbol='SPY'),reproducibility=SimpleNamespace(seed=42))
    def unavailable(*a,**kw):raise AssertionError('No SQL or provider input needed')
    monkeypatch.setattr('modelFactory.data_loader.load_benchmark_bars',unavailable)
    result=d.train(cfg,None,root,lambda *a:None,oracle_features=frame[frame.date.le('2023-12-31')],
        benchmark=train_bars.assign(symbol='SPY'),years=[2024])
    assert result['features']==columns and len(result['models'])==2
    assert {r['side'] for r in result['models']}=={'long','short'}
    assert d.load_manifest(root)[0]==result
    for record in result['models']:
        weights=joblib.load(root/record['file'])
        assert weights['model'].n_features_in_==173
        assert weights['model'][-1].n_features_in_==173
        assert list(weights['model'][-1].feature_names_in_)==columns
        assert len(predict(weights,frame.iloc[-2:]))==2
    scores=pd.DataFrame(dict(date=pd.to_datetime(['2024-01-02']),symbol='ABC',proba_extreme=.9))
    out=d.infer(None,root,scores,oracle_features=frame,bar_frame=bars)
    assert out.long_probability.between(0,1).all() and out.short_probability.between(0,1).all()
    d.validate_saved(root,scores,out.rename(columns={'date':'prediction_date'}))
    future=frame.copy();future.loc[future.date.gt('2024-01-02'),columns]=1e12
    again=d.infer(None,root,scores,oracle_features=future,bar_frame=bars)
    pd.testing.assert_frame_equal(out,again)
    atomic_json(root/'feature_profile.json',dict(feature_columns=columns[::-1],generator_options={}))
    with pytest.raises(ValueError,match='incompatible|profile'):d.load_manifest(root)
