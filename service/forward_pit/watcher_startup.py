"""Start a persistent US PAPER watcher before scheduled execution, never orders.

The ordinary IHM registry kills its children on exit. A scheduled batch exits
after its workflow, so this watcher uses independent file handles (not pipes)
and is deliberately not registered as a disposable workflow child.
"""
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import time
import uuid

from sqlalchemy import text

from execution_engine.db_io import ExecutionRepository
from ihm.services.pipeline_runner import PROJECT_ROOT, build_subprocess_env
from ihm.services.watcher_runtime import build_watcher_command

LOGGER = logging.getLogger(__name__)
STARTUP_TIMEOUT_SECONDS = 120


def _is_watcher_command(command):
    expected = (PROJECT_ROOT/'execution_engine/protection_watcher.py').resolve()
    for argument in command:
        try:
            path = Path(argument)
            if path.name == 'protection_watcher.py' and path.resolve() == expected:
                return True
        except (OSError, ValueError):
            continue  # Other programs' arguments need not be valid paths.
    return False


def _compatible(command, account_id):
    def flag(name, default=None):
        return command[command.index(name)+1] if name in command and command.index(name)+1 < len(command) else default
    return (flag('--mode') == 'service' and flag('--account') == account_id
            and flag('--broker-mode', 'paper') == 'paper' and '--exec-run-id' not in command)


def find_running_service(account_id):
    """Also catch a service still starting, before its first heartbeat exists."""
    import psutil
    for process in psutil.process_iter(['cmdline']):
        command = process.info.get('cmdline') or []
        if not _is_watcher_command(command):
            continue
        account = command[command.index('--account')+1] if '--account' in command else 'default'
        if account != account_id:
            continue
        if not _compatible(command, account_id):
            raise RuntimeError('Watcher déjà démarré mais incompatible ; étape 12 bloquée sans nouveau démarrage')
        return process
    return None


def healthy_service(repo, account_id):
    """A fresh heartbeat alone is not proof of an account-wide PAPER service."""
    if not repo.is_watcher_healthy(account_id=account_id):
        return False
    with repo.engine.connect() as conn:
        row = conn.execute(text('''SELECT pid, hostname FROM watcher_heartbeats
            WHERE account_id=:account AND watcher_name='execution_protection_watcher'
            ORDER BY last_heartbeat_at DESC LIMIT 1'''), {'account': account_id}).mappings().first()
    if not row or str(row.get('hostname') or '').lower() != socket.gethostname().lower():
        raise RuntimeError('Watcher existant non vérifiable sur cet ordinateur ; étape 12 bloquée')
    import psutil
    try:
        command = psutil.Process(int(row['pid'])).cmdline()
    except psutil.NoSuchProcess:
        return False
    except (psutil.AccessDenied, TypeError, ValueError) as exc:
        raise RuntimeError('Identité du watcher existant non vérifiable ; étape 12 bloquée') from exc
    # A once scan, a LIVE watcher or a service restricted to an older exec run
    # cannot provide the required continuous protection of new entries.
    if not _is_watcher_command(command) or not _compatible(command, account_id):
        raise RuntimeError('Watcher existant incompatible (mode/compte/périmètre) ; étape 12 bloquée')
    return True


def ensure_watcher(engine, options, *, directory, stop_event, timeout_seconds=STARTUP_TIMEOUT_SECONDS):
    """Reuse a healthy service; otherwise start once and await its SQL heartbeat."""
    if options.execution_mode != 'paper':
        return {'status': 'SKIPPED_SIMULATE'}
    if engine.url.database != 'alpha_trade':
        raise ValueError('Démarrage watcher réservé à alpha_trade US PAPER')
    from service.forward_pit.us_pipeline import require_paper_account
    account = options.account_id or 'default'
    require_paper_account(account)
    repo = ExecutionRepository(engine)
    if stop_event.is_set():
        raise RuntimeError('Démarrage watcher annulé avant étape 12')
    if healthy_service(repo, account):
        LOGGER.info('Watcher avant étape 12 : service PAPER sain réutilisé compte=%s', account)
        return {'status': 'REUSED_HEALTHY', 'account_id': account, 'broker_mode': 'paper'}
    existing = find_running_service(account)
    if existing is not None:
        LOGGER.info('Watcher déjà démarré compte=%s pid=%s ; attente du heartbeat, sans doublon', account, existing.pid)
        deadline = time.monotonic()+timeout_seconds
        while not stop_event.is_set():
            if healthy_service(repo, account):
                return {'status': 'REUSED_HEALTHY', 'pid': existing.pid, 'account_id': account, 'broker_mode': 'paper'}
            if not existing.is_running() or time.monotonic() >= deadline:
                raise RuntimeError('Watcher déjà démarré mais non sain ; étape 12 bloquée sans nouveau démarrage')
            stop_event.wait(.5)
        raise RuntimeError('Attente watcher annulée ; aucune étape 12 lancée')
    directory = Path(directory)/f'watcher-{uuid.uuid4().hex[:8]}'
    directory.mkdir(parents=True, exist_ok=False)
    command = build_watcher_command(mode='service', account_id=account, broker_mode='paper',
        profit_taker_pct=options.execution_take_profit_pct,
        trailing_stop_pct=options.execution_trailing_stop_pct,
        manual_buy_stop_loss_pct=options.execution_manual_buy_stop_loss_pct,
        trailing_activation_trigger=options.execution_trailing_trigger,
        trailing_activation_r_multiple=options.execution_trailing_r_multiple,
        trailing_activation_profit_pct=options.execution_trailing_profit_pct)
    # Pin the child to the exact same server/database/credential environment.
    # Credentials are never written to the state or the logs.
    env = build_subprocess_env(db_config={'name': 'alpha_trade'})
    env['DB_HOST'] = engine.url.host or 'localhost'
    if getattr(engine.url, 'port', None):
        env['DB_HOST'] += f':{engine.url.port}'
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP |
             subprocess.CREATE_BREAKAWAY_FROM_JOB) if os.name == 'nt' else 0
    with (directory/'stdout.log').open('a', encoding='utf-8') as stdout, (directory/'stderr.log').open('a', encoding='utf-8') as stderr:
        child = subprocess.Popen(command, cwd=str(PROJECT_ROOT), env=env,
            stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=flags,
            start_new_session=os.name != 'nt')
    state = {'status': 'STARTING', 'pid': child.pid, 'account_id': account, 'broker_mode': 'paper',
             'started_at': datetime.now(UTC).isoformat(), 'command': command,
             'stdout_path': str(directory/'stdout.log'), 'stderr_path': str(directory/'stderr.log'),
             'survives_batch_exit': True}
    def save():
        (directory/'startup.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    save()
    LOGGER.info('Watcher avant étape 12 : démarrage compte=%s pid=%s logs=%s', account, child.pid, directory)
    deadline = time.monotonic()+timeout_seconds
    try:
        while True:
            if stop_event.is_set():
                raise RuntimeError('Attente watcher annulée ; aucune étape 12 lancée')
            # Check process termination before accepting a possibly older heartbeat.
            code = child.poll()
            if code is not None:
                # Another verified service may have won leader election meanwhile.
                if healthy_service(repo, account):
                    state['status'] = 'REUSED_HEALTHY'
                    break
                raise RuntimeError(f'Watcher arrêté avant disponibilité (exit={code}) ; logs={directory}')
            if healthy_service(repo, account):
                state['status'] = 'READY'
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f'Heartbeat watcher absent après {timeout_seconds}s ; étape 12 bloquée ; logs={directory}')
            stop_event.wait(.5)
    except Exception as exc:
        state.update(status='STARTUP_FAILED', error=str(exc))
        save()
        # Do not kill a service that may already protect previously held positions.
        raise
    save()
    LOGGER.info('Watcher avant étape 12 : %s compte=%s', state['status'], account)
    return state
