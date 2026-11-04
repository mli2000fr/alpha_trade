"""Bounded recovery of inventoried files moved by the app, without omissions."""
import json
from pathlib import Path

from .storage import safe_path,sha_file


class FileCaptureError(ValueError):
    def __init__(self, relative, cause):
        missing=isinstance(cause,FileNotFoundError)
        self.details=dict(failed_path=relative,file_error='SOURCE_FILE_MISSING' if missing else 'SOURCE_FILE_READ_ERROR',
            cause_type=type(cause).__name__,filesystem_errno=getattr(cause,'errno',None),
            filesystem_winerror=getattr(cause,'winerror',None))
        self.public_message=('Fichier source inventorié introuvable' if missing else 'Lecture du fichier source impossible')+' : '+relative
        super().__init__(self.public_message)


def recovered_source(root, record):
    """Only scoped options-rearm archives with matching metadata and receipt hash.

    This never restores a live file. The recovered version is read directly
    into the backup under its originally inventoried path.
    """
    relative=Path(record['path'])
    parts=relative.parts
    if len(parts)<4 or parts[:2]!=('artifacts','options_directional'):
        return None
    import re
    if not re.fullmatch('opt-[a-f0-9]{32}',parts[2]):
        return None
    parent_parts=parts[:-1]
    if len(parent_parts)!=3 and not (len(parent_parts)==5 and parts[3]=='accounts'):
        return None
    name=relative.name
    if name not in ('risk.claim.json','risk_summary.json','risk_binding.json','execution.claim.json','execution.result.json') and not re.fullmatch(r'execution\.effects_possible\.[a-f0-9]{32}\.json',name):
        return None
    parent=safe_path(root,Path(*parent_parts).as_posix())
    matches=[]
    for kind in ('manual_rearms','execution_attempts','risk_attempts'):
        directory=parent/kind
        if not directory.is_dir():
            continue
        for archived in directory.glob('*/'+name):
            candidate=safe_path(root,archived.relative_to(root).as_posix())
            receipt_path=safe_path(root,(archived.parent/'authorization.json').relative_to(root).as_posix())
            try:
                stat=candidate.stat()
                if (stat.st_size,stat.st_mtime_ns)!=(record['size'],record['mtime_ns']):
                    continue
                receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
                if receipt.get('run_id')!=parts[2] or receipt.get('account_id','default')!=(parts[4].split('account-',1)[-1].rsplit('-',1)[0] if len(parent_parts)==5 else 'default'):
                    continue
                expected=(receipt.get('hashes') or receipt.get('files') or {}).get(name)
                if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected):
                    continue
                value=sha_file(candidate)
                if value==expected:
                    matches.append((candidate,expected))
            except (FileNotFoundError,json.JSONDecodeError):
                continue
    if len({value for _,value in matches})>1:
        raise ValueError('Plusieurs versions archivées incompatibles : '+record['path'])
    return matches[0] if matches else None


def open_source(root, record, *, live):
    try:
        path=safe_path(root,record['path'])
        return path.open('rb'),None,None
    except FileNotFoundError as error:
        try:
            recovered=recovered_source(root,record) if live else None
        except OSError as cause:
            raise FileCaptureError(record['path'],cause) from cause
        if recovered:
            candidate,expected=recovered
            try:
                return candidate.open('rb'),candidate.relative_to(root).as_posix(),expected
            except OSError as cause:
                raise FileCaptureError(record['path'],cause) from cause
        raise FileCaptureError(record['path'],error) from error
    except OSError as error:
        raise FileCaptureError(record['path'],error) from error


def failure_details(error, *, root=None):
    details=dict(getattr(error,'details',{}))
    if not details and isinstance(error,OSError):
        details=dict(cause_type=type(error).__name__,filesystem_errno=error.errno,
                     filesystem_winerror=getattr(error,'winerror',None))
        if root is not None and error.filename:
            try:
                details['failed_path']=Path(error.filename).resolve().relative_to(Path(root).resolve()).as_posix()
            except (OSError,ValueError):
                pass  # Never log an arbitrary absolute path or exception text.
    return details
