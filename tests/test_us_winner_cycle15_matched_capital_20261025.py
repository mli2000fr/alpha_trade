from dataclasses import asdict,replace
from datetime import date

import pandas as pd
import pytest

from scripts.research import us_winner_cycle15_matched_capital_20261025 as study
from tests.test_winner_global_liquidation import data_with_global_drawdown


def test_only_capital_changes_and_all_risk_exit_rules_stay_frozen(monkeypatch):
    cfg,_,_=data_with_global_drawdown()
    monkeypatch.setattr(study.cycle,'BASE_CONFIGURATION',lambda *_:cfg)
    before=study.cycle.configuration({},date(2020,1,2))
    after=study.matched_configuration({},date(2020,1,2),7980.1667511581745)
    study.verify_capital_only(before,after,7980.1667511581745)
    assert after.winner_cycle_drawdown_pct==.15 and after.winner_hard_drawdown_pct is None
    assert after.winner_drawdown_cooldown_months==3
    assert after.exec_config.winner_pyramiding==before.exec_config.winner_pyramiding
    assert after.risk_config.max_positions==before.risk_config.max_positions
    with pytest.raises(ValueError):study.verify_capital_only(before,replace(after,cost_round_trip_bps=99),after.initial_equity)


@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf')])
def test_invalid_initial_capital_rejected(value):
    with pytest.raises(ValueError):study.matched_configuration({},date(2020,1,2),value)


def test_initial_deposit_not_assumed_4000_in_cash_audit():
    f=pd.DataFrame([dict(event='BUY_FILL',symbol='A',quantity=10,price=100.,costs=.8),
        dict(event='GLOBAL_DD_TRIGGER',symbol=None,quantity=None,price=None,costs=None),
        dict(event='SELL_FILL',symbol='A',quantity=10,price=90.,costs=.72),
        dict(event='GLOBAL_DD_RESUME',symbol=None,quantity=None,price=None,costs=None)])
    cash,fees,held=study.control_audit.independent_cash(study.financial_events(f),7980.1667511581745)
    assert cash==pytest.approx(7878.6467511581745) and fees==pytest.approx(1.52) and held=={}
    f.loc[1,'costs']=5.
    with pytest.raises(ValueError,match='hidden'):study.financial_events(f)


def test_scope_restores_controller_and_audit():
    import backtesting.winner_global_liquidation as module
    old=(module.GlobalLiquidation,study.cycle.BASE_AUDIT,study.cycle.CURRENT_FOLDER)
    with study.scope(None):
        assert module.GlobalLiquidation==study.cycle.CycleOnlyLiquidation
        assert study.cycle.BASE_AUDIT==study.explicit_normal_audit
    assert old==(module.GlobalLiquidation,study.cycle.BASE_AUDIT,study.cycle.CURRENT_FOLDER)


def test_actual_native_cycle_replay_books_the_matched_deposit(monkeypatch):
    cfg,args,_=data_with_global_drawdown()
    initial=7980.1667511581745
    monkeypatch.setattr(study.cycle,'BASE_CONFIGURATION',lambda *_:cfg)
    actual=study.matched_configuration({},cfg.start_date,initial)
    with study.scope(None):
        result=study.base.BacktestEngine(actual).run(**args)
    summary=study.grid.metrics(result,initial)
    cash,fees,held=study.control_audit.independent_cash(study.financial_events(result.trade_events_df),initial)
    assert cash==pytest.approx(summary['settled_cash'])
    assert fees==pytest.approx(summary['costs'])
    assert held=={p['symbol']:p['qty'] for p in summary['open_positions']}
    assert summary['global_liquidation']['events']
    assert summary['global_liquidation']['reset_deposits']==0
    assert summary['initial_equity']==initial
