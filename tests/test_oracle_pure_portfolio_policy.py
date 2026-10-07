"""Explicit amplitude-only LONG strategy in the shared risk builder."""
from datetime import date, datetime, timezone
from dataclasses import replace
import pytest
import pandas as pd
from risk_management.config import RiskConfig
from risk_management.models import SelectionScore, PriceInfo
from risk_management.portfolio_builder import PortfolioBuilder
from risk_management.operational_data import BacktestOperationalDataAdapter
from service.market.models import neutral_snapshot

DAY = date(2025, 1, 2)


def setup(*, positions=(), orders=(), buying_power=4000., **overrides):
    cfg = RiskConfig(account_equity=4000, min_breakout_days=1,
        min_position_notional=0, max_positions=overrides.pop('max_positions', 8),
        max_position_weight=.25, max_sector_weight=.5, **overrides)
    builder = PortfolioBuilder(cfg, regime_snapshot=neutral_snapshot(DAY),
        sector_map={'HELD': 'Tech'})
    snapshot = BacktestOperationalDataAdapter.build(account_id='fixture',
        account={'equity': 4000., 'cash': buying_power, 'settled_cash': buying_power,
                 'buying_power': buying_power}, positions=positions, orders=orders,
        as_of=datetime(2025, 1, 2, 21, tzinfo=timezone.utc), source='backtest_fixture')
    builder.set_operational_snapshot(snapshot)
    return builder


def build(builder, candidates=None):
    candidates = candidates or [SelectionScore('NEW', 'Tech', .9, score_source='oracle_amplitude', snapshot_date=DAY)]
    return builder.build(candidates,
        {c.symbol: PriceInfo(c.symbol, 100., 2., DAY, DAY) for c in candidates},
        trade_date=DAY, selection_policy='oracle_pure_long')


def test_oracle_is_not_a_fake_directional_probability():
    entries = build(setup())
    assert entries and entries[0].approved_shares > 0
    assert entries[0].predicted_proba is None
    assert entries[0].side == 'buy'
    assert entries[0].score_source == 'oracle_amplitude'


def test_nominal_directional_policy_still_requires_prediction():
    b = setup()
    assert b.build([SelectionScore('NEW', 'Tech', .9)],
        {'NEW': PriceInfo('NEW', 100., 2.)}, trade_date=DAY) == []


def test_real_existing_slots_are_reserved():
    b = setup(max_positions=1, positions=[{'symbol': 'HELD', 'qty': 10,
        'side': 'long', 'avg_entry_price': 100., 'current_price': 100.}])
    assert all(e.approved_shares == 0 for e in build(b))


def test_pending_entry_reserves_slot_without_double_counting_position():
    b = setup(max_positions=1, orders=[{'id': 'pending', 'symbol': 'PENDING',
        'side': 'buy', 'qty': 1., 'type': 'market', 'status': 'open'}])
    assert all(e.approved_shares == 0 for e in build(b))


def test_no_buying_power_no_approved_quantity():
    assert all(e.approved_shares == 0 for e in build(setup(buying_power=0)))


def test_same_symbol_pending_order_is_not_resubmitted():
    b = setup(orders=[{'id': 'pending', 'symbol': 'NEW', 'side': 'buy',
                      'qty': 1., 'type': 'market', 'status': 'open'}])
    assert build(b) == []


def test_regime_blocks_longs_without_neutral_fallback():
    b = setup()
    b._regime_snapshot = replace(neutral_snapshot(DAY), allowed_long_entries=False)
    assert build(b) == []


@pytest.mark.parametrize('problem', ['snapshot', 'date', 'equity', 'sector', 'kelly', 'short'])
def test_missing_or_ambiguous_contract_fails_closed(problem):
    b = setup(enable_kelly_sizing=problem == 'kelly')
    candidates = [SelectionScore('NEW', 'Tech', .9, snapshot_date=DAY)]
    if problem == 'snapshot': b._operational_snapshot = None
    if problem == 'date': candidates = [replace(candidates[0], snapshot_date=date(2025, 1, 1))]
    if problem == 'equity': b._cfg = b._cfg.with_overrides(account_equity=5000)
    if problem == 'sector': candidates = [replace(candidates[0], sector='Unknown')]
    if problem == 'short': candidates = [replace(candidates[0], side='sell')]
    with pytest.raises(ValueError): build(b, candidates)


def bridge_inputs():
    days = pd.bdate_range(end=DAY, periods=25)
    close = pd.DataFrame({'NEW': 100.}, index=days)
    b = setup()
    return b, dict(scores_df=pd.DataFrame([{'trade_date': DAY, 'symbol': 'NEW',
        'sector': 'Tech', 'proba_extreme': .9}]), predictions_df=pd.DataFrame(),
        close_df=close, high_df=close+1, low_df=close-1,
        risk_config=b._cfg, score_column='proba_extreme',
        selection_policy='oracle_pure_long')


def test_backtest_bridge_and_shared_builder_have_identical_decisions():
    from backtesting.risk_bridge import build_phase2_risk_result
    b, kwargs = bridge_inputs()
    calls = []
    def provider(day):
        calls.append(day)
        return b.operational_snapshot
    result = build_phase2_risk_result(**kwargs, operational_snapshot_provider=provider)
    direct = b.build([SelectionScore('NEW', 'Tech', .9, score_source='proba_extreme', snapshot_date=DAY)],
        {'NEW': PriceInfo('NEW', 100., 2., DAY, DAY)},
        trade_date=DAY, selection_policy='oracle_pure_long')
    assert calls == [DAY]
    assert result.entries[0].approved_shares == direct[0].approved_shares
    assert result.entries[0].stop_price_initial == direct[0].stop_price_initial
    assert result.entries[0].take_profit_price == direct[0].take_profit_price
    assert result.entries[0].predicted_proba is None


def test_bridge_refuses_daily_fresh_account_assumption_for_oracle():
    from backtesting.risk_bridge import build_phase2_risk_result
    _, kwargs = bridge_inputs()
    with pytest.raises(ValueError, match='snapshot provider'):
        build_phase2_risk_result(**kwargs)


def test_sector_preflight_does_not_backdate_future_evidence():
    from scripts.research.us_concentrated_live_parity_preflight import coverage
    candidates = pd.DataFrame([{'date': DAY, 'symbol': 'NEW'}])
    history = pd.DataFrame([{'id': 1, 'symbol': 'NEW', 'snapshot_date': DAY,
        'available_at': '2025-01-03', 'sector': 'Tech'}])
    assert coverage(candidates, history)['qualified_sector_days'] == 0
    history.loc[0, 'available_at'] = '2025-01-02 20:00:00'
    assert coverage(candidates, history)['qualified_sector_days'] == 1
