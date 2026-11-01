"""Reclaim only a proven dead local watcher lease, never an active leader."""
from datetime import timezone
import logging
from pathlib import Path
import socket

import psutil
from sqlalchemy import text

LOGGER = logging.getLogger(__name__)


def release_dead_local_watcher_lease(engine, account_id, *, dry_run=False):
    scope = f'watcher:{account_id or "default"}'
    with engine.connect() as conn:
        lease = conn.execute(text('SELECT locked_by_run_id,acquired_at,expires_at FROM execution_locks '
            'WHERE account_id=:scope'), dict(scope=scope)).mappings().first()
        heartbeat = conn.execute(text('SELECT pid,hostname,last_heartbeat_at FROM watcher_heartbeats '
            'WHERE account_id=:account AND watcher_name=\'execution_protection_watcher\''),
            dict(account=account_id or 'default')).mappings().first()
    if not lease or not heartbeat or str(heartbeat['hostname']).lower() != socket.gethostname().lower():
        return False
    if not str(lease['locked_by_run_id']).startswith('watch-service-'):
        return False
    # A freshly acquired lease may precede its first heartbeat. Never steal it.
    def utc(value):
        if isinstance(value, str):
            from datetime import datetime
            value = datetime.fromisoformat(value)
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if utc(lease['acquired_at']) > utc(heartbeat['last_heartbeat_at']):
        return False
    try:
        psutil.Process(int(heartbeat['pid']))
    except psutil.NoSuchProcess:
        pass
    except (psutil.AccessDenied, TypeError, ValueError) as exc:
        raise RuntimeError('Watcher précédent non vérifiable ; verrou conservé') from exc
    else:
        return False  # Includes PID reuse: uncertainty is never permission.
    expected = Path(__file__).with_name('protection_watcher.py').resolve()
    for process in psutil.process_iter(['cmdline']):
        command = process.info.get('cmdline') or []
        try:
            script_ok = any(Path(v).name == expected.name and Path(v).resolve() == expected for v in command)
        except (OSError, ValueError):
            continue
        if not script_ok:
            continue
        account = command[command.index('--account')+1] if '--account' in command else 'default'
        if account == (account_id or 'default'):
            return False
    params = dict(scope=scope, account=account_id or 'default', owner=lease['locked_by_run_id'],
        acquired=lease['acquired_at'], expires=lease['expires_at'], pid=heartbeat['pid'],
        hostname=heartbeat['hostname'], heartbeat=heartbeat['last_heartbeat_at'])
    if dry_run:
        return True
    with engine.begin() as conn:
        removed = conn.execute(text('''DELETE FROM execution_locks WHERE account_id=:scope
            AND locked_by_run_id=:owner AND acquired_at=:acquired AND expires_at=:expires
            AND EXISTS (SELECT 1 FROM watcher_heartbeats WHERE account_id=:account
                AND watcher_name='execution_protection_watcher' AND pid=:pid AND hostname=:hostname
                AND last_heartbeat_at=:heartbeat)'''), params).rowcount
        if removed:
            conn.execute(text('''UPDATE watcher_heartbeats SET status='STOPPED'
                WHERE account_id=:account AND watcher_name='execution_protection_watcher'
                AND pid=:pid AND hostname=:hostname AND last_heartbeat_at=:heartbeat'''),params)
    if removed:
        LOGGER.info('Verrou watcher abandonné libéré: account=%s ancien_pid=%s owner=%s',
            account_id,heartbeat['pid'],lease['locked_by_run_id'])
    return bool(removed)
