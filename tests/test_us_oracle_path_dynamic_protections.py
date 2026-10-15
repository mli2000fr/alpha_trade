from functools import partial

import numpy as np
import pandas as pd
import pytest

from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_path_dynamic_protections import (
    choose_profile,build_context,ContextLedger,ContextSession,PROFILES,
)
from scripts.research.us_oracle_path_top5_leverage_grid import UnlimitedLedger,margin_policy,MarginAwareSession
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def inputs(**overrides):
    result=dict(vix=15.,spy_close=100.,spy_sma200=90.,spy_ret20=.1,
        breadth50=.8,breadth_coverage=1.,stock_close=100.,stock_sma50=90.,relative_ret20=.1)
    result.update(overrides)
    return result


def test_profiles_and_priority_are_frozen():
    assert PROFILES=={'REFERENCE':(.15,.20),'DEFENSIVE':(.10,.10),'TREND':(.20,.30)}
    assert choose_profile(inputs(),'normal')[0]=='TREND'
    assert choose_profile(inputs(),'capital_preservation')[0]=='DEFENSIVE'
    c=inputs();c['vix']=30
    assert choose_profile(c,'normal')[0]=='DEFENSIVE'
    c=inputs();c['vix']=25
    assert choose_profile(c,'normal')[0]=='REFERENCE'


@pytest.mark.parametrize('field',['vix','spy_sma200','stock_sma50','relative_ret20','breadth50'])
def test_missing_data_never_invents_a_favourable_regime(field):
    c=inputs();c[field]=np.nan
    assert choose_profile(c,'normal')==('REFERENCE','MISSING_INPUT_BASELINE')


def test_coverage_boundary_and_unknown_mode():
    c=inputs();c['breadth_coverage']=.79
    assert choose_profile(c,'normal')[1]=='LOW_BREADTH_COVERAGE_BASELINE'
    c['breadth_coverage']=.8
    assert choose_profile(c,'normal')[0]=='TREND'
    with pytest.raises(ValueError,match='Unknown'):
        choose_profile(c,'invented')


def test_market_trend_alone_does_not_promote_a_weak_stock():
    c=inputs();c['relative_ret20']=-.01
    assert choose_profile(c,'normal')[0]=='REFERENCE'
    c=inputs();c['breadth50']=.39
    assert choose_profile(c,'normal')[0]=='DEFENSIVE'
    c=inputs();c['spy_close']=80;c['breadth50']=.49
    assert choose_profile(c,'normal')[0]=='DEFENSIVE'


def test_context_is_truncation_invariant_and_breadth_is_not_top5():
    from scripts.research.us_oracle_path_top5_leverage_grid import nyse_sessions
    days=nyse_sessions('2023-01-01','2025-01-15')
    day=pd.Timestamp('2025-01-02')
    prices=pd.DataFrame([dict(date=d,symbol=s,close=p,volume=100000,is_filled=0)
        for i,d in enumerate(days) for s,p in [('SPY',100+i*.1),('A',100+i*.2),('B',200-i*.1)]])
    macro=pd.DataFrame({'trade_date':days,'vix':15.})
    candidates=pd.DataFrame({'date':[day],'symbol':['A']})
    original=build_context(prices,macro,['A','B'],candidates)
    assert original.breadth50.iloc[0]==.5  # A up, B down: not 100% TOP1
    assert original.breadth_count.iloc[0]==2
    truncated=build_context(prices[prices.date.le(day)],macro[macro.trade_date.le(day)],['A','B'],candidates)
    pd.testing.assert_frame_equal(original,truncated)
    changed=prices.copy();changed.loc[changed.date.gt(day),'close']=1e9
    altered_macro=macro.copy();altered_macro.loc[altered_macro.trade_date.gt(day),'vix']=99
    pd.testing.assert_frame_equal(original,build_context(changed,altered_macro,['A','B'],candidates))


def simulate(output,*,dynamic,context=None,move=False,native_control=False):
    frames,scores,macro,days=fixture_data()
    context=context if context is not None else pd.DataFrame([dict(date=d,symbol='FIXTURE',**inputs()) for d in days])
    if move:
        frames['high'].loc[days[1],'FIXTURE']=125
        for column,price in [('opens',122),('high',131),('low',121),('close',125)]:
            frames[column].loc[days[2],'FIXTURE']=price
    ref=[]
    def factory(cfg,**kwargs):
        if native_control:
            ledger=UnlimitedLedger(cfg,sl=.05,trail=.15,tp=.20,study_end=days[-1],events=(),**kwargs)
        else:
            ledger=ContextLedger(cfg,context=context,dynamic=dynamic,study_end=days[-1],events=(),**kwargs)
        ref.append(ledger);return ledger
    result=run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},macro=macro,
        market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=output,ledger_factory=factory,
        session_factory=partial(ContextSession if not native_control else MarginAwareSession,ledger_ref=ref),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=True),
        daily_exit_policy=margin_policy,reject_constrained_entries=True)
    return result,ref[0],pd.read_parquet(output/'trades.parquet'),days


def test_disabled_rule_exactly_reproduces_native_control(tmp_path):
    a,_,_,_=simulate(tmp_path/'fixed',dynamic=False)
    b,_,_,_=simulate(tmp_path/'native',dynamic=False,native_control=True)
    assert a['return_pct']==b['return_pct']
    for name in ['trades.parquet','daily.parquet']:
        pd.testing.assert_frame_equal(pd.read_parquet(tmp_path/'fixed'/name),pd.read_parquet(tmp_path/'native'/name))


def test_trend_profile_is_anchored_to_fill_and_never_revised_from_future_context(tmp_path):
    _,_,_,days=fixture_data()
    c=pd.DataFrame([dict(date=d,symbol='FIXTURE',**inputs()) for d in days])
    c.loc[c.date.gt(days[0]),'vix']=99  # future bad regime must not rewrite existing position
    result,ledger,trades,_=simulate(tmp_path,dynamic=True,context=c,move=True)
    assert len(trades)==1
    trade=trades.iloc[0]
    assert trade.entry_date==days[1]
    assert trade.exit_date==days[2]
    assert trade.exit_price==130
    assert trade.replay_initial_stop_price==95
    assert trade.replay_take_profit_price==130
    assert trade.replay_trailing_stop_pct==.20
    audit=ledger.fill_profile_audits[0]
    assert audit['decision_date']==str(days[0].date())
    assert audit['profile']=='TREND'
    assert result['cash_reconciliation_error']==pytest.approx(0,abs=1e-8)


def test_defensive_profile_keeps_hard_sl5(tmp_path):
    _,_,_,days=fixture_data()
    c=pd.DataFrame([dict(date=d,symbol='FIXTURE',**inputs()) for d in days]);c['vix']=30
    _,ledger,_,_=simulate(tmp_path,dynamic=True,context=c)
    p=ledger.protections['FIXTURE'].signals_df.iloc[0]
    assert p.replay_initial_stop_price==95
    assert p.replay_take_profit_price==pytest.approx(110)
    assert p.replay_trailing_stop_pct==.10
