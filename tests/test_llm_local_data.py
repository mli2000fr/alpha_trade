"""V5 trend filters: real SQLite evidence + mocked paid transports, no orders."""
import copy
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine,event,text,update

from event_sentiment import news_archive as archive
from service.eodhd.consensus_snapshot import FIELDS
from service.llm_directional import runner
from service.llm_directional.config import FilterConfig,load_filter_config
from service.llm_directional.local_evidence import enrich_contexts
from service.llm_directional.openai_client import ResponsesClient,build_request,SCHEMA
from service.llm_directional.prompts import VERSION
from service.llm_directional.repository import metadata,Repository,digest
from service.llm_directional.validation import parse_response

NOW=datetime(2026,10,18,22,tzinfo=timezone.utc)
CFG=FilterConfig(enabled=True,analysis_mode='local_data_only',allow_short=True)


@pytest.fixture
def engine():
    engine=create_engine('sqlite:///:memory:')
    metadata.create_all(engine)
    archive.META.create_all(engine)
    numeric=','.join(f'`{field}` FLOAT' for field in FIELDS)
    with engine.begin() as conn:
        conn.execute(text(f'''CREATE TABLE stock_analyst_consensus_eodhd_history (
            id INTEGER PRIMARY KEY,provider TEXT,symbol TEXT,snapshot_date DATE,
            fiscal_period_end DATE,horizon_raw TEXT,currency TEXT,observed_at DATETIME,
            available_at DATETIME,run_id TEXT,raw_hash TEXT,qualification_status TEXT,
            units_qualified INTEGER,fiscal_identity_qualified INTEGER,historical_pit_qualified INTEGER,
            {numeric})'''))
        base=dict(provider='eodhd',symbol='ABC',snapshot_date='2026-10-18',
            fiscal_period_end='2026-12-31',horizon_raw='0q',currency=None,
            observed_at='2026-10-18 20:00:00',available_at='2026-10-18 20:01:00',
            run_id='test-consensus',raw_hash='a'*64,qualification_status='QUALIFIED',
            units_qualified=1,fiscal_identity_qualified=1,historical_pit_qualified=0,
            eps_current=1.2,eps_avg=1.1,eps_7d_ago=1.,eps_analyst_count=12,
            revisions_up_30d=8,revisions_down_30d=None)
        rows=[dict(base,id=1),dict(base,id=2,snapshot_date='2026-10-17',
            observed_at='2026-10-17 20:00:00',available_at='2026-10-17 20:01:00',eps_current=1.),
            dict(base,id=3,symbol='OTHER'),dict(base,id=4,snapshot_date='2026-10-19',
            observed_at='2026-10-19 20:00:00',available_at='2026-10-19 20:01:00'),
            dict(base,id=5,fiscal_period_end='2020-12-31'),
            dict(base,id=6,symbol='PENDING',available_at=None)]
        for row in rows:
            conn.execute(text('INSERT INTO stock_analyst_consensus_eodhd_history ('+
                ','.join(row)+') VALUES ('+','.join(':'+key for key in row)+')'),row)
        body=dict(id=1,article_id='article-1',received_article_id='article-1',ingestion_source='eodhd',
            snapshot_hash='raw1',text_hash='text1',headline='ABC reports strong results',
            content='ABC Corporation raises its sales guidance. '+('text '*700),
            publication_precision='EXPLICIT_TIMEZONE',publication_utc=datetime(2026,10,18,18),
            raw_payload={},first_observed_at=datetime(2026,10,18,20))
        conn.execute(archive.RAW_VERSIONS.insert(),body)
        conn.execute(archive.MAP_VERSIONS.insert(),dict(id=1,article_id='article-1',raw_version_id=1,
            snapshot_hash='map1',mapping_rows=[{'symbol':'ABC'}],mapping_context={'identity_qualified':True},
            payload_scope_complete=True,first_observed_at=datetime(2026,10,18,20)))
        conn.execute(archive.OBSERVATIONS.insert(),[
            dict(id=1,batch_id='test',article_id='article-1',stream_key='article',origin='PROVIDER_COLLECTION',
                raw_version_id=1,mapping_version_id=None,observed_at=datetime(2026,10,18,20),available_at=datetime(2026,10,18,20,1)),
            dict(id=2,batch_id='test',article_id='article-1',stream_key='mapping:payload:all',origin='PROVIDER_COLLECTION',
                raw_version_id=None,mapping_version_id=1,observed_at=datetime(2026,10,18,20),available_at=datetime(2026,10,18,20,1))])
    return engine


def contexts(engine,cfg=CFG,symbol='ABC'):
    return enrich_contexts(engine,[dict(symbol=symbol,oracle_rank=1,oracle_score=.9,
        trade_date='2026-10-16',horizon_sessions=20,issuer_reference={'company_name':'ABC Corporation'},
        prices_through_decision_date=[dict(date='2026-10-16',close=10)])],cfg,NOW)


def response(context,decision='LONG',web=False,source=None):
    source=source or context['local_evidence'][0]
    value=dict(symbol=context['symbol'],issuer='ABC Corporation',identity_verified=True,
        decision=decision,confidence=.9,bull_case='Improving expectations',bear_case='Adverse execution risk',
        catalysts=['Results'],sources=[],consensus_analysis='EPS consensus revised upward; units caveat retained.',
        local_evidence=[dict(source_id=source['source_id'],quote=source['text'][:100])])
    output=[]
    if web:
        value['sources']=[dict(url=f'https://example.com/{i}',title='Issuer statement',
            published_at='2026-10-18T18:00:00Z') for i in range(2)]
        output.append(dict(type='web_search_call',status='completed',action={'sources':value['sources']}))
    output.append(dict(type='message',content=[dict(type='output_text',text=json.dumps(value))]))
    return dict(status='completed',output=output)


def mutate_answer(raw,**values):
    item=raw['output'][-1]['content'][0]
    answer=json.loads(item['text']);answer.update(values);item['text']=json.dumps(answer)
    return raw


def test_cutoff_exact_period_source_receipts_and_no_writes(engine):
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda c,cu,s,p,ctx,m:statements.append(s))
    ctx=contexts(engine)[0]
    assert ctx['analysis_protocol']==VERSION
    assert {s['kind'] for s in ctx['local_evidence']}=={'consensus','news'}
    consensus=ctx['local_evidence'][0]
    assert consensus['source_id'].startswith('consensus:1:')
    assert consensus['prior_actual_snapshots'][0]['source_id'].startswith('consensus:2:')
    assert json.loads(consensus['text'])['values']['revisions_down_30d'] is None
    assert ctx['local_evidence'][1]['text_truncated'] is True
    assert len(ctx['local_evidence'][1]['text'])==CFG.local_news_max_chars
    assert all(s.lstrip().upper().startswith(('SELECT','PRAGMA')) for s in statements)
    old=enrich_contexts(engine,[dict(symbol='ABC')],CFG,NOW-timedelta(days=2))[0]
    assert not old['local_evidence']
    assert not contexts(engine,symbol='PENDING')[0]['local_evidence']


def test_unqualified_data_included_but_cannot_authorize_alone(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_analyst_consensus_eodhd_history SET units_qualified=0,qualification_status='RESEARCH_ONLY'"))
    ctx=contexts(engine)[0]
    assert ctx['local_evidence'][0]['eligible_for_direction'] is False
    parsed=parse_response(response(ctx),'ABC',CFG,NOW.replace(tzinfo=None),context=ctx)
    assert parsed['assessment_outcome']=='ABSTAIN_UNQUALIFIED'
    assert 'insufficient_qualified_local_sources' in parsed['selection_blockers']
    # Qualified archived news can independently support an assessment; metadata stays unchanged.
    assert parse_response(response(ctx,source=ctx['local_evidence'][1]),'ABC',CFG,
        NOW.replace(tzinfo=None),context=ctx)['eligible']


def test_pending_and_changed_mapping_do_not_claim_wrong_text(engine):
    with engine.begin() as conn:
        conn.execute(update(archive.OBSERVATIONS).where(archive.OBSERVATIONS.c.id==2).values(available_at=None))
    assert all(s['kind']!='news' for s in contexts(engine)[0]['local_evidence'])


def test_recently_closed_earnings_period_is_not_discarded(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_analyst_consensus_eodhd_history SET fiscal_period_end='2026-09-30' WHERE id=1"))
    source=contexts(engine)[0]['local_evidence'][0]
    assert json.loads(source['text'])['fiscal_period_end']=='2026-09-30'


@pytest.mark.parametrize('provider',['openai','deepseek'])
def test_local_transport_no_web_no_openai_key_for_deepseek(engine,monkeypatch,provider):
    cfg=replace(CFG,provider=provider)
    ctx=contexts(engine,cfg)[0]
    request=build_request(ctx,cfg)
    assert 'TP/SL first touch' in (request.get('instructions') or request['analysis_request']['messages'][0]['content'])
    assert 'assessment_take_profit_pct' not in json.dumps(request)
    raw=response(ctx)
    calls=[]
    monkeypatch.setenv('DEEPSEEK_API_KEY','fake-deepseek-key')
    if provider=='openai':monkeypatch.setenv('OPENAI_API_KEY','fake-openai-key')
    else:monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    deep_raw=dict(choices=[dict(finish_reason='stop',message={'content':raw['output'][-1]['content'][0]['text']})])
    def post(url,**kwargs):
        calls.append((url,kwargs))
        return SimpleNamespace(status_code=200,headers={},json=lambda:raw if provider=='openai' else deep_raw)
    result=ResponsesClient(cfg,SimpleNamespace(post=post))(request)
    assert len(calls)==1 and ('deepseek.com' if provider=='deepseek' else 'openai.com') in calls[0][0]
    assert parse_response(result,'ABC',cfg,NOW.replace(tzinfo=None),context=ctx)['eligible']
    assert 'fake-' not in json.dumps(request)+json.dumps(result)
    if provider=='openai':
        assert request['tools']==[] and request['tool_choice']=='none'
    else:
        assert 'tools' not in request['analysis_request'] and 'web_request' not in request


def test_web_mode_also_receives_consensus_with_a_distinct_prompt(engine):
    cfg=replace(CFG,analysis_mode='web_search')
    ctx=contexts(engine,cfg)[0]
    web=build_request(ctx,cfg)
    assert json.loads(web['input'])['local_evidence']==ctx['local_evidence']
    assert web['tools'][0]['type']=='web_search'
    local=build_request(contexts(engine)[0],CFG)
    assert web['instructions']!=local['instructions']
    assert parse_response(response(ctx,web=True),'ABC',cfg,NOW.replace(tzinfo=None),context=ctx)['eligible']
    with pytest.raises(ValueError,match='Web'):
        parse_response(response(ctx),'ABC',cfg,NOW.replace(tzinfo=None),context=ctx)


@pytest.mark.parametrize('kind',['url','tool','untraceable','future','altered','low','short_disabled','abstain'])
def test_local_validation_is_not_a_web_gate_bypass(engine,kind):
    ctx=contexts(engine)[0];raw=response(ctx);cfg=CFG
    if kind=='url':raw=mutate_answer(raw,sources=[dict(url='https://example.com',title='invented',published_at=None)])
    if kind=='tool':raw['output'].insert(0,dict(type='web_search_call',status='completed'))
    if kind=='untraceable':raw=mutate_answer(raw,local_evidence=[dict(source_id='invented',quote='Not in supplied evidence')])
    if kind=='future':
        ctx['local_evidence'][0]['available_at_utc']=(NOW+timedelta(days=1)).isoformat()
        ctx['local_evidence_sha256']=digest(ctx['local_evidence'])
    if kind=='altered':ctx['local_evidence'][0]['text']='changed text'
    if kind=='low':raw=mutate_answer(raw,confidence=.1)
    if kind=='short_disabled':raw=mutate_answer(raw,decision='SHORT');cfg=replace(CFG,allow_short=False)
    if kind=='abstain':raw=mutate_answer(raw,decision='ABSTAIN',identity_verified=False,local_evidence=[])
    if kind in ('url','tool','future','altered'):
        with pytest.raises(ValueError):parse_response(raw,'ABC',cfg,NOW.replace(tzinfo=None),context=ctx)
    else:
        assert not parse_response(raw,'ABC',cfg,NOW.replace(tzinfo=None),context=ctx)['eligible']


@pytest.mark.parametrize('field,value',[('analysis_mode','bad'),('consensus_max_periods',0),
    ('consensus_history_count',-1),('min_local_sources',0),('local_news_max_chars',True)])
def test_new_config_validation(field,value):
    with pytest.raises(ValueError):FilterConfig(**{field:value})


def test_archive_replay_rebuilds_same_request_without_sql_reread(engine,monkeypatch):
    ctx=contexts(engine)[0]
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a,**kw:None)
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW.replace(tzinfo=None))
    import service.llm_directional.repository as repo
    monkeypatch.setattr(repo,'utcnow',lambda:NOW.replace(tzinfo=None))
    result=runner.analyze(engine=engine,batch_id='fixture-model',trade_date='2026-10-16',
        symbol_source='universe-file:test.txt',config=CFG,inputs=[ctx],check_account=False,
        client=lambda request:response(json.loads(request['input'])),run_id='local-test')
    assert result['selected']==['ABC']
    archived,items=Repository(engine).get('local-test')
    assert archived['protocol_version']==VERSION
    assert json.loads(items[0]['request_json'])==build_request(json.loads(repo.dumps(ctx)),CFG)
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM stock_analyst_consensus_eodhd_history'))
    _,selected=runner.qualified_selection(engine,'local-test',date(2026,10,16),'default',now=NOW.replace(tzinfo=None))
    assert [s['symbol'] for s in selected]==['ABC']
    from service.llm_directional.report import report
    assert report(engine,'local-test')['web_provider'] is None


def test_actual_yaml_valid_mode_and_no_barrier_override():
    cfg=load_filter_config()
    assert cfg.analysis_mode in ('web_search','local_data_only')
    assert not any('barrier' in name for name in cfg.snapshot())
