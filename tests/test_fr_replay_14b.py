from dataclasses import replace
import json

import pytest

from service.fr import research_replay_14b as replay
from ihm.services import backtesting_runner, fr_replay_launch


@pytest.mark.parametrize('changes', [
    {'market_code': 'US_EQ'}, {'market_code': 'CN_A'}, {'database_alias': 'us_primary'},
    {'fold': 8}, {'fold': True}, {'policy': 'short'}, {'variant': 'optimized'},
    {'tax_scenario': 'exempt'}, {'cost_scenario': 'zero'},
])
def test_fr_rejects_cross_market_and_unregistered_cells(changes):
    with pytest.raises(ValueError):
        replay.validate_options(replace(replay.FRResearchReplayOptions(), **changes))


def test_fr_command_never_uses_us_module():
    options = replay.FRResearchReplayOptions(output_root=str(replay.OUTPUT_PARENT / 'test' / 'artifacts'))
    command = backtesting_runner.build_backtesting_command('fr-research-replay', options)
    assert command[command.index('-m')+1] == 'service.fr.research_replay_14b'
    assert 'backtesting' not in command
    assert command[command.index('--market-code')+1] == 'FR_EQ'
    assert command[command.index('--database-alias')+1] == 'fr_primary'
    with pytest.raises(TypeError):
        backtesting_runner.build_backtesting_command('fr-research-replay', backtesting_runner.BacktestRunOptions(start='2024-01-01'))


@pytest.mark.parametrize('output', [None, 'artifacts/models', str(replay.OUTPUT_PARENT)])
def test_output_scope(output):
    with pytest.raises(ValueError):
        replay.validate_options(replay.FRResearchReplayOptions(output_root=output), require_output=True)


def test_worker_preflight_error_is_observable_and_doesnt_overwrite(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(replay, 'OUTPUT_PARENT', tmp_path)
    def reject(_options):
        raise ValueError('changed archive')
    monkeypatch.setattr(replay, 'preflight', reject)
    options = replay.FRResearchReplayOptions(output_root=str(tmp_path / 'run' / 'artifacts'))
    with pytest.raises(ValueError, match='changed archive'):
        replay.run(options)
    result = json.loads((tmp_path / 'run/artifacts/failure.json').read_text())
    assert result['status'] == 'FAILED'
    assert result['economic_go_allowed'] is False
    assert replay.latest_progress_event(capsys.readouterr().out)['stage'] == 'failed'
    with pytest.raises(FileExistsError):
        replay.run(options)


def test_progress_parser_ignores_other_markets_and_corrupt_events():
    assert replay.latest_progress_event('::cn_replay_progress::{"stage":"completed"}') is None
    assert replay.latest_progress_event(replay.PROGRESS_PREFIX + '{bad') is None
    assert replay.latest_progress_event(replay.PROGRESS_PREFIX + '{"stage":"fake"}') is None
    assert replay.latest_progress_event(replay.PROGRESS_PREFIX + '{"stage":"loading"}\n' + replay.PROGRESS_PREFIX + '{bad')['stage'] == 'loading'


def test_us_history_excludes_fr_and_cn(monkeypatch):
    from ihm.pages import backtesting
    records = [dict(run_id='us', run_kind='run'), dict(run_id='cn', run_kind='cn-research-replay'),
               dict(run_id='fr', run_kind='fr-research-replay')]
    monkeypatch.setattr(backtesting, 'load_backtesting_history', lambda: records)
    monkeypatch.setattr(backtesting, 'list_active_backtesting_runs', lambda: records)
    active, all_runs = backtesting._merge_runs()
    assert [r['run_id'] for r in active] == ['us']
    assert [r['run_id'] for r in all_runs] == ['us']


def test_registry_dedicated_command_without_db(tmp_path, monkeypatch):
    from ihm.services import backtesting_registry as registry, pipeline_lock
    class FakeProcess:
        pid = 4242
        stdout = stderr = None
        def poll(self):
            return 0
    class FakeThread:
        def __init__(self, *a, **k):
            pass
        def start(self):
            pass
        def join(self, timeout=None):
            pass
    runs = tmp_path / 'runs'
    launched = []
    monkeypatch.setattr(registry, 'RUNS_DIR', runs)
    monkeypatch.setattr(registry, 'HISTORY_INDEX_PATH', runs / 'history_index.json')
    monkeypatch.setattr(registry, '_ACTIVE_RUNS', {})
    monkeypatch.setattr(replay, 'OUTPUT_PARENT', runs / 'fr-research-replay')
    monkeypatch.setattr(fr_replay_launch, 'preflight', lambda options: None)
    monkeypatch.setattr(registry, 'build_subprocess_env', lambda db_config=None: {})
    monkeypatch.setattr(registry.subprocess, 'Popen', lambda command, **kwargs: (launched.append(command), FakeProcess())[1])
    monkeypatch.setattr(registry.threading, 'Thread', FakeThread)
    pipeline_lock.set_locks_dir_for_tests(tmp_path / 'locks')
    try:
        record = registry.start_backtesting_run('fr-research-replay', 'FR research', replay.FRResearchReplayOptions())
        command = launched[0]
        assert command[command.index('-m')+1] == 'service.fr.research_replay_14b'
        assert record.run_id in command[-1]
        assert registry.poll_backtesting_run(record.run_id)['status'] == 'completed'
    finally:
        pipeline_lock.set_locks_dir_for_tests(None)
