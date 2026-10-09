import hashlib
import json
from datetime import date, datetime

import pytest

from service.fr import publish_daily_bars_staging as publisher


def source(tmp_path, rows=None):
    root=tmp_path/'d'; symbol='AB.PA'; window=['2026-10-01','2026-10-08']
    rows=rows if rows is not None else [dict(date='2026-10-02',open=10,high=11,low=9,
                                           close=10,adjusted_close=10,volume=100)]
    payload={'symbol':symbol,'window':window,'rows':rows}
    raw=json.dumps(payload,sort_keys=True).encode(); digest=hashlib.sha256(raw).hexdigest()
    (root/'raw').mkdir(parents=True); (root/'raw'/f'{digest}.json').write_bytes(raw)
    key=hashlib.sha256(symbol.encode()).hexdigest(); folder=root/'observations'/key
    folder.mkdir(parents=True)
    meta={'symbol':symbol,'window':window,'raw_sha256':digest,
          'observed_at':'2026-10-02T18:00:00+00:00','available_at':'2026-10-02T18:00:00+00:00'}
    (folder/'one.json').write_text(json.dumps(meta))
    return root,folder,meta


def test_archive_validation_and_first_observation(tmp_path):
    root,folder,meta=source(tmp_path)
    (folder/'two.json').write_text(json.dumps({**meta,'observed_at':'2026-10-03T18:00:00+00:00',
                                            'available_at':'2026-10-03T18:00:00+00:00'}))
    rows,errors,empty=publisher.prepare(root,['AB.PA'],date(2026,10,2),date(2026,10,8))
    assert not errors and not empty and len(rows)==1
    assert rows[0]['observed']==datetime(2026,10,2,18)
    assert rows[0]['rows'][0]['quality']=='VALID'


@pytest.mark.parametrize('change',['hash','identity','duplicate','quality','timezone','traversal'])
def test_invalid_source_not_published(tmp_path,change):
    row=dict(date='2026-10-02',open=10,high=11,low=9,close=10,adjusted_close=10,volume=100)
    rows=[row,row] if change=='duplicate' else [{**row,'volume':-1}] if change=='quality' else [row]
    root,folder,meta=source(tmp_path,rows)
    if change=='hash': next((root/'raw').glob('*.json')).write_text('{}')
    if change=='identity': meta['symbol']='US.US'
    if change=='timezone': meta['available_at']='2026-10-02T18:00:00'
    if change=='traversal': meta['raw_sha256']='../outside'
    (folder/'one.json').write_text(json.dumps(meta))
    rows,errors,_=publisher.prepare(root,['AB.PA'],date(2026,10,2),date(2026,10,8))
    assert not rows and errors


def test_empty_response_is_not_zero_bar(tmp_path):
    root,_,_=source(tmp_path,[])
    rows,errors,empty=publisher.prepare(root,['AB.PA'],date(2026,10,2),date(2026,10,8))
    assert rows==[] and errors==[] and empty==1


def test_missing_timezone_refused():
    with pytest.raises(ValueError,match='Timezone'):
        publisher.timestamp('2026-10-02T18:00:00')


class Result:
    def __init__(self,value=None,rows=()): self.value=value; self.rows=rows
    def scalar(self): return self.value
    def scalar_one(self): return self.value
    def scalars(self): return self.rows
    def mappings(self): return self
    def first(self): return self.rows[0] if self.rows else None
    def one(self): return self.rows[0]


class Connection:
    def __init__(self,database='alpha_trade_fr'):
        self.database=database; self.calls=[]; self.rows={}; self.checkpoint=False
    def execute(self,statement,params=None):
        sql=str(statement); self.calls.append((sql,params))
        if 'SELECT DATABASE()' in sql: return Result(self.database)
        if 'SELECT raw_payload_id' in sql: return Result(1)
        if 'SELECT classifier_version' in sql:
            return Result(rows=[{'classifier_version':publisher.CLASSIFIER}] if self.checkpoint else [])
        if 'SELECT session_date' in sql: return Result(rows=list(self.rows))
        if 'INSERT INTO fr_provider_bars_staging' in sql:
            for row in params: self.rows.setdefault(row['day'],row)
        if 'SELECT COUNT(*)' in sql: return Result(rows=[{'total':len(self.rows),'valid':len(self.rows)}])
        if 'INSERT INTO fr_staging_progress' in sql: self.checkpoint=True
        return Result()


def test_wrong_database_blocks_all_writes():
    conn=Connection('alpha_trade')
    with pytest.raises(ValueError,match='other than'):
        publisher.publish_payload(conn,{},run_id='r',published_at=datetime(2026,10,9))
    assert len(conn.calls)==1


def test_replay_preserves_values_and_first_sql_availability(tmp_path):
    root,_,_=source(tmp_path)
    payloads,_,_=publisher.prepare(root,['AB.PA'],date(2026,10,2),date(2026,10,8))
    conn=Connection(); payload=payloads[0]
    assert publisher.publish_payload(conn,payload,run_id='r',published_at=datetime(2026,10,9))==1
    first=dict(conn.rows[date(2026,10,2)])
    assert first['available']==datetime(2026,10,9)
    assert first['observed']==datetime(2026,10,2,18)
    assert publisher.publish_payload(conn,payload,run_id='r2',published_at=datetime(2026,10,10))==0
    assert conn.rows[date(2026,10,2)]==first
    assert all('stock_bars_daily' not in sql and 'fr_corporate_actions' not in sql for sql,_ in conn.calls)


def test_broader_window_does_not_skip_unimported_rows(tmp_path):
    root,_,_=source(tmp_path)
    payloads,_,_=publisher.prepare(root,['AB.PA'],date(2026,10,2),date(2026,10,8))
    conn=Connection(); conn.checkpoint=True
    assert publisher.publish_payload(conn,payloads[0],run_id='r',published_at=datetime(2026,10,9))==1
