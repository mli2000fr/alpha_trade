"""Risk approval -> next-session shared gap gate -> real-quantity protections."""
from datetime import date, datetime, timezone
from dataclasses import replace

import pandas as pd
import pytest

from backtesting.oracle_portfolio_session import OraclePortfolioSession
from backtesting.execution_replay import simulate_phase3_execution_replay
from backtesting.execution_lifecycle_replay import build_phase4_protection_replay
from risk_management.operational_data import BacktestOperationalDataAdapter
from service.market.models import neutral_snapshot
from scripts.research.us_concentrated_contract_audit import frozen_configs

DAY = date(2025, 1, 2)


def approved_entries():
    risk, execution = frozen_configs()
    risk = risk.with_overrides(min_breakout_days=1, min_position_notional=0)
    s = OraclePortfolioSession(risk, sector_map={'FIXTURE': 'Technology'}, account_long_only=False)
    days = pd.bdate_range(end=DAY, periods=25)
    close = pd.DataFrame({'FIXTURE': 100.}, index=days)
    snapshot = BacktestOperationalDataAdapter.build(account_id='fixture',
        account={'equity': 4000., 'cash': 4000., 'settled_cash': 4000., 'buying_power': 4000.},
        positions=[], orders=[], as_of=datetime(2025, 1, 2, 21, tzinfo=timezone.utc), source='test')
    entries = s.decide(DAY, scores=pd.DataFrame([{'symbol': 'FIXTURE', 'trade_date': DAY, 'proba_extreme': .9}]),
        snapshot=snapshot, regime=neutral_snapshot(DAY), close=close, high=close+1, low=close-1)
    return [e for e in entries if e.approved_shares > 0], execution


@pytest.mark.parametrize('gap,accepted', [(0., True), (.03, True), (.031, False), (-.031, False)])
def test_gap_applies_after_approval_not_during_ranking(gap, accepted):
    entries, execution = approved_entries()
    assert len(entries) == 1
    opens = pd.DataFrame({'FIXTURE': [100., 100*(1+gap)]},
                         index=pd.to_datetime(['2025-01-02', '2025-01-03']))
    result = simulate_phase3_execution_replay(entries, execution_config=execution,
        open_df=opens, risk_run_id_prefix='oracle_chronological', enforce_live_gap_filter=True)
    assert len(result.signals_df) == int(accepted)
    assert len(result.diagnostics['gap_rejections']) == int(not accepted)
    if accepted:
        row = result.signals_df.iloc[0]
        assert row.execution_date == opens.index[1]
        assert row.filled_qty == pytest.approx(entries[0].approved_shares)
        phase4 = build_phase4_protection_replay(result, execution_config=execution)
        assert phase4.signals_df.iloc[0].filled_qty == pytest.approx(entries[0].approved_shares)
    else:
        assert not result.execution_result.fills
        assert not result.execution_result.child_intents


def test_missing_next_open_never_falls_back_to_future_close():
    entries, execution = approved_entries()
    opens = pd.DataFrame({'FIXTURE': [100., float('nan'), 100.]},
        index=pd.to_datetime(['2025-01-02', '2025-01-03', '2025-01-06']))
    result = simulate_phase3_execution_replay(entries, execution_config=execution,
        open_df=opens, risk_run_id_prefix='missing', enforce_live_gap_filter=True)
    assert result.signals_df.empty
    assert result.diagnostics['skipped_missing_open'] == 1


@pytest.mark.parametrize('quantity', [.5, 12.5, 25.])
def test_non_unit_approved_quantity_survives_synthetic_retry_chain(quantity):
    entries, execution = approved_entries()
    entry = replace(entries[0], approved_shares=quantity)
    opens = pd.DataFrame({'FIXTURE': [100., 100.]},
                         index=pd.to_datetime(['2025-01-02', '2025-01-03']))
    result = simulate_phase3_execution_replay([entry], execution_config=execution,
        open_df=opens, risk_run_id_prefix='quantity', enforce_live_gap_filter=True)
    assert sum(fill.filled_qty for fill in result.execution_result.fills) == pytest.approx(quantity)
    assert result.signals_df.iloc[0].filled_qty == pytest.approx(quantity)
