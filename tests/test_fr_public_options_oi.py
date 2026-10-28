from contextlib import nullcontext
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from sqlalchemy import create_engine, text

from service.fr import public_options_oi as oi


PRODUCT = dict(symbol='OR.PA', product_code='OR4', underlying_isin='FR0000120321',
               product_url=oi.BASE+'/en/product/stock-options/or4-dpar')
MONTH = '01-12-2026'


def directory(next_page=False):
    return ('''<main><table><tbody><tr>
      <td class="views-field-field-contract-name"><a href="/en/product/stock-options/or4-dpar">L'Oreal</a></td>
      <td class="views-field-field-contract-code">OR4</td>
      <td class="views-field-field-contract-underlying-isin">FR0000120321</td>
      </tr></tbody></table>'''+('''<a href="?page=1">Next</a><a href="?page=5">Last</a>''' if next_page else '')+'</main>').encode()


def row(side, value, settlement='4.50'):
    return dict(strike=f'<a href="/en/product/stock-options/OR4-DPAR/instrument?Class_symbol=OR4&amp;Class_exchange=DPAR&amp;cOrP={side}&amp;md={MONTH}">390.00</a>',
                open_interest=value, settl=settlement, daily_vol='-', last_date='22:25')


def chain(call='20', put='2.73'):
    return json.dumps(dict(extended=[dict(volumeDate='26/10/26',
        rowc=[row('C',call)], rowp=[row('P',put,settlement='2.73')])])).encode()


@pytest.mark.parametrize('value,number,status', [('1,000',1000,'NUMERIC_ONLY'),
    ('1 000',1000,'NUMERIC_ONLY'),('0',0,'NUMERIC_ONLY'),('-',None,'MISSING'),
    (None,None,'MISSING'),('2.73',None,'INVALID'),('-3',None,'INVALID'),
    ('12,34',None,'INVALID'),('NaN',None,'INVALID'),(str(2**64),None,'INVALID')])
def test_oi_is_not_a_price(value,number,status):
    assert oi.integer(value)==(number,status)


def test_chain_keeps_raw_bad_put_and_never_invents_dates():
    call,put=oi.parse_chain(chain(),PRODUCT,[MONTH])
    assert call['open_interest']==20 and call['option_type']=='CALL'
    assert put['oi_raw']=='2.73' and put['open_interest'] is None
    assert put['quality_status']=='INVALID'
    for item in (call,put):
        assert item['expiry_month']==date(2026,12,1)
        assert item['expiration_date'] is item['oi_reference_date'] is item['contract_isin'] is None
        assert item['volume_date']==date(2026,10,26) and not item['ml_eligible']
        assert not json.loads(item['quality_json'])['oi_date_qualified']


def test_silent_missing_maturity_is_rejected():
    with pytest.raises(ValueError,match='Mois demandés non retournés'):
        oi.parse_chain(chain(),PRODUCT,[MONTH,'01-06-2027'])


def test_integral_oi_identical_to_settlement_is_ambiguous():
    payload=json.loads(chain()); payload['extended'][0]['rowc']=[row('C','20','20.00')]
    first=oi.parse_chain(json.dumps(payload),PRODUCT,[MONTH])[0]
    assert first['open_interest'] is None and first['quality_status']=='AMBIGUOUS_SETTLEMENT'


@pytest.mark.parametrize('change', ['side','product','month','duplicate','future','strike'])
def test_contradictory_contracts_are_rejected(change):
    payload=json.loads(chain()); group=payload['extended'][0]
    if change=='side': group['rowc'][0]=row('P','20')
    if change=='product': group['rowc'][0]['strike']=group['rowc'][0]['strike'].replace('OR4','OR5')
    if change=='month': group['rowc'][0]['strike']=group['rowc'][0]['strike'].replace(MONTH,'01-01-2027')
    if change=='duplicate': group['rowc']*=2
    if change=='future': group['volumeDate']='01/01/50'
    if change=='strike': group['rowc'][0]['strike']=group['rowc'][0]['strike'].replace('390.00','-390.00')
    with pytest.raises(ValueError): oi.parse_chain(json.dumps(payload),PRODUCT,[MONTH])


def test_directory_pagination_and_exact_isin():
    rows,next_page=oi.parse_directory(directory(True),oi.DIRECTORY)
    assert rows[0]['underlying_isin']==PRODUCT['underlying_isin']
    assert next_page==oi.DIRECTORY+'?page=1'
    assert oi.parse_directory(directory(),oi.DIRECTORY+'?page=1')[1] is None
    with pytest.raises(ValueError): oi.parse_directory(directory().replace(b'OR4',b'OR5'),oi.DIRECTORY)
    with pytest.raises(ValueError): oi.parse_underlying(b'<tr><td>ISIN</td><td>US0000120321</td></tr>',PRODUCT['underlying_isin'])


@pytest.mark.parametrize('url', [oi.BASE+'/en/product/stock-options/or4-dpar',
    'http://live.euronext.com/robots.txt',oi.DIRECTORY+'?page=1&query=secret',
    'https://other.example/en/ajax/getUnderlying/OR4/DPAR/options'])
def test_requests_are_restricted_to_public_routes(url):
    with pytest.raises(ValueError): oi.validate_url(url)


@pytest.fixture
def environment(tmp_path,monkeypatch):
    # SQL transactions and durable response bodies are exercised without network/MySQL.
    engine=create_engine('sqlite:///'+str(tmp_path/'oi.sqlite'))
    ddl=Path('database/sql/fr/migration_fr_0011_public_option_oi.sql').read_text()
    import re
    ddl=re.sub(r'--[^\n]*','',ddl)
    ddl=re.sub(r'\) ENGINE=[^;]+;',');',ddl)
    ddl=re.sub(r'^ KEY [^\n]+\n','',ddl,flags=re.M)
    ddl=ddl.replace('BIGINT UNSIGNED','BIGINT').replace('LONGBLOB','BLOB')
    with engine.begin() as conn:
        for statement in ddl.split(';'):
            if statement.strip(): conn.exec_driver_sql(statement)
    monkeypatch.setattr(oi,'check_schema',lambda engine:None)
    monkeypatch.setattr(oi,'reference_scope',lambda path:(1,{'OR.PA':({'isin':PRODUCT['underlying_isin']},set())},[]))
    monkeypatch.setattr(oi,'verified_session',lambda:nullcontext(SimpleNamespace(headers={})))
    calls=[]
    def fetch(method,url,params):
        calls.append((method,url,params))
        if url.endswith('robots.txt'): return b'User-agent: *\nAllow: /',200
        if '/list' in url: return directory(),200
        if '/getUnderlying/' in url: return b'<table><tr><td>ISIN</td><td>FR0000120321</td></tr></table>',200
        if '/getPricesOptionsForm/' in url:
            return f'<select id="maturityDates"><option value="{MONTH}">Dec 2026</option></select>'.encode(),200
        assert method=='POST' and params=={'ps':'999','md[]':[MONTH]}
        if '/submitOptionsForm/' in url: return b'<div id="price_option_details_0"></div>',200
        return chain(),200
    yield engine,tmp_path,calls,fetch
    engine.dispose()


def invoke(env, **changes):
    engine,root,calls,fetch=env
    result={'status':'RUNNING'}
    oi.collect(changes.pop('cfg',{}),result,root=root/'run',identities=root/'identities',
               engine=engine,fetcher=changes.pop('fetcher',fetch),sleep=lambda seconds:None,**changes)
    return result


def test_collection_commits_raw_and_rows_without_qualifying_them(environment):
    result=invoke(environment)
    engine,root,calls,_=environment
    assert len(calls)==6 and result['persisted_count']==2 and result['numeric_oi_rows']==1
    assert result['invalid_oi_rows']==1 and result['data_status']=='PARTIAL'
    assert result['received_count']==1 and not result['directional_filter_ready']
    with engine.connect() as c:
        assert c.execute(text('SELECT status FROM fr_option_oi_public_runs')).scalar()=='PARTIAL'
        for r in c.execute(text('SELECT body,body_sha256,available_at FROM fr_option_oi_public_responses')).mappings():
            assert oi.digest(r['body'])==r['body_sha256'] and r['available_at']
        assert c.execute(text('SELECT sum(ml_eligible) FROM fr_option_oi_public_contracts')).scalar()==0
    report=json.loads(next((root/'run/reports').glob('*.json')).read_text())
    assert report['status']=='PARTIAL' and len(list((root/'run/receipts').glob('*.json')))==6


def test_dry_run_has_no_sql_or_http_or_files(environment):
    result=invoke(environment,dry_run=True)
    engine,root,calls,_=environment
    assert not calls and not (root/'run').exists() and not result['sql_writes']
    with engine.connect() as c: assert c.execute(text('SELECT count(*) FROM fr_option_oi_public_runs')).scalar()==0


@pytest.mark.parametrize('code',[403,429])
def test_refusal_stops_without_retry_and_preserves_body(environment,code):
    engine,root,calls,fetch=environment
    def refuse(method,url,params):
        if 'getUnderlying' in url:
            calls.append((method,url,params));return b'Forbidden',code
        return fetch(method,url,params)
    with pytest.raises(PermissionError): invoke(environment,fetcher=refuse)
    assert len(calls)==3
    with engine.connect() as c:
        assert c.execute(text('SELECT status FROM fr_option_oi_public_runs')).scalar()=='FAILED'
        assert c.execute(text('SELECT body FROM fr_option_oi_public_responses WHERE http_status=:code'),{'code':code}).scalar()==b'Forbidden'


def test_parse_failure_keeps_unservable_raw(environment):
    engine,root,calls,fetch=environment
    def broken(method,url,params):
        if method=='POST': calls.append((method,url,params));return b'{broken',200
        return fetch(method,url,params)
    with pytest.raises(RuntimeError,match='incomplète'): invoke(environment,fetcher=broken)
    with engine.connect() as c:
        row=c.execute(text('SELECT body,available_at,parse_status FROM fr_option_oi_public_responses WHERE body=:body'),{'body':b'{broken'}).one()
        assert row== (b'{broken',None,'RECEIVED')
        assert c.execute(text('SELECT count(*) FROM fr_option_oi_public_contracts')).scalar()==0


def test_budget_failure_is_not_success(environment):
    with pytest.raises(RuntimeError,match='Budget'): invoke(environment,cfg={'max_http_requests':2})
    assert len(environment[2])==2
    with environment[0].connect() as c:
        assert c.execute(text('SELECT status FROM fr_option_oi_public_runs')).scalar()=='FAILED'


def test_wrong_database_rejected_before_access():
    engine=SimpleNamespace(url=SimpleNamespace(database='alpha_trade'))
    with pytest.raises(ValueError,match='alpha_trade_fr'): oi.check_schema(engine)


def test_catalogue_handler_calls_collector_with_fr_scope(tmp_path,monkeypatch):
    from service.fr import operational_batch_15a as runner
    calls=[]
    monkeypatch.setattr(oi,'collect',lambda *args,**kw:calls.append(kw))
    monkeypatch.setattr(runner,'OPS',tmp_path/'ops')
    cfg=runner.load_section(oi.BATCH,runner.ROOT/'batch_fr.yaml')
    runner._handle(oi.BATCH,cfg,{},dry_run=False,today=None)
    assert len(calls)==1 and not (tmp_path/'ops'/oi.BATCH/'.lock').exists()
    assert calls[0]['identities'].is_relative_to(runner.ROOT/'artifacts/fr')
