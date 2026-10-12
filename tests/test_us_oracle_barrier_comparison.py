from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from backtesting.execution_lifecycle_replay import ProtectionReplayResult
from modelFactory.oracle_barrier import SCORES, TARGETS
from scripts.research.us_oracle_barrier_comparison import (
    FixedBarrierLedger, audit_selection, fixed_barrier_protections, freeze_candidates,
    readonly_statement,
)
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def test_fixed_barriers_use_actual_fill_and_update_all_tp_and_sl_fields():
    signals = pd.DataFrame([dict(symbol='X', fill_price=110., replay_initial_stop_price=80.,
        replay_take_profit_price=117., replay_trailing_stop_pct=.15)])
    orders = pd.DataFrame([dict(symbol='X', intent_role='initial_stop', stop_price=80., limit_price=None),
        dict(symbol='X', intent_role='take_profit', stop_price=None, limit_price=117.)])
    original = ProtectionReplayResult(signals, signals.copy(), {}, orders)
    result = fixed_barrier_protections(original)
    for frame in (result.signals_df, result.protection_frame):
        assert frame.replay_initial_stop_price.iloc[0] == pytest.approx(102.3)
        assert frame.replay_take_profit_price.iloc[0] == pytest.approx(132.)
    assert result.order_lifecycle_frame.stop_price.iloc[0] == pytest.approx(102.3)
    assert result.order_lifecycle_frame.limit_price.iloc[1] == pytest.approx(132.)
    assert original.signals_df.replay_take_profit_price.iloc[0] == 117.


@pytest.mark.parametrize('outcome', ['expiry', 'tp', 'sl', 'gap', 'expiry_collision'])
def test_native_portfolio_fixed_tp20_sl7_and_j21_open(tmp_path, outcome):
    frames, scores, macro, trading = fixture_data()
    # Entry happens on index 1; 20 holding sessions are indices 1..20.
    frames['opens'].loc[trading[21], 'FIXTURE'] = 101.
    frames['close'].loc[trading[21], 'FIXTURE'] = 105.
    frames['high'].loc[trading[21], 'FIXTURE'] = 106.
    if outcome == 'tp':
        frames['high'].loc[trading[2], 'FIXTURE'] = 125.
    if outcome in {'sl', 'gap'}:
        frames['low'].loc[trading[2], 'FIXTURE'] = 90.
    if outcome == 'gap':
        frames['opens'].loc[trading[2], 'FIXTURE'] = 90.
    if outcome == 'expiry_collision':
        # Expired before these intraday prices can touch either protection.
        frames['high'].loc[trading[21], 'FIXTURE'] = 140.
        frames['low'].loc[trading[21], 'FIXTURE'] = 80.
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}),
        policy='ORACLE_TOP10', variant='CURRENT_NO_EXPIRY', output=tmp_path,
        ledger_factory=FixedBarrierLedger, expiry_open_sessions=20,
        decision_end_date=str(trading[0].date()),
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    trade = pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.entry_date == trading[1]
    assert trade.replay_initial_stop_price == pytest.approx(93.)
    assert trade.replay_take_profit_price == pytest.approx(120.)
    assert trade.exit_date == trading[2 if outcome in {'tp', 'sl', 'gap'} else 21]
    assert trade.exit_price == pytest.approx({'tp': 120., 'sl': 93., 'gap': 90.}.get(outcome, 101.))
    assert abs(result['cash_reconciliation_error']) < 1e-6
    assert result['closed_positions'] == 1


def test_expiry_requires_tail_and_cannot_be_changed_to_terminal_close(tmp_path):
    frames, scores, macro, trading = fixture_data()
    with pytest.raises(ValueError, match='Insufficient expiry tail'):
        run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'},
            macro=macro, market_config=parse_market_regimes({'enabled': False}),
            policy='ORACLE_TOP10', variant='CURRENT_NO_EXPIRY', output=tmp_path,
            ledger_factory=FixedBarrierLedger, expiry_open_sessions=20,
            end_date=trading[5], decision_end_date=trading[0],
            protection_options=dict(take_profit_enabled=True, trailing_enabled=False))


def test_no_new_entries_in_expiry_tail(tmp_path):
    frames, scores, macro, trading = fixture_data()
    scores = pd.concat([scores, scores.assign(date=trading[20])], ignore_index=True)
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}),
        policy='ORACLE_TOP10', variant='CURRENT_NO_EXPIRY', output=tmp_path,
        ledger_factory=FixedBarrierLedger, expiry_open_sessions=20,
        decision_end_date=trading[0],
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    assert result['closed_positions'] == 1


def test_macro_not_required_after_last_expiry_in_cash_only_tail(tmp_path):
    frames, scores, macro, trading = fixture_data()
    macro = type(macro)(macro.frame.loc[macro.frame.index < trading[21]].reset_index(drop=True))
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}),
        policy='ORACLE_TOP10', variant='CURRENT_NO_EXPIRY', output=tmp_path,
        ledger_factory=FixedBarrierLedger, expiry_open_sessions=20,
        decision_end_date=trading[0],
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    assert result['closed_positions'] == 1
    assert abs(result['cash_reconciliation_error']) < 1e-6


def test_missing_macro_with_a_held_position_still_blocks(tmp_path):
    frames, scores, macro, trading = fixture_data()
    macro = type(macro)(macro.frame.loc[macro.frame.index != trading[5]].reset_index(drop=True))
    with pytest.raises(ValueError, match='Missing macro date'):
        run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'},
            macro=macro, market_config=parse_market_regimes({'enabled': False}),
            policy='ORACLE_TOP10', variant='CURRENT_NO_EXPIRY', output=tmp_path,
            ledger_factory=FixedBarrierLedger, expiry_open_sessions=20,
            decision_end_date=trading[0],
            protection_options=dict(take_profit_enabled=True, trailing_enabled=False))


@pytest.mark.parametrize('scenario', ['collision', 'tp_gap'])
def test_native_conservative_fill_differs_from_an_optimistic_label(tmp_path, scenario):
    frames, scores, macro, trading = fixture_data()
    frames['high'].loc[trading[2], 'FIXTURE'] = 135.
    if scenario == 'collision':
        frames['low'].loc[trading[2], 'FIXTURE'] = 80.
        expected = 93.
    else:
        frames['opens'].loc[trading[2], 'FIXTURE'] = 130.
        frames['low'].loc[trading[2], 'FIXTURE'] = 129.
        frames['close'].loc[trading[2], 'FIXTURE'] = 132.
        expected = 120.  # Not an invented favourable fill at the opening 130.
    run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}),
        policy='ORACLE_TOP10', variant='CURRENT_NO_EXPIRY', output=tmp_path,
        ledger_factory=FixedBarrierLedger, expiry_open_sessions=20,
        decision_end_date=trading[0],
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    trade = pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.exit_price == pytest.approx(expected)


def test_rank_ties_and_future_unknowns_do_not_reselect_or_change_sizing():
    scores = pd.DataFrame({'date': pd.Timestamp('2025-01-02'),
        'symbol': [f'S{i:02d}' for i in range(60)], 'old_score': np.arange(60)[::-1]/60,
        SCORES['long']: np.arange(60)[::-1]/600,
        'future_quality': [False]*10+[True]*50})
    for count in (10, 20, 50):
        a = freeze_candidates(scores, count, 'OLD_TERMINAL_LONG')
        b = freeze_candidates(scores, count, 'NEW_BARRIER_LONG')
        assert len(a) == count
        assert a.symbol.tolist() == scores.symbol.iloc[:count].tolist()
        assert a.proba_extreme.tolist() == b.proba_extreme.tolist()
        assert 'future_quality' not in a
    scores['old_score'] = .5
    scores = scores.iloc[::-1]
    assert freeze_candidates(scores, 10, 'OLD_TERMINAL_LONG').symbol.tolist() == [f'S{i:02d}' for i in range(10)]


def test_direction_threshold_abstentions_and_unknowns_remain_separate():
    scores = pd.DataFrame({'date': pd.Timestamp('2025-01-02'), 'symbol': ['A', 'B', 'C'],
        'old_score': [.9, .8, .7], SCORES['long']: [.6, .3, .55],
        SCORES['short']: [.2, .54, .55], 'max_score': [.6, .54, .55]})
    labels = pd.DataFrame({'date': scores.date, 'symbol': scores.symbol,
        TARGETS['long']: [np.nan, 1., 0.], TARGETS['short']: [0., 0., 1.],
        'long_outcome': ['UNQUALIFIED', 'TP', 'SL'], 'short_outcome': ['SL', 'SL', 'TP']})
    selected, annual, directional = audit_selection(scores, labels)
    assert len(selected) == 18  # 3 candidates x 2 arms x 3 counts
    assert annual[0]['unknown'] == 1
    assert directional[0]['abstentions'] == 2
    assert directional[0]['long_selected'] == 1
    assert directional[0]['evaluated'] == 0


@pytest.mark.parametrize('statement', ['INSERT INTO x VALUES(1)', 'UPDATE x SET x=1', 'DELETE FROM x',
    'DROP TABLE x', 'SET TRANSACTION READ WRITE', 'CALL hidden_write()', 'WITH x AS(SELECT 1) DELETE FROM y'])
def test_sql_write_guard_rejects_mutations(statement):
    with pytest.raises(RuntimeError, match='SELECT-only'):
        readonly_statement(None, None, statement, None, None, False)


def test_sql_guard_allows_readonly_setup_and_select():
    for statement in ('SET TRANSACTION READ ONLY', 'SELECT date FROM stock_bars_daily'):
        readonly_statement(None, None, statement, None, None, False)
