import numpy as np
import pandas as pd
import pytest

from scripts.research import us_tradable_tp10_variants as s
from scripts.research import us_tradable_symbol_reliability as base
from tests.test_us_tradable_symbol_reliability import bars


def flat():
    b=bars(21);b[['open','close']]=100.;b.high=101.;b.low=99.
    return b


@pytest.mark.parametrize('side',['LONG','SHORT'])
def test_previous_tp20_sl7_contract_preserved(side):
    b=bars();positions=np.arange(len(b)-20)
    expected=base.vector_paths(b,positions,side);actual=s.paths(b,positions,side,tp=.2,sl=.07)
    for k in expected:np.testing.assert_equal(actual[k],expected[k])


@pytest.mark.parametrize('side',['LONG','SHORT'])
def test_tp10_sl10_collision_stop_first(side):
    b=flat();b.loc[b.index[1],['high','low']]=[115.,85.]
    r=s.paths(b,[0],side,tp=.1,sl=.1)
    assert r['sl_first'][0] and r['ambiguity'][0]
    assert r['path_return'][0]==pytest.approx(-.1)


@pytest.mark.parametrize('side',['LONG','SHORT'])
def test_no_stop_can_recover_after_large_adverse_move(side):
    b=flat();b.loc[b.index[2],['open','high','low','close']]=[80.,81.,75.,80.] if side=='LONG' else [120.,125.,119.,120.]
    b.loc[b.index[5],['high','low']]=[115.,99.] if side=='LONG' else [101.,85.]
    stopped=s.paths(b,[0],side,tp=.1,sl=.1);free=s.paths(b,[0],side,tp=.1,sl=None)
    assert stopped['sl_first'][0] and free['tp_first'][0]
    assert free['path_return'][0]==pytest.approx(.1)
    assert free['mae_before_exit_bar'][0]==pytest.approx(.25)
    assert not free['sl_first'][0] and not free['ambiguity'][0]


@pytest.mark.parametrize('side',['LONG','SHORT'])
def test_no_stop_expires_day20_at_close_with_large_loss(side):
    b=flat();b.loc[b.index[-1],['open','high','low','close']]=[50.,51.,49.,50.] if side=='LONG' else [250.,251.,249.,250.]
    r=s.paths(b,[0],side,tp=.1,sl=None)
    assert r['outcome'][0]=='TIMEOUT' and r['exit_session'][0]==20
    assert r['path_return'][0]==pytest.approx(-.5 if side=='LONG' else -1.5)


def test_gap_stop_can_exceed_ten_percent():
    b=flat();b.loc[b.index[2],['open','high','low','close']]=[75.,76.,70.,75.]
    r=s.paths(b,[0],'LONG',tp=.1,sl=.1)
    assert r['gap_stop'][0] and r['path_return'][0]==pytest.approx(-.25)
    assert r['mae_through_exit_bar'][0]==pytest.approx(.25)  # low70 is AFTER exit open


def test_open_tp_precedes_intraday_opposite_barrier():
    b=flat();b.loc[b.index[2],['open','high','low','close']]=[115.,120.,80.,90.]
    r=s.paths(b,[0],'LONG',tp=.1,sl=.1)
    assert r['tp_first'][0] and not r['ambiguity'][0]
    assert r['exit_price'][0]==pytest.approx(110.)
    assert r['mae_through_exit_bar'][0]<.1


@pytest.mark.parametrize('side,column,value,expected',[
    ('LONG','high',110.,'TP'),('SHORT','low',90.,'TP'),
    ('LONG','low',90.,'SL'),('SHORT','high',110.,'SL')])
def test_exact_ten_percent_touch_counts(side,column,value,expected):
    b=flat();b.loc[b.index[1],column]=value
    r=s.paths(b,[0],side,tp=.1,sl=.1)
    assert r['outcome'][0]==expected and r['exit_session'][0]==1


def test_no_stop_exact_tp_touch_counts():
    b=flat();b.loc[b.index[1],'high']=110.
    assert s.paths(b,[0],'LONG',tp=.1,sl=None)['tp_first'][0]


@pytest.mark.parametrize('tp,sl',[(0,.1),(.1,0),(.1,-.1),(1,.1)])
def test_invalid_parameters_rejected(tp,sl):
    with pytest.raises(ValueError):s.paths(flat(),[0],'LONG',tp=tp,sl=sl)
