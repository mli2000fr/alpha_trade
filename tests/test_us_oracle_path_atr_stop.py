from dataclasses import replace
from functools import partial

import numpy as np
import pandas as pd
import pytest

from risk_management.config import RiskConfig
from risk_management.position_sizer import PositionSizer
from risk_management.models import PriceInfo
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_path_atr_stop import (
    ATRRiskConfig, ATRStopLedger, ATRStopSession, ARMS, atr_stop_fraction, committed_fills, sizing_metadata,
)
from scripts.research.us_oracle_path_top5_leverage_grid import UnlimitedLedger, MarginAwareSession, margin_policy
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def test_rule_and_boundaries_not_optimized():
    assert [atr_stop_fraction(100, a) for a in [2, 5, 8, 10, 50]] == [.05, .05, .08, .10, .10]


def test_report_distinguishes_size_change_from_unchanged_risk_budget():
    assert sizing_metadata(ARMS[0])['sizing_unchanged']
    assert not sizing_metadata(ARMS[1])['sizing_unchanged']
    assert sizing_metadata(ARMS[1])['risk_budget_unchanged']


@pytest.mark.parametrize('price,atr', [(0, 1), (100, None), (100, np.nan), (100, -1), (True, 2)])
def test_unknown_atr_or_price_never_falls_back(price, atr):
    with pytest.raises(ValueError):
        atr_stop_fraction(price, atr)


def test_overrides_and_dataclass_replace_keep_research_sizing():
    c = ATRRiskConfig(risk_per_trade_pct=.02, fixed_stop_pct=None)
    for modified in [c.with_overrides(account_equity=4000), replace(c, risk_multiplier=.5)]:
        assert isinstance(modified, ATRRiskConfig)
        assert modified.stop_distance(100, 8) == 8
        assert modified.risk_per_trade_pct == .02


def test_risk_budget_identical_quantity_reduces_for_wider_stop():
    common = dict(account_equity=4000, risk_per_trade_pct=.02, min_position_notional=0, allow_fractional_shares=True)
    pi = PriceInfo('A', 100, 8)
    fixed = PositionSizer(RiskConfig(**common, fixed_stop_pct=.05)).compute(pi)
    atr = PositionSizer(ATRRiskConfig(**common)).compute(pi)
    assert fixed.proposed_shares == 16
    assert atr.proposed_shares == 10
    assert fixed.proposed_shares*5 == atr.proposed_shares*8 == 80
    assert pi.atr_20 == 8  # raw ATR never replaced to trick risk guards


def simulate(output, arm, native=False, change=False, gap=False):
    frames, scores, macro, days = fixture_data()
    frames['high']['FIXTURE'] = 104
    frames['low']['FIXTURE'] = 96  # known ATR8 at entry decision
    if change:
        frames['low'].loc[days[2], 'FIXTURE'] = 94  # fixed stops; ATR does not
        frames['high'].loc[days[3]:, 'FIXTURE'] = 140
        frames['low'].loc[days[3]:, 'FIXTURE'] = 99  # future huge ATR cannot widen initial stop
    if gap:
        frames['opens'].loc[days[1], 'FIXTURE'] = 102
    refs = []
    def factory(cfg, **kwargs):
        cls = UnlimitedLedger if native else ATRStopLedger
        extra = dict(sl=.05, trail=.15, tp=.20) if native else dict(arm=arm)
        ledger = cls(cfg, study_end=days[-1], events=(), **extra, **kwargs)
        refs.append(ledger); return ledger
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'}, macro=macro,
        market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10', variant='CURRENT_NO_EXPIRY',
        output=output, ledger_factory=factory,
        session_factory=partial(MarginAwareSession if native else ATRStopSession, ledger_ref=refs),
        protection_options=dict(take_profit_enabled=True, trailing_enabled=True),
        daily_exit_policy=margin_policy, reject_constrained_entries=True)
    return result, refs[0], days


def test_fixed_arm_exact_native_curve_and_trades(tmp_path):
    simulate(tmp_path/'fixed', ARMS[0])
    simulate(tmp_path/'native', ARMS[0], native=True)
    for name in ['trades.parquet', 'daily.parquet']:
        pd.testing.assert_frame_equal(pd.read_parquet(tmp_path/'fixed'/name), pd.read_parquet(tmp_path/'native'/name), check_exact=True)


def test_atr_keeps_sl8_and_tp20_trailing15_frozen(tmp_path):
    result, ledger, days = simulate(tmp_path, ARMS[1], change=True)
    fills = committed_fills(ledger)
    assert len(fills) == 1
    assert fills[0]['sl'] == .08
    trades = pd.read_parquet(tmp_path/'trades.parquet')
    t = trades.iloc[0]
    assert t.entry_date == days[1]
    assert t.exit_date == days[3]
    assert t.exit_price == 120
    assert t.replay_initial_stop_price == 92
    assert t.replay_take_profit_price == 120
    assert t.replay_trailing_stop_pct == .15
    assert result['cash_reconciliation_error'] == pytest.approx(0, abs=1e-8)


def test_fill_gap_does_not_recompute_percentage_or_increase_budget(tmp_path):
    _, ledger, _ = simulate(tmp_path, ARMS[1], gap=True)
    fill = committed_fills(ledger)[0]
    assert fill['sl'] == .08
    assert fill['fill_price'] == 102
    assert fill['stop_price'] == pytest.approx(102*.92)
    assert fill['base_risk_budget_usd'] == 80
    assert fill['attempted_nominal_risk_usd'] <= fill['effective_risk_budget_usd']*1.03
