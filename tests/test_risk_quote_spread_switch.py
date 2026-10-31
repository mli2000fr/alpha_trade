"""Step-11 quote bypass is explicit and cannot bypass execution or other liquidity checks."""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from risk_management.config import RiskConfig, load_risk_config
from risk_management.liquidity import (
    BorrowSnapshot, BorrowStatus, LiquidityGate, PreSubmissionGate, SpreadSnapshot,
)


def test_default_and_production_yaml_disable_step11_quote_check():
    assert RiskConfig().quote_spread_check_enabled is False
    root = Path(__file__).resolve().parents[1]
    data = yaml.safe_load((root / 'config.yaml').read_text(encoding='utf-8'))
    assert data['risk_management']['quote_spread_check_enabled'] is False
    assert load_risk_config(equity=1974.30).quote_spread_check_enabled is False


@pytest.mark.parametrize('enabled', [False, True])
def test_yaml_switch_survives_capital_preset_resolution(enabled):
    config = RiskConfig.from_yaml_section(
        {'quote_spread_check_enabled': enabled}, equity=1974.30,
    )
    assert config.quote_spread_check_enabled is enabled


@pytest.mark.parametrize('bad', ['false', 'true', 0, 1, None])
def test_switch_requires_real_boolean(bad):
    with pytest.raises(ValueError, match='booléen'):
        RiskConfig.from_yaml_section({'quote_spread_check_enabled': bad})
    with pytest.raises(ValueError, match='booléen'):
        LiquidityGate(quote_spread_check_enabled=bad)


@pytest.mark.parametrize('enabled', [False, True])
def test_step11_loads_quotes_only_when_enabled_and_always_loads_borrow(monkeypatch, enabled):
    import risk_management.cli as cli

    calls = []
    today = date(2026, 10, 27)
    borrow = {'AAPL': BorrowSnapshot('AAPL')}

    def quotes(symbols, *, account_id):
        assert enabled, 'Disabled step 11 must never call latest quotes'
        calls.append(('quotes', symbols, account_id))
        return {}  # Realistic outcome on SIP HTTP 403.

    def loans(symbols, *, account_id, trade_date):
        calls.append(('borrow', symbols, account_id, trade_date))
        return borrow

    monkeypatch.setattr(cli, '_load_live_spread_snapshots', quotes)
    monkeypatch.setattr(cli, '_load_live_borrow_snapshots', loans)
    gate, spreads, actual_borrow = cli._load_risk_liquidity_inputs(
        RiskConfig(quote_spread_check_enabled=enabled), ['AAPL'],
        account_id='default', trade_date=today,
    )
    assert spreads == {}
    assert actual_borrow is borrow
    assert calls[-1] == ('borrow', ['AAPL'], 'default', today)
    assert len(calls) == (2 if enabled else 1)
    result = gate.evaluate('AAPL', 'long', 100, adv_usd=10_000_000)
    assert result.go is (not enabled)
    assert result.quote_spread_checked is enabled
    assert ('quote_snapshot_manquant' in result.reason) is enabled


@pytest.mark.parametrize('quote', [
    None,
    SpreadSnapshot('AAPL'),
    SpreadSnapshot('AAPL', bid=90, ask=110, quote_time=datetime.now(timezone.utc)),
    SpreadSnapshot('AAPL', bid=99.99, ask=100.01,
                   quote_time=datetime.now(timezone.utc) - timedelta(days=1)),
])
def test_disabled_quote_check_ignores_missing_invalid_wide_stale_quotes(quote):
    gate = LiquidityGate(quote_spread_check_enabled=False)
    result = gate.evaluate('AAPL', 'long', 100, spread=quote, adv_usd=10_000_000)
    baseline = gate.evaluate('AAPL', 'long', 100, adv_usd=10_000_000)
    assert result.go
    assert result.to_dict()['quote_spread_checked'] is False
    assert result.estimated_slippage_bps == baseline.estimated_slippage_bps


@pytest.mark.parametrize('kwargs,reason', [
    ({'adv_usd': None}, 'adv_indisponible'),
    ({'adv_usd': 1_000}, 'min_adv'),
    ({'side': 'short'}, 'borrow_snapshot_manquant'),
    ({'side': 'short', 'borrow': BorrowSnapshot('AAPL', status=BorrowStatus.NOT_SHORTABLE)}, 'not_shortable'),
    ({'side': 'short', 'borrow': BorrowSnapshot('AAPL', status=BorrowStatus.HARD_TO_BORROW)}, 'HTB_sans_locate'),
])
def test_disabling_quote_guard_preserves_other_liquidity_vetoes(kwargs, reason):
    params = {'side': 'long', 'adv_usd': 10_000_000, **kwargs}
    side = params.pop('side')
    result = LiquidityGate(quote_spread_check_enabled=False).evaluate('AAPL', side, 100, **params)
    assert not result.go
    assert reason in result.reason


def test_disabling_quotes_preserves_slippage_limit():
    result = LiquidityGate(quote_spread_check_enabled=False, max_slippage_bps=0).evaluate(
        'AAPL', 'long', 100, adv_usd=10_000_000,
    )
    assert not result.go
    assert 'slippage_estime' in result.reason


def test_disabling_quotes_preserves_participation_limit():
    result = LiquidityGate(quote_spread_check_enabled=False).evaluate(
        'AAPL', 'long', 20_000, adv_usd=1_000_000,
    )
    assert not result.go
    assert 'max_entry' in result.reason


def test_execution_stays_strict_even_given_step11_gate_with_quotes_disabled():
    gate = PreSubmissionGate(liquidity_gate=LiquidityGate(quote_spread_check_enabled=False))
    result = gate.evaluate('AAPL', 'long', 100, adv_usd=10_000_000)
    assert not result.go
    assert result.reason == 'spread_indisponible_pre_soumission'
