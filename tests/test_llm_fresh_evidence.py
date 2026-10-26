"""V7 freshness, qualified SEC evidence, bounded summaries and archived replay; offline."""
from copy import deepcopy
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
import hashlib
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine,event,text

from service.eodhd.consensus_snapshot import FIELDS
from service.llm_directional import fresh_evidence as evidence,runner
from service.llm_directional.config import FilterConfig
from service.llm_directional.openai_client import ResponsesClient,build_request
from service.llm_directional.prompts import FRESH_VERSION
from service.llm_directional.repository import metadata,runs,digest,dumps,Repository
from service.llm_directional.validation import parse_response

NOW=datetime(2026,10,18,22,tzinfo=timezone.utc)
CFG=FilterConfig(enabled=True,analysis_mode='local_data_only',allow_short=True)
ACCESSION='0000001234-26-000001'
URL='https://www.sec.gov/Archives/edgar/data/1234/000000123426000001/abc.htm'
BODY='<html><body><p>ABC Corporation — Results of Operations. We raised guidance for sales. '+('Revenue improved. '*50)+'</p></body></html>'


class Calendar:
    def sessions(self,start,end):
        days=[]
        while start<=end:
            if start.weekday()<5:
                days.append(SimpleNamespace(session_date=start,is_open=True,
                    close_at_utc=datetime.combine(start,datetime.min.time(),timezone.utc)+timedelta(hours=20)))
            start+=timedelta(days=1)
        return days


@pytest.fixture
def engine(monkeypatch):
    import common.market_calendar
    monkeypatch.setattr(common.market_calendar,'get_market_calendar',lambda *a,**k:Calendar())
    engine=create_engine('sqlite:///:memory:')
    event.listen(engine,'connect',lambda conn,record:conn.create_function('OCTET_LENGTH',1,lambda v:len(v) if v else 0))
    metadata.create_all(engine)
    ddl=[
        '''CREATE TABLE stock_analyst_consensus_eodhd_history(id INT,provider TEXT,symbol TEXT,snapshot_date DATE,
        fiscal_period_end DATE,horizon_raw TEXT,currency TEXT,observed_at DATETIME,available_at DATETIME,
        run_id TEXT,raw_hash TEXT,qualification_status TEXT,units_qualified INT,fiscal_identity_qualified INT,
        historical_pit_qualified INT,'''+','.join(k+' FLOAT' for k in FIELDS)+')',
        '''CREATE TABLE stock_bars_daily(symbol TEXT,date DATE,open FLOAT,high FLOAT,low FLOAT,close FLOAT,
        volume INT,is_filled INT,data_source TEXT,data_adjustment TEXT,ingested_at DATETIME,last_updated DATETIME)''',
        '''CREATE TABLE stock_earnings_calendar(symbol TEXT,earnings_date DATE,eps_estimate FLOAT,revenue_estimate FLOAT,
        eps_actual FLOAT,fiscal_period TEXT,last_updated DATETIME)''',
        '''CREATE TABLE security_master_snapshots(symbol TEXT,cik TEXT,snapshot_date DATE,available_at DATETIME,run_id TEXT)''',
        '''CREATE TABLE pit_collection_runs(run_id TEXT,status TEXT,finished_at DATETIME)''',
        '''CREATE TABLE sec_filing_raw(accession_number TEXT,cik TEXT,symbol TEXT,form_type TEXT,filing_date DATE,
        acceptance_datetime DATETIME,filing_url TEXT,content_sha256 TEXT,content_text TEXT,
        available_at DATETIME,observed_at DATETIME,run_id TEXT)''',
        '''CREATE TABLE sec_filing_documents(id INT,accession_number TEXT,document_type TEXT,document_sequence INT,
        content_blob BLOB,content_sha256 TEXT,document_url TEXT,available_at DATETIME,observed_at DATETIME,run_id TEXT)''',
        '''CREATE TABLE corporate_action_source_events(symbol TEXT,action_type TEXT,effective_date DATE,available_at DATETIME)''',
        '''CREATE TABLE stock_fundamentals_daily(id INT,symbol TEXT,trade_date DATE,available_date DATE,fetched_at DATETIME,
        fiscal_period_end DATE,form TEXT,accession_number TEXT,source TEXT,'''+','.join(k+' FLOAT' for k in evidence.FUND_FIELDS)+')',
    ]
    with engine.begin() as conn:
        for sql in ddl:conn.execute(text(sql))
        conn.execute(text('''INSERT INTO stock_analyst_consensus_eodhd_history
            (id,provider,symbol,snapshot_date,fiscal_period_end,horizon_raw,observed_at,available_at,raw_hash,
            qualification_status,units_qualified,fiscal_identity_qualified,historical_pit_qualified,eps_avg,eps_low,eps_high)
            VALUES (1,'eodhd','ABC','2026-10-18','2026-12-31','0q','2026-10-18 20:00:00','2026-10-18 20:01:00',
            'test','RESEARCH_ONLY',0,0,0,1.2,1.0,1.4)'''))
        conn.execute(text("INSERT INTO pit_collection_runs VALUES ('master','COMPLETED','2026-10-17 12:01:00'),('sec','COMPLETED_WITH_WARNINGS','2026-10-16 22:01:00')"))
        conn.execute(text("INSERT INTO security_master_snapshots VALUES ('ABC','0000001234','2026-10-17','2026-10-17 12:00:00','master')"))
        conn.execute(text('''INSERT INTO sec_filing_raw VALUES (:accession,'0000001234','ABC','8-K','2026-10-16',
            '2026-10-16 17:00:00',:url,:hash,:body,'2026-10-16 22:00:00','2026-10-16 22:00:00','sec')'''),
            dict(accession=ACCESSION,url=URL,hash=hashlib.sha256(BODY.encode()).hexdigest(),body=BODY))
        conn.execute(text("INSERT INTO stock_earnings_calendar VALUES ('ABC','2026-10-21',1.2,1000000,999,'Q3','2026-10-17 12:00:00')"))
        conn.execute(text('''INSERT INTO stock_fundamentals_daily(id,symbol,trade_date,available_date,fetched_at,
            fiscal_period_end,form,accession_number,source,revenue,eps,debt_to_equity)
            VALUES (1,'ABC','2026-08-01','2026-08-02','2026-09-13 11:00:00','2026-06-30','10-Q',:accession,'SEC_EDGAR',1000000,1.1,.4)'''),dict(accession=ACCESSION))
        days=Calendar().sessions(date(2026,9,18),date(2026,10,16))[-21:]
        for index,session in enumerate(days):
            conn.execute(text('''INSERT INTO stock_bars_daily VALUES ('ABC',:day,:open,:high,:low,:close,:volume,0,
                'alpaca_sip','raw','2026-10-17 01:00:00','2026-10-17 01:00:00')'''),
                dict(day=session.session_date,open=10+index,high=12+index,low=9+index,close=11+index,volume=1000+index))
    return engine


def ctx(engine,cfg=CFG,cutoff=NOW):
    return evidence.enrich_contexts(engine,[dict(symbol='ABC',trade_date='2026-10-16',oracle_rank=1,
        oracle_score=.9,horizon_sessions=20,issuer_reference={'company_name':'ABC Corporation'},
        prices_through_decision_date=[{'date':'2016-01-01','close':999}])],cfg,cutoff)[0]


def response(context,*,kind='sec',decision='LONG',web=False):
    src=next(s for s in context['local_evidence'] if s['kind']==kind)
    value=dict(symbol='ABC',issuer='ABC Corporation',identity_verified=True,decision=decision,confidence=.9,
        bull_case='Guidance improvement',bear_case='Execution risks',catalysts=['Guidance'],sources=[],
        local_evidence=[dict(source_id=src['source_id'],quote=src['text'][:120])],
        consensus_analysis='Unqualified provisional EPS context, no assumed currency.',
        context_analysis='Fresh SEC guidance; earnings soon, opposing execution risk. Financial periods are older.')
    output=[]
    if web:
        value['sources']=[dict(url=f'https://issuer.example/{i}',title='Release',published_at='2026-10-18T12:00:00Z') for i in range(2)]
        output.append(dict(type='web_search_call',status='completed',action={'sources':value['sources']}))
    output.append(dict(type='message',content=[dict(type='output_text',text=json.dumps(value))]))
    return dict(status='completed',output=output)


def test_packet_is_bounded_fresh_and_read_only(engine):
    statements=[];event.listen(engine,'before_cursor_execute',lambda c,cu,s,p,ct,m:statements.append(s))
    value=ctx(engine)
    assert value['analysis_protocol']==FRESH_VERSION
    assert {s['kind'] for s in value['local_evidence']}=={'consensus','earnings_calendar','sec','price_volume','fundamentals'}
    assert all(s.lstrip().upper().startswith(('SELECT','PRAGMA')) for s in statements)
    assert value['prices_through_decision_date'][-1]['date']=='2026-10-16'
    assert not any(p['date']=='2016-01-01' for p in value['prices_through_decision_date'])
    calendar=next(s for s in value['local_evidence'] if s['kind']=='earnings_calendar')
    assert 'eps_actual' not in calendar['text'] and '999' not in calendar['text']
    assert json.loads(calendar['text'])['announcement_time'] is None
    assert not next(s for s in value['local_evidence'] if s['kind']=='consensus')['eligible_for_direction']
    sec=next(s for s in value['local_evidence'] if s['kind']=='sec')
    assert len(sec['text'])<=CFG.evidence_sec_excerpt_chars
    assert sec['available_at_utc']=='2026-10-16T22:01:00+00:00'  # Includes completion, not run start.
    assert 'publication_utc' not in sec and sec['publication_precision']=='FILING_DATE_ONLY'
    assert parse_response(response(value),'ABC',CFG,NOW,context=value)['eligible']


@pytest.mark.parametrize('future', [False, True])
def test_price_pair_priority_respects_cutoff_before_limiting_history(engine, future):
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO stock_bars_daily
            SELECT symbol,date,open,high,low,close+0.5,volume+500,is_filled,'eodhd_eod',
                data_adjustment,:available,:available FROM stock_bars_daily
            WHERE data_source='alpaca_sip' '''),
            {'available': '2026-10-19 01:00:00' if future else '2026-10-17 01:00:00'})
    value = ctx(engine)
    prices = value['prices_through_decision_date']
    assert len(prices) == 21
    assert prices[-1]['date'] == '2026-10-16'
    assert prices[-1]['close'] == (31. if future else 31.5)


@pytest.mark.parametrize('sql,kind',[
    ("UPDATE stock_earnings_calendar SET last_updated='2026-10-01'",'earnings_calendar'),
    ("UPDATE stock_fundamentals_daily SET fetched_at='2026-08-01'",'fundamentals'),
    ("UPDATE stock_fundamentals_daily SET source='Yahoo Finance'",'fundamentals'),
    ("UPDATE stock_fundamentals_daily SET available_date='2026-10-19'",'fundamentals'),
    ("UPDATE stock_fundamentals_daily SET fiscal_period_end='2024-01-01'",'fundamentals'),
    ("UPDATE stock_analyst_consensus_eodhd_history SET available_at='2026-10-14'",'consensus'),
    ("UPDATE stock_analyst_consensus_eodhd_history SET eps_avg=99",'consensus'),
    ("UPDATE sec_filing_raw SET content_sha256='wrong'",'sec'),
    ("UPDATE sec_filing_raw SET filing_url='https://not-sec.example/abc'",'sec'),
    ("UPDATE sec_filing_raw SET filing_date='2026-09-01'",'sec'),
    ("UPDATE sec_filing_raw SET cik='0000999999'",'sec'),
    ("UPDATE pit_collection_runs SET status='RUNNING' WHERE run_id='sec'",'sec'),
    ("UPDATE pit_collection_runs SET finished_at='2026-10-19' WHERE run_id='sec'",'sec'),
    ("UPDATE security_master_snapshots SET available_at='2026-09-01'",'sec'),
])
def test_stale_unqualified_future_or_inconsistent_sources_are_not_transmitted(engine,sql,kind):
    with engine.begin() as conn:conn.execute(text(sql))
    value=ctx(engine)
    assert not any(s['kind']==kind for s in value['local_evidence'])
    assert value['local_data_status'][kind]['status']!='AVAILABLE'


@pytest.mark.parametrize('sql',[
    "DELETE FROM stock_bars_daily WHERE date='2026-10-16'",
    "UPDATE stock_bars_daily SET last_updated='2026-10-19' WHERE date='2026-10-16'",
    "UPDATE stock_bars_daily SET data_source='alpaca_iex' WHERE date='2026-10-16'",
    "UPDATE stock_bars_daily SET is_filled=1 WHERE date='2026-10-16'",
    "UPDATE stock_bars_daily SET high=1 WHERE date='2026-10-16'",
])
def test_price_J_is_mandatory_and_no_J_minus_one_fallback(engine,sql):
    with engine.begin() as conn:conn.execute(text(sql))
    with pytest.raises(ValueError):ctx(engine)


def test_calendar_and_price_facts_cannot_alone_authorize_long(engine):
    value=ctx(engine)
    for kind in ('earnings_calendar','price_volume','fundamentals','consensus'):
        result=parse_response(response(value,kind=kind),'ABC',CFG,NOW,context=value)
        assert not result['eligible'] and result['fresh_local_source_count']==0


def test_price_summary_and_split_guard(engine):
    value=ctx(engine)
    source=next(s for s in value['local_evidence'] if s['kind']=='price_volume')
    values=json.loads(source['text'])
    assert values['history_sessions']==21 and values['returns_pct']['20']==round((31/11-1)*100,4)
    assert values['volume_relative_to_prior_20_sessions']>0
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO corporate_action_source_events VALUES ('ABC','split','2026-10-12','2026-10-12 20:00:00')"))
    values=json.loads(next(s for s in ctx(engine)['local_evidence'] if s['kind']=='price_volume')['text'])
    assert values['history_sessions']==1 and values['returns_pct']['20'] is None


@pytest.mark.parametrize('kind',['consensus','sec','earnings_calendar','fundamentals','price_volume'])
def test_archive_validation_rejects_freshness_tampering_even_with_rehashed_packet(engine,kind):
    value=ctx(engine);source=next(s for s in value['local_evidence'] if s['kind']==kind)
    if kind=='price_volume':source['price_trade_date']='2020-01-01'
    elif kind=='fundamentals':source['fetch_at_utc']='2020-01-01T00:00:00Z'
    else:source['available_at_utc']='2020-01-01T00:00:00Z'
    value['local_evidence_sha256']=digest(value['local_evidence'])
    with pytest.raises(ValueError,match='périmée'):
        parse_response(response(value),'ABC',CFG,NOW,context=value)


def test_delayed_context_cannot_trigger_paid_call(engine,monkeypatch):
    value=ctx(engine)
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:(NOW+timedelta(minutes=31)).replace(tzinfo=None))
    with pytest.raises(RuntimeError,match='aucun candidat'):
        runner.analyze(engine=engine,batch_id='fixture',trade_date='2026-10-16',symbol_source='universe-file:test.txt',
            config=CFG,inputs=[value],check_account=False,client=lambda p:pytest.fail('Paid call after context expiry'))


def test_v7_archive_revalidation_does_not_read_mutable_tables(engine,monkeypatch):
    value=ctx(engine)
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a:None)
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW.replace(tzinfo=None))
    import service.llm_directional.repository as repo
    monkeypatch.setattr(repo,'utcnow',lambda:NOW.replace(tzinfo=None))
    result=runner.analyze(engine=engine,batch_id='fixture',trade_date='2026-10-16',symbol_source='universe-file:test.txt',
        config=CFG,inputs=[value],check_account=False,client=lambda p:response(value),run_id='fresh-v7-test')
    assert result['selected']==['ABC']
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM stock_earnings_calendar'))
        conn.execute(text('DELETE FROM sec_filing_raw'))
    _,selected=runner.qualified_selection(engine,'fresh-v7-test',date(2026,10,16),'default',now=NOW.replace(tzinfo=None))
    assert [i['symbol'] for i in selected]==['ABC']
    from service.llm_directional.report import report
    assert report(engine,'fresh-v7-test')['candidates'][0]['context_analysis']


@pytest.mark.parametrize('provider,mode',[('openai','local_data_only'),('openai','web_search'),
    ('deepseek','local_data_only'),('deepseek','web_search')])
def test_v7_request_preserves_models_local_mode_and_native_deepseek(engine,provider,mode):
    cfg=replace(CFG,provider=provider,analysis_mode=mode)
    value=ctx(engine,cfg);request=build_request(value,cfg)
    if provider=='openai':
        assert request['model']==cfg.model and 'context_analysis' in request['text']['format']['schema']['required']
        assert bool(request['tools'])==(mode=='web_search')
    elif mode=='web_search':
        assert request['web_provider']=='deepseek' and request['analysis_protocol']==FRESH_VERSION
        assert 'web_request' not in request and request['analysis_model']==cfg.deepseek_model
    else:
        assert request['analysis_request']['model']==cfg.deepseek_model and 'web_request' not in request


@pytest.mark.parametrize('provider,mode',[('openai','local_data_only'),('openai','web_search'),
    ('deepseek','local_data_only'),('deepseek','web_search')])
def test_v7_full_mock_transport_and_parse(engine,monkeypatch,provider,mode):
    from service.llm_directional import deepseek_search as search
    monkeypatch.setenv('OPENAI_API_KEY','fake-key');monkeypatch.setenv('DEEPSEEK_API_KEY','fake-key')
    monkeypatch.setattr(search.time,'sleep',lambda n:None)
    cfg=replace(CFG,provider=provider,analysis_mode=mode)
    value=ctx(engine,cfg);calls=[]
    def post(url,**kwargs):
        calls.append(url)
        if url==search.SEARCH_URL:
            raw=dict(results=[dict(url=f'https://issuer.example/{i}',title='Release',
                date='2026-10-18T12:00:00Z',content='Guidance publication') for i in range(2)])
        elif url==search.FETCH_URL:
            raw=dict(content='Guidance publication')
        elif url==search.CHAT_URL:
            answer=json.loads(response(value,web=mode=='web_search')['output'][-1]['content'][0]['text'])
            raw=dict(choices=[dict(finish_reason='stop',message={'content':json.dumps(answer)})])
        else:
            assert url=='https://api.openai.com/v1/responses'
            raw=response(value,web=mode=='web_search')
        return SimpleNamespace(status_code=200,headers={},json=lambda:raw)
    raw=ResponsesClient(cfg,SimpleNamespace(post=post))(build_request(value,cfg))
    parsed=parse_response(raw,'ABC',cfg,NOW,context=value)
    assert parsed['eligible'] and parsed['context_analysis']
    if provider=='deepseek':assert all('deepseek.com' in url for url in calls)
    if mode=='local_data_only':assert len(calls)==1


@pytest.mark.parametrize('bad_date',['2026-10-01T12:00:00Z','2026-10-20T12:00:00Z',None,
    '2026-10-18','2026-10-18T12:00:00'])
def test_native_web_excludes_stale_future_unknown_and_ambiguous_pages_before_analysis(engine,monkeypatch,bad_date):
    from service.llm_directional import deepseek_search as search
    monkeypatch.setenv('DEEPSEEK_API_KEY','fake-key');monkeypatch.setattr(search.time,'sleep',lambda n:None)
    cfg=replace(CFG,provider='deepseek',analysis_mode='web_search')
    value=ctx(engine,cfg);payload=build_request(value,cfg);fetched=[]
    assert 'after:2026-10-11' in payload['search_requests'][0]['query']
    def post(url,request,key,label):
        if url==search.SEARCH_URL:
            return dict(results=[dict(url=f'https://issuer.example/{i}',title='Release',
                date='2026-10-18T12:00:00Z',content='Current guidance') for i in range(2)]+
                [dict(url='https://issuer.example/old',date=bad_date,content='SHOULD_NOT_BE_SENT')])
        if url==search.FETCH_URL:
            fetched.append(request['url']);return dict(content='Fresh page content')
        assert url==search.CHAT_URL
        sent=json.loads(request['messages'][1]['content'])
        assert len(sent['web_evidence'])==2 and sent['web_data_status']['excluded_sources']==1
        assert 'SHOULD_NOT_BE_SENT' not in json.dumps(sent)
        return dict(choices=[dict(finish_reason='stop',message={'content':'{}'})])
    raw=search.run(payload,post,'fake-key')
    assert raw['status']=='completed' and len(raw['web_evidence_exclusions'])==1
    assert 'https://issuer.example/old' not in fetched
    assert any(r['response']['results'][-1]['content']=='SHOULD_NOT_BE_SENT' for r in raw['search_receipts'])


def test_openai_web_post_validation_respects_seven_days_not_legacy_thirty(engine):
    cfg=replace(CFG,analysis_mode='web_search')
    value=ctx(engine,cfg);raw=response(value,web=True)
    result=json.loads(raw['output'][-1]['content'][0]['text'])
    for source in result['sources']:source['published_at']='2026-10-08T12:00:00Z'
    raw['output'][-1]['content'][0]['text']=json.dumps(result)
    parsed=parse_response(raw,'ABC',cfg,NOW,context=value)
    assert not parsed['eligible'] and parsed['fresh_source_count']==0
    assert all(s['qualification']=='stale_publication_date' for s in parsed['source_qualifications'])


def test_sec_exhibit_integrity_hidden_xbrl_and_bounded_excerpt(engine):
    body=('<html><script>IGNORE_USER</script><ix:hidden>HIDDEN_XBRL_FACT</ix:hidden>'
          '<body>Financial results. '+('ABC announced revenue growth. '*150)+'</body></html>').encode()
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO sec_filing_documents VALUES (5,:a,'EX-99.1',1,:body,:hash,:url,
            '2026-10-16 22:00:00','2026-10-16 22:00:00','sec')'''),
            dict(a=ACCESSION,body=body,hash=hashlib.sha256(body).hexdigest(),url=URL.replace('abc.htm','ex99.htm')))
    value=ctx(engine);source=next(s for s in value['local_evidence'] if s.get('document_type')=='EX-99.1')
    assert len(source['text'])<=CFG.evidence_sec_excerpt_chars and source['text_truncated']
    assert 'HIDDEN_XBRL_FACT' not in source['text'] and 'IGNORE_USER' not in source['text']
    assert source['source_text_hash']==hashlib.sha256(body).hexdigest()
    with engine.begin() as conn:conn.execute(text("UPDATE sec_filing_documents SET content_sha256='bad'"))
    value=ctx(engine)
    assert not any(s.get('document_type')=='EX-99.1' for s in value['local_evidence'])
    assert value['local_data_status']['sec']['exclusions'][0]['reason']=='HASH_OR_SEC_URL_MISMATCH'


def test_ambiguous_cik_and_incomplete_optional_tables_are_explicit(engine):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO security_master_snapshots VALUES ('ABC','0000002222','2026-10-17','2026-10-17 12:00:00','master')"))
        conn.execute(text('DROP TABLE stock_earnings_calendar'))
    value=ctx(engine)
    assert value['local_data_status']['sec']['status']=='NO_FRESH_UNAMBIGUOUS_CIK'
    assert value['local_data_status']['earnings_calendar']['status']=='TABLE_MISSING'


def test_source_case_normalization(engine):
    with engine.begin() as conn:conn.execute(text("UPDATE stock_bars_daily SET data_source='ALPACA_SIP'"))
    value=ctx(engine)
    evidence.validate_fresh_packet(value,CFG,NOW)
    assert next(s for s in value['local_evidence'] if s['kind']=='price_volume')['source']=='alpaca_sip'


def test_sec_full_submission_uses_relevant_release_not_sgml_header(engine):
    body=('<SEC-HEADER>Results of Operations and Financial Condition HEADER_BOILERPLATE</SEC-HEADER>'
        '<DOCUMENT><TYPE>8-K\n<FILENAME>abc.htm\n<TEXT><html>Legal front cover only.</html></TEXT></DOCUMENT>'
        '<DOCUMENT><TYPE>EX-99.1\n<FILENAME>release.htm\n<TEXT><html>Financial results. '
        +('ABC raised full year guidance and provided cautionary risks. '*30)+
        '</html></TEXT></DOCUMENT><DOCUMENT><TYPE>GRAPHIC\n<TEXT>BINARY_NOISE</TEXT></DOCUMENT>')
    with engine.begin() as conn:
        conn.execute(text('UPDATE sec_filing_raw SET content_text=:body,content_sha256=:hash'),
            dict(body=body,hash=hashlib.sha256(body.encode()).hexdigest()))
    source=next(s for s in ctx(engine)['local_evidence'] if s['kind']=='sec')
    assert source['excerpt_document_type']=='EX-99.1' and source['excerpt_container']=='ARCHIVED_FULL_SUBMISSION'
    assert 'raised full year guidance' in source['text']
    assert all(word not in source['text'] for word in ('HEADER_BOILERPLATE','BINARY_NOISE','Legal front cover'))


@pytest.mark.parametrize('field,bad',[('evidence_context_max_age_minutes',0),('evidence_sec_max_documents',6),
    ('evidence_news_max_age_days',True),('evidence_consensus_max_age_hours',169),
    ('evidence_fundamental_max_period_age_days',401)])
def test_freshness_config_is_bounded(field,bad):
    with pytest.raises(ValueError):replace(CFG,**{field:bad})


def test_preview_is_read_only_and_does_not_reuse_archived_evidence(engine,monkeypatch,tmp_path):
    from scripts.research import us_llm_fresh_context_preview as preview
    class Clock:
        @staticmethod
        def now(tz):return NOW
    monkeypatch.setattr(preview,'datetime',Clock)
    value=ctx(engine)
    value['local_evidence']=[{'text':'OBSOLETE_PAYLOAD_MUST_NOT_BE_REUSED'}]
    repo=Repository(engine)
    repo.create(run_id='preview-fixture',trade_date=date(2026,10,16),batch_id='test',account_id='default',
        status='COMPLETED',started_at=NOW.replace(tzinfo=None),config_json=dumps(CFG.snapshot()),
        input_json=dumps({'candidates':[value]}),input_sha256='fixture',protocol_version=FRESH_VERSION)
    result=preview.run(engine,tmp_path/'preview',run_id='preview-fixture',config=CFG)
    assert result['preview_built']==1 and result['blocked']==0
    assert 'OBSOLETE_PAYLOAD_MUST_NOT_BE_REUSED' not in (tmp_path/'preview'/'ABC.json').read_text(encoding='utf-8')
