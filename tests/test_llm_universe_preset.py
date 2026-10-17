"""Archived universe preset is independent of PAPER sizing equity. No broker/API."""
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import update

from risk_management import cli
from service.llm_directional import risk_adapter
from service.llm_directional.repository import runs
from tests.test_llm_directional_filter import isolated, analyze, response


DAY = date(2026, 10, 7)


def create_analysis(engine):
    return analyze(engine, lambda request: response(json.loads(request['input'])['symbol']))


def test_1974_dollars_keeps_the_qualified_2001_universe(isolated, monkeypatch):
    create_analysis(isolated)
    universe = SimpleNamespace(symbols=('ABC',), data_quality_grade='full', universe_run_id='u-exact')
    repo = SimpleNamespace(engine=isolated, load_tradable_universe_asof=Mock(return_value=universe))
    equity_resolver = Mock(side_effect=AssertionError('No implicit equity fallback in LLM universe lookup'))
    monkeypatch.setattr(cli, 'resolve_capital_preset_for_equity', equity_resolver)
    result, key, source = cli._load_tradable_universe_for_risk(repo, trade_date=DAY,
        effective_equity=1974.30, llm_filter_run_id='test-run', account_id='default')
    assert result is universe and key == 'capital_2001_5000' and source == 'llm_archived_input'
    repo.load_tradable_universe_asof.assert_called_once_with(DAY, 'capital_2001_5000')
    equity_resolver.assert_not_called()


@pytest.mark.parametrize('equity', [1500., 1974.30, 4000., 12000.])
def test_equity_does_not_change_the_archived_universe(isolated, equity):
    create_analysis(isolated)
    repo = SimpleNamespace(engine=isolated, load_tradable_universe_asof=Mock(return_value='u'))
    assert cli._load_tradable_universe_for_risk(repo, trade_date=DAY, effective_equity=equity,
        llm_filter_run_id='test-run')[1] == 'capital_2001_5000'


def test_non_llm_retains_equity_based_lookup(monkeypatch):
    resolver = Mock(return_value=SimpleNamespace(key='capital_0_2000'))
    monkeypatch.setattr(cli, 'resolve_capital_preset_for_equity', resolver)
    repo = SimpleNamespace(load_tradable_universe_asof=Mock(return_value='u'))
    assert cli._load_tradable_universe_for_risk(repo, trade_date=DAY, effective_equity=1974.30) == (
        'u', 'capital_0_2000', 'account_equity')
    resolver.assert_called_once_with(1974.30)
    repo.load_tradable_universe_asof.assert_called_once_with(DAY, 'capital_0_2000')


@pytest.mark.parametrize('key', [None, '', False, 'invalid-preset', ' capital_2001_5000 '])
def test_bad_archived_preset_never_falls_back(monkeypatch, key):
    run = {'input_json': json.dumps({'capital_preset_key': key})}
    monkeypatch.setattr(risk_adapter, 'qualified_selection', Mock(return_value=(run, [])))
    repo = SimpleNamespace(engine=object(), load_tradable_universe_asof=Mock())
    with pytest.raises(ValueError, match='[Pp]reset'):
        cli._load_tradable_universe_for_risk(repo, trade_date=DAY, effective_equity=1974.30,
                                           llm_filter_run_id='llm-id')
    repo.load_tradable_universe_asof.assert_not_called()


def test_snapshot_hash_check_still_precedes_lookup(isolated):
    create_analysis(isolated)
    with isolated.begin() as conn:
        conn.execute(update(runs).where(runs.c.run_id == 'test-run')
                     .values(input_json=json.dumps({'capital_preset_key': 'capital_0_2000'})))
    repo = SimpleNamespace(engine=isolated, load_tradable_universe_asof=Mock())
    with pytest.raises(ValueError, match='Snapshot LLM altéré'):
        cli._load_tradable_universe_for_risk(repo, trade_date=DAY, effective_equity=1974.30,
                                           llm_filter_run_id='test-run')
    repo.load_tradable_universe_asof.assert_not_called()


def test_missing_published_universe_remains_blocking(isolated):
    create_analysis(isolated)
    from common.tradable_universe import UniverseSnapshotNotFoundError
    repo = SimpleNamespace(engine=isolated, load_tradable_universe_asof=Mock(
        side_effect=UniverseSnapshotNotFoundError('missing publication')))
    with pytest.raises(UniverseSnapshotNotFoundError):
        cli._load_tradable_universe_for_risk(repo, trade_date=DAY, effective_equity=1974.30,
                                           llm_filter_run_id='test-run')
    repo.load_tradable_universe_asof.assert_called_once_with(DAY, 'capital_2001_5000')


def test_preset_lookup_does_not_inflate_existing_sizing_equity(isolated):
    create_analysis(isolated)
    from risk_management.config import RiskConfig
    # The helper takes a scalar equity, never a mutable RiskConfig to override.
    cfg = RiskConfig(account_equity=1974.30)
    before = cfg.fingerprint
    repo = SimpleNamespace(engine=isolated, load_tradable_universe_asof=Mock(return_value='u'))
    cli._load_tradable_universe_for_risk(repo, trade_date=DAY, effective_equity=cfg.account_equity,
                                      llm_filter_run_id='test-run')
    assert cfg.account_equity == 1974.30 and cfg.fingerprint == before


def test_llm_candidate_outside_tradable_universe_is_still_excluded(isolated):
    create_analysis(isolated)
    assert risk_adapter.load_candidates(isolated, 'test-run', DAY, 'default', 'u-exact', ['OTHER']) == []
