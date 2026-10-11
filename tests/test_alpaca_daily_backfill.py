from datetime import datetime,timezone
from unittest.mock import Mock
import pytest
from service.alpaca import daily_history as client
from dataIntegrityEngine import backfill_alpaca_history as module


def bars():
    return [dict(t='2026-01-02T05:00:00Z',o=100,h=104,l=99,c=102,v=1000,n=100,vw=101),
            dict(t='2026-01-05T05:00:00Z',o=102,h=105,l=100,c=104,v=1500,n=120,vw=103)]


def test_canonical_keys_no_double_split_or_volume_change():
    daily,raw=module.convert('ABC',bars(),'sip','2026-01-01','2026-01-31')
    assert daily[0]['date'].isoformat()=='2026-01-02'
    assert raw[0]['timestamp']=='2026-01-02 09:30:00' and raw[0]['timeframe']=='1D'
    assert daily[0]['volume']==1000 and daily[0]['close']==102
    assert raw[0]['data_source']==daily[0]['data_source']=='alpaca_sip'
    assert daily[0]['daily_return'] is None
    assert daily[1]['daily_return']==pytest.approx(104/102-1)


def test_duplicate_or_invalid_rejected():
    with pytest.raises(ValueError,match='Duplicate'):module.convert('ABC',[bars()[0]]*2,'sip','2026-01-01','2026-01-31')
    bad={**bars()[0],'h':1}
    with pytest.raises(ValueError):module.convert('ABC',[bad],'sip','2026-01-01','2026-01-31')


def test_client_explicit_feed_cutoff_and_pagination(monkeypatch):
    requests=[]
    def response(session,method,url,**kwargs):
        requests.append(dict(kwargs['params']))
        result=Mock()
        result.json.return_value={'bars':{'ABC':[bars()[len(requests)-1]]},
            'next_page_token':'next' if len(requests)==1 else None}
        return result
    monkeypatch.setattr(client,'request_with_retry',response)
    monkeypatch.setattr(client,'_build_headers',lambda account:{})
    monkeypatch.setattr(client.time,'sleep',lambda *a:None)
    rows=client.fetch_daily_history('ABC',start='2026-01-01',end='2026-01-05',session=Mock(),
        now=datetime(2026,1,5,22,tzinfo=timezone.utc))
    assert len(rows)==2 and requests[0]['feed']=='sip' and requests[0]['asof']=='-'
    assert requests[0]['adjustment']=='split' and requests[1]['page_token']=='next'
    assert datetime.fromisoformat(requests[0]['end'])==datetime(2026,1,5,21,40,tzinfo=timezone.utc)


@pytest.mark.parametrize('write',[False,True])
def test_resume_commits_before_bookmark(tmp_path,monkeypatch,write):
    monkeypatch.setattr(module,'completed_window',lambda *a:('2026-01-01','2026-01-31'))
    fetch=Mock(return_value=bars());monkeypatch.setattr(module,'fetch_daily_history',fetch)
    monkeypatch.setattr(module,'_upsert_stock_bars_daily',lambda db,rows:len(rows))
    monkeypatch.setattr(module,'_upsert_stock_bars',lambda db,rows:len(rows))
    db=Mock();db.execute.return_value.scalar.return_value='alpha_trade'
    result=module.run_backfill(symbols=['ABC'],dry_run=not write,session=db,output_root=tmp_path)
    assert result['persisted']==(2 if write else 0)
    assert db.commit.call_count==(1 if write else 0)
    second=module.run_backfill(symbols=['ABC'],dry_run=not write,session=db,output_root=tmp_path)
    assert second['symbols_skipped_resumed']==1 and fetch.call_count==1


def test_failed_commit_not_bookmarked(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'completed_window',lambda *a:('2026-01-01','2026-01-31'))
    monkeypatch.setattr(module,'fetch_daily_history',lambda *a,**k:bars())
    monkeypatch.setattr(module,'_upsert_stock_bars_daily',lambda db,rows:len(rows))
    monkeypatch.setattr(module,'_upsert_stock_bars',lambda db,rows:len(rows))
    db=Mock();db.execute.return_value.scalar.return_value='alpha_trade';db.commit.side_effect=RuntimeError('failure')
    result=module.run_backfill(symbols=['ABC'],dry_run=False,session=db,output_root=tmp_path)
    assert result['failed']==1 and result['persisted']==0
    assert not any(tmp_path.glob('*/state.json'))
