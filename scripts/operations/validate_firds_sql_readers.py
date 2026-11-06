"""Read-only production acceptance with the canonical local FIRDS directory absent."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from sqlalchemy import event

from service.fr import firds_storage as files
from service.fr.esma_firds_annual_chain import validate_history
from service.fr.esma_firds_download import _check
from service.fr.esma_firds_full_reconcile import reconcile
from service.fr.esma_firds_gap_audit import audit
from service.fr.esma_firds_history import replay
from service.fr.esma_firds_reframe import reframe
from service.fr.qualification_dossier_16g import read_proof
from service.fr.universe_contract_6a import _sha256


def run(output):
    project = Path(__file__).resolve().parents[2]
    output = Path(output).resolve()
    allowed = project / 'artifacts/operations/firds_sql_removal'
    if not output.is_relative_to(allowed) or output == allowed:
        raise ValueError('Dedicated FIRDS acceptance directory required')
    output.mkdir(parents=True, exist_ok=False)
    if files.ROOT.exists():
        raise ValueError('Test requires canonical local FIRDS directory to be absent')
    source = project / 'artifacts/operations/firds_sql_history_import/20261105-v1'
    manifest = json.loads((source / 'source-manifest.json').read_text(encoding='utf-8'))
    journal = {}
    for line in (source / 'files.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line); journal[row['path']] = row
    repo = files.default_repository()
    sql_statements = 0
    def readonly(conn, cursor, statement, parameters, context, executemany):
        nonlocal sql_statements
        if statement.lstrip().split(None, 1)[0].upper() not in ('SELECT', 'SET', 'SHOW'):
            raise AssertionError('Acceptance must not write SQL')
        sql_statements += 1
    event.listen(repo.engine, 'before_cursor_execute', readonly)
    checks = []
    def record(name, **data):
        checks.append(dict(check=name, **data))
        print(json.dumps(checks[-1], ensure_ascii=False), flush=True)
    try:
        expected = sorted(str(files.ROOT / row['path']) for row in manifest['files'] if row['path'].endswith('.zip'))
        listed = files.paths(files.ROOT, '*.zip', recursive=True)
        if sorted(map(str, listed)) != expected:
            raise ValueError('SQL archive listing differs from imported manifest')
        record('all_zip_resources_listed_without_disk', count=len(listed))
        for row in manifest['files']:
            if not row['path'].endswith('.json'):
                continue
            path = files.ROOT / row['path']
            data, digest = read_proof(path)
            if digest != journal[row['path']]['sha256'] or _sha256(path) != digest:
                raise ValueError('Raw metadata hash mismatch: ' + row['path'])
        record('all_json_proofs_read_and_hashes_preserved',
               count=sum(r['path'].endswith('.json') for r in manifest['files']))
        root = files.ROOT / 'replay_2018'
        for year in range(2018, 2027):
            end = date(year, 12, 31) if year < 2026 else date(2026, 10, 1)
            history = validate_history(root / f'history_{year}_observed_v2.json', end)
            record('annual_history', year=year, files=history['files_processed'])
        for year in range(2018, 2027):
            row = next(r for r in manifest['files'] if '/'+str(year)+'/' in r['path'] and r['path'].endswith('.zip'))
            proof = _check(files.ROOT / row['path'], None)
            if proof['sha256'] != journal[row['path']]['sha256']:
                raise ValueError('ZIP SQL checksum mismatch')
            record('SQL_zip_sha256_and_full_crc', year=year, bytes=proof['bytes'])
        gap = audit(root, end=date(2026, 10, 1))
        old_gap = json.loads(files.read_text(root / 'gap_audit.json'))
        if any(gap.get(k) != v for k, v in old_gap.items()):
            raise ValueError('Gap audit changed after SQL routing')
        record('full_index_gap_audit_identical', indexed=gap['files_indexed'],
               missing=gap['files_missing_from_storage'])
        original = json.loads(files.read_text(root / 'history_2018.json'))
        observed = json.loads(files.read_text(root / 'history_2018_observed_v2.json'))
        rebuilt = reframe(original, hashlib.sha256(files.read_bytes(root / 'history_2018.json')).hexdigest())
        if rebuilt != observed:
            raise ValueError('Reframe differs from frozen report')
        record('reframe_identical_to_frozen_2018_report', versions=rebuilt['counts']['version_records'])
        index = json.loads(files.read_text(root / 'index.json'))
        initial = replay(root / 'index.json', project / 'artifacts/fr/eodhd/backfill_2016/sprint5_subset_audit.json',
                         root, end=date.fromisoformat(index['full_date']))
        record('initial_full_replay_from_sql', files=initial['files_processed'], counts=initial['counts'])
        full = files.paths(files.ROOT / 'full_reconciliation_2018/2018', '*.zip')
        current = reconcile(observed, full, date(2018, 12, 29))
        frozen = json.loads(files.read_text(root / 'full_reconciliation_2018_observed_v2.json'))
        if any(current.get(k) != v for k, v in frozen.items()) or current.get('excluded_non_equity_replay_records'):
            raise ValueError('2018 Full reconciliation differs from frozen report')
        record('real_XML_full_reconciliation_identical', files=len(full), pairs=current['replayed_active_records'])
        # Separate Python process: routing must work without inherited ContextVar.
        cmd = [sys.executable, '-X', 'utf8', '-m', 'service.fr.esma_firds_reframe',
            '--input', str(root / 'history_2018.json'), '--output', str(output / 'cli-reframe.json')]
        child = subprocess.run(cmd, cwd=project, capture_output=True, text=True, encoding='utf-8', check=True)
        if json.loads((output / 'cli-reframe.json').read_text(encoding='utf-8')) != observed:
            raise ValueError('Standalone CLI differs from frozen report')
        record('standalone_subprocess_without_context', exit_code=child.returncode)
        if files.ROOT.exists():
            raise ValueError('Local archive directory recreated during read-only acceptance')
        result = dict(status='PASSED_SQL_ONLY_WITH_LOCAL_DIRECTORY_ABSENT',
            completed_at=datetime.now(timezone.utc).isoformat(), sql_database='alpha_trade_fr',
            checks=checks, sql_statements=sql_statements, SQL_writes=False, provider_calls=0,
            local_archive_directory_absent=True, historical_pit_promoted=False)
        (output / 'report.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        return result
    finally:
        event.remove(repo.engine, 'before_cursor_execute', readonly)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
