from dataclasses import replace
from functools import partial

import numpy as np
import pandas as pd
import pytest

from backtesting.oracle_portfolio_session import OraclePortfolioSession
from backtesting.execution_replay import _build_synthetic_fill_attempts
from backtesting.trading_constraints import TradingConstraintConfig
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_short_replay import (
    SHORT_SCORE, ShortLedger, ShortSession, freeze_short_candidates, verify_short_trades,
)
from service.market import parse_market_regimes
from service.market.models import neutral_snapshot

D1, D2, D3 = map(pd.Timestamp, ['2025-01-02','2025-01-03','2025-01-06'])


@pytest.mark.parametrize('quantity',[1,2,9,17,23,55,117,1001])
def test_synthetic_short_partial_fills_are_whole_and_sum_to_approved(quantity):
    attempts = _build_synthetic_fill_attempts(execution_day=D2,target_qty=quantity,
        symbol='TEST',whole_shares=True)
    assert all(a.filled_qty==int(a.filled_qty) for a in attempts)
    assert sum(a.filled_qty for a in attempts)==quantity
    assert attempts[-1].cumulative_filled_qty==quantity


def test_synthetic_short_cannot_fill_a_fractional_target():
    with pytest.raises(ValueError,match='whole-share'):
        _build_synthetic_fill_attempts(execution_day=D2,target_qty=9.5,whole_shares=True)


def setup():
    days = pd.bdate_range(end=D3,periods=30)
    close = pd.DataFrame({'FIXTURE':100.},index=days)
    cfg = frozen_backtest_config(D1,D3)
    cfg.risk_config = cfg.risk_config.with_overrides(min_breakout_days=1,min_position_notional=0)
    ledger = ShortLedger(cfg,opens=close.copy(),close=close.copy(),high=close+1,
        low=close-1,volume=close*10000,sector_map={'FIXTURE':'Technology'},events=())
    session = ShortSession(cfg.risk_config,sector_map=ledger.sectors,account_long_only=False)
    return ledger,session


def decide(ledger,session,day,regime=None):
    ledger.mark_close()
    return session.decide(day.date(),scores=pd.DataFrame([
        dict(trade_date=day,symbol='FIXTURE',proba_extreme=.9)]),snapshot=ledger.snapshot(),
        regime=regime or replace(neutral_snapshot(day.date()),allowed_short_entries=True),close=ledger.close,
        high=ledger.high,low=ledger.low,volume=ledger.volume)


def opened_fixture():
    ledger,session = setup()
    ledger.begin_day(D1)
    approved = [e for e in decide(ledger,session,D1) if e.approved_shares>0]
    assert len(approved)==1 and approved[0].side=='sell'
    assert approved[0].approved_shares == int(approved[0].approved_shares)
    ledger.finish_day()
    ledger.begin_day(D2)
    _,opened = ledger.execute_approved(approved,execution_config=ledger.config.exec_config)
    assert opened==['FIXTURE']
    return ledger,session


def test_short_ranking_uses_only_short_head_and_stable_tie_break():
    frame = pd.DataFrame([dict(date=D1,symbol=f'S{i:02}',**{SHORT_SCORE:.9 if i<12 else .1},
        proba_long_tp_before_sl=1.,future_return=999.) for i in reversed(range(20))])
    selected = freeze_short_candidates(frame,10)
    assert selected.symbol.tolist()==[f'S{i:02}' for i in range(10)]
    assert selected.selection_rank.tolist()==list(range(1,11))
    assert 'future_return' not in selected and 'proba_long_tp_before_sl' not in selected
    assert selected.proba_extreme.tolist()==pytest.approx([1-i/20 for i in range(10)])


@pytest.mark.parametrize('value',[np.nan,np.inf,-.1,1.1])
def test_invalid_short_score_rejected(value):
    with pytest.raises(ValueError):
        freeze_short_candidates(pd.DataFrame([dict(date=D1,symbol='X',**{SHORT_SCORE:value})]),10)


def test_short_account_and_feature_gates_remain_enforced():
    ledger,session = setup()
    with pytest.raises(ValueError,match='SHORT'):
        OraclePortfolioSession(session.config,sector_map=ledger.sectors,account_long_only=True,strategy_side='sell')
    with pytest.raises(ValueError,match='SHORT'):
        ShortSession(session.config.with_overrides(short_selling_enabled=False),
            sector_map=ledger.sectors,account_long_only=False)
    cfg = ledger.config
    cfg.trading_constraints = TradingConstraintConfig(account_type='cash')
    with pytest.raises(ValueError,match='margin'):
        ShortLedger(cfg,opens=ledger.opens,close=ledger.close,high=ledger.high,low=ledger.low,
            volume=ledger.volume,sector_map=ledger.sectors)


def test_regime_can_block_forced_short_entries():
    ledger,session = setup()
    ledger.begin_day(D1)
    regime = replace(neutral_snapshot(D1.date()),allowed_short_entries=False)
    assert not any(e.approved_shares>0 for e in decide(ledger,session,D1,regime))


def test_short_sale_credit_liability_cover_orders_and_fixed_barriers():
    ledger,session = opened_fixture()
    p = ledger.state.positions['FIXTURE']
    assert p.replay_initial_stop_price==pytest.approx(110.)
    assert p.replay_take_profit_price==pytest.approx(80.)
    assert p.quantity==int(p.quantity)
    assert ledger.state.settled_cash>4000.
    ledger.mark_close()
    snapshot = ledger.snapshot()
    assert snapshot.account.equity<4000.  # Sale proceeds are not profit.
    assert snapshot.positions[0].side=='short'
    assert all(o.side=='buy' for o in snapshot.open_orders)
    session.record_fill('entry',day=D2.date(),symbol='FIXTURE',entry=True)
    session.record_fill('loss',day=D2.date(),symbol='FIXTURE',entry=False,realized_pnl=-10.)
    assert session.trades.to_summary()['total_entries']==1


@pytest.mark.parametrize('opening,reason,fill',[
    (120.,'initial_stop_gap_open',120.),(70.,'take_profit_gap_limit',80.),
])
def test_short_held_open_gap_has_priority_over_intraday_collision(opening,reason,fill):
    ledger,_ = opened_fixture()
    assert ledger.apply_observed_protections(phase='intraday')==[]
    ledger.mark_close(); ledger.finish_day()
    ledger.opens.at[D3,'FIXTURE']=opening
    ledger.high.at[D3,'FIXTURE']=125.
    ledger.low.at[D3,'FIXTURE']=65.
    ledger.begin_day(D3)
    closed = ledger.apply_observed_protections(phase='open')
    assert len(closed)==1 and closed[0]['exit_reason']==reason
    assert closed[0]['exit_price']==pytest.approx(fill)
    assert closed[0]['entry_notional_return_pct']==pytest.approx(100*(1-fill/100))
    assert closed[0]['borrow_cost']>0
    ledger.mark_close(); ledger.finish_day()
    assert ledger.reconciliation_error()==pytest.approx(0.,abs=1e-9)


@pytest.mark.parametrize('high,low,reason,fill',[(101.,79.,'take_profit',80.),
    (111.,99.,'initial_stop',110.),(111.,79.,'initial_stop',110.)])
def test_short_intraday_barriers_and_conservative_collision(high,low,reason,fill):
    ledger,_ = opened_fixture()
    ledger.high.at[D2,'FIXTURE']=high; ledger.low.at[D2,'FIXTURE']=low
    assert ledger.apply_observed_protections(phase='open')==[]
    closed = ledger.apply_observed_protections(phase='intraday')
    assert len(closed)==1 and closed[0]['exit_reason']==reason
    assert closed[0]['exit_price']==pytest.approx(fill)
    ledger.mark_close(); ledger.finish_day()
    assert ledger.reconciliation_error()==pytest.approx(0.,abs=1e-9)


def test_future_low_does_not_cause_short_tp_early():
    ledger,_ = opened_fixture()
    ledger.low.at[D3,'FIXTURE']=1.
    assert ledger.apply_observed_protections(phase='intraday')==[]
    assert 'FIXTURE' in ledger.state.positions


def test_fractional_entry_rejected_before_account_mutation():
    ledger,session = setup()
    ledger.begin_day(D1)
    entries = [e for e in decide(ledger,session,D1) if e.approved_shares>0]
    ledger.finish_day(); ledger.begin_day(D2)
    fractional = [replace(entries[0],approved_shares=entries[0].approved_shares+.5)]
    with pytest.raises(ValueError,match='Fractional'):
        ledger.execute_approved(fractional,execution_config=ledger.config.exec_config)
    assert not ledger.state.positions and ledger.state.settled_cash==4000.


def test_short_unknown_exchange_obligation_blocks_without_inventing_a_cash_flow():
    ledger,_ = opened_fixture()
    ledger.mark_close(); ledger.finish_day()
    ledger.ca_events=(dict(day=str(D3.date()),source='FIXTURE'),)
    with pytest.raises(ValueError,match='liability'):
        ledger.begin_day(D3)
    assert 'FIXTURE' in ledger.state.positions


def test_whole_share_partial_cover_preserves_remainder_and_reconciles():
    ledger,_ = opened_fixture()
    q = ledger.state.positions['FIXTURE'].quantity
    requested = q/2+.1
    closed = ledger.close_resolved([dict(symbol='FIXTURE',exit_date=D2,exit_price=100.,
        exit_reason='regime_reduce',quantity=requested)],phase='open')
    assert closed[0]['quantity']==int(requested)
    assert ledger.state.positions['FIXTURE'].quantity==q-int(requested)
    assert ledger.whole_share_reductions[0]['executed']==int(requested)
    ledger.mark_close(); ledger.finish_day(); ledger.begin_day(D3)
    ledger.close_resolved([dict(symbol='FIXTURE',exit_date=D3,exit_price=100.,
        exit_reason='regime_liquidate')],phase='open')
    ledger.mark_close(); ledger.finish_day()
    assert ledger.reconciliation_error()==pytest.approx(0.,abs=1e-9)


@pytest.mark.parametrize('allow_normal',[False,True])
def test_native_short_expiry_and_independent_trade_audit(tmp_path,allow_normal):
    days = pd.bdate_range('2024-01-01','2025-02-05')
    close = pd.DataFrame({'FIXTURE':100.,'SPY':100.},index=days)
    frames = dict(opens=close.copy(),close=close,high=close+1,low=close-1,volume=close*10000)
    trading = days[days>='2025-01-02']
    scores = pd.DataFrame([dict(date=trading[0],symbol='FIXTURE',proba_extreme=.9,selected=True)])
    macro = ArchivedMacro(pd.DataFrame({'trade_date':trading,'sentiment_score':0.}))
    result = run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},
        macro=macro,market_config=parse_market_regimes({'enabled':False}),policy='selected',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,start_date=str(trading[0].date()),
        session_factory=ShortSession,ledger_factory=partial(ShortLedger,events=()),
        expiry_open_sessions=20,protection_options=dict(take_profit_enabled=True,trailing_enabled=False),
        research_allow_short_normal=allow_normal)
    trades = pd.read_parquet(tmp_path/'trades.parquet')
    if not allow_normal:
        assert trades.empty and result['return_pct']==0 and not result['research_allow_short_normal']
        return
    assert len(trades)==1 and trades.entry_date.iloc[0]==trading[1]
    assert trades.exit_date.iloc[0]==trading[21] and trades.exit_reason.iloc[0]=='expiry_open'
    prices = close.stack().rename('close').reset_index().rename(columns={'level_0':'date','level_1':'symbol'})
    prices['open']=prices.close; prices['high']=prices.close+1; prices['low']=prices.close-1
    audit = verify_short_trades(trades,prices,days,.20,.10,.003)
    assert audit['closed_positions']==1 and audit['losing']==1
    assert audit['borrow_usd']>0 and result['cash_reconciliation_error']==pytest.approx(0.,abs=1e-9)
    with pytest.raises(ValueError,match='borrow'):
        verify_short_trades(trades,prices,days,.20,.10,.01)
