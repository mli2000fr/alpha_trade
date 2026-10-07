"""Synthetic phase2 -> 3 -> 4 -> 5 -> 7 -> simulator contract, no SQL."""
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from scripts.research.us_concentrated_contract_audit import (
    frozen_configs, frozen_backtest_config, validate_replay_tape,
)


def assemble(side='buy', scenario='tp'):
    from backtesting.execution_replay import simulate_phase3_execution_replay
    from backtesting.execution_lifecycle_replay import build_phase4_protection_replay
    from backtesting.protection_watcher_replay import build_phase5_watcher_replay
    from backtesting.exit_lifecycle_replay import build_phase7_exit_lifecycle_replay
    from risk_management.models import PriceInfo, SelectionScore, PredictionInfo
    from risk_management.portfolio_builder import PortfolioBuilder

    risk, execution = frozen_configs()
    # Isolated fixture: remove selection gates to exercise both forced sides,
    # not a change to the frozen experiment's portfolio eligibility policy.
    risk = risk.with_overrides(min_breakout_days=1, min_position_notional=0,
        short_selling_enabled=True, short_rotation_required=False,
        short_require_bearish_benchmark=False, short_min_score=0)
    short = side == 'sell'
    prediction = PredictionInfo('FIXTURE', .9, 0 if short else 2, 'synthetic',
        predicted_side='short' if short else 'long', proba_long=.05 if short else .9,
        proba_short=.9 if short else .05, proba_flat=.05)
    entries = PortfolioBuilder(risk).build(
        [SelectionScore('FIXTURE', 'Technology', .9)],
        {'FIXTURE': PriceInfo('FIXTURE', 100, 2)},
        predictions={'FIXTURE': prediction}, trade_date=date(2025, 1, 2))
    entries = [e for e in entries if e.approved_shares > 0]
    assert len(entries) == 1
    entry = replace(entries[0], score_snapshot_date=date(2025, 1, 2),
                    price_asof_date=date(2025, 1, 2), atr_asof_date=date(2025, 1, 2))
    days = pd.to_datetime(['2025-01-02', '2025-01-03', '2025-01-06'])
    opens = pd.DataFrame({'FIXTURE': [100., 100., 100.]}, index=days)
    highs = opens.copy()
    lows = opens.copy()
    if scenario == 'tp':
        highs['FIXTURE'] = [100, 101, 101 if short else 107]
        lows['FIXTURE'] = [100, 99, 93 if short else 99]
    elif scenario == 'stop':
        highs['FIXTURE'] = [100, 106 if short else 101, 100]
        lows['FIXTURE'] = [100, 99 if short else 94, 100]
    elif scenario == 'trailing':
        highs['FIXTURE'] = [100, 101, 105 if short else 103]
        lows['FIXTURE'] = [100, 99, 97 if short else 95]
    phase3 = simulate_phase3_execution_replay([entry], execution_config=execution,
        open_df=opens, risk_run_id_prefix='synthetic_contract', exec_run_id='synthetic_contract')
    phase4 = build_phase4_protection_replay(phase3, execution_config=execution)
    phase5 = build_phase5_watcher_replay(phase4, high_df=highs, low_df=lows)
    phase7 = build_phase7_exit_lifecycle_replay(phase5, high_df=highs, low_df=lows,
                                              intrabar_priority='conservative', swing_only=False)
    return entry, phase7, opens, highs, lows


@pytest.mark.parametrize('side', ['buy', 'sell'])
@pytest.mark.parametrize('scenario,reason', [('tp', 'take_profit'), ('stop', 'initial_stop'), ('trailing', 'trailing_stop')])
def test_pipeline_quantity_fill_protection_exit_and_oco(side, scenario, reason):
    from backtesting.simulator import BacktestEngine
    entry, tape, opens, highs, lows = assemble(side, scenario)
    validate_replay_tape(tape.signals_df, opens.index)
    cfg = frozen_backtest_config(opens.index[0], opens.index[-1])
    result = BacktestEngine(cfg).run(open_df=opens, close=opens, high=highs, low=lows,
                                     signals_df=tape.signals_df)
    assert len(result.closed_trades_df) == 1
    trade, signal = result.closed_trades_df.iloc[0], tape.signals_df.iloc[0]
    assert abs(trade.quantity) == pytest.approx(entry.approved_shares)
    assert trade.entry_price == signal.fill_price == 100
    assert trade.entry_date == signal.execution_date == opens.index[1]
    assert trade.exit_date == signal.replay_exit_date
    assert trade.exit_price == signal.replay_exit_price
    assert trade.exit_reason == reason == signal.replay_exit_reason
    assert bool(signal.replay_oco_sibling_canceled)
    assert signal.replay_take_profit_price == (94 if side == 'sell' else 106)
    assert signal.replay_initial_stop_price == (105 if side == 'sell' else 95)
    assert signal.replay_trailing_stop_pct == pytest.approx(.05)
    assert not cfg.time_stop_enabled


def test_tape_rejects_missing_protection_and_same_day_entry():
    _, tape, opens, _, _ = assemble()
    broken = tape.signals_df.drop(columns='replay_initial_stop_price')
    with pytest.raises(ValueError, match='Incomplete replay tape'):
        validate_replay_tape(broken, opens.index)
    broken = tape.signals_df.copy()
    broken['execution_date'] = broken.trade_date
    with pytest.raises(ValueError, match='not next session'):
        validate_replay_tape(broken, opens.index)


def test_frozen_config_has_effective_not_just_declared_risk_controls():
    cfg = frozen_backtest_config('2025-01-02', '2025-01-06')
    assert cfg.risk_overlay.sectoral_cap.enabled
    assert cfg.risk_overlay.sectoral_cap.max_sector_exposure_pct == .5
    assert cfg.risk_overlay.drawdown_breaker.enabled
    assert cfg.risk_overlay.drawdown_breaker.max_dd_pct == .15
    assert cfg.risk_overlay.target_annual_vol == .13
    assert cfg.require_replay_quantities
    assert cfg.require_replay_protections
    from backtesting.simulator import BacktestEngine
    assert BacktestEngine(cfg)._resolve_max_gross_exposure_limit(4000) == cfg.risk_config.max_gross_exposure


def test_engine_itself_blocks_missing_protections():
    from backtesting.simulator import BacktestEngine
    _, tape, opens, highs, lows = assemble()
    cfg = frozen_backtest_config(opens.index[0], opens.index[-1])
    with pytest.raises(ValueError, match='Incomplete replay protection tape'):
        BacktestEngine(cfg).run(open_df=opens, close=opens, high=highs, low=lows,
            signals_df=tape.signals_df.drop(columns='replay_initial_stop_price'))
