"""Native Search/Fetch receipts + offline pipeline replay; no real paid API call."""
from copy import deepcopy
from dataclasses import replace
from datetime import date,datetime,timezone
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from service.llm_directional import deepseek_search as search,runner
from service.llm_directional.config import FilterConfig
from service.llm_directional.local_evidence import enrich_contexts
from service.llm_directional.openai_client import ResponsesClient,build_request
from service.llm_directional.prompts import DEEPSEEK_SEARCH_VERSION,VERSION
from service.llm_directional.repository import Repository,digest,metadata
from service.llm_directional.validation import parse_response

NOW=datetime(2026,10,18,22,tzinfo=timezone.utc)
CFG=FilterConfig(enabled=True,provider='deepseek',analysis_mode='web_search',allow_short=True)


def context():
    evidence=[dict(source_id='consensus:test',kind='consensus',text='EPS current estimate 1.20',
        available_at_utc='2026-10-18T20:00:00+00:00',qualification_status='RESEARCH_ONLY')]
    return dict(symbol='ABC',oracle_rank=1,oracle_score=.8,trade_date='2026-10-16',
        issuer_reference={'company_name':'ABC Corporation'},horizon_sessions=20,
        analysis_protocol=DEEPSEEK_SEARCH_VERSION,analysis_mode='web_search',
        evidence_cutoff_utc=NOW.isoformat(),local_evidence=evidence,
        local_evidence_sha256=digest(evidence))


def answer():
    return dict(symbol='ABC',issuer='ABC Corporation',identity_verified=True,decision='LONG',
        confidence=.9,bull_case='Rising guidance',bear_case='Execution and squeeze risks',catalysts=['Results'],
        consensus_analysis='Provisional EPS context; fiscal units not yet qualified.',local_evidence=[],
        sources=[dict(url=f'https://issuer.example/{i}',title=f'Release {i}',
            published_at='2026-10-18T18:00:00Z') for i in range(2)])


def fake_session(*,mutate=None,search_raw=None,fail=None,finish='stop',fetch_code=200):
    calls=[]
    def post(url,**kwargs):
        calls.append((url,kwargs))
        code=fail[1] if fail and url==fail[0] else 200
        if url==search.SEARCH_URL:
            value=deepcopy(search_raw) if search_raw is not None else dict(results=[dict(url=s['url'],
                title=s['title'],date=s['published_at'],content='Issuer published guidance. '*900,
                snippet='Release',summary='Guidance increased.') for s in answer()['sources']])
        elif url==search.FETCH_URL:
            code=fetch_code if not fail else code
            value=dict(title='Issuer release',content='Actual page text. '*900)
        elif url==search.CHAT_URL:
            value=answer()
            if mutate:mutate(value)
            value=dict(choices=[dict(finish_reason=finish,message={'content':json.dumps(value)})],
                       usage={'prompt_tokens':200,'completion_tokens':150})
        else:
            pytest.fail('Unexpected endpoint (especially OpenAI): '+url)
        return SimpleNamespace(status_code=code,headers={},json=lambda:value)
    return SimpleNamespace(post=post),calls


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setenv('DEEPSEEK_API_KEY','fake-native-key')
    monkeypatch.setattr(search.time,'sleep',lambda seconds:None)


def execute(cfg=CFG,**kwargs):
    session,calls=fake_session(**kwargs)
    ctx=context();payload=build_request(ctx,cfg)
    raw=ResponsesClient(cfg,session)(payload)
    return ctx,payload,raw,calls


def test_native_search_fetch_analysis_only_deepseek_and_consensus_preserved():
    ctx,payload,raw,calls=execute()
    assert [url for url,_ in calls]==[search.SEARCH_URL]*2+[search.FETCH_URL]*2+[search.CHAT_URL]
    assert raw['analysis_protocol']==DEEPSEEK_SEARCH_VERSION
    assert len(raw['search_receipts'])==2 and len(raw['fetch_receipts'])==2
    sent=json.loads(raw['analysis_request']['messages'][1]['content'])
    assert sent['context']==ctx and sent['context']['local_evidence'][0]['kind']=='consensus'
    assert all(s['page_fetched'] and s['content_truncated'] for s in sent['web_evidence'])
    assert all(len(s['content'])==CFG.deepseek_web_text_chars for s in sent['web_evidence'])
    assert raw['analysis_request']['model']==CFG.deepseek_model
    assert all('fake-native-key'==k['headers']['Authorization'].removeprefix('Bearer ') for _,k in calls)
    assert all(k['allow_redirects'] is False for _,k in calls)
    assert 'fake-native-key' not in json.dumps(payload)+json.dumps(raw)
    assert 'openai' not in json.dumps(payload).lower()
    parsed=parse_response(raw,'ABC',CFG,NOW,context=ctx)
    assert parsed['eligible'] and parsed['fresh_source_count']==2


def test_new_live_context_uses_native_protocol_only_for_deepseek_web():
    engine=create_engine('sqlite:///:memory:')
    for cfg,version in ((CFG,DEEPSEEK_SEARCH_VERSION),(replace(CFG,provider='openai'),VERSION),
                        (replace(CFG,analysis_mode='local_data_only'),VERSION)):
        ctx=enrich_contexts(engine,[dict(symbol='ABC')],cfg,NOW)[0]
        assert ctx['analysis_protocol']==version
    assert runner._protocol([context()])==DEEPSEEK_SEARCH_VERSION
    with pytest.raises(ValueError):runner._protocol([context(),dict(symbol='XYZ')])


@pytest.mark.parametrize('limit,searches,fetches',[(1,1,0),(2,2,0),(3,2,1),(5,2,2)])
def test_hard_web_budget_and_search_query_limits(limit,searches,fetches):
    cfg=replace(CFG,max_tool_calls=limit)
    _,payload,_,calls=execute(cfg)
    assert len(calls)==searches+fetches+1
    assert all(len(r['query'])<=128 and r['count']==5 and r['need_content'] for r in payload['search_requests'])
    assert 'local_evidence' not in json.dumps(payload['search_requests'])
    long=context();long['issuer_reference']['company_name']='Very long issuer '*100
    assert len(build_request(long,cfg)['search_requests'][0]['query'])<=128


@pytest.mark.parametrize('endpoint,code',[(search.SEARCH_URL,401),(search.SEARCH_URL,402),
    (search.SEARCH_URL,429),(search.FETCH_URL,429),(search.CHAT_URL,403)])
def test_technical_failure_archived_without_retry_or_fallback(endpoint,code):
    ctx,_,raw,calls=execute(fail=(endpoint,code))
    assert f'HTTP {code}' in raw['error']
    assert raw['status']!='completed' and raw['search_receipts']
    assert sum(url==endpoint for url,_ in calls)==1
    with pytest.raises(ValueError):parse_response(raw,'ABC',CFG,NOW,context=ctx)
    if endpoint==search.CHAT_URL:
        assert raw['analysis_request'] and raw['fetch_receipts']


@pytest.mark.parametrize('code',[403,404])
def test_optional_fetch_denial_respected_not_retried(code):
    ctx,_,raw,calls=execute(fetch_code=code)
    assert raw['status']=='completed' and all('error' in r for r in raw['fetch_receipts'])
    sent=json.loads(raw['analysis_request']['messages'][1]['content'])
    assert not any(r['page_fetched'] for r in sent['web_evidence'])
    assert parse_response(raw,'ABC',CFG,NOW,context=ctx)['eligible']
    assert sum(url==search.FETCH_URL for url,_ in calls)==2  # Two distinct URLs, no retry.


@pytest.mark.parametrize('kind',['url','date','unknown_date','future','confidence','short_disabled'])
def test_unqualified_sources_or_direction_never_selected(kind):
    cfg=replace(CFG,allow_short=False) if kind=='short_disabled' else CFG
    def mutate(a):
        if kind=='url':a['sources'][0]['url']='https://invented.example/news'
        if kind in ('date','unknown_date'):a['sources'][0]['published_at']='2026-10-18'
        if kind=='future':
            for source in a['sources']:source['published_at']='2026-10-20T12:00:00Z'
        if kind=='confidence':a['confidence']=.1
        if kind=='short_disabled':a['decision']='SHORT'
    ctx,_,raw,_=execute(cfg,mutate=mutate)
    if kind=='unknown_date':
        for receipt in raw['search_receipts']:receipt['response']['results'][0]['date']=None
    # Fake flattened convenience traces cannot authorize a model-made URL/date.
    raw['output'][0]['action']['sources'].append({'url':'https://invented.example/news'})
    parsed=parse_response(raw,'ABC',cfg,NOW,context=ctx)
    assert not parsed['eligible']
    if kind in ('date','unknown_date','future'):
        assert parsed['excluded_sources'][0]['exclusion_reason']=='provider_date_mismatch'


def test_empty_search_can_be_valid_abstention_not_technical_error():
    ctx,_,raw,calls=execute(search_raw={'results':[]},mutate=lambda a:a.update(decision='ABSTAIN',sources=[]))
    result=parse_response(raw,'ABC',CFG,NOW,context=ctx)
    assert result['assessment_outcome']=='ABSTAIN' and not result['eligible']
    assert len(calls)==3 and not raw['fetch_receipts']


@pytest.mark.parametrize('raw',[{},dict(results=None),dict(results=[42]),dict(results=[dict(content=None)])])
def test_malformed_search_fails_closed(raw):
    ctx,_,archive,calls=execute(search_raw=raw)
    assert archive['error'] and len(calls)==1
    with pytest.raises(ValueError):parse_response(archive,'ABC',CFG,NOW,context=ctx)


@pytest.mark.parametrize('url',['http://localhost/x','https://127.0.0.1/x','https://10.0.0.1/x',
    'file:///etc/passwd','https://user:password@example.com/x','https://example.com:99/x',
    'https://example.com/space here','https://x.internal/a'])
def test_private_or_unsafe_results_never_fetched_or_forwarded(url):
    ctx,_,raw,calls=execute(search_raw=dict(results=[dict(url=url,title='Unsafe')]),
                           mutate=lambda a:a.update(decision='ABSTAIN',sources=[]))
    assert not any(endpoint==search.FETCH_URL for endpoint,_ in calls)
    assert json.loads(raw['analysis_request']['messages'][1]['content'])['web_evidence']==[]
    assert parse_response(raw,'ABC',CFG,NOW,context=ctx)['assessment_outcome']=='ABSTAIN'


def test_tampered_native_payload_rejected_before_network():
    ctx=context();payload=build_request(ctx,CFG)
    payload['search_requests'][0]['query']='different'
    session,calls=fake_session()
    with pytest.raises(ValueError,match='incompatible'):ResponsesClient(CFG,session)(payload)
    assert not calls


def test_truncated_analysis_and_foreign_protocol_fail_closed():
    ctx,_,raw,_=execute(finish='length')
    with pytest.raises(ValueError):parse_response(raw,'ABC',CFG,NOW,context=ctx)
    raw['analysis_protocol']=VERSION
    with pytest.raises(ValueError,match='Provenance'):parse_response(raw,'ABC',CFG,NOW,context=ctx)


def test_native_pipeline_archive_can_revalidate_without_api_or_rereading_sql(monkeypatch):
    engine=create_engine('sqlite:///:memory:');metadata.create_all(engine)
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a:None)
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW.replace(tzinfo=None))
    import service.llm_directional.repository as repo
    monkeypatch.setattr(repo,'utcnow',lambda:NOW.replace(tzinfo=None))
    session,calls=fake_session()
    result=runner.analyze(engine=engine,batch_id='fixture-model',trade_date='2026-10-16',
        symbol_source='universe-file:test.txt',config=CFG,inputs=[context()],check_account=False,
        client=ResponsesClient(CFG,session),run_id='native-test')
    assert result['selected']==['ABC']
    run,items=Repository(engine).get('native-test')
    assert run['protocol_version']==DEEPSEEK_SEARCH_VERSION
    assert json.loads(items[0]['response_json'])['search_receipts']
    _,selected=runner.qualified_selection(engine,'native-test',date(2026,10,16),'default',now=NOW.replace(tzinfo=None))
    assert [item['symbol'] for item in selected]==['ABC'] and len(calls)==5
    from service.llm_directional.report import report
    assert report(engine,'native-test')['web_provider']=='deepseek'


def test_old_v5_deepseek_relay_archive_still_revalidates_without_new_call(monkeypatch):
    engine=create_engine('sqlite:///:memory:');metadata.create_all(engine)
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a:None)
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW.replace(tzinfo=None))
    import service.llm_directional.repository as repo
    monkeypatch.setattr(repo,'utcnow',lambda:NOW.replace(tzinfo=None))
    ctx=dict(context(),analysis_protocol=VERSION)
    legacy=dict(provider='deepseek',web_response={'status':'completed','output':[
        dict(type='web_search_call',status='completed',action={'sources':answer()['sources']})]},
        analysis_response={'choices':[dict(finish_reason='stop',message={'content':json.dumps(answer())})]})
    result=runner.analyze(engine=engine,batch_id='fixture-model',trade_date='2026-10-16',
        symbol_source='universe-file:test.txt',config=CFG,inputs=[ctx],check_account=False,
        client=lambda request:legacy,run_id='legacy-v5-test')
    assert result['selected']==['ABC']
    _,selected=runner.qualified_selection(engine,'legacy-v5-test',date(2026,10,16),'default',now=NOW.replace(tzinfo=None))
    assert [item['symbol'] for item in selected]==['ABC']
    from service.llm_directional.report import report
    assert report(engine,'legacy-v5-test')['web_provider']=='openai'


def test_preflight_deepseek_web_neither_requires_nor_checks_openai(monkeypatch):
    from service.llm_directional import preflight
    from common import verified_http
    import database.connection as connection
    import dotenv
    import sys
    engine=create_engine('sqlite:///:memory:');metadata.create_all(engine)
    monkeypatch.setattr(connection,'get_sqlalchemy_engine',lambda:engine)
    monkeypatch.setattr(preflight,'load_filter_config',lambda:CFG)
    monkeypatch.setattr(preflight,'assert_paper_account',lambda:None)
    monkeypatch.setattr(dotenv,'load_dotenv',lambda:None)
    monkeypatch.setattr(sys,'argv',['preflight','--check-api'])
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=200,json=lambda:{'data':[{'id':CFG.deepseek_model}]})
    monkeypatch.setattr(verified_http,'verified_session',lambda:SimpleNamespace(get=get))
    preflight.main()
    assert calls==['https://api.deepseek.com/models']


def test_foreign_web_annotations_cannot_augment_native_proof():
    ctx,_,raw,_=execute(mutate=lambda a:a['sources'].append(dict(
        url='https://invented.example/news',title='Not seen',published_at=None)))
    raw['web_response']={'output':[dict(type='message',content=[dict(type='output_text',
        annotations=[dict(type='url_citation',url='https://invented.example/news')])])]}
    result=parse_response(raw,'ABC',CFG,NOW,context=ctx)
    assert not result['eligible']
    assert result['excluded_sources'][0]['exclusion_reason']=='untraceable_url'


@pytest.mark.parametrize('field,value',[('deepseek_search_queries',3),('deepseek_search_results',0),
    ('deepseek_fetch_pages',-1),('deepseek_web_text_chars',True)])
def test_native_config_ranges(field,value):
    with pytest.raises(ValueError):replace(CFG,**{field:value})
