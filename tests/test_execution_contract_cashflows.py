"""Actual simulator cash-flow fixtures, not a historical strategy backtest."""
from datetime import date

import pandas as pd
import pytest

from backtesting.simulator import BacktestConfig, BacktestEngine
from common.trading_costs import TradingCostModel


def fixture_run(side='buy', spread=5, quote=None, forced=0, multiplier=1, borrow=0,
                qty=2, price=100, strict=True):
    days = pd.to_datetime(['2025-01-02', '2025-01-03', '2025-01-06'])
    market = pd.DataFrame({'FIXTURE': [price]*3}, index=days)
    signals = pd.DataFrame([dict(symbol='FIXTURE', trade_date=days[0], selected=True,
        side=side, filled_qty=qty, replay_exit_date=days[2], replay_exit_price=price,
        replay_exit_reason='contract_fixture', score=1.)])
    costs = TradingCostModel(spread_bps=spread, commission_bps=1, slippage_bps=2,
                             borrow_fee_annual=borrow)
    cfg = BacktestConfig(start_date=date(2025, 1, 2), end_date=date(2025, 1, 6),
        initial_equity=4000, trading_cost_model=costs, min_score_threshold=0,
        execution_replay_mode='execution_replay', exit_lifecycle_replay_mode='exit_lifecycle_replay',
        require_replay_quantities=strict, cost_round_trip_bps=forced, cost_multiplier=multiplier,
        time_stop_enabled=False)
    quotes = None if quote is None else market*0+quote
    return BacktestEngine(cfg).run(open_df=market, close=market, high=market, low=market,
                                  signals_df=signals, spread_df=quotes)


@pytest.mark.parametrize('side', ['buy', 'sell'])
@pytest.mark.parametrize('spread', [0, 5, 10])
def test_flat_price_exact_cashflows(side, spread):
    result = fixture_run(side=side, spread=spread)
    trade = result.closed_trades_df.iloc[0]
    expected_fees = 200 * 2*(spread+1+2)/10000
    assert trade.entry_price == 100
    assert trade.exit_price == 100
    assert abs(trade.quantity) == 2
    assert trade.pnl == pytest.approx(-expected_fees)
    assert result.final_value() == pytest.approx(4000-expected_fees)


@pytest.mark.parametrize('side', ['buy', 'sell'])
def test_full_quote_replaces_not_adds_fallback(side):
    result = fixture_run(side=side, spread=20, quote=6)
    assert result.closed_trades_df.iloc[0].pnl == pytest.approx(-200*2*(3+1+2)/10000)


@pytest.mark.parametrize('side', ['buy', 'sell'])
def test_forced_cost_is_paid_once_per_leg(side):
    result = fixture_run(side=side, quote=50, forced=20)
    assert result.closed_trades_df.iloc[0].pnl == pytest.approx(-200*.002)


def test_multiplier_scales_all_canonical_components():
    assert fixture_run(multiplier=2).closed_trades_df.iloc[0].pnl == pytest.approx(-200*.0016*2)


def test_borrow_counts_sessions_not_weekend_days():
    result = fixture_run(side='sell', spread=0, borrow=.252)
    # Friday entry to Monday exit = one trading interval, not three calendar days.
    assert result.closed_trades_df.iloc[0].pnl == pytest.approx(-200*.0006-200*.001)


@pytest.mark.parametrize('qty', [0, -2, float('inf'), float('nan')])
def test_invalid_quantity_never_becomes_internal_sizing(qty):
    with pytest.raises(ValueError, match='Missing valid replay quantity'):
        fixture_run(qty=qty)


def test_missing_declared_fill_cannot_fall_back_to_approved_quantity():
    cfg = BacktestConfig(start_date=date(2025, 1, 2), end_date=date(2025, 1, 6),
        execution_replay_mode='execution_replay', require_replay_quantities=True)
    engine = BacktestEngine(cfg)
    assert engine._resolve_signal_quantity_override(pd.Series({'filled_qty': float('nan'), 'approved_shares': 2})) is None


def test_portfolio_clipping_is_explicit_failure_in_strict_mode():
    with pytest.raises(ValueError, match='quantity clipped'):
        fixture_run(qty=10000)


def test_strict_mode_requires_execution_replay():
    with pytest.raises(ValueError, match='require_replay_quantities'):
        BacktestConfig(start_date=date(2025, 1, 2), end_date=date(2025, 1, 6),
                       require_replay_quantities=True)


def test_gap_filter_still_uses_raw_open_with_canonical_costs():
    from backtesting.microstructure import MicrostructureConfig
    days = pd.to_datetime(['2025-01-02', '2025-01-03', '2025-01-06'])
    prices = pd.DataFrame({'FIXTURE': [100., 104., 104.]}, index=days)
    signals = pd.DataFrame([dict(symbol='FIXTURE', trade_date=days[0], selected=True,
                                filled_qty=1, score=1.)])
    cfg = BacktestConfig(start_date=days[0].date(), end_date=days[-1].date(),
        initial_equity=4000, use_canonical_costs=True, min_score_threshold=0,
        execution_replay_mode='execution_replay', require_replay_quantities=True,
        microstructure=MicrostructureConfig(max_entry_gap_pct=.03))
    result = BacktestEngine(cfg).run(open_df=prices, close=prices, high=prices, low=prices,
                                     signals_df=signals)
    assert result.diagnostics.blocked_entry_gap == 1
    assert result.closed_trades_df.empty


def test_time_stop_off_does_not_imply_forced_h20_exit():
    days = pd.bdate_range('2025-01-02', periods=27)
    prices = pd.DataFrame({'FIXTURE': [100.]*len(days)}, index=days)
    signals = pd.DataFrame([dict(symbol='FIXTURE', trade_date=days[0], selected=True,
        filled_qty=1, score=1., replay_exit_date=days[-1], replay_exit_price=100,
        replay_exit_reason='fixture_terminal')])
    cfg = BacktestConfig(start_date=days[0].date(), end_date=days[-1].date(),
        initial_equity=4000, use_canonical_costs=True, min_score_threshold=0,
        execution_replay_mode='execution_replay', require_replay_quantities=True,
        exit_lifecycle_replay_mode='exit_lifecycle_replay', time_stop_enabled=False)
    result = BacktestEngine(cfg).run(open_df=prices, close=prices, high=prices, low=prices,
                                     signals_df=signals)
    assert len(result.closed_trades_df) == 1
    assert result.closed_trades_df.iloc[0].exit_date == days[-1]
    assert result.closed_trades_df.iloc[0].exit_reason == 'fixture_terminal'
