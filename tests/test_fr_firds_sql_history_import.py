import io
import zipfile

import pytest
from sqlalchemy import text

from fr_sql_primary_helpers import sqlite_primary
from service.fr.collection_storage import Repository,sha
from service.fr.firds_sql_history_import import import_file,source_files,verify_object,import_outcomes


@pytest.fixture
def archive_repo(tmp_path):
    engine=sqlite_primary(tmp_path/'archive.sqlite')
    repo=Repository(engine,root=tmp_path/'fr')
    source=repo.root/'esma_firds';source.mkdir(parents=True)
    yield repo,source
    engine.dispose()


def archive_bytes(body=b'<root/>'):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as z:
        z.writestr('data.xml',body)
    return stream.getvalue()


def test_roundtrip_binary_chunks_idempotence_and_deduplication(archive_repo):
    repo,source=archive_repo
    raw=archive_bytes(b'x'*2_500_001)
    file=source/'sample.zip';file.write_bytes(raw)
    row=source_files(source)[0]
    a=import_file(repo,source,row);b=import_file(repo,source,row)
    assert a['status']=='IMPORTED_VERIFIED' and a['parts']==3
    assert b['status']=='ALREADY_PRESENT_VERIFIED' and a['sha256']==b['sha256']==sha(raw)
    assert repo.get(file)==raw and not a['head_preserved']
    second=source/'copy.zip';second.write_bytes(raw)
    c=import_file(repo,source,next(r for r in source_files(source) if r['path']=='copy.zip'))
    with repo.engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM fr_collection_objects')).scalar()==1
        assert conn.execute(text('SELECT COUNT(*) FROM fr_collection_object_parts')).scalar()==3
        assert conn.execute(text('SELECT COUNT(*) FROM fr_collection_versions')).scalar()==2
        assert conn.execute(text('SELECT COUNT(*) FROM fr_collection_heads')).scalar()==2


def test_import_does_not_replace_newer_current_resource(archive_repo):
    repo,source=archive_repo;file=source/'baseline.json'
    repo.put(file,b'{"version":"newer SQL"}')
    file.write_bytes(b'{"version":"older archive"}')
    r=import_file(repo,source,source_files(source)[0])
    assert r['head_preserved'] and repo.get(file)==b'{"version":"newer SQL"}'
    verify_object(repo.engine,sha(file.read_bytes()),len(file.read_bytes()))
    with repo.engine.connect() as c:
        assert c.execute(text('SELECT COUNT(*) FROM fr_collection_versions')).scalar()==2
        # The source file has no vintage date to be invented by the importer.
        assert c.execute(text('SELECT MIN(available_at) FROM fr_collection_versions')).scalar()>'2026-01-01'


def test_corrupt_or_missing_sql_chunks_are_rejected(archive_repo):
    repo,source=archive_repo;file=source/'sample.zip';file.write_bytes(archive_bytes())
    row=source_files(source)[0];r=import_file(repo,source,row)
    with repo.engine.begin() as c:
        c.execute(text('UPDATE fr_collection_object_parts SET body=:raw WHERE content_sha256=:hash'),dict(raw=b'corrupt',hash=r['sha256']))
    with pytest.raises(ValueError,match='checksum'):
        import_file(repo,source,row)


def test_changed_source_and_invalid_zip_never_publish_resource(archive_repo):
    repo,source=archive_repo;file=source/'sample.zip';file.write_bytes(archive_bytes())
    row=source_files(source)[0];file.write_bytes(b'changed')
    with pytest.raises(ValueError,match='modified'):
        import_file(repo,source,row)
    with pytest.raises(zipfile.BadZipFile):
        import_file(repo,source,source_files(source)[0])
    with repo.engine.connect() as c:
        assert c.execute(text('SELECT COUNT(*) FROM fr_collection_objects')).scalar()==0


def test_bounded_concurrent_import_deduplicates_shared_content(archive_repo):
    repo,source=archive_repo;raw=archive_bytes(b'x'*100000)
    for i in range(8):(source/f'{i}.zip').write_bytes(raw)
    output=list(import_outcomes(repo,source,source_files(source),workers=4))
    assert len(output)==8 and all(item['status']=='IMPORTED_VERIFIED' for _,item in output)
    with repo.engine.connect() as c:
        assert c.execute(text('SELECT COUNT(*) FROM fr_collection_objects')).scalar()==1
        assert c.execute(text('SELECT COUNT(*) FROM fr_collection_heads')).scalar()==8


def test_resume_finishes_unpublished_version_without_replacing_current_head(archive_repo):
    repo,source=archive_repo;file=source/'state.json'
    repo.put(file,b'current SQL value')
    archived=b'previous archive value';file.write_bytes(archived)
    repo.put(file,archived,preserve_existing_head=True)
    with repo.engine.begin() as c:
        c.execute(text('UPDATE fr_collection_versions SET available_at=NULL WHERE content_sha256=:hash'),dict(hash=sha(archived)))
    result=import_file(repo,source,source_files(source)[0])
    assert result['status']=='ALREADY_PRESENT_VERIFIED' and result['head_preserved']
    assert repo.get(file)==b'current SQL value'
    with repo.engine.connect() as c:
        assert c.execute(text('SELECT available_at FROM fr_collection_versions WHERE content_sha256=:hash'),dict(hash=sha(archived))).scalar() is not None


def test_resume_republishes_missing_head_after_interrupted_commit(archive_repo):
    repo,source=archive_repo;file=source/'sample.zip';file.write_bytes(archive_bytes())
    repo.put(file,file.read_bytes())
    with repo.engine.begin() as c:
        c.execute(text('DELETE FROM fr_collection_heads'))
        c.execute(text('UPDATE fr_collection_versions SET available_at=NULL'))
    result=import_file(repo,source,source_files(source)[0])
    assert result['status']=='ALREADY_PRESENT_VERIFIED' and not result['head_preserved']
    assert repo.get(file)==file.read_bytes()
