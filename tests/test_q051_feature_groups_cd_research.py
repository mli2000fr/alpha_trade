"""C/D continuation preserves the reference inputs, history and price tape."""
import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_path.directional import INPUTS
from scripts.research import us_q051_feature_groups_20261116 as first
from scripts.research import us_q051_feature_groups_cd_20261116 as cd


def sample():
    dates=pd.bdate_range('2014-01-02',periods=1500);rng=np.random.default_rng(19)
    prices=80*np.exp(np.cumsum(rng.normal(.0002,.015,len(dates))))
    benchmark=100*np.exp(np.cumsum(rng.normal(.0003,.01,len(dates))))
    bars=pd.DataFrame(dict(date=dates,symbol='TEST',open=prices*.998,high=prices*1.02,low=prices*.98,
        close=prices,adj_close=prices,volume=rng.integers(100000,1000000,len(dates)),is_filled=0,
        instrument_id=123,data_source='eodhd_eod',data_adjustment='split'))
    return dates,bars,pd.DataFrame(dict(date=dates,close=benchmark,adj_close=benchmark))


def test_additions_preserve_exact_reference_values_and_dates():
    dates,bars,bench=sample();actual=cd.common_panel(bars,bench,dates);expected=first.common_panel(bars,bench,dates)
    pd.testing.assert_frame_equal(actual[expected.columns],expected,rtol=0,atol=1e-12)
    assert len(actual)>500
    assert {k:len(INPUTS)+len(v) for k,v in cd.GROUPS.items()}==dict(C=27,D=28)
    assert np.isfinite(actual[[*cd.GROUPS['C'],*cd.GROUPS['D']]]).all().all()


def test_future_price_changes_leave_past_cd_features_unchanged():
    dates,bars,bench=sample();cutoff=dates[-100];original=cd.common_panel(bars,bench,dates)
    for c in ['open','high','low','close','adj_close']:bars.loc[bars.date.gt(cutoff),c]*=1.7
    bench.loc[bench.date.gt(cutoff),['close','adj_close']]*=.6
    changed=cd.common_panel(bars,bench,dates)
    pd.testing.assert_frame_equal(original[original.date.le(cutoff)].reset_index(drop=True),
        changed[changed.date.le(cutoff)].reset_index(drop=True),rtol=0,atol=1e-12)


def test_old_empty_price_responses_are_not_requeried(monkeypatch):
    monkeypatch.setattr(cd,'read',lambda path:dict(requested=['KNOWN_EMPTY']))
    assert cd.missing_pairs('2021-01-04',{'KNOWN_EMPTY','PRESENT','NEW'}, {'PRESENT':None})==['NEW']


def test_preparation_imports_reach_only_readonly_engine(monkeypatch,tmp_path):
    from database import connection
    class EngineReached(Exception):pass
    def engine(**kwargs):raise EngineReached
    def frame(path,*args,**kwargs):
        name=str(path)
        if name.endswith('signals.parquet'):return pd.DataFrame({'trade_date':[pd.Timestamp('2021-01-04')],'symbol':['TEST']})
        if name.endswith('sectors.parquet'):return pd.DataFrame({'symbol':['TEST'],'sector':['Technology']})
        if name.endswith('actions.parquet'):return pd.DataFrame()
        return pd.DataFrame({'TEST':[100.,101.]},index=pd.to_datetime(['2021-01-04','2021-01-05']))
    monkeypatch.setattr(cd,'ROOT',tmp_path);monkeypatch.setattr(cd.pd,'read_parquet',frame)
    monkeypatch.setattr(connection,'get_sqlalchemy_engine',engine)
    with pytest.raises(EngineReached):cd.prepare_market()
