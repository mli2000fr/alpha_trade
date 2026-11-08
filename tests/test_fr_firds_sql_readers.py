"""Exercise historical FIRDS readers with no local archive directory at all."""
from datetime import date
import hashlib
import io
from pathlib import Path
import zipfile

import pytest
from sqlalchemy import text

from fr_sql_primary_helpers import sqlite_primary
from service.fr import collection_storage as storage, firds_storage as files
from service.fr.esma_firds_download import _check, _download
from service.fr.esma_firds_history import replay, archive_records
from service.fr.esma_firds_full_reconcile import reconcile
from service.fr.esma_firds_gap_audit import audit
from service.fr.esma_firds_reference_pilot import extract_reference_files
from service.fr.esma_firds_annual_chain import validate_history
from service.fr.esma_firds_reframe import reframe
from service.fr.qualification_dossier_16g import read_proof
from service.fr.universe_contract_6a import _sha256


@pytest.fixture
def sql_only(tmp_path, monkeypatch):
    engine = sqlite_primary(tmp_path / 'primary.sqlite')
    repo = storage.Repository(engine, root=tmp_path / 'fr')
    monkeypatch.setattr(files, 'ROOT', repo.root / 'esma_firds')
    monkeypatch.setattr(files, 'default_repository', lambda: repo)
    yield repo
    engine.dispose()


def seed(repo):
    root = repo.root / 'esma_firds/replay_2018'
    name = 'FULINS_E_20180106_01of01.zip'
    payload = ('<Document><RefData><FinInstrmGnlAttrbts><Id>FR0000000000</Id>'
        '<FullNm>Example</FullNm><ClssfctnTp>ESVUFR</ClssfctnTp><NtnlCcy>EUR</NtnlCcy>'
        '</FinInstrmGnlAttrbts><TradgVnRltdAttrbts><Id>XPAR</Id>'
        '<FrstTradDt>2017-01-01</FrstTradDt></TradgVnRltdAttrbts></RefData></Document>')
    body = io.BytesIO()
    with zipfile.ZipFile(body, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('full.xml', payload)
    raw = body.getvalue()
    item = dict(date='2018-01-06', file=name, type='FULINS_E',
                md5=hashlib.md5(raw).hexdigest(), url='https://must-not-be-called.invalid')
    repo.put(root / '2018' / name, raw)
    files.write_json(root / 'index.json', dict(full_date='2018-01-06', files=[item]))
    files.write_json(root / 'download_state.json', dict(files=[dict(file=name, sha256=storage.sha(raw))], failed=[]))
    files.write_json(root / 'subset.json', dict(rule_version='fr_s5_subset_v1', symbols=[
        dict(symbol='EX.PA', isin_reported='FR0000000000', provider_status_current='Active',
             status='CANDIDATE_REQUIRES_EXTERNAL_PROOFS')]))
    assert not repo.root.exists()
    return root, item, raw


def test_replay_audit_reconciliation_pilot_hash_and_resume_without_local_files(sql_only, monkeypatch):
    repo = sql_only
    root, item, raw = seed(repo)
    # Every physical file open below the logical FR archive root is forbidden.
    original = Path.open
    def guarded(path, *args, **kwargs):
        if path.is_relative_to(repo.root):
            raise AssertionError('Unexpected local archive access: ' + str(path))
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded)
    path = root / '2018' / item['file']
    assert _check(path, item['md5'])['sha256'] == storage.sha(raw)
    assert len(list(archive_records(path, {'FR0000000000'}, {'XPAR'}))) == 1
    result = replay(root / 'index.json', root / 'subset.json', root, end=date(2018, 1, 6))
    assert result['complete'] and result['counts']['version_records'] == 1
    files.write_json(root / 'history.json', result)
    assert validate_history(root / 'history.json', date(2018, 1, 6)) == result
    assert read_proof(root / 'history.json')[1] == _sha256(root / 'history.json')
    resumed = replay(root / 'index.json', root / 'subset.json', root, end=date(2018, 1, 7),
                     resume_from=root / 'history.json')
    assert resumed['files_processed'] == 1
    assert resumed['missing_delta_days'] == ['2018-01-07']
    assert reframe(result, 'source-hash')['counts'] == result['counts']
    assert reconcile(result, files.paths(root / '2018', '*.zip'), date(2018, 1, 6))['candidate_pairs_reconciled']
    assert audit(root, end=date(2018, 1, 6))['download_verified_as_indexed']
    matches, _ = extract_reference_files(files.paths(repo.root / 'esma_firds', '*.zip', recursive=True),
        {'FR0000000000'}, {item['file']: item['md5']})
    assert len(matches) == 1
    assert storage.read_bytes(path) == raw  # standalone operational helper, no context needed
    assert storage.exists(path)
    assert not repo.root.exists()


def test_sql_missing_or_corrupt_never_falls_back_to_local_file(sql_only):
    root, item, raw = seed(sql_only)
    path = root / '2018' / item['file']
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    with sql_only.engine.begin() as c:
        c.execute(text('UPDATE fr_collection_object_parts SET body=:bad WHERE content_sha256=:hash'),
                  dict(bad=b'corrupt', hash=storage.sha(raw)))
    with pytest.raises(ValueError, match='corrompu'):
        _check(path, None)
    missing = root / 'absent.json'
    missing.write_text('{}')
    assert not files.is_file(missing)
    with pytest.raises(FileNotFoundError, match='SQL'):
        files.read_text(missing)


def test_existing_sql_archive_reused_by_downloader_without_supplier_call(sql_only, monkeypatch):
    root, item, raw = seed(sql_only)
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('Unexpected supplier download'))
    proof = _download(item, root, None)
    assert proof['reused'] and proof['sha256'] == storage.sha(raw)
    assert not sql_only.root.exists()


def test_workers_keep_explicit_sql_context_for_nonstandard_fixture_root(sql_only, monkeypatch):
    from service.fr import esma_firds_download as download
    root, item, _ = seed(sql_only)
    monkeypatch.setattr(download, 'list_files', lambda *a: [item])
    monkeypatch.setattr(download, '_tls_context', lambda: None)
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('Unexpected supplier download'))
    # Automatic canonical routing is disabled here: the worker must receive context.
    monkeypatch.setattr(files, 'ROOT', sql_only.root / 'different')
    with storage.use(sql_only):
        result = download.run(date(2018, 1, 6), date(2018, 1, 6), date(2018, 1, 6), root, workers=2)
    assert result['complete'] and not result['failed']
    assert not sql_only.root.exists()


def test_sql_checksum_control_still_enforced(sql_only):
    root, item, _ = seed(sql_only)
    with pytest.raises(ValueError, match='MD5'):
        _check(root / '2018' / item['file'], '0' * 32)
