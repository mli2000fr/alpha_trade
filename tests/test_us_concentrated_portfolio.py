"""Stateful research sizing and immutable gap exits, without database access."""
from dataclasses import replace
import pandas as pd
import pytest
from test_concentrated_pipeline_contract import assemble
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_portfolio import StatefulVariantPortfolio, PortfolioEvidenceError
from scripts.research.us_concentrated_portfolio import merge_variant_signals
from scripts.research.us_concentrated_exit_variants import resolve_long_path


def fixture():
    _, tape, opens, high, low = assemble()
    signals = tape.signals_df.copy()
    signals['decision_atr'] = 2.
    signals['decision_close'] = 100.
    signals['variant_path_status'] = 'RESOLVED'
    signals['variant_path_flags'] = ''
    cfg = frozen_backtest_config(opens.index[0], opens.index[-1])
    cfg.risk_config = cfg.risk_config.with_overrides(min_breakout_days=1)
    return cfg, signals, opens, high, low


def execute(cfg, signals, opens, high, low, close=None):
    return StatefulVariantPortfolio(cfg).run_tape(signals, opens,
        opens if close is None else close, high, low, opens*10000)


def test_real_sizing_cashflow_and_both_leg_costs():
    cfg, signals, opens, high, low = fixture()
    result, approvals, exposure = execute(cfg, signals, opens, high, low)
    assert len(result.closed_trades_df) == 1
    trade = result.closed_trades_df.iloc[0]
    assert approvals.iloc[0].proposed_qty_atr == pytest.approx(10)
    assert trade.quantity == pytest.approx(10)
    assert trade.entry_price == 100
    assert trade.exit_price == 106
    assert 4000 < result.final_value() < 4060
    assert exposure.positions.max() == 1
    assert result.final_value() == pytest.approx(4000+trade.pnl)


@pytest.mark.parametrize('price,reason', [(90., 'initial_stop_gap'), (106., 'take_profit_gap')])
def test_gap_exit_price_is_not_slipped_twice(price, reason):
    cfg, signals, opens, high, low = fixture()
    signals['replay_exit_price'] = price
    signals['replay_exit_reason'] = reason
    opens.iloc[-1, 0] = 90 if price == 90 else 110
    high.iloc[-1, 0] = 112
    low.iloc[-1, 0] = 89
    result, _, _ = execute(cfg, signals, opens, high, low)
    assert result.closed_trades_df.iloc[0].exit_price == price


def test_future_entry_day_close_does_not_change_quantity():
    cfg, signals, opens, high, low = fixture()
    a, aa, _ = execute(cfg, signals, opens, high, low)
    close = opens.copy()
    close.iloc[1, 0] = 500
    cfg2, _, _, _, _ = fixture()
    b, bb, _ = execute(cfg2, signals, opens, high, low, close)
    assert aa.iloc[0].approved_qty == bb.iloc[0].approved_qty


def test_unqualified_selected_path_blocks_whole_replay():
    cfg, signals, opens, high, low = fixture()
    signals['variant_path_status'] = 'BLOCKED_PRICE_PATH'
    with pytest.raises(PortfolioEvidenceError, match='Selected path unqualified'):
        execute(cfg, signals, opens, high, low)


def test_unfinanced_candidate_does_not_use_future_path_as_entry_filter():
    cfg, signals, opens, high, low = fixture()
    signals['decision_atr'] = 10000.
    signals['variant_path_status'] = 'BLOCKED_PRICE_PATH'
    result, approvals, _ = execute(cfg, signals, opens, high, low)
    assert result.closed_trades_df.empty
    assert approvals.iloc[0].reason == 'SIZING_OR_PORTFOLIO_CAP'
    assert result.final_value() == 4000


def test_duplicates_fail_instead_of_double_debit():
    cfg, signals, opens, high, low = fixture()
    with pytest.raises(ValueError, match='Duplicate'):
        execute(cfg, pd.concat([signals, signals]), opens, high, low)


def test_shared_unknown_sector_cap_and_capital_not_reset():
    cfg, signals, opens, high, low = fixture()
    frames = []
    for n in range(8):
        f = signals.copy()
        f['symbol'] = f'S{n}'
        f['rank'] = n+1
        frames.append(f)
    def expand(frame):
        return pd.DataFrame({f'S{n}': frame.iloc[:, 0] for n in range(8)})
    result, approvals, exposure = execute(cfg, pd.concat(frames), expand(opens), expand(high), expand(low))
    assert approvals.cash_before.is_monotonic_decreasing
    assert sum(result.closed_trades_df.quantity*100) <= 2000
    assert exposure.positions.max() <= 8
    assert approvals.approved_qty.eq(0).any()


def test_gap_resolver_to_portfolio_end_to_end():
    cfg, signals, opens, high, low = fixture()
    opens.iloc[-1, 0] = 90
    high.iloc[-1, 0] = 108
    low.iloc[-1, 0] = 89
    data = pd.DataFrame({'open': opens.iloc[:, 0], 'high': high.iloc[:, 0],
        'low': low.iloc[:, 0], 'close': opens.iloc[:, 0], 'volume': 10000,
        'is_filled': 0})
    data['instrument'] = 1.
    resolved = resolve_long_path(signals.iloc[0], opens.index, data.to_numpy(), 'NO_TP_FIXED_SL_20_AFTER_ENTRY')
    signals['candidate_id'] = 'fixture'
    signals['path_flags'] = 'OLD_FLAGS_MUST_NOT_COLLIDE'
    variant = pd.DataFrame([{**resolved, 'candidate_id': 'fixture'}])
    merged = merge_variant_signals(signals, variant)
    result, _, _ = execute(cfg, merged, opens, high, low)
    assert result.closed_trades_df.iloc[0].exit_price == 90


def test_held_position_today_close_cannot_size_todays_second_entry():
    cfg, signals, opens, high, low = fixture()
    days = pd.date_range('2025-01-02', periods=4, freq='B')
    a = signals.copy()
    a['symbol'] = 'A'
    a['trade_date'], a['execution_date'], a['replay_exit_date'] = days[0], days[1], days[3]
    b = a.copy()
    b['symbol'] = 'B'
    b['trade_date'], b['execution_date'] = days[1], days[2]
    for f in (a, b):
        f['watcher_transition_state'] = 'pending'
        f['watcher_transition_effective_date'] = pd.NaT
    prices = pd.DataFrame(100., index=days, columns=['A', 'B'])
    cfg.end_date = days[-1].date()
    _, first, _ = execute(cfg, pd.concat([a, b]), prices, prices+10, prices-1)
    cfg2 = frozen_backtest_config(days[0], days[-1])
    cfg2.risk_config = cfg2.risk_config.with_overrides(min_breakout_days=1)
    altered = prices.copy()
    altered.loc[days[2], 'A'] = 500
    _, second, _ = execute(cfg2, pd.concat([a, b]), prices, prices+10, prices-1, altered)
    assert first.loc[first.symbol.eq('B'), 'approved_qty'].iloc[0] == second.loc[second.symbol.eq('B'), 'approved_qty'].iloc[0]
