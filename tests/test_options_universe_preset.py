"""Options universe lineage and actual sizing capital must remain separate."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from risk_management import cli
from risk_management.config import RiskConfig
from service.options_directional import risk_adapter


DAY = date(2026, 10, 26)
REPORT = dict(run_id='opt-'+'a'*32, status='COMPLETED', trade_date=str(DAY),
              account_id='default', capital_preset_key='capital_2001_5000')


@pytest.mark.parametrize('equity', [1500., 1974.30, 4000., 12000.])
@pytest.mark.parametrize('account', ['default','test1','test2'])
def test_options_keeps_archived_preset_without_changing_equity(monkeypatch, equity, account):
    resolver = Mock(side_effect=AssertionError('No implicit equity universe fallback'))
    monkeypatch.setattr(cli, 'resolve_capital_preset_for_equity', resolver)
    repo = SimpleNamespace(load_tradable_universe_asof=Mock(return_value='exact-universe'))
    cfg = RiskConfig(account_equity=equity)
    fingerprint = cfg.fingerprint
    assert cli._load_tradable_universe_for_risk(repo, trade_date=DAY,
        effective_equity=cfg.account_equity, options_filter_report=REPORT,account_id=account) == (
            'exact-universe', 'capital_2001_5000', 'options_archived_input')
    repo.load_tradable_universe_asof.assert_called_once_with(DAY, 'capital_2001_5000')
    resolver.assert_not_called()
    assert cfg.account_equity == equity and cfg.fingerprint == fingerprint


@pytest.mark.parametrize('key', [None, '', False, 'invalid-preset', ' capital_2001_5000 '])
def test_bad_archived_preset_never_falls_back(key):
    repo = SimpleNamespace(load_tradable_universe_asof=Mock())
    with pytest.raises(ValueError, match='Preset'):
        cli._load_tradable_universe_for_risk(repo, trade_date=DAY,
            effective_equity=1974.30, options_filter_report={**REPORT, 'capital_preset_key':key})
    repo.load_tradable_universe_asof.assert_not_called()


@pytest.mark.parametrize('change', [dict(trade_date='2026-10-23'), dict(account_id='test1'),
                                    dict(status='FAILED'), dict(run_id=None)])
def test_incompatible_report_fails(change):
    with pytest.raises(ValueError, match='incompatible'):
        risk_adapter.archived_universe_preset({**REPORT, **change}, DAY)


def test_missing_publication_still_blocks():
    from common.tradable_universe import UniverseSnapshotNotFoundError
    repo = SimpleNamespace(load_tradable_universe_asof=Mock(
        side_effect=UniverseSnapshotNotFoundError('missing')))
    with pytest.raises(UniverseSnapshotNotFoundError):
        cli._load_tradable_universe_for_risk(repo, trade_date=DAY,
            effective_equity=1974.30, options_filter_report=REPORT)
    repo.load_tradable_universe_asof.assert_called_once_with(DAY, 'capital_2001_5000')


def test_two_directional_filters_are_not_combined():
    with pytest.raises(ValueError, match='Un seul filtre'):
        cli._load_tradable_universe_for_risk(object(), trade_date=DAY, effective_equity=1974.30,
            llm_filter_run_id='llm-test', options_filter_report=REPORT)
