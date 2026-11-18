"""The experiment adds columns without changing baseline values or future causality."""
import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_path.directional import INPUTS,panels
from scripts.research.us_q051_feature_groups_20261116 import common_panel,GROUPS


def sample():
    dates=pd.bdate_range('2014-01-02',periods=1500)
    rng=np.random.default_rng(17);price=80*np.exp(np.cumsum(rng.normal(.0002,.015,len(dates))))
    benchmark=100*np.exp(np.cumsum(rng.normal(.0002,.01,len(dates))))
    bars=pd.DataFrame(dict(date=dates,symbol='TEST',open=price*.999,high=price*1.02,low=price*.98,
        close=price,adj_close=price,volume=rng.integers(100000,1000000,len(dates)),is_filled=0,
        instrument_id=123,data_source='eodhd_eod',data_adjustment='split'))
    bench=pd.DataFrame(dict(date=dates,close=benchmark,adj_close=benchmark))
    return dates,bars,bench


def test_group_sizes_and_exact_compact_values():
    dates,bars,bench=sample();new=common_panel(bars,bench,dates);old=panels(bars,bench,dates)
    assert len(new)>500
    merged=old.merge(new,on=['date','symbol'],suffixes=('_old','_new'))
    assert len(merged)==len(new)
    for column in INPUTS:
        np.testing.assert_allclose(merged[column+'_old'],merged[column+'_new'],rtol=0,atol=1e-12,equal_nan=True)
    assert {v:len(INPUTS)+len(extra) for v,extra in GROUPS.items()}==dict(T0=24,A=28,B=29)


def test_features_do_not_change_when_future_prices_change():
    dates,bars,bench=sample();cutoff=dates[-100];original=common_panel(bars,bench,dates)
    bars=bars.copy();bench=bench.copy()
    for c in ['open','high','low','close','adj_close']:bars.loc[bars.date.gt(cutoff),c]*=1.5
    bench.loc[bench.date.gt(cutoff),['close','adj_close']]*=.7
    changed=common_panel(bars,bench,dates)
    left=original.loc[original.date.le(cutoff)].reset_index(drop=True)
    right=changed.loc[changed.date.le(cutoff)].reset_index(drop=True)
    pd.testing.assert_frame_equal(left,right,rtol=0,atol=1e-12)


def test_market_preparation_imports_reach_readonly_engine(monkeypatch,tmp_path):
    """Catch the missing EXT import before a long training campaign is needed."""
    from scripts.research import us_q051_feature_groups_replay_20261116 as replay
    from database import connection
    class EngineReached(Exception):pass
    def engine(**kwargs):raise EngineReached
    def frame(path,*args,**kwargs):
        name=str(path)
        if name.endswith('signals.parquet'):return pd.DataFrame({'trade_date':[pd.Timestamp('2021-01-04')],'symbol':['TEST']})
        if name.endswith('sectors.parquet'):return pd.DataFrame({'symbol':['TEST'],'sector':['Technology']})
        if name.endswith('actions.parquet'):return pd.DataFrame()
        return pd.DataFrame({'TEST':[100.,101.]},index=pd.to_datetime(['2021-01-04','2021-01-05']))
    monkeypatch.setattr(replay,'ROOT',tmp_path)
    monkeypatch.setattr(replay.pd,'read_parquet',frame)
    monkeypatch.setattr(connection,'get_sqlalchemy_engine',engine)
    with pytest.raises(EngineReached):replay.prepare_market()


def test_market_preparation_guard_covers_only_its_campaign(monkeypatch,tmp_path):
    from contextlib import contextmanager
    from pathlib import Path
    from scripts.research import us_q051_feature_groups_replay_20261116 as replay
    from database import connection
    from backtesting import isolation
    class EngineReached(Exception):pass
    class Engine:
        def connect(self):raise EngineReached
    roots=[]
    @contextmanager
    def guard(root):
        roots.append(Path(root).resolve())
        yield
    def frame(path,*args,**kwargs):
        name=str(path)
        if name.endswith('signals.parquet'):return pd.DataFrame({'trade_date':[pd.Timestamp('2021-01-04')],'symbol':['TEST']})
        if name.endswith('sectors.parquet'):return pd.DataFrame({'symbol':['TEST'],'sector':['Technology']})
        if name.endswith('actions.parquet'):return pd.DataFrame()
        return pd.DataFrame({'TEST':[100.,101.]},index=pd.to_datetime(['2021-01-04','2021-01-05']))
    monkeypatch.setattr(replay,'ROOT',tmp_path)
    monkeypatch.setattr(replay.pd,'read_parquet',frame)
    monkeypatch.setattr(connection,'get_sqlalchemy_engine',lambda **kwargs:Engine())
    monkeypatch.setattr(isolation,'ReadOnlyReplay',lambda root:type('Guard',(),{'install':lambda self:guard(root)})())
    with pytest.raises(EngineReached):replay.prepare_market()
    assert roots==[tmp_path.resolve()]
