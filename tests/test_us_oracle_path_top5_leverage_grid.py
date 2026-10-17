from functools import partial
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_path_top5_leverage_grid import (
    UnlimitedLedger, MarginAwareSession, configure_leverage, key, planned_cases,
    maintenance_requirement, margin_policy, ResearchMarginExecutionConfig,
)
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def test_grid_has_144_unique_profiles():
    cases=planned_cases()
    assert len(cases)==len(set(map(key,cases)))==144
    assert sum(c[2] is None and c[3] is None for c in cases)==9
    assert {c[0] for c in cases}=={2024,2025,2026}


@pytest.mark.parametrize('sl',[.05,.07,.10])
def test_budget_is_stop_adjusted_but_entry_leverage_never_exceeds_two(sl):
    cfg=frozen_backtest_config(pd.Timestamp('2025-01-01'),pd.Timestamp('2025-02-01'))
    configure_leverage(cfg,sl)
    assert cfg.risk_config.fixed_stop_pct==sl
    assert cfg.risk_config.risk_per_trade_pct/sl==pytest.approx(.4)
    assert cfg.risk_config.max_gross_exposure==2
    assert cfg.exec_config.leverage.max_leverage==2
    assert cfg.exec_config.leverage.min_equity_usd==2000
    assert cfg.exec_config.leverage.disable_in_capital_preservation


def test_interest_accounts_for_weekend_and_only_debit_cash():
    fake=SimpleNamespace(days=pd.to_datetime(['2025-01-03','2025-01-06']),
        current_day=pd.Timestamp('2025-01-03'),study_end=pd.Timestamp('2025-12-31'))
    state=SimpleNamespace(settled_cash=-4000.)
    charge=UnlimitedLedger._accrue_margin_interest(fake,state,annual_rate=.065)
    assert charge==pytest.approx(4000*.065*3/360)
    assert state.settled_cash==pytest.approx(-4000-charge)
    state.settled_cash=2000
    assert UnlimitedLedger._accrue_margin_interest(fake,state,annual_rate=.065)==0


def test_execution_cap_extension_is_isolated_and_preserved_by_replace():
    from dataclasses import replace
    from execution_engine.config import ExecutionConfig
    with pytest.raises(ValueError,match='regime_max_gross'):
        ExecutionConfig(regime_max_gross_exposure=2.)
    cfg=ResearchMarginExecutionConfig(regime_max_gross_exposure=2.)
    assert replace(cfg,entry_mode='capital_preservation',regime_max_gross_exposure=.5).regime_max_gross_exposure==.5
    with pytest.raises(ValueError,match='Research execution cap'):
        replace(cfg,regime_max_gross_exposure=2.01)
    with pytest.raises(ValueError,match='fill_timeout'):
        replace(cfg,fill_timeout_seconds=-1)


def test_open_position_costs_and_interest_reconcile_without_fake_liquidation():
    ledger=SimpleNamespace(unvalued_claims=[],config=SimpleNamespace(initial_equity=4000),
        interest=10,state=SimpleNamespace(closed_trades=[dict(pnl=100)],
            positions={'A':SimpleNamespace(entry_cost=3000)},settled_cash=1090,unsettled_cash=0))
    assert UnlimitedLedger.reconciliation_error(ledger)==0
    ledger.unvalued_claims=[dict(symbol='A')]
    with pytest.raises(ValueError,match='Unvalued'):
        UnlimitedLedger.reconciliation_error(ledger)


def test_maintenance_tiers_and_close_only_margin_action():
    positions={'A':SimpleNamespace(quantity=10,entry_date=pd.Timestamp('2025-01-02')),
               'B':SimpleNamespace(quantity=10,entry_date=pd.Timestamp('2025-01-02')),
               'C':SimpleNamespace(quantity=10,entry_date=pd.Timestamp('2025-01-02'))}
    prices=pd.Series({'A':2.,'B':5.,'C':10.})
    assert maintenance_requirement(positions,prices)==75
    ledger=SimpleNamespace(state=SimpleNamespace(positions=positions),margin_audits=[],equity_unchecked=lambda:74.)
    day=pd.Timestamp('2025-01-03')
    orders=margin_policy(day,ledger,{'close':prices.to_frame().T.set_axis([day])})
    assert ledger.margin_breached
    assert len(orders)==3
    assert all(x['decision_date']==day for x in orders)
    assert all(x['policy_reason']=='MAINTENANCE_MARGIN_FULL_EXIT_NEXT_OPEN' for x in orders)


def simulate(tmp_path,*,trail=None,tp=None):
    frames,scores,macro,days=fixture_data()
    # The same held title remains a candidate every day: no reinforcement.
    scores=pd.concat([scores.assign(date=d) for d in days],ignore_index=True)
    ref=[]
    def factory(cfg,**kwargs):
        ledger=UnlimitedLedger(cfg,sl=.10,trail=trail,tp=tp,study_end=days[-1],events=(),**kwargs)
        ref.append(ledger)
        return ledger
    result=run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},macro=macro,
        market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,ledger_factory=factory,
        session_factory=partial(MarginAwareSession,ledger_ref=ref),
        protection_options=dict(take_profit_enabled=tp is not None,trailing_enabled=trail is not None),
        daily_exit_policy=margin_policy,reject_constrained_entries=True)
    return result,ref[0],pd.read_parquet(tmp_path/'trades.parquet'),days


def test_no_time_exit_no_terminal_sale_and_no_reinforcement(tmp_path):
    result,ledger,trades,days=simulate(tmp_path)
    assert trades.empty
    assert len(ledger.state.positions)==1
    pos=ledger.state.positions['FIXTURE']
    assert pos.entry_date==days[1]
    assert len(days)>21
    assert ledger.terminal_exits_suppressed==1
    assert result['cash_reconciliation_error']==pytest.approx(0,abs=1e-8)
    assert result['return_pct']<0  # even unsold entry has real simulated costs
    # Cash and all existing state remain live throughout the same daily loop.
    assert ledger.state.settled_cash<4000


def test_trailing_retains_initial_stop_and_open_position_after_h20(tmp_path):
    _,ledger,trades,_=simulate(tmp_path,trail=.20)
    assert trades.empty
    assert len(ledger.state.positions)==1
    assert ledger.state.positions['FIXTURE'].replay_initial_stop_price==pytest.approx(90)
