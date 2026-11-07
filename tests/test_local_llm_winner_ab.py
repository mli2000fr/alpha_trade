import copy
import json

import pandas as pd
import pytest

from service.local_ai.research_veto import Cache, key_for, validate_response
from scripts.research.us_local_llm_winner_ab import news_context, price_summary, verified, analyze, news_query_windows, refreeze


def packet():
    return dict(model='qwen3.5-9b',context=dict(symbol='ABC',news=[dict(source_id='n1',
        text='ABC announces lower guidance for the next quarter.',primary_ticker_association=True)]))


def response():
    value=dict(symbol='ABC',assessment='UNFAVORABLE',evidence_quality='SUFFICIENT',
        reason='Guidance en baisse.',counterarguments=['Risque de reprise déjà anticipée.'],
        facts=[dict(source_id='n1',quote='ABC announces lower guidance',impact='BEARISH',issuer_is_subject=True)])
    return dict(content=json.dumps(value),model='qwen3.5-9b',finish_reason='stop')


def test_exact_bearish_issuer_fact_can_veto():
    assert validate_response(response(),packet())['veto'] is True


def test_paragraph_whitespace_is_accepted_but_missing_words_are_not():
    p=packet();p['context']['news'][0]['text']='ABC announces\n\nlower guidance for the next quarter.'
    result=validate_response(response(),p)
    assert result['veto'] and result['citation_whitespace_normalized']==1
    p['context']['news'][0]['text']='ABC announces unexpectedly lower guidance for the next quarter.'
    with pytest.raises(ValueError,match='Citation'):validate_response(response(),p)


@pytest.mark.parametrize('field,value',[('assessment','INDETERMINABLE'),('evidence_quality','INSUFFICIENT')])
def test_no_information_is_not_a_bearish_veto(field,value):
    r=response();v=json.loads(r['content']);v[field]=value;r['content']=json.dumps(v)
    assert validate_response(r,packet())['veto'] is False


@pytest.mark.parametrize('field,value',[('impact','BULLISH'),('issuer_is_subject',False)])
def test_bullish_or_partner_news_is_not_a_veto(field,value):
    r=response();v=json.loads(r['content']);v['facts'][0][field]=value;r['content']=json.dumps(v)
    assert validate_response(r,packet())['veto'] is False


def test_secondary_ticker_association_cannot_veto():
    p=packet();p['context']['news'][0]['primary_ticker_association']=False
    assert not validate_response(response(),p)['veto']


@pytest.mark.parametrize('field,value',[('quote','Citation qui est totalement inventée'),('source_id','unknown')])
def test_untraceable_quotes_are_rejected(field,value):
    r=response();v=json.loads(r['content']);v['facts'][0][field]=value;r['content']=json.dumps(v)
    with pytest.raises(ValueError,match='Citation'):validate_response(r,packet())


@pytest.mark.parametrize('field,value',[('finish_reason','length'),('model','other')])
def test_truncated_or_wrong_model_response_fails(field,value):
    r=response();r[field]=value
    with pytest.raises(ValueError):validate_response(r,packet())


def test_duplicate_json_keys_rejected():
    r=response();r['content']=r['content'].replace('"symbol": "ABC"','"symbol":"ABC","symbol":"ABC"')
    with pytest.raises(ValueError,match='dupliquée'):validate_response(r,packet())


def test_cache_reuses_exact_request_and_changes_on_context_prompt_model_options(tmp_path):
    req=dict(model='qwen3.5-9b',messages=[dict(role='user',content='ABC at 2025-01-02')],max_tokens=4096)
    key=key_for(req,'weights-v1');cache=Cache(tmp_path/'cache.sqlite3')
    cache.put(key,req,response(),dict(valid=True,veto=True))
    assert cache.latest(key)['response']==response()
    for field,value in [('model','other'),('max_tokens',2048),('messages',[dict(role='user',content='ABC at 2025-01-03')])]:
        changed=copy.deepcopy(req);changed[field]=value
        assert key_for(changed,'weights-v1')!=key
        assert cache.latest(key_for(changed,'weights-v1')) is None
    assert key_for(req,'weights-v2')!=key
    cache.put(key,req,None,dict(valid=False,veto=False))
    assert cache.conn.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==2
    cache.close()


def test_news_future_cutoff_date_only_and_body_duplicates():
    def row(article,published,body='A sufficiently long news article. '*20):
        return dict(symbol='ABC',article_id=article,published_at_utc=pd.Timestamp(published),
            provider_publication=published,body=body,headline='ABC reports',ingestion_source='eodhd',
            content_sha256='same',content_chars=len(body),is_primary_ticker=1)
    rows=[row('valid','2025-01-02T18:00:00Z'),row('duplicate','2025-01-02T17:00:00Z'),
          row('exact-cutoff','2025-01-02T21:00:00Z'),row('future','2025-01-03T15:00:00Z'),
          row('old','2024-12-20T15:00:00Z')]
    bad=row('date-only','2025-01-02T16:00:00Z');bad['provider_publication']='2025-01-02';rows.append(bad)
    result,counts=news_context(pd.DataFrame(rows),'ABC',pd.Timestamp('2025-01-02T21:00:00Z'))
    assert len(result)==1 and result[0]['source_id'].startswith('news:valid:')
    assert counts['recent']==3 and counts['invalid_publication']==1


def test_news_excerpt_limit_is_explicit_and_not_complete_corpus():
    rows=[]
    for i in range(8):
        rows.append(dict(symbol='ABC',article_id=str(i),published_at_utc=pd.Timestamp('2025-01-02T18:00:00Z'),
            provider_publication='2025-01-02T18:00:00Z',body='Long body '*400,content_chars=4000,
            headline='ABC',content_sha256=str(i),ingestion_source='eodhd',is_primary_ticker=1))
    result,counts=news_context(pd.DataFrame(rows),'ABC',pd.Timestamp('2025-01-02T21:00:00Z'))
    assert len(result)==6 and counts['omitted']==2
    assert all(v['body_excerpt_truncated'] for v in result)


def test_price_context_cannot_use_future_bars():
    bars=pd.DataFrame([dict(symbol='ABC',date=pd.Timestamp(d),open=p,high=p+1,low=p-1,close=p,
        volume=100,is_filled=0,data_source='alpaca_sip',data_adjustment='raw')
        for d,p in [('2025-01-02',10),('2025-01-03',100)]])
    value=price_summary(bars,'ABC','2025-01-02')
    assert value['last_close']==10 and value['sessions']==1


def test_query_partitions_cover_all_lookbacks_without_overlap_or_far_away_months():
    days=['2025-01-31','2025-02-03','2025-03-20']
    spans=news_query_windows(days)
    assert all(a<b and (b-a).days<=31 for a,b in spans)
    assert all(b<=c for (a,b),(c,d) in zip(spans,spans[1:]))
    for day in days:
        for t in pd.date_range(pd.Timestamp(day)-pd.Timedelta(days=7),pd.Timestamp(day),freq='D'):
            assert sum(a<=t<b for a,b in spans)==1
    assert not any(a<=pd.Timestamp('2025-02-20')<b for a,b in spans)


def test_packet_hash_guard_fails_before_network(tmp_path):
    (tmp_path/'protocol.json').write_text(json.dumps(dict(files={'requests.json':'wrong'},sources={})),encoding='utf8')
    (tmp_path/'requests.json').write_text('[]',encoding='utf8')
    with pytest.raises(ValueError,match='figé'):verified(tmp_path)


def test_analyze_no_news_keeps_baseline_without_constructing_client(tmp_path,monkeypatch):
    import scripts.research.us_local_llm_winner_ab as module
    p=packet();p.update(key='test',symbol='ABC',signal_date='2025-01-02',request={'model':p['model']})
    p['context']['news']=[]
    (tmp_path/'requests.json').write_text(json.dumps([p]),encoding='utf8')
    monkeypatch.setattr(module,'verified',lambda _: {})
    def forbidden(*a,**k):raise AssertionError('No local or cloud API expected')
    monkeypatch.setattr(module,'Client',forbidden)
    result=analyze(tmp_path)
    assert result['status']=='ANALYSIS_COMPLETE_RESEARCH_ONLY'
    assert result['vetoes']==0 and result['local_calls_this_invocation']==0
    assert json.loads((tmp_path/'decisions.json').read_text())[0]['veto'] is False


def test_budget_revision_reuses_sealed_inputs_but_changes_request_cache_identity(tmp_path):
    from scripts.research.us_concentrated_historical_tapes import digest
    source=tmp_path/'source';source.mkdir()
    p=dict(symbol='ABC',signal_date='2025-01-02',context=dict(symbol='ABC',news=[]),
           request=dict(messages=[],model='qwen3.5-9b',max_tokens=4096),key='old-key')
    (source/'requests.json').write_text(json.dumps([p]),encoding='utf8')
    for n in ('prompt.txt','signals.parquet','news-snapshot.parquet'):
        (source/n).write_bytes(b'unchanged historical input')
    pd.DataFrame([dict(signal_date='2025-01-02',symbol='ABC',request_characters=100)]).to_csv(source/'coverage.csv',index=False)
    old=dict(prepared_at_utc='2026-11-07',connection={'max_output_tokens':4096},status='PREPARED',
        candidates=1,with_news=0,without_news=1,sources={},files={p.name:digest(p) for p in source.iterdir()})
    (source/'protocol.json').write_text(json.dumps(old),encoding='utf8')
    before=digest(source/'protocol.json');out=tmp_path/'revised'
    refreeze(source,out)
    assert digest(source/'protocol.json')==before
    for n in ('prompt.txt','signals.parquet','news-snapshot.parquet'):
        assert digest(source/n)==digest(out/n)
    changed=json.loads((out/'requests.json').read_text())[0]
    assert changed['context']==p['context']
    assert changed['key']!=p['key'] and changed['request']['max_tokens']==8192
    assert changed['request']['response_format']['type']=='json_schema'


def test_double_budget_preserves_valid_cache_exactly_and_rekeys_only_failed_or_pending(tmp_path):
    from scripts.research.us_concentrated_historical_tapes import digest
    source=tmp_path/'source';source.mkdir()
    revision='qwen3.5-9b-local-20261107-research-v2-structured'
    packets=[]
    for day in ('2025-01-02','2025-01-03','2025-01-06'):
        p=packet();p.update(symbol='ABC',signal_date=day)
        p['request']=dict(model=p['model'],messages=[dict(role='user',content=day)],max_tokens=8192)
        p['key']=key_for(p['request'],revision);packets.append(p)
    cache=Cache(source/'analyses.sqlite3')
    good=response();good['request']=packets[0]['request']
    cache.put(packets[0]['key'],packets[0]['request'],good,validate_response(good,packets[0]))
    cache.put(packets[1]['key'],packets[1]['request'],None,dict(valid=False,veto=False,error='length'))
    cache.close()
    (source/'requests.json').write_text(json.dumps(packets),encoding='utf8')
    for name in ('prompt.txt','signals.parquet','news-snapshot.parquet'):
        (source/name).write_bytes(b'frozen')
    pd.DataFrame([dict(signal_date=p['signal_date'],symbol=p['symbol']) for p in packets]).to_csv(source/'coverage.csv',index=False)
    files={p.name:digest(p) for p in source.iterdir() if p.suffix!='.sqlite3'}
    plan=dict(prepared_at_utc='2026-11-07',declared_model_revision=revision,connection=dict(max_output_tokens=8192),
        status='PREPARED',candidates=3,with_news=3,without_news=0,sources={},files=files)
    (source/'protocol.json').write_text(json.dumps(plan),encoding='utf8')
    before={p.name:digest(p) for p in source.iterdir()}
    out=tmp_path/'doubled'
    refreeze(source,out,max_output_tokens=16384,preserve_valid=True,timeout_seconds=600)
    changed=json.loads((out/'requests.json').read_text())
    assert changed[0]==packets[0]
    assert [p['request']['max_tokens'] for p in changed]==[8192,16384,16384]
    assert changed[1]['key']!=packets[1]['key'] and changed[2]['key']!=packets[2]['key']
    resumed=Cache(out/'analyses.sqlite3')
    assert resumed.latest(changed[0]['key'])['response']==good
    assert resumed.latest(changed[1]['key']) is None
    assert resumed.latest(packets[1]['key'])['validation']['valid'] is False
    resumed.close()
    assert {p.name:digest(p) for p in source.iterdir()}==before
    amended=json.loads((out/'protocol.json').read_text())
    assert amended['connection']['timeout_seconds']==600
    assert amended['cached_valid_requests_preserved']==1
