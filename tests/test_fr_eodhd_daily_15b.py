import gzip
import json
from datetime import date

import pytest
from service.fr import eodhd_daily_15b as daily


def setup(tmp_path, monkeypatch):
    ids = tmp_path/'ids.jsonl.gz'
    with gzip.open(ids, 'wt', encoding='utf-8') as stream:
        for symbol in ('AB.PA','AC.PA'):
            stream.write(json.dumps(dict(provider_symbol=symbol,identity_state='VERIFIED_RESEARCH',provider_status_current='active'))+'\n')
    monkeypatch.setenv('EODHD_API_TOKEN','secret-test')
    return ids, tmp_path/'daily', dict(lookback_days=7,request_interval_seconds=.1)


def bar(close=10):
    return dict(date='2026-10-02',open=10,high=12,low=8,close=close,volume=100,adjusted_close=close)


def execute(cfg, root, ids, **kwargs):
    result = dict(received_count=0,persisted_count=0,failed_count=0,warning_count=0)
    daily.collect(cfg,result,root=root,identities=ids,today=date(2026,10,5),**kwargs)
    return result


def test_refresh_dedup_correction_and_explicit_resume(tmp_path, monkeypatch):
    ids, root, cfg = setup(tmp_path,monkeypatch)
    calls = []
    rows = [bar()]
    monkeypatch.setattr(daily,'_fetch',lambda *a,**k: (calls.append(a[0]),rows.copy())[1])
    assert execute(cfg,root,ids)['persisted_count'] == 2
    assert execute(cfg,root,ids)['unchanged_rows'] == 2
    assert len(calls) == 4  # Normal rerun re-fetches.
    assert execute(cfg,root,ids,resume=True)['resumed_symbols'] == 2
    assert len(calls) == 4
    rows[:] = [bar(11)]
    assert execute(cfg,root,ids)['changed_rows'] == 2
    assert len(list((root/'raw').glob('*.json'))) == 4
    assert all(len(json.loads(p.read_text())['bars']) == 1 for p in (root/'latest').glob('*.json'))


@pytest.mark.parametrize('rows', [[bar(),bar()], [{**bar(),'date':'2026-09-01'}], [{**bar(),'volume':-1}], []])
def test_invalid_does_not_overwrite_latest(tmp_path,monkeypatch,rows):
    ids,root,cfg = setup(tmp_path,monkeypatch)
    monkeypatch.setattr(daily,'_fetch',lambda *a,**k: rows)
    with pytest.raises(RuntimeError,match='reprise'):
        execute(cfg,root,ids)
    assert not (root/'latest').exists()
    assert not (root/'.lock').exists()


def test_partial_failure_resume_and_dryrun(tmp_path,monkeypatch):
    ids,root,cfg = setup(tmp_path,monkeypatch)
    calls=[]
    def fetch(endpoint,*a,**k):
        calls.append(endpoint)
        if endpoint == 'eod/AC.PA':
            raise RuntimeError('HTTP 500')
        return [bar()]
    monkeypatch.setattr(daily,'_fetch',fetch)
    with pytest.raises(RuntimeError):
        execute(cfg,root,ids)
    monkeypatch.setattr(daily,'_fetch',lambda endpoint,*a,**k: (calls.append(endpoint),[bar()])[1])
    assert execute(cfg,root,ids,resume=True)['resumed_symbols'] == 1
    assert calls == ['eod/AB.PA','eod/AC.PA','eod/AC.PA']
    monkeypatch.setattr(daily,'_fetch',lambda *a,**k: pytest.fail('dry-run network'))
    empty=tmp_path/'empty'
    execute(cfg,empty,ids,dry_run=True)
    assert not empty.exists()


def test_lock_and_bad_universe(tmp_path,monkeypatch):
    ids,root,cfg=setup(tmp_path,monkeypatch)
    root.mkdir(); (root/'.lock').touch()
    with pytest.raises(RuntimeError,match='verrouillée'):
        execute(cfg,root,ids)
    assert (root/'.lock').exists()
    with gzip.open(ids,'wt') as s:
        s.write(json.dumps(dict(provider_symbol='AAPL.US',identity_state='VERIFIED_RESEARCH',provider_status_current='active')))
    with pytest.raises(ValueError,match='Paris'):
        execute(cfg,root,ids,dry_run=True)


def test_atomic_retries_transient_windows_lock_without_partial_write(tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path / 'checkpoint.json'
    path.write_text('{"old": true}')
    original = Path.replace
    attempts = []
    def replace(temp, destination):
        attempts.append(1)
        assert json.loads(path.read_text()) == {'old': True}
        if len(attempts) < 3:
            raise PermissionError('temporary sharing violation')
        return original(temp, destination)
    monkeypatch.setattr(Path, 'replace', replace)
    monkeypatch.setattr(daily.time, 'sleep', lambda _: None)
    daily.atomic(path, {'new': True})
    assert len(attempts) == 3
    assert json.loads(path.read_text()) == {'new': True}
    assert not list(tmp_path.glob('*.tmp'))


def test_atomic_permanent_denial_is_bounded_and_keeps_old_checkpoint(tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path / 'checkpoint.json'
    path.write_text('{"old": true}')
    attempts = []
    def denied(*args):
        attempts.append(1)
        raise PermissionError('permanent denial')
    monkeypatch.setattr(Path, 'replace', denied)
    monkeypatch.setattr(daily.time, 'sleep', lambda _: None)
    with pytest.raises(PermissionError, match='permanent'):
        daily.atomic(path, {'new': True})
    assert len(attempts) == 10
    assert json.loads(path.read_text()) == {'old': True}


def test_atomic_other_io_failure_is_not_retried(tmp_path, monkeypatch):
    from pathlib import Path
    attempts = []
    def failed(*args):
        attempts.append(1)
        raise OSError('disk full')
    monkeypatch.setattr(Path, 'replace', failed)
    monkeypatch.setattr(daily.time, 'sleep', lambda _: pytest.fail('unexpected retry'))
    with pytest.raises(OSError, match='disk full'):
        daily.atomic(tmp_path / 'checkpoint.json', {'new': True})
    assert len(attempts) == 1
