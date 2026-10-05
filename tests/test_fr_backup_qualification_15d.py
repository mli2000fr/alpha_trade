import gzip
from pathlib import Path
import tarfile

import pytest

from service.fr.backup_qualification_15d import safe_member, validate_sql, verified_archive, _write


@pytest.mark.parametrize('name', ['../x','/fr/x','fr/../../x','fr\\x','C:/fr/x','cn/x'])
def test_archive_paths_rejected(name):
    with pytest.raises(ValueError): safe_member(name,'fr')


def test_archive_and_real_restore_all_hashes(tmp_path):
    source=tmp_path/'fr'; source.mkdir()
    (source/'data').write_bytes(b'content\x00' * 100)
    (source/'empty').mkdir()
    progress=tmp_path/'progress.json'
    result=verified_archive(source,tmp_path/'backup',keep=1,extract=True,progress=progress)
    assert result['phase']=='VERIFIED' and result['extraction_verified']
    restored=Path(result['restore_path'])/'fr'
    assert (restored/'data').read_bytes()==(source/'data').read_bytes()
    assert (restored/'empty').is_dir()
    assert progress.is_file()
    second=verified_archive(source,tmp_path/'backup',keep=1,extract=False)
    assert len(second['rotated'])==1
    assert not Path(result['archive']).exists()
    assert restored.exists()  # no recursive deletion of extraction evidence


def test_destination_inside_source_and_invalid_keep_rejected(tmp_path):
    source=tmp_path/'fr'; source.mkdir()
    with pytest.raises(ValueError): verified_archive(source,source/'backup')
    with pytest.raises(ValueError): verified_archive(source,tmp_path/'backups',keep=0)


@pytest.mark.parametrize('sql', ['USE alpha_trade_fr;','CREATE DATABASE foo;',
    'DROP DATABASE alpha_trade;', 'SELECT * FROM `alpha_trade_cn`.`test`;'])
def test_sql_production_escape_rejected(tmp_path,sql):
    archive=tmp_path/'dump.gz'
    with gzip.open(archive,'wt',encoding='utf-8') as stream: stream.write(sql)
    with pytest.raises(ValueError): validate_sql(archive)


def test_plain_dump_without_database_switch_allowed(tmp_path):
    archive=tmp_path/'dump.gz'
    with gzip.open(archive,'wt',encoding='utf-8') as stream:
        stream.write('-- Database: alpha_trade_fr\nCREATE TABLE `t` (id INT);\nINSERT INTO `t` VALUES (1);\n')
    validate_sql(archive)


def test_atomic_progress_retries_transient_windows_lock(tmp_path,monkeypatch):
    from service.fr import backup_qualification_15d as module
    original=Path.replace
    calls=[]
    def replace(path,target):
        calls.append(1)
        if len(calls)<3: raise PermissionError('WinError 5')
        return original(path,target)
    monkeypatch.setattr(Path,'replace',replace)
    monkeypatch.setattr(module.time,'sleep',lambda value:None)
    _write(tmp_path/'progress.json',{'phase':'VERIFIED'})
    assert len(calls)==3 and (tmp_path/'progress.json').is_file()
    assert not list(tmp_path.glob('*.tmp'))
