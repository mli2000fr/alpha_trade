import numpy as np
import pytest
from scripts.research import us_top10_confirmation_protection_grid as s
from tests.test_us_top10_three_session_confirmation import fixture


def test_grid_bounded_unique_reference_included():
    g=s.profiles(); assert len(g)==16 and g['TP10_SL5']==dict(tp=.10,sl=.05)
    assert len({tuple(p.values()) for p in g.values()})==16


@pytest.mark.parametrize('side,change,expected',[
    ('LONG',dict(high=106),105.),('SHORT',dict(low=94),95.)])
def test_tp5_applies_both_sides(side,change,expected):
    f=fixture()
    for col,value in change.items(): f.loc[f.index[4],col]=value
    r=s.execute(f,[1],side,dict(tp=.05,sl=.10)); assert r['exit_price'][0]==expected and r['tp_first'][0]


def test_wider_sl_not_reusing_reference_outcome():
    f=fixture(); f.loc[f.index[4],'low']=94; f.loc[f.index[5],'high']=111
    a=s.execute(f,[1],'LONG',dict(tp=.1,sl=.05)); b=s.execute(f,[1],'LONG',dict(tp=.1,sl=.10))
    assert a['sl_first'][0] and b['tp_first'][0]
    assert a['entry_price'][0]==b['entry_price'][0]==100


def selection_rows():
    return [dict(year=2024,profile=name,arm=arm,n=20,mean_net=float(i))
        for arm in s.MAIN_ARMS for i,name in enumerate(s.profiles())]


def test_selection_never_uses_test_year_winner():
    rows=selection_rows(); before=s.select_2024(rows,s.profiles())
    poison=[dict(year=2026,profile='TP5_SL3',arm=arm,n=999,mean_net=99999) for arm in s.MAIN_ARMS]
    assert before==s.select_2024(rows+poison,s.profiles())
    assert before['CONFIRMED_LONG']['profile']=='TP20_SL10'


def test_tie_prefers_smaller_stop_then_smaller_tp():
    rows=selection_rows()
    for row in rows: row['mean_net']=0.
    assert all(v['profile']=='TP5_SL3' for v in s.select_2024(rows,s.profiles()).values())


def test_incomplete_selection_grid_is_rejected():
    with pytest.raises(ValueError): s.select_2024(selection_rows()[1:],s.profiles())


def test_gap_stop_not_capped_by_grid_stop():
    f=fixture(); f.iloc[5,f.columns.get_indexer(['open','high','low','close'])]=[80,81,79,80]
    r=s.execute(f,[1],'LONG',dict(tp=.2,sl=.1))
    assert r['exit_price'][0]==80 and r['gap_stop'][0] and r['path_return'][0]==pytest.approx(-.2)


def test_same_j_plus_three_entry_and_j_plus_twelve_expiry_for_all_profiles():
    f=fixture(); f.iloc[13,f.columns.get_indexer(['open','high','low','close'])]=[100,102,99,101]
    for protection in s.profiles().values():
        r=s.execute(f,[1],'LONG',protection)
        assert r['entry_price'][0]==100 and r['exit_price'][0]==101 and r['exit_session'][0]==10


def test_atr20_known_only_through_j_plus_two():
    f=fixture(); old,reason=s.atr20_at_confirmation(f,[20]); assert reason[0]==''
    f.loc[f.index[23]:,['open','high','low','close']]*=10
    new,_=s.atr20_at_confirmation(f,[20]); np.testing.assert_array_equal(old,new)
    assert old[0]==2.


def test_atr_caps_and_two_to_one_reward_risk():
    take,stop=s.atr_distances([.1,2.,20.],[100.,100.,100.],s.atr_profiles()['ATR1.5_RR2'])
    np.testing.assert_allclose(stop,[.03,.03,.10]); np.testing.assert_allclose(take,stop*2)


def test_atr_history_rejects_missing_or_changed_source():
    f=fixture(); f.loc[f.index[5],'is_filled']=1
    atr,reason=s.atr20_at_confirmation(f,[20]); assert np.isnan(atr[0]) and reason[0]!=''
    f=fixture(); f.loc[f.index[5],'data_source']='other'
    atr,reason=s.atr20_at_confirmation(f,[20]); assert np.isnan(atr[0]) and reason[0]!=''


@pytest.mark.parametrize('side',['LONG','SHORT'])
def test_variable_path_exact_parity_with_fixed_contract(side):
    from tests.test_us_tradable_symbol_reliability import bars
    f=bars(80); pos=np.arange(1,65)
    for spec in s.profiles().values():
        a=s.execute(f,pos,side,spec); b=s.variable_paths(f,pos,side,np.full(len(pos),spec['tp']),np.full(len(pos),spec['sl']))
        for k,v in a.items(): np.testing.assert_array_equal(v,b[k])


def test_selection_supports_both_families_without_test_data():
    grid={**s.profiles(),**s.atr_profiles()}
    rows=[dict(year=2024,arm=arm,profile=name,n=20,mean_net=float(i)) for arm in s.MAIN_ARMS for i,name in enumerate(grid)]
    selected=s.select_2024(rows,grid)
    assert all(v['profile']=='ATR2_RR2' for v in selected.values())
