"""Qualification réelle des sauvegardes FR, sans restauration en production.

Les archives ne sont jamais extraites par extractall. La rotation n'a lieu
qu'après vérification complète. Les répertoires de restauration sont conservés
pour inspection ; aucune suppression récursive automatique.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid

from sqlalchemy import create_engine, text

from database.router import get_market_engine, resolve_database_route, _credential
from service.fr.operational_batch_15a import ROOT, load_section

BLOCK = 1024 * 1024


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(BLOCK), b''):
            digest.update(block)
    return digest.hexdigest()


def _write(path, payload):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporary.replace(path)


def safe_member(name, root_name):
    path = PurePosixPath(name)
    if ('\\' in name or ':' in name or path.is_absolute() or '..' in path.parts
            or not path.parts or path.parts[0] != root_name):
        raise ValueError('Chemin archive non sûr : ' + name)
    return path


def verified_archive(source, destination, *, keep=3, extract=False, progress=None):
    """Archive gzip niveau 1, compare tous les hashes, extraction réelle optionnelle."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if keep < 1 or not source.is_dir() or destination.is_relative_to(source):
        raise ValueError('Source/destination/rotation invalide')
    entries = sorted(source.rglob('*'))
    if source.is_symlink() or source.is_junction() or any(p.is_symlink() or p.is_junction() for p in entries):
        raise ValueError('Lien/jonction interdit dans la sauvegarde')
    files = [p for p in entries if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    destination.mkdir(parents=True, exist_ok=True)
    required = size * (2 if extract else 1) + 1024**3
    if shutil.disk_usage(destination).free < required:
        raise RuntimeError('Espace libre insuffisant pour archive et restauration')
    token = datetime.now(UTC).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    archive = destination / ('fr_artifacts_' + token + '.tar.gz')
    temporary = archive.with_suffix('.partial')
    manifest = {}
    state = {'phase': 'ARCHIVING', 'files_total': len(files), 'bytes_total': size,
             'files_done': 0, 'archive': str(archive)}
    notify = lambda: _write(progress, state) if progress else None
    notify()
    # Un hash préalable puis contrôle stat après lecture empêchent une validation
    # silencieuse d'une source qui change pendant la sauvegarde.
    with tarfile.open(temporary, 'w:gz', compresslevel=1) as output:
        for number, path in enumerate(files, 1):
            before = path.stat()
            name = str(PurePosixPath(source.name, path.relative_to(source).as_posix()))
            digest = digest_file(path)
            output.add(path, arcname=name, recursive=False)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError('Source modifiée pendant sauvegarde : ' + str(path))
            manifest[name] = {'bytes': before.st_size, 'sha256': digest}
            state['files_done'] = number
            if number % 20 == 0: notify()
    if files != [p for p in sorted(source.rglob('*')) if p.is_file()]:
        raise RuntimeError('Inventaire source modifié pendant sauvegarde')
    restore = destination / ('restore_probe_' + token) if extract else None
    if restore: restore.mkdir(exist_ok=False)
    state.update(phase='EXTRACTING_VERIFY' if extract else 'VERIFYING', files_done=0)
    notify()
    seen = set()
    with tarfile.open(temporary, 'r|gz') as handle:
        for member in handle:
            relative = safe_member(member.name, source.name)
            if not member.isfile() or member.name in seen or member.name not in manifest:
                raise ValueError('Membre archive inattendu ou dupliqué')
            seen.add(member.name)
            stream = handle.extractfile(member)
            digest = hashlib.sha256()
            target = restore.joinpath(*relative.parts) if restore else None
            if target: target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile() if target is None else target.open('xb') as output:
                # Sans extraction, le flux est hashé sans conserver une copie disque.
                for block in iter(lambda: stream.read(BLOCK), b''):
                    digest.update(block)
                    if target: output.write(block)
            if digest.hexdigest() != manifest[member.name]['sha256'] or member.size != manifest[member.name]['bytes']:
                raise RuntimeError('Hash/taille archive incorrect : ' + member.name)
            if target and digest_file(target) != manifest[member.name]['sha256']:
                raise RuntimeError('Hash fichier restauré incorrect')
            state['files_done'] = len(seen)
            if len(seen) % 20 == 0: notify()
    if seen != set(manifest): raise RuntimeError('Fichiers manquants dans archive')
    temporary.replace(archive)
    _write(archive.with_suffix('.manifest.json'), manifest)
    # Seulement les archives de ce service, et seulement après validation.
    old = sorted(destination.glob('fr_artifacts_*.tar.gz'))[:-keep]
    for path in old:
        path.unlink()
        path.with_suffix('.manifest.json').unlink(missing_ok=True)
    state.update(phase='VERIFIED', restore_path=str(restore) if restore else None,
                 archive_bytes=archive.stat().st_size, verification='ALL_FILES_SHA256',
                 extraction_verified=extract, rotated=[str(p) for p in old])
    notify()
    return state


def validate_sql(archive):
    """Fail-closed : aucune instruction de sélection/création de base ou référence production."""
    with gzip.open(archive, 'rt', encoding='utf-8') as stream:
        for line in stream:
            if line.lstrip().startswith('--'): continue
            if re.search(r'\b(?:USE\s+|(?:CREATE|DROP|ALTER)\s+DATABASE\b)', line, re.I):
                raise ValueError('Dump non isolable : instruction de base')
            if re.search(r'`?alpha_trade(?:_fr|_cn)?`?\s*\.', line, re.I):
                raise ValueError('Dump avec référence qualifiée vers une base de production')


def _inventory(engine, database):
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT TABLE_NAME,TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA=:db ORDER BY TABLE_NAME"), {'db':database}).all()
        counts = {}
        for name, kind in tables:
            if not re.fullmatch(r'[A-Za-z0-9_$]+', name): raise ValueError('Nom table inattendu')
            if kind == 'BASE TABLE': counts[name] = int(conn.execute(text(f'SELECT COUNT(*) FROM `{name}`')).scalar_one())
        schema = {}
        for family, query in {
            'columns': 'SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=:db ORDER BY TABLE_NAME,ORDINAL_POSITION',
            'indexes': 'SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME,SUB_PART FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=:db ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX',
            'triggers': 'SELECT TRIGGER_NAME,EVENT_MANIPULATION,EVENT_OBJECT_TABLE,ACTION_TIMING,ACTION_STATEMENT FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=:db ORDER BY TRIGGER_NAME',
            'routines': 'SELECT ROUTINE_NAME,ROUTINE_TYPE,ROUTINE_DEFINITION FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=:db ORDER BY ROUTINE_NAME',
            'views': 'SELECT TABLE_NAME,VIEW_DEFINITION FROM information_schema.VIEWS WHERE TABLE_SCHEMA=:db ORDER BY TABLE_NAME',
        }.items():
            schema[family] = [list(row) for row in conn.execute(text(query), {'db':database}).all()]
        return {'tables': [list(row) for row in tables], 'counts':counts, 'schema':schema}


def database_probe(cfg):
    from scripts.backup_db import backup_db
    from service.market.cn_backup_restore_17b import _mysql
    route = resolve_database_route('fr_primary', 'FR_EQ')
    user = _credential(route.user_env, route.fallback_user_env)
    password = _credential(route.password_env, route.fallback_password_env)
    source = get_market_engine('FR_EQ', database_alias='fr_primary')
    target = 'alpha_trade_fr_restore_' + uuid.uuid4().hex[:8]
    executable = Path(cfg['mysqldump_path']).with_name('mysql.exe').resolve(strict=True)
    args = dict(executable=executable, host=route.host, user=user, password=password)
    restored = None
    try:
        before = _inventory(source, route.database)
        backup = backup_db(host=route.host, db=route.database, user=user, password=password,
            dest_dir=ROOT/'backups/fr/db', keep=int(cfg['keep']), archive_prefix='alpha_trade_fr',
            mysqldump_path=cfg['mysqldump_path'], include_routines=True, include_triggers=True)
        if backup.errors: raise RuntimeError('; '.join(backup.errors))
        archive = Path(backup.dump_path)
        validate_sql(archive)
        exists = _mysql(['--execute', f"SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='{target}'"], **args)
        if exists.returncode or target in exists.stdout: raise RuntimeError('Cible restauration existante/invérifiable')
        created = _mysql(['--execute', f'CREATE DATABASE `{target}` CHARACTER SET utf8mb4'], **args)
        if created.returncode: raise RuntimeError('Création base temporaire refusée')
        print('Base temporaire créée : ' + target, flush=True)
        env = os.environ.copy(); env['MYSQL_PWD'] = password
        with tempfile.TemporaryFile() as errors:
            proc = subprocess.Popen([str(executable), '-h', route.host, '-u', user,
                '--binary-mode', '--local-infile=0', '--default-character-set=utf8mb4', target],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors, env=env)
            try:
                with gzip.open(archive, 'rb') as stream:
                    for block in iter(lambda: stream.read(BLOCK), b''): proc.stdin.write(block)
                proc.stdin.close()
                if proc.wait(): raise RuntimeError('Échec restauration MySQL (base temporaire conservée)')
            except BaseException:
                if proc.poll() is None: proc.kill(); proc.wait()
                raise
        restored = create_engine(source.url.set(database=target), pool_pre_ping=True)
        actual = _inventory(restored, target)
        after = _inventory(source, route.database)
        if before != after: raise RuntimeError('Source modifiée pendant le dump ; comparaison non qualifiée')
        if actual != before: raise RuntimeError('Inventaire/lignes/schéma restaurés différents')
        return {'status':'RESTORE_VERIFIED', 'archive':str(archive), 'restore_database':target,
                'source_database':route.database, 'archive_sha256':digest_file(archive),
                'inventory':actual, 'production_writes':False, 'temporary_database_retained':True}
    finally:
        if restored is not None: restored.dispose()
        source.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['artifacts', 'database'])
    parser.add_argument('--batch-config', type=Path, default=ROOT/'batch_fr.yaml')
    args = parser.parse_args()
    folder = ROOT/'backups/fr/qualification'/ (datetime.now(UTC).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    print('Suivi : ' + str(folder/'progress.json'), flush=True)
    report = {'status':'FAILED', 'action':args.action, 'started_at':datetime.now(UTC).isoformat()}
    try:
        cfg = load_section('fr_'+('artifacts_backup' if args.action=='artifacts' else 'db_backup'), args.batch_config)
        if args.action == 'database': report.update(database_probe(cfg))
        else:
            archives=[]
            for relative, child in [('artifacts/fr','data'), ('artifacts/models/fr_eq','models')]:
                source=ROOT/relative
                if source.exists():
                    archives.append(verified_archive(source, ROOT/'backups/fr/artifacts'/child,
                        keep=int(cfg['keep']), extract=True, progress=folder/'progress.json'))
                elif child=='data': raise FileNotFoundError(source)
            report.update(status='EXTRACTION_VERIFIED', archives=archives)
    except Exception as exc:
        report['error_message'] = type(exc).__name__ + ': ' + str(exc)
    report['finished_at'] = datetime.now(UTC).isoformat()
    _write(folder/'report.json', report)
    print(json.dumps({'status':report['status'],'report':str(folder/'report.json'), 'error_message':report.get('error_message')},ensure_ascii=False),flush=True)
    if report['status']=='FAILED': raise SystemExit(1)


if __name__ == '__main__': main()
