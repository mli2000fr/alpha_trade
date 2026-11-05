from datetime import timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd

from common.winner_pyramiding import WinnerPyramidingConfig
from common.winner_risk_state import CampaignRiskState
from backtesting.winner_global_liquidation import GlobalLiquidation
from risk_management.config import RiskConfig
from scripts.research.us_selected_universe_winner_dd15_20261104 import (
    Book, entry_terms, confirmation_terms)
import scripts.research.us_selected_universe_winner_dd15_20261104 as study


def tape(values):
    opening=pd.Timestamp('2024-01-03T14:30:00Z').to_pydatetime()
    data=np.ones((2,78,1,5))*100
    data[0,:,:,1]=101.
    data[1,:,0,3]=values
    return SimpleNamespace(smap={'AAA':0},opens=[opening-timedelta(days=1),opening],
        counts=[78,78],complete=np.ones((2,1),bool),values=data)


def test_native_confirmation_delay_and_causal_next_open():
    values=np.array([100.,102.,103.]+[104.]*75)
    t=tape(values)
    policy=WinnerPyramidingConfig(confirmation_bars=2,market_data_delay_seconds=930)
    assert confirmation_terms(t,1,5,'AAA',policy) is None
    terms=confirmation_terms(t,1,6,'AAA',policy)
    assert terms['decided_at']==pd.Timestamp('2024-01-03T15:00:30Z')
    assert terms['fill_k']==7
    assert terms['ceiling']==104.03
    assert pd.Timestamp(terms['evidence_last_end'])==pd.Timestamp('2024-01-03T14:45Z')


def test_confirmation_is_breakout_not_two_increases_below_prior_high():
    t=tape(np.array([97.,98.,99.]+[99.]*75))
    p=WinnerPyramidingConfig(confirmation_bars=2,market_data_delay_seconds=930)
    assert confirmation_terms(t,1,6,'AAA',p) is None


def test_future_bar_does_not_change_earlier_confirmation():
    t=tape(np.array([100.,102.,103.]+[104.]*75))
    p=WinnerPyramidingConfig(confirmation_bars=2,market_data_delay_seconds=930)
    a=confirmation_terms(t,1,6,'AAA',p)
    t.values[1,3:,0,3]=1000.
    assert confirmation_terms(t,1,6,'AAA',p)==a


def test_no_retroactive_fill_at_last_observed_open():
    t=tape(np.array([100.,102.,103.]+[104.]*75))
    p=WinnerPyramidingConfig(confirmation_bars=2,market_data_delay_seconds=930)
    assert confirmation_terms(t,1,77,'AAA',p) is None


def test_allocation_scale_keeps_cash_and_integer_sizing():
    assert entry_terms(4000.,4000.,100.,1.)==8
    assert entry_terms(4000.,4000.,100.,.1)==0 # below minimum notional at this price
    assert entry_terms(4000.,4000.,10.,.1)==9
    assert entry_terms(4000.,30.,10.,1.)==0


def test_native_b4_liquidates_half_worst_positions_not_half_quantity():
    cfg=RiskConfig(account_equity=4000.,max_portfolio_drawdown_pct=.15,policy='b4')
    seed=pd.Timestamp('2024-01-02').date()
    guard=CampaignRiskState(cfg,observations=[(seed,4000.)],regimes={seed:'BULL'})
    book=Book()
    for i,s in enumerate('ABCD'):
        book.holdings[s]=dict(quantity=1,price=100.)
        book.marks[s]=70.+i
    l=GlobalLiquidation(SimpleNamespace(initial_equity=4000.),cfg,
        SimpleNamespace(force_close_on_breaker=True,force_close_pct=.5))
    evaluated=guard.evaluate(seed,3399.,'BULL',daily_pnl=-601.)
    l.observe(pd.Timestamp('2024-01-02T15:00Z').to_pydatetime(),3399.,book,evaluated)
    assert l.pending['symbols']==['A','B']
    assert l.pending['force_close_pct']==.5 and not l.halted
    assert evaluated['allocation_scale']<=.1


def test_b4_intraday_observations_do_not_count_as_favorable_days():
    cfg=RiskConfig(account_equity=4000.,max_portfolio_drawdown_pct=.15,policy='b4')
    seed=pd.Timestamp('2024-01-02').date()
    guard=CampaignRiskState(cfg,observations=[(seed,4000.)],regimes={seed:'BULL'})
    guard.evaluate(seed,3300.,'BULL',daily_pnl=-700.)
    for _ in range(40):guard.evaluate(seed,3350.,'BULL',daily_pnl=-650.)
    assert guard.data['episode']['favorable_streak']==0


def replay_tape():
    cal=pd.DatetimeIndex(['2023-12-29','2024-01-02','2024-01-03','2024-01-04','2024-01-05'])
    days=cal[1:]
    values=np.tile([100.,105.,99.,100.,1000.],(4,78,1,1))
    values[0,:,:,1]=101.
    values[1,1,0,3]=102.;values[1,2,0,3]=103.
    return SimpleNamespace(calendar=cal,days=days,global_index=np.arange(1,5),
        opens=[pd.Timestamp(str(d.date())+'T14:30Z').to_pydatetime() for d in days],
        smap={'AAA':0},counts=np.array([78]*4),complete=np.ones((4,1),bool),values=values,
        regimes=pd.Series(['BULL']*len(cal),index=cal),
        risk=RiskConfig(account_equity=4000.,policy='b4',max_portfolio_drawdown_pct=.15),
        native_policy=WinnerPyramidingConfig(confirmation_bars=2,market_data_delay_seconds=930),
        top={'winner_h10':{days[0]:[dict(symbol='AAA',oracle_rank=1,score=.9)]}},
        quality={('winner_h10',1,'AAA'):True})


def test_small_full_replay_and_sealed_resume(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'OUT',tmp_path)
    t=replay_tape()
    r=study.run_case(t,'winner_h10','2024','BASE')
    assert r['buys']==1 and r['final_positions']==1 and r['closed_trades']==0
    assert r['dd15'] is False and r['liquidation']['enabled'] is False
    assert study.run_case(t,'winner_h10','2024','BASE')==r


def test_full_confirmation_replay_fills_only_after_evidence_delay(tmp_path,monkeypatch):
    import json
    monkeypatch.setattr(study,'OUT',tmp_path)
    t=replay_tape()
    r=study.run_case(t,'winner_h10','2024','WINNER_DD15')
    assert r['buys']==1 and r['dd15'] and r['confirmation']
    orders=json.loads((tmp_path/'runs/winner_h10/2024/WINNER_DD15/confirmation-orders.json').read_text())
    filled=[o for o in orders if o['status']=='FILLED']
    assert len(filled)==1
    assert pd.Timestamp(filled[0]['fill_time'])>=pd.Timestamp('2024-01-03T15:05Z')
    assert filled[0]['fill_price']<=filled[0]['ceiling']
