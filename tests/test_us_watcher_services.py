from datetime import UTC, datetime
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

from service.forward_pit import us_watcher_services as service
from service.forward_pit.outcomes import BatchRunError


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(service, 'ROOT', tmp_path)
    monkeypatch.setattr(service, '_utcnow', lambda: datetime(2026, 11, 25, 16, 30, tzinfo=UTC))
    registry = Mock()
    registry.resolve.return_value.mode = 'paper'
    monkeypatch.setattr(service, 'AccountRegistry', lambda: registry)
    monkeypatch.setattr(service, 'ExecutionRepository', Mock())
    present = Mock(return_value=None)
    start = Mock(return_value=dict(status='READY', pid=123, survives_batch_exit=True))
    health = Mock(return_value=True)
    monkeypatch.setattr(service, 'find_running_service', present)
    monkeypatch.setattr(service, 'healthy_service', health)
    monkeypatch.setattr(service, 'ensure_watcher', start)
    engine = SimpleNamespace(url=SimpleNamespace(database='alpha_trade'))
    cfg = dict(market_code='US_EQ', account_ids=['default', 'test1', 'test2'])
    return engine, cfg, present, start, health, registry


@pytest.mark.parametrize('instant,opened', [
    ('2026-11-25T14:29:59+00:00', False),
    ('2026-11-25T14:30:00+00:00', True),
    ('2026-11-25T20:30:00+00:00', True),
    ('2026-11-25T21:00:00+00:00', False),
    ('2026-11-26T16:30:00+00:00', False),  # Thanksgiving
    ('2026-11-27T17:30:00+00:00', True),
    ('2026-11-27T18:00:00+00:00', False),  # shortened session
    ('2026-11-28T16:30:00+00:00', False),
    ('2026-03-16T13:30:00+00:00', True),  # US DST before Europe
    ('2026-03-16T20:00:00+00:00', False),
])
def test_real_calendar_holidays_half_days_and_dst(instant, opened):
    assert service.market_state(datetime.fromisoformat(instant))['market_open'] is opened


def test_closed_market_never_queries_accounts_or_starts(env, monkeypatch):
    monkeypatch.setattr(service, '_utcnow', lambda: datetime(2026, 11, 26, 16, 30, tzinfo=UTC))
    result = service.collect(env[0], env[1], 'closed', False)
    assert result.details['skip_reason'] == 'US_MARKET_CLOSED'
    env[2].assert_not_called()
    env[3].assert_not_called()
    env[5].resolve.assert_not_called()


def test_all_running_services_are_preserved(env):
    env[2].return_value = SimpleNamespace(pid=456)
    result = service.collect(env[0], env[1], 'existing', False)
    assert (result.requested, result.received, result.persisted) == (3, 3, 0)
    assert result.details['already_running'] == 3
    env[3].assert_not_called()


def test_only_missing_accounts_started_sequentially_and_reported(env, tmp_path):
    env[2].side_effect = lambda a: SimpleNamespace(pid=456) if a == 'test1' else None
    result = service.collect(env[0], env[1], 'missing', False)
    assert (result.received, result.persisted) == (3, 2)
    options = [call.args[1] for call in env[3].call_args_list]
    assert [o.account_id for o in options] == ['default', 'test2']
    assert all(o.execution_mode == 'paper' and not o.q051_paper_enabled for o in options)
    assert all(not c.kwargs['stop_event'].is_set() for c in env[3].call_args_list)
    report = json.loads((tmp_path/'artifacts/operations/us_watcher_services/missing/report.json').read_text(encoding='utf-8'))
    assert report['details']['started'] == 2
    assert report['details']['services_survive_batch_exit']


def test_existing_unhealthy_or_starting_service_never_replaced(env):
    env[2].return_value = SimpleNamespace(pid=456)
    env[4].return_value = False
    with pytest.raises(BatchRunError) as error:
        service.collect(env[0], env[1], 'unhealthy', False)
    assert error.value.outcome.failed == 3
    env[3].assert_not_called()


def test_conflicting_service_reported_without_blocking_other_accounts(env):
    env[2].side_effect = [RuntimeError('Watcher incompatible'), None, None]
    with pytest.raises(BatchRunError) as error:
        service.collect(env[0], env[1], 'conflict', False)
    assert (error.value.outcome.failed, error.value.outcome.persisted) == (1, 2)
    assert [c.args[1].account_id for c in env[3].call_args_list] == ['test1', 'test2']


def test_dry_run_never_starts_or_writes(env, tmp_path):
    result = service.collect(env[0], env[1], 'preview', True)
    assert all(a['status'] == 'WOULD_START' for a in result.details['accounts'])
    env[3].assert_not_called()
    assert not (tmp_path/'artifacts').exists()


def test_race_uses_native_reused_result(env):
    env[3].return_value = dict(status='REUSED_HEALTHY')
    result = service.collect(env[0], env[1], 'race', False)
    assert result.persisted == 0 and result.details['already_running'] == 3


def test_close_during_supervision_prevents_new_start(env, monkeypatch):
    monkeypatch.setattr(service, 'market_state', Mock(side_effect=[
        dict(market_open=True), dict(market_open=False), dict(market_open=False), dict(market_open=False)]))
    result = service.collect(env[0], env[1], 'close', False)
    assert result.empty == 3
    env[3].assert_not_called()


def test_live_account_and_other_database_fail_before_any_start(env):
    env[5].resolve.return_value.mode = 'live'
    with pytest.raises(ValueError, match='PAPER'):
        service.collect(env[0], env[1], 'live', False)
    env[3].assert_not_called()
    env[0].url.database = 'alpha_trade_fr'
    with pytest.raises(ValueError, match='US_EQ'):
        service.collect(env[0], env[1], 'fr', False)


def test_batch_catalog_has_hourly_ny_schedule_and_is_visible_in_us():
    root = service.Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root/'batch.yaml').read_text(encoding='utf-8'))['us_watcher_services']
    assert cfg['enabled'] and cfg['timezone'] == 'America/New_York'
    assert cfg['run_hours'] == '9,10,11,12,13,14,15' and cfg['run_minutes'] == '30'
    from ihm.services.batch_management import load_market_batch_specs
    spec = next(s for s in load_market_batch_specs('US_EQ') if s.name == 'us_watcher_services')
    assert spec.runnable and spec.task_name == 'AlphaTrade-UsWatcherServices'
