from dataclasses import replace

import pandas as pd
import pytest

from scripts.research import us_winner_cycle15_min70_20261025 as study


def frozen_configuration():
    parent=study.base.read(study.CONTROL/'protocol.json')
    return study.base_configuration(parent)


def test_configuration_preserves_every_non_cycle_field_and_no_hidden_cap():
    before=frozen_configuration();after=study.with_cycle(before)
    assert after.initial_equity==4000.
    assert after.risk_config.effective_min_notional==70.
    assert after.exec_config.winner_pyramiding==before.exec_config.winner_pyramiding
    assert after.risk_config.risk_per_trade_pct==.0125
    assert after.winner_cycle_drawdown_pct==.15 and after.winner_drawdown_cooldown_months==3
    assert after.winner_hard_drawdown_pct is None and not after.winner_global_drawdown_halt
    assert after.risk_config.force_close_pct==after.exec_config.force_close_pct==1.
    study.cycle.CycleOnlyLiquidation(after,after.risk_config,after.exec_config)


def test_bridge_rejects_drift_in_frozen_parameters():
    import copy
    parent=study.base.read(study.CONTROL/'protocol.json')
    wrong=copy.deepcopy(parent);wrong['after']['initial_equity']=9000.
    with pytest.raises(ValueError,match='configuration drift'):study.base_configuration(wrong)


def test_actual_native_cycle_books_4000_min70_and_sells_all_positions():
    from tests.test_winner_global_liquidation import data_with_global_drawdown
    cfg,args,_=data_with_global_drawdown()
    cfg=replace(cfg,risk_config=replace(cfg.risk_config,min_position_notional=70.))
    cfg=study.with_cycle(cfg)
    with study.shared.scope(None):result=study.base.BacktestEngine(cfg).run(**args)
    summary=study.grid.metrics(result,4000.)
    cash,fees,held=study.shared.control_audit.independent_cash(
        study.shared.financial_events(result.trade_events_df),4000.)
    assert cash==pytest.approx(summary['settled_cash'])
    assert fees==pytest.approx(summary['costs'])
    assert held=={p['symbol']:p['qty'] for p in summary['open_positions']}
    info=summary['global_liquidation']
    assert info['events'] and info['force_close_pct']==1.
    assert info['cycle_threshold_pct']==.15 and info['hard_threshold_pct'] is None
    assert info['reset_deposits']==0
    first=info['events'][0]
    buys=result.trade_events_df[result.trade_events_df.event.eq('BUY_FILL')]
    after=buys[pd.to_datetime(buys.time,utc=True).ge(pd.Timestamp(first['detected_at']))]
    assert after.empty


def test_shared_scope_restores_risk_adapter():
    original=study.cycle.BASE_AUDIT,study.cycle.CURRENT_FOLDER
    with study.shared.scope(None):assert study.cycle.BASE_AUDIT==study.shared.explicit_normal_audit
    assert original==(study.cycle.BASE_AUDIT,study.cycle.CURRENT_FOLDER)
