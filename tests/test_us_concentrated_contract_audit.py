from datetime import date

import pandas as pd
import pytest

from scripts.research.us_concentrated_contract_audit import classify_bar, frozen_configs, require_economic_gate


def test_vendor_zero_is_not_certification():
    assert classify_bar('BAND', {}, {'volume': 0}).startswith('RESERVED_')
    assert classify_bar('BAND', {}, None).startswith('BLOCKED_')
    assert classify_bar('BAND', {}, {'volume': 100}).endswith('NOT_APPLIED')


def test_mp_disagreement_stays_reserved():
    assert classify_bar('MP', {'close': 45.23}, {'close': 44}).startswith('RESERVED_')


def test_explicit_research_contract_does_not_inherit_h20_defaults():
    risk, execution = frozen_configs()
    assert risk.atr_stop_multiple_for(20) == 2.5
    assert risk.tp_params_for(20) == (3, .07)
    assert execution.time_stop.enabled is False
    assert execution.trailing_pct_long_override is None
    assert risk.max_positions == 8
    assert risk.account_equity == 4000
    assert execution.simulated_account_equity == 4000
    assert execution.max_entry_gap_pct == .03
    assert risk.max_sector_weight == .5


def test_actual_sizing_tp_and_quantity_consumption():
    from backtesting.simulator import BacktestConfig, BacktestEngine, _production_tp_price
    from risk_management.models import PriceInfo
    from risk_management.position_sizer import PositionSizer
    risk, execution = frozen_configs()
    # Make the isolated fixture's minimum explicit; this is proposed sizing,
    # not the portfolio-approved quantity or historical economic replay.
    fixture = risk.with_overrides(min_position_notional=0, enforce_min_notional=None)
    shares = PositionSizer(fixture).compute(PriceInfo(symbol='FIXTURE', last_close=100, atr_20=2))
    assert shares.proposed_shares == pytest.approx(4000 * fixture.risk_per_trade_pct * fixture.risk_multiplier / 5)
    assert PositionSizer(fixture).compute(PriceInfo(symbol='FIXTURE', last_close=100, atr_20=None)).proposed_shares == 0
    cfg = BacktestConfig(start_date=date(2025, 1, 1), end_date=date(2025, 1, 2),
                         risk_config=risk, exec_config=execution, use_canonical_costs=True)
    engine = BacktestEngine(cfg)
    assert not cfg.time_stop_enabled
    assert engine._resolve_signal_quantity_override(pd.Series({'filled_qty': 1.25, 'approved_shares': 9})) == 1.25
    assert engine._resolve_signal_quantity_override(pd.Series(dtype=float)) is None
    assert _production_tp_price(100, .02, 3, .07, False) == 106
    assert _production_tp_price(100, .05, 3, .07, True) == 93


def test_spread_lookup_retains_full_quote_value():
    from backtesting.simulator import BacktestConfig, BacktestEngine
    risk, execution = frozen_configs()
    cfg = BacktestConfig(start_date=date(2025, 1, 1), end_date=date(2025, 1, 2),
                         risk_config=risk, exec_config=execution, use_canonical_costs=True)
    engine = BacktestEngine(cfg)
    day = pd.Timestamp('2025-01-02')
    quotes = pd.DataFrame({'FIXTURE': [10.]}, index=[day])
    assert engine._get_spread_bps(quotes, day, 'FIXTURE', fallback_bps=5) == 10
    assert engine._get_spread_bps(None, day, 'FIXTURE', fallback_bps=5) == 5


def test_economic_gate_is_fail_closed():
    with pytest.raises(ValueError, match='parity not certified'):
        require_economic_gate({'source_hashes': {}, 'status': 'BLOCKED_BEFORE_ECONOMIC_PERFORMANCE',
                               'contract': {'blockers': ['COST_SEMANTICS']}})


def test_changed_source_invalidates_contract(tmp_path):
    import hashlib
    source = tmp_path/'fixture.py'
    source.write_text('old', encoding='utf-8')
    report = {'source_hashes': {'fixture.py': hashlib.sha256(source.read_bytes()).hexdigest()},
              'status': 'READY_FOR_ECONOMIC_REPLAY', 'contract': {'blockers': []}}
    require_economic_gate(report, tmp_path)
    source.write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='Execution source changed'):
        require_economic_gate(report, tmp_path)
