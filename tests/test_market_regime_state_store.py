"""State sentinel regression; local temp files, no SQL/API/broker calls."""
from datetime import date
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from service.market.models import MarketRegimeState
from service.market.state_store import load_regime_state, save_regime_state


def test_missing_file_has_no_previous_state(tmp_path):
    assert load_regime_state(tmp_path / 'absent.json') is None


def test_empty_dict_sentinel_has_no_previous_state(tmp_path):
    path = tmp_path / 'latest.json'
    path.write_text('{}', encoding='utf-8')
    assert load_regime_state(path) is None
    assert path.read_text(encoding='utf-8') == '{}'


def test_writer_none_roundtrip(tmp_path):
    path = tmp_path / 'latest.json'
    save_regime_state(None, path)
    assert json.loads(path.read_text(encoding='utf-8')) == {}
    assert load_regime_state(path) is None


def test_valid_defensive_state_is_not_reset(tmp_path):
    path = tmp_path / 'latest.json'
    state = MarketRegimeState(trade_date=date(2026, 10, 16), current_mode='close_only',
        previous_mode='capital_preservation', entered_at=date(2026, 10, 15),
        last_transition_at=date(2026, 10, 15), last_hard_trigger_at=date(2026, 10, 16),
        soft_entry_streak=2, hard_calm_streak=1, days_in_current_mode=2,
        release_remaining_days=3)
    save_regime_state(state, path)
    assert load_regime_state(path) == state


@pytest.mark.parametrize('content', ['[]', 'null', 'true', '42', '"text"',
    '{"current_mode":"close_only"}', '{"trade_date":"invalid"}',
    '{"trade_date":null}', '{"trade_date":"2026-10-16","soft_entry_streak":"bad"}',
    '', '{'])
def test_malformed_nonempty_state_stays_an_error(tmp_path, content):
    path = tmp_path / 'latest.json'
    path.write_text(content, encoding='utf-8')
    with pytest.raises((ValueError, TypeError)):
        load_regime_state(path)
    assert path.read_text(encoding='utf-8') == content


def test_risk_empty_state_reaches_snapshot_calculation_without_forcing_normal(monkeypatch, tmp_path):
    import service.market as market
    from risk_management import cli
    day = date(2026, 10, 16)
    path = tmp_path / 'latest.json'
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(cli, 'load_config', lambda: {'market_regimes': {'enabled': True}})
    monkeypatch.setattr(market, 'load_regime_state', lambda: load_regime_state(path))
    monkeypatch.setattr(market, 'save_regime_state', lambda state: save_regime_state(state, path))
    monkeypatch.setattr(market, 'build_default_macro_provider', lambda cfg: object())
    monkeypatch.setattr(market, 'DbSentimentScoreProvider', lambda *a, **kw: object())
    next_state = MarketRegimeState(trade_date=day, current_mode='close_only')
    snapshot = SimpleNamespace(trade_date=day, mode='close_only', next_state=next_state)
    builder = Mock(return_value=snapshot)
    monkeypatch.setattr(market, 'build_snapshot', builder)
    result = cli._resolve_market_regime_snapshot(day, 1974.30, SimpleNamespace(engine=None))
    assert result is snapshot and result.mode == 'close_only'
    assert builder.call_args.kwargs['previous_state'] is None
    assert builder.call_args.args[0] == day
    assert load_regime_state(path) == next_state


@pytest.mark.parametrize('malformed', [False, True])
def test_bad_macro_or_corrupt_state_does_not_become_qualified_normal(monkeypatch, tmp_path, malformed):
    import service.market as market
    from risk_management import cli
    path = tmp_path / 'latest.json'
    content = '{"current_mode":"close_only"}' if malformed else '{}'
    path.write_text(content, encoding='utf-8')
    monkeypatch.setattr(cli, 'load_config', lambda: {'market_regimes': {'enabled': True}})
    monkeypatch.setattr(market, 'load_regime_state', lambda: load_regime_state(path))
    monkeypatch.setattr(market, 'build_default_macro_provider', lambda cfg: object())
    monkeypatch.setattr(market, 'DbSentimentScoreProvider', lambda *a, **kw: object())
    builder = Mock(side_effect=ValueError('macro unavailable'))
    save = Mock()
    monkeypatch.setattr(market, 'build_snapshot', builder)
    monkeypatch.setattr(market, 'save_regime_state', save)
    assert cli._resolve_market_regime_snapshot(date(2026, 10, 16), 1974.30, SimpleNamespace(engine=None)) is None
    save.assert_not_called()
    assert path.read_text(encoding='utf-8') == content
    if malformed:
        builder.assert_not_called()
