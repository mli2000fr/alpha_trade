"""Execution must use the canonical risk repository, never the removed RiskDbIo."""
from datetime import date
from unittest.mock import MagicMock

import pytest

import run_execution
from risk_management import db_io
from risk_management.liquidity import PreSubmissionGate
from risk_management.models import PriceInfo


def test_adv_vol_load_uses_real_repository_api_at_signal_date(monkeypatch):
    factory = MagicMock()
    factory.return_value.load_prices_asof.return_value = {
        'OKTA': PriceInfo('OKTA', 100, 2, date(2026, 10, 27), date(2026, 10, 27), 10_000_000),
        'P': PriceInfo('P', 50, None, date(2026, 10, 27), None, None),
    }
    monkeypatch.setattr(db_io, 'RiskRepository', factory)
    adv, vol = run_execution._load_pre_submission_adv_vol(['P', 'OKTA'], trade_date=date(2026, 10, 27))
    factory.assert_called_once_with()
    factory.return_value.load_prices_asof.assert_called_once_with(
        symbols=['P', 'OKTA'], trade_date=date(2026, 10, 27), atr_window=20,
    )
    assert adv == {'OKTA': 10_000_000}
    assert vol == {'OKTA': .02}
    # Loading ADV cannot bypass an unavailable quote at order submission.
    result = PreSubmissionGate().evaluate('OKTA', 'long', 100, adv_usd=adv['OKTA'], daily_vol_pct=vol['OKTA'])
    assert not result.go and result.reason == 'spread_indisponible_pre_soumission'


def test_no_targets_does_not_instantiate_repository(monkeypatch):
    factory = MagicMock(side_effect=AssertionError('No database call expected'))
    monkeypatch.setattr(db_io, 'RiskRepository', factory)
    assert run_execution._load_pre_submission_adv_vol([], trade_date=date(2026, 10, 27)) == ({}, {})
    factory.assert_not_called()


@pytest.mark.parametrize('failure_phase', ['constructor', 'load'])
def test_repository_failure_returns_missing_data_without_fake_liquidity(monkeypatch, failure_phase):
    factory = MagicMock()
    if failure_phase == 'constructor':
        factory.side_effect = RuntimeError('DB unavailable')
    else:
        factory.return_value.load_prices_asof.side_effect = RuntimeError('DB unavailable')
    monkeypatch.setattr(db_io, 'RiskRepository', factory)
    assert run_execution._load_pre_submission_adv_vol(['OKTA'], trade_date=date(2026, 10, 27)) == ({}, {})


@pytest.mark.parametrize('adv,atr,close', [(float('nan'), float('nan'), 100),
    (float('inf'), float('inf'), 100), (-1, -1, 100), (None, 2, 0), (None, 2, float('inf'))])
def test_invalid_numbers_are_not_published_as_usable_inputs(monkeypatch, adv, atr, close):
    repo = MagicMock()
    repo.load_prices_asof.return_value = {'OKTA': PriceInfo('OKTA', close, atr, adv_usd=adv)}
    monkeypatch.setattr(db_io, 'RiskRepository', lambda: repo)
    assert run_execution._load_pre_submission_adv_vol(['OKTA'], trade_date=date(2026, 10, 27)) == ({}, {})
