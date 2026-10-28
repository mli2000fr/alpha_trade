"""Exclusive risk attempt; retry only a proven pre-publication lookup failure."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import re
import uuid

from .store import digest, write_new


@contextmanager
def risk_lock(folder, *, lock_name='risk.lock'):
    # Kernel lock, released on process death. The durable claim is separate.
    with (folder/lock_name).open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _failure_path(folder, attempt_id):
    if not isinstance(attempt_id, str) or not re.fullmatch(r'[a-f0-9]{32}', attempt_id):
        raise ValueError('Identifiant de tentative risque invalide')
    return folder/f'risk.prepublication_failure.{attempt_id}.json'


def record_universe_lookup_failure(folder, attempt_id, report, error,*,account_id='default'):
    """Called ONLY at the universe-loading checkpoint, never after publication."""
    path = _failure_path(folder, attempt_id)
    claim = json.loads((folder/'risk.claim.json').read_text(encoding='utf-8'))
    if (claim.get('attempt_id') != attempt_id or claim.get('run_id') != report['run_id']
            or claim.get('account_id','default')!=account_id
            or claim.get('report_sha256') != digest(report)):
        raise ValueError('Tentative risque incompatible avec le snapshot options')
    write_new(path, dict(attempt_id=attempt_id, run_id=report['run_id'],account_id=account_id,
        claim_sha256=digest(claim), report_sha256=digest(report),
        phase='universe_lookup_before_publication', retryable=True,
        error_type=type(error).__name__, error=str(error),
        failed_at=datetime.now(timezone.utc).isoformat()))


@contextmanager
def risk_attempt(folder, report,*,account_id='default'):
    with risk_lock(folder):
        # An existing output, even partial or invalid, is an ambiguous outcome.
        # Never recompute over it or allow a second execution.
        for name in ('risk_summary.json', 'risk_binding.json', 'execution.claim.json'):
            if (folder/name).exists():
                raise FileExistsError(f'Risque déjà publié ou issue ambiguë : {name} ; vérifier avant reprise')
        claim_path = folder/'risk.claim.json'
        if claim_path.exists():
            old = json.loads(claim_path.read_text(encoding='utf-8'))
            attempt_id = old.get('attempt_id')
            if not attempt_id:
                raise FileExistsError('Ancien verrou risque sans preuve de reprise ; vérification manuelle requise')
            failure_path = _failure_path(folder, attempt_id)
            if not failure_path.exists():
                raise FileExistsError('Risque déjà tenté, issue non qualifiée ; aucune reprise automatique')
            failure = json.loads(failure_path.read_text(encoding='utf-8'))
            if (old.get('run_id') != report['run_id'] or old.get('report_sha256') != digest(report)
                    or old.get('account_id','default')!=account_id
                    or failure.get('account_id','default')!=account_id
                    or failure.get('attempt_id') != attempt_id or failure.get('run_id') != report['run_id']
                    or failure.get('phase') != 'universe_lookup_before_publication'
                    or failure.get('retryable') is not True
                    or failure.get('claim_sha256') != digest(old)
                    or failure.get('report_sha256') != digest(report)):
                raise ValueError('Preuve de reprise risque altérée ou incompatible')
            archive = folder/'risk_attempts'/attempt_id
            archive.mkdir(parents=True, exist_ok=False)
            claim_path.rename(archive/'risk.claim.json')
        claim = dict(attempt_id=uuid.uuid4().hex, run_id=report['run_id'],account_id=account_id,
                     report_sha256=digest(report), started_at=datetime.now(timezone.utc).isoformat())
        write_new(claim_path, claim)
        yield claim
