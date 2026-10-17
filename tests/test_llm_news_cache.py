"""SQLite/fake transport only. No real DB, secrets, API or broker calls."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
from threading import Event

import pytest
from sqlalchemy import create_engine,func,select,update

from service.llm_directional.news_cache import (ARTICLES,CACHE,IMPORTS,META,USES,BundledEvidenceOnly,CacheMiss,
    NewsCache,UnresolvedAttempt,request_identity,sha)
from service.llm_directional import news_cache_cli as cli
from service.llm_directional.stored_news import analyze_article,article_request,parse


@pytest.fixture
def engine(tmp_path):
    value=create_engine('sqlite:///'+str(tmp_path/'cache.db'))
    META.create_all(value)
    yield value
    value.dispose()


def article():return dict(article_id='source:one',headline='New shares are being issued',summary='',
    body='The company issues new shares for cash.',publication_utc='2025-01-02T15:00:00Z')


def request():return article_request(symbol='TEST',issuer_reference={'company_name':'Test Corp'},
    article=article(),model='gpt-6-luna')


def response():
    value=dict(decision='BEARISH',confidence=.8,issuer_match='MATCH',basis='MATERIAL_FACT',reason='Cash financing.',
        evidence=[dict(article_id='source:one',kind='FINANCING',quote='issues new shares for cash')])
    return dict(id='response-one',model='gpt-6-luna',status='completed',usage={'input_tokens':100,'output_tokens':60},
        output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(value))])])


def execute(cache,req,consumer='test',**kwargs):
    return cache.execute(req,scope='ARTICLE_AT_PUBLICATION',consumer=consumer,qualifier=parse,**kwargs)


def test_single_paid_call_then_database_hit_without_key_or_transport(engine,tmp_path,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    calls=[];cache=NewsCache(engine)
    first=execute(cache,request(),transport=lambda p:(calls.append(p) or response()),allow_paid=True,journal_root=tmp_path/'spool')
    second=execute(cache,request(),consumer='another-experiment')
    assert first['api_calls']==1 and second['api_calls']==0 and second['cache_hit']
    assert len(calls)==1 and second['assessment']['veto_long']
    assert second['available_at'] is not None and second['research_only']
    assert (tmp_path/'spool'/first['cache_key']/'response.json').exists()
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(CACHE)).scalar_one()==1
        assert conn.execute(select(func.count()).select_from(ARTICLES)).scalar_one()==1
        assert conn.execute(select(func.count()).select_from(USES)).scalar_one()==2


def test_cache_miss_cannot_spend_or_claim_by_default(engine):
    with pytest.raises(CacheMiss):execute(NewsCache(engine),request(),transport=lambda p:pytest.fail('paid call'))
    with engine.connect() as conn:assert conn.execute(select(func.count()).select_from(CACHE)).scalar_one()==0


@pytest.mark.parametrize('change',['text','symbol','model','issuer','publication','prompt','schema'])
def test_changed_request_never_reuses_wrong_verdict(engine,change):
    cache=NewsCache(engine);req=request()
    cache.import_response(req,response(),scope='ARTICLE_AT_PUBLICATION',consumer='import',provenance={},qualifier=parse)
    altered=copy.deepcopy(req);context=json.loads(altered['input'])
    if change=='text':context['articles'][0]['body']+=' Updated.'
    elif change=='symbol':context['symbol']='OTHER'
    elif change=='model':altered['model']='another-model'
    elif change=='issuer':context['issuer_reference']['company_name']='Different Corp'
    elif change=='publication':context['articles'][0]['publication_utc']='2025-01-03T15:00:00Z'
    elif change=='prompt':altered['instructions']+=' Different version.'
    else:altered['text']['format']['name']='new_schema_version'
    altered['input']=json.dumps(context)
    with pytest.raises(CacheMiss):execute(cache,altered)


def test_invalid_quote_is_stored_once_and_never_repaid(engine,tmp_path):
    raw=response();raw['output'][0]['content'][0]['text']=raw['output'][0]['content'][0]['text'].replace(
        'issues new shares for cash','is making huge profits')
    cache=NewsCache(engine)
    first=execute(cache,request(),transport=lambda p:raw,allow_paid=True,journal_root=tmp_path/'spool')
    second=execute(cache,request(),consumer='next',transport=lambda p:pytest.fail('invalid must not be repaid'),allow_paid=True)
    assert first['status']==second['status']=='INVALID'
    assert second['assessment']['decision']=='UNKNOWN_INVALID_RESPONSE' and not second['assessment']['veto_long']


def test_ambiguous_transport_blocks_future_calls(engine,tmp_path):
    cache=NewsCache(engine);calls=[]
    def fail(p):calls.append(p);raise TimeoutError('possibly paid')
    with pytest.raises(UnresolvedAttempt):execute(cache,request(),transport=fail,allow_paid=True,journal_root=tmp_path/'spool')
    with pytest.raises(UnresolvedAttempt):execute(cache,request(),transport=fail,allow_paid=True,journal_root=tmp_path/'spool')
    assert len(calls)==1


def test_two_workers_cannot_make_two_calls(engine,tmp_path):
    started,finish=Event(),Event();calls=[]
    def slow(p):calls.append(p);started.set();assert finish.wait(10);return response()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(execute,NewsCache(engine),request(),transport=slow,allow_paid=True,journal_root=tmp_path/'spool')
        try:
            assert started.wait(10)
            with pytest.raises(UnresolvedAttempt):execute(NewsCache(engine),request(),transport=slow,allow_paid=True,journal_root=tmp_path/'spool')
        finally:finish.set()
        assert first.result()['api_calls']==1
    assert len(calls)==1


def test_import_idempotent_but_never_overwrites_a_second_response(engine):
    cache=NewsCache(engine)
    args=dict(scope='ARTICLE_AT_PUBLICATION',consumer='import',provenance={'source':'saved'},qualifier=parse)
    first=cache.import_response(request(),response(),**args)
    assert cache.import_response(request(),response(),**args)['created'] is False
    changed=response();changed['id']='different-paid-response'
    with pytest.raises(ValueError,match='Different paid'):cache.import_response(request(),changed,**args)
    assert json.loads(cache.get(first['cache_key'])['response_json'])['id']=='response-one'


def test_matching_saved_raw_can_recover_missing_post_commit_receipt(engine):
    cache=NewsCache(engine);req=request()
    key,owner,_=cache.claim(req,'ARTICLE_AT_PUBLICATION')
    cache.save_raw(key,owner,response())
    with engine.begin() as conn:conn.execute(update(CACHE).where(CACHE.c.cache_key==key).values(available_at=None))
    with pytest.raises(UnresolvedAttempt):execute(cache,req)
    restored=cache.import_response(req,response(),scope='ARTICLE_AT_PUBLICATION',consumer='recovery',provenance={},qualifier=parse)
    assert restored['api_calls']==0 and restored['available_at'] is not None


def test_bundle_is_not_a_per_article_verdict(engine):
    req=request();context=json.loads(req['input'])
    context.update(decision_date='2025-01-02',cutoff_utc='2025-01-02T21:00:00Z');req['input']=json.dumps(context)
    cache=NewsCache(engine)
    cache.import_response(req,response(),scope='SYMBOL_DATE_BUNDLE',consumer='import',provenance={},qualifier=parse)
    with pytest.raises(CacheMiss):execute(cache,request())
    found=cache.find_article('TEST','source:one')
    assert len(found)==1 and found[0]['analysis_scope']=='SYMBOL_DATE_BUNDLE'
    context['decision_date']='2025-01-03';req['input']=json.dumps(context)
    with pytest.raises(CacheMiss):cache.execute(req,scope='SYMBOL_DATE_BUNDLE',consumer='new',qualifier=parse)


def test_legacy_bundle_does_not_cause_silent_extra_article_payment(engine):
    req=request();context=json.loads(req['input'])
    context.update(decision_date='2025-01-02',cutoff_utc='2025-01-02T21:00:00Z');req['input']=json.dumps(context)
    cache=NewsCache(engine)
    cache.import_response(req,response(),scope='SYMBOL_DATE_BUNDLE',consumer='import',provenance={},qualifier=parse)
    with pytest.raises(BundledEvidenceOnly):
        analyze_article(engine,symbol='TEST',issuer_reference={'company_name':'Test Corp'},article=article(),
            model='gpt-6-luna',consumer_run_id='new',allow_paid=True,
            transport=lambda p:pytest.fail('must not repay an article silently'))


def test_changed_parser_does_not_overwrite_imported_input_snapshot(engine):
    cache=NewsCache(engine)
    key=cache.save_import('saved',{'packets':[],'qualifier_sha256':'old'})
    assert cache.save_import('saved',{'packets':[],'qualifier_sha256':'new'})==key
    assert json.loads(cache.get_import(key)['snapshot_json'])['qualifier_sha256']=='old'
    with pytest.raises(ValueError,match='Imported run changed'):
        cache.save_import('saved',{'packets':[{'changed':True}],'qualifier_sha256':'new'})


def test_article_cannot_smuggle_a_decision_date():
    req=request();value=json.loads(req['input']);value['decision_date']='2025-01-02';req['input']=json.dumps(value)
    with pytest.raises(ValueError):request_identity(req,'ARTICLE_AT_PUBLICATION')


@pytest.mark.parametrize('field',['tools','previous_response_id','conversation'])
def test_web_or_conversation_not_cacheable(field):
    req=request();req[field]=[{'type':'web_search'}] if field=='tools' else 'old-id'
    with pytest.raises(ValueError):request_identity(req,'ARTICLE_AT_PUBLICATION')


def test_raw_corruption_refuses_reuse(engine):
    cache=NewsCache(engine)
    saved=cache.import_response(request(),response(),scope='ARTICLE_AT_PUBLICATION',consumer='import',provenance={},qualifier=parse)
    with engine.begin() as conn:
        conn.execute(update(CACHE).where(CACHE.c.cache_key==saved['cache_key']).values(response_json='{}'))
    with pytest.raises(ValueError,match='integrity'):execute(cache,request())


def test_article_entrypoint_is_date_independent_and_cache_first(engine):
    req=request();cache=NewsCache(engine)
    cache.import_response(req,response(),scope='ARTICLE_AT_PUBLICATION',consumer='import',provenance={},qualifier=parse)
    result=analyze_article(engine,symbol='TEST',issuer_reference={'company_name':'Test Corp'},article=article(),
        model='gpt-6-luna',consumer_run_id='later-day')
    assert result['cache_hit'] and result['api_calls']==0


def test_article_identity_is_independent_of_dictionary_key_order():
    first=article_request(symbol='TEST',issuer_reference={'company_name':'Test','exchange':'NYSE'},article=article(),model='gpt-6-luna')
    second=article_request(symbol='TEST',issuer_reference={'exchange':'NYSE','company_name':'Test'},
        article=dict(reversed(list(article().items()))),model='gpt-6-luna')
    assert first==second


def test_database_only_replay_after_files_unavailable(engine,tmp_path,monkeypatch):
    root=tmp_path/'sealed';(root/'api').mkdir(parents=True)
    req=request();context=json.loads(req['input']);context.update(decision_date='2025-01-02',cutoff_utc='2025-01-02T21:00:00Z')
    req['input']=json.dumps(context)
    packet=dict(context,oracle_rank=1)
    no_news=dict(context,symbol='NONE',articles=[],oracle_rank=2)
    files={'packets.json':[packet,no_news],'api/000.request.json':req,'api/000.response.json':response()}
    for name,value in files.items():(root/name).write_text(json.dumps(value),encoding='utf-8')
    manifest={'actual_calls':1,'files':{str(Path(name)):cli.file_sha(root/name) for name in files}}
    (root/'analysis.json').write_text(json.dumps(manifest),encoding='utf-8')
    (root/'prepare.json').write_text(json.dumps({'files':{'packets.json':cli.file_sha(root/'packets.json')}}),encoding='utf-8')
    first=cli.import_run(engine,root);again=cli.import_run(engine,root)
    assert first['inserted']==1 and again['reused']==1
    monkeypatch.setattr(cli,'saved_requests',lambda p:pytest.fail('must use database only'))
    output=tmp_path/'reuse'
    report=cli.replay_import(engine,first['import_id'],output)
    assert report['api_calls']==0 and report['cache_hits']==1 and report['candidates']==2
    assert json.loads((output/'assessments.json').read_text())[1]['decision']=='UNKNOWN_NO_QUALIFIED_TEXT'
    with engine.connect() as conn:assert conn.execute(select(func.count()).select_from(IMPORTS)).scalar_one()==1


def test_canonical_sql_contains_all_cache_tables_and_columns():
    source=Path('database/sql/ml/llm_news_analysis_cache.sql').read_text(encoding='utf-8')
    import re
    tables=re.findall(r'CREATE TABLE IF NOT EXISTS alpha_trade\.(\w+)\s*\((.*?)\) ENGINE',source,re.S)
    assert {name for name,body in tables}==set(META.tables)
    for name,body in tables:
        for column in META.tables[name].c:assert re.search(r'\b'+column.name+r'\s+',body)


def test_wrong_market_database_is_refused():
    from types import SimpleNamespace
    with pytest.raises(ValueError,match='US alpha_trade'):
        NewsCache(SimpleNamespace(dialect=SimpleNamespace(name='mysql'),url=SimpleNamespace(database='alpha_trade_fr')))
