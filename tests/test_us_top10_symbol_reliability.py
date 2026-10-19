import pandas as pd
import pytest

from scripts.research import us_top10_symbol_reliability as s


def data():
    days=pd.bdate_range('2023-01-02','2026-09-30')
    rows=[]
    for i,d in enumerate(days[260:600]):
        for symbol in ['GOOD','BAD']:
            for side in ['LONG','SHORT']:
                win=symbol=='GOOD' and side=='LONG'
                rows.append(dict(date=d,entry_date=days[261+i],last_path_date=days[280+i],
                    symbol=symbol,side=side,tp_first=win,net_outcome=.19 if win else -.071,
                    entry_price=100.,exit_price=120. if win else 93. if side=='LONG' else 107.,
                    exit_session=20,path_return=.2 if win else -.07))
    return pd.DataFrame(rows),days


def test_full_maturity_is_strictly_before_rebalance():
    f,days=data();cut=pd.Timestamp('2024-03-01')
    h=s.matured_history(f,cut,days)
    assert h.last_path_date.lt(cut).all()
    f.loc[0,'last_path_date']=cut
    assert 0 not in s.matured_history(f,cut,days).index


def test_future_values_cannot_change_prior_membership():
    f,days=data();cut=pd.Timestamp('2025-01-02')
    old,_=s.states_at(f,cut,days)
    future=f.last_path_date.ge(cut)
    f.loc[future,'tp_first']=~f.loc[future,'tp_first']
    f.loc[future,'net_outcome']=1000
    new,_=s.states_at(f,cut,days)
    pd.testing.assert_frame_equal(old,new)


def test_same_ticker_repetitions_not_independent_episodes():
    f,days=data();first=f[f.symbol.eq('GOOD')&f.side.eq('LONG')].head(20)
    result=s.independent_episodes(first)
    assert len(result)==1
    changed=first.copy();changed.net_outcome=1000;changed.tp_first=~changed.tp_first
    assert s.independent_episodes(changed).index.tolist()==result.index.tolist()


def test_independent_windows_do_not_overlap():
    f,_=data()
    selected=s.independent_episodes(f)
    for _,g in selected.groupby(['symbol','side']):
        assert (g.entry_date.iloc[1:].to_numpy()>g.last_path_date.iloc[:-1].to_numpy()).all()


def test_stale_history_outside_504_sessions_excluded():
    f,days=data();cut=days[800]
    history=s.matured_history(f,cut,days)
    assert history.date.ge(days[296]).all()


def test_minimum_support_and_bad_stock_not_qualified():
    f,days=data();early,_=s.states_at(f,pd.Timestamp('2024-03-01'),days)
    assert not early.passed.any() and early.qualification.eq('INSUFFICIENT_HISTORY').all()
    late,_=s.states_at(f,pd.Timestamp('2025-04-01'),days)
    assert not late[late.symbol.eq('BAD')].passed.any()
    good=late[late.symbol.eq('GOOD')&late.side.eq('LONG')].iloc[0]
    assert good.passed and good.episodes>=8


def test_unseen_or_both_sides_abstain():
    f=pd.DataFrame(dict(symbol=['A','A','B','B'],side=['LONG','SHORT']*2))
    states=pd.DataFrame(dict(symbol=['A','A'],side=['LONG','SHORT'],passed=[True,True]))
    result=s.apply_states(f,states)
    assert not result.chosen_side.any()


def test_selection_does_not_use_outcomes_and_no_replacement():
    f=pd.DataFrame(dict(symbol=['A','A','B','B'],side=['LONG','SHORT']*2,tp_first=[False]*4))
    states=pd.DataFrame(dict(symbol=['A'],side=['LONG'],passed=[True]))
    result=s.apply_states(f,states)
    f.tp_first=True
    pd.testing.assert_series_equal(result.chosen_side,s.apply_states(f,states).chosen_side)
    assert result[result.chosen_side].symbol.tolist()==['A']


def test_friction_positive_and_borrow_short_only():
    f,_=data();net=s.attach_costs(f)
    assert net.assumed_cost.gt(0).all()
    assert net.loc[net.side.eq('LONG'),'assumed_borrow'].eq(0).all()
    assert net.loc[net.side.eq('SHORT'),'assumed_borrow'].gt(0).all()
    assert net.net_outcome.lt(net.path_return).all()


def test_wilson_is_not_raw_success_fraction():
    assert s.wilson_lower(6,8)<.75
    assert s.wilson_lower(0,8)==pytest.approx(0,abs=1e-12)
    with pytest.raises(ValueError):s.wilson_lower(2,1)
