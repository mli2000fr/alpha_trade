"""Migration jobs only: OS-held serialization + recoverable ownership receipt.

No SQL, batch, broker or watcher consults this lock. A killed worker releases
the OS guard; its JSON receipt is archived only after proving its owner dead.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

import psutil

LOCK='.alpha_trade_migration.lock.json'
GUARD='.alpha_trade_migration.guard'
MESSAGES={
    'MIGRATION_BUSY':'Une autre sauvegarde ou restauration utilise déjà ce projet.',
    'LOCK_OWNER_UNVERIFIED':'Le propriétaire du verrou ne peut pas être vérifié ; aucun déverrouillage automatique.',
    'LOCK_INVALID':'Le verrou de migration est illisible ; vérifier son propriétaire avant reprise.',
}


class MigrationLockError(ValueError):
    def __init__(self,code,pid=None):
        pid=pid if type(pid) is int and pid>0 else None
        self.code=code;self.owner_pid=pid
        super().__init__(MESSAGES[code]+(f' PID : {pid}.' if pid else ''))


def worker_identity():
    return dict(pid=os.getpid(),process_created_at=psutil.Process(os.getpid()).create_time())


def owner_state(receipt):
    """Return alive/dead/unknown; a reused PID does not own an older receipt."""
    pid=receipt.get('pid')
    if type(pid) is not int or pid<=0:return 'unknown'
    try:
        process=psutil.Process(pid)
        if not process.is_running() or process.status()==psutil.STATUS_ZOMBIE:return 'dead'
        created=process.create_time();expected=receipt.get('process_created_at')
        if type(expected) in (int,float) and abs(created-expected)>.1:return 'dead'
        if expected is None:
            try:started=datetime.fromisoformat(receipt['started_at']).timestamp()
            except (KeyError,TypeError,ValueError):return 'unknown'
            if created>started+1:return 'dead'
        return 'alive'
    except psutil.NoSuchProcess:return 'dead'
    except (psutil.AccessDenied,OSError):return 'unknown'


@contextmanager
def os_guard(root):
    path=Path(root)/GUARD
    # Never unlink this inode: doing so could create two independent OS locks.
    with path.open('a+b') as stream:
        if os.fstat(stream.fileno()).st_size==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:raise MigrationLockError('MIGRATION_BUSY') from exc
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


@contextmanager
def migration_lock(root):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True);path=root/LOCK
    with os_guard(root):
        recovered=None
        if path.exists():
            try:receipt=json.loads(path.read_text(encoding='utf-8'))
            except (ValueError,OSError):raise MigrationLockError('LOCK_INVALID') from None
            if not isinstance(receipt,dict):raise MigrationLockError('LOCK_INVALID')
            state=owner_state(receipt)
            if state!='dead':
                raise MigrationLockError('MIGRATION_BUSY' if state=='alive' else 'LOCK_OWNER_UNVERIFIED',receipt.get('pid'))
            archive=root/('.alpha_trade_migration.lock.stale-'+uuid.uuid4().hex+'.json')
            os.replace(path,archive)
            recovered=dict(owner_pid=receipt['pid'],archive=archive.name)
        token=uuid.uuid4().hex
        value=dict(**worker_identity(),token=token,started_at=datetime.now(timezone.utc).isoformat())
        try:
            with path.open('x',encoding='utf-8') as out:json.dump(value,out)
        except FileExistsError as exc:raise MigrationLockError('MIGRATION_BUSY') from exc
        try:yield recovered
        finally:
            # Preserve any receipt replaced externally; never unlock its owner.
            try:
                if json.loads(path.read_text(encoding='utf-8')).get('token')==token:path.unlink()
            except (OSError,ValueError,AttributeError):pass
