import numpy as np
import pandas as pd
import pytest

from scripts.research import us_tradable_symbol_reliability as s
from scripts.research import us_top10_symbol_reliability as gate
from tests.test_us_top10_symbol_reliability import data


def bars(n=90):
    rng=np.random.default_rng(7)
    opens=100*np.exp(np.cumsum(rng.normal(0,.04,n)))
    close=opens*np.exp(rng.normal(0,.04,n))
    return pd.DataFrame(dict(open=opens,close=close,high=np.maximum(opens,close)*1.1,
        low=np.minimum(opens,close)*.9,volume=1e6,is_filled=0,instrument_id=1,
        data_source='eodhd_eod',data_adjustment='split'),index=pd.bdate_range('2024-01-01',periods=n))


@pytest.mark.parametrize('side',['LONG','SHORT'])
def test_vector_paths_matches_scalar_on_every_row(side):
    b=bars();indices=np.arange(len(b)-20);vector=s.vector_paths(b,indices,side)
    for i in indices:
        scalar=s.barrier_path(b.iloc[i+1:i+21],side)
        assert scalar['path_status']=='QUALIFIED'
        for field,values in vector.items():
            if isinstance(values[i],(float,np.floating)):assert values[i]==pytest.approx(scalar[field])
            else:assert values[i]==scalar[field]


def test_original_order_no_unknown_future_window():
    with pytest.raises(ValueError):s.vector_paths(bars(20),[0],'LONG')


def test_fast_episodes_and_qualification_identical_to_prior_gate():
    f,days=data()
    pd.testing.assert_frame_equal(s.independent_fast(f),gate.independent_episodes(f))
    cut=pd.Timestamp('2025-04-01')
    old,h1=gate.states_at(f,cut,days);new,h2=s.states_fast(f,cut,days)
    pd.testing.assert_frame_equal(old,new)
    pd.testing.assert_frame_equal(h1,h2)


def test_future_mutation_cannot_change_full_universe_membership():
    f,days=data();cut=pd.Timestamp('2025-01-02');a,_=s.states_fast(f,cut,days)
    future=f.last_path_date.ge(cut)
    f.loc[future,'net_outcome']=1000;f.loc[future,'tp_first']=~f.loc[future,'tp_first']
    b,_=s.states_fast(f,cut,days)
    pd.testing.assert_frame_equal(a,b)


def test_current_universe_has_no_top10_or_top20_restriction(tmp_path):
    path=tmp_path/'universe.txt';path.write_text('ZZZ,AAA\nBBB,aaa')
    assert s.symbols_from_file(path)==['AAA','BBB','ZZZ']


def test_causal_quality_rejects_missing_prior_bar_and_not_mature():
    b=bars(90);b.index=pd.bdate_range('2026-06-01',periods=90)
    days=b.index
    raw=b.rename_axis('date').reset_index();raw.loc[10,'is_filled']=1
    _,keep,reasons=s.qualify_symbol(raw,days,np.array([25,75]),[], 'TEST')
    assert len(keep)==0
    assert reasons[0]=='MISSING_OR_INVALID_21_SESSION_CAUSAL_HISTORY'
    assert reasons[1]=='NOT_MATURE_AT_OBSERVATION_END'


def test_known_identity_event_not_treated_as_return():
    b=bars(90);raw=b.rename_axis('date').reset_index()
    _,keep,reasons=s.qualify_symbol(raw,b.index,np.array([30]),
        [dict(source='TEST',target='NEW',day=str(b.index[40].date()))],'TEST')
    assert len(keep)==0 and reasons[0]=='KNOWN_IDENTITY_EVENT_IN_FEATURE_OR_PATH'
