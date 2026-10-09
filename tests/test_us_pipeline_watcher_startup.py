from dataclasses import replace
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from ihm.services.pipeline_runner import pipeline_page_default_options
from service.forward_pit import watcher_startup as startup


@pytest.fixture
def environment(monkeypatch, tmp_path):
    engine = SimpleNamespace(url=SimpleNamespace(database='alpha_trade', host='localhost'))
    options = replace(pipeline_page_default_options(trade_date='2026-10-09'),
                      execution_mode='paper', account_id='default')
    repo = MagicMock()
    monkeypatch.setattr(startup, 'ExecutionRepository', lambda e: repo)
    monkeypatch.setattr('service.forward_pit.us_pipeline.require_paper_account', lambda a: None)
    monkeypatch.setattr(startup, 'build_subprocess_env', lambda **kw: {})
    monkeypatch.setattr(startup, 'find_running_service', lambda account: None)
    child = Mock(pid=123, poll=Mock(return_value=None))
    spawn = Mock(return_value=child)
    monkeypatch.setattr(startup.subprocess, 'Popen', spawn)
    return engine, options, repo, child, spawn, tmp_path, threading.Event()


def run(env, **kwargs):
    engine, options, _, _, _, directory, event = env
    return startup.ensure_watcher(engine, options, directory=directory, stop_event=event, **kwargs)


def test_reuses_healthy_without_process_or_files(environment, monkeypatch):
    monkeypatch.setattr(startup, 'healthy_service', lambda *a: True)
    assert run(environment)['status'] == 'REUSED_HEALTHY'
    environment[4].assert_not_called()
    assert not list(environment[5].glob('watcher-*'))


def test_start_waits_for_heartbeat_and_outlives_parent(environment, monkeypatch):
    health = iter([False, False, True])
    monkeypatch.setattr(startup, 'healthy_service', lambda *a: next(health))
    result = run(environment)
    assert result['status'] == 'READY' and result['survives_batch_exit']
    args, kw = environment[4].call_args
    command = args[0]
    assert command[command.index('--mode')+1] == 'service'
    assert command[command.index('--account')+1] == 'default'
    assert command[command.index('--broker-mode')+1] == 'paper'
    assert '--exec-run-id' not in command
    assert kw['stdin'] == startup.subprocess.DEVNULL
    # No pipes/read threads tied to the short-lived scheduled batch.
    assert kw['stdout'] != startup.subprocess.PIPE and kw['stderr'] != startup.subprocess.PIPE
    assert Path(result['stdout_path']).exists()
    assert kw['env']['DB_HOST'] == 'localhost'
    if startup.os.name == 'nt':
        assert kw['creationflags'] & startup.subprocess.CREATE_NO_WINDOW
        assert kw['creationflags'] & startup.subprocess.CREATE_BREAKAWAY_FROM_JOB
    environment[3].terminate.assert_not_called()
    environment[3].kill.assert_not_called()


def test_existing_process_waits_for_heartbeat_without_duplicate(environment, monkeypatch):
    health = iter([False, False, True])
    monkeypatch.setattr(startup, 'healthy_service', lambda *a: next(health))
    monkeypatch.setattr(startup, 'find_running_service', lambda account: SimpleNamespace(pid=456, is_running=lambda: True))
    assert run(environment)['status'] == 'REUSED_HEALTHY'
    environment[4].assert_not_called()


def test_existing_unhealthy_process_blocks_without_duplicate(environment, monkeypatch):
    monkeypatch.setattr(startup, 'healthy_service', lambda *a: False)
    monkeypatch.setattr(startup, 'find_running_service', lambda account: SimpleNamespace(pid=456, is_running=lambda: True))
    with pytest.raises(RuntimeError, match='sans nouveau démarrage'):
        run(environment, timeout_seconds=0)
    environment[4].assert_not_called()


def test_startup_timeout_blocks_and_reports_logs(environment, monkeypatch):
    monkeypatch.setattr(startup, 'healthy_service', lambda *a: False)
    with pytest.raises(RuntimeError, match='Heartbeat.*étape 12 bloquée'):
        run(environment, timeout_seconds=0)
    state = next(environment[5].glob('watcher-*/startup.json')).read_text(encoding='utf-8')
    assert 'STARTUP_FAILED' in state


def test_crash_before_heartbeat_blocks(environment, monkeypatch):
    monkeypatch.setattr(startup, 'healthy_service', lambda *a: False)
    environment[3].poll.return_value = 1
    with pytest.raises(RuntimeError, match='exit=1'):
        run(environment)


def test_leader_race_reuses_the_verified_winner(environment, monkeypatch):
    states = iter([False, True])
    monkeypatch.setattr(startup, 'healthy_service', lambda *a: next(states))
    environment[3].poll.return_value = 0
    assert run(environment)['status'] == 'REUSED_HEALTHY'


def test_simulate_never_starts_watcher(environment, monkeypatch):
    env = list(environment)
    env[1] = replace(env[1], execution_mode='simulate')
    monkeypatch.setattr(startup, 'healthy_service', lambda *a: pytest.fail('health queried'))
    assert run(env)['status'] == 'SKIPPED_SIMULATE'
    env[4].assert_not_called()


def test_cancel_before_start_and_other_database_rejected(environment):
    environment[6].set()
    with pytest.raises(RuntimeError, match='annulé'):
        run(environment)
    environment[4].assert_not_called()
    environment[0].url.database = 'alpha_trade_fr'
    with pytest.raises(ValueError, match='alpha_trade US PAPER'):
        run(environment)


@pytest.mark.parametrize('command,acceptable', [
    (['python', 'execution_engine/protection_watcher.py', '--mode', 'service', '--account', 'default', '--broker-mode', 'paper'], True),
    (['python', 'execution_engine/protection_watcher.py', '--mode', 'once'], False),
    (['python', 'execution_engine/protection_watcher.py', '--mode', 'service', '--account', 'test1'], False),
    (['python', 'execution_engine/protection_watcher.py', '--mode', 'service', '--broker-mode', 'live'], False),
    (['python', 'execution_engine/protection_watcher.py', '--mode', 'service', '--exec-run-id', 'old'], False),
    (['python', 'other.py', '--mode', 'service'], False),
])
def test_heartbeat_pid_must_identify_paper_account_wide_service(environment, monkeypatch, command, acceptable):
    repo = environment[2]
    repo.is_watcher_healthy.return_value = True
    repo.engine.connect.return_value.__enter__.return_value.execute.return_value.mappings.return_value.first.return_value = {
        'pid': 123, 'hostname': startup.socket.gethostname()}
    monkeypatch.setattr('psutil.Process', lambda pid: SimpleNamespace(cmdline=lambda: command))
    if acceptable:
        assert startup.healthy_service(repo, 'default')
    else:
        with pytest.raises(RuntimeError, match='incompatible'):
            startup.healthy_service(repo, 'default')


def test_dead_heartbeat_process_is_not_healthy(environment, monkeypatch):
    import psutil
    repo = environment[2]
    repo.engine.connect.return_value.__enter__.return_value.execute.return_value.mappings.return_value.first.return_value = {
        'pid': 123, 'hostname': startup.socket.gethostname()}
    def dead(pid):
        raise psutil.NoSuchProcess(pid)
    monkeypatch.setattr(psutil, 'Process', dead)
    assert not startup.healthy_service(repo, 'default')


def test_process_inventory_does_not_confuse_accounts(monkeypatch):
    command = [str(startup.PROJECT_ROOT/'execution_engine/protection_watcher.py'),
               '--mode', 'service', '--account', 'test1', '--broker-mode', 'paper']
    process = SimpleNamespace(info={'cmdline':command}, pid=321)
    monkeypatch.setattr('psutil.process_iter', lambda attrs: [process])
    assert startup.find_running_service('default') is None
    assert startup.find_running_service('test1') is process
    command[command.index('service')] = 'once'
    with pytest.raises(RuntimeError, match='déjà démarré mais incompatible'):
        startup.find_running_service('test1')
