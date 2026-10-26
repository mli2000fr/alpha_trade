"""One authorized failed-symbol retry, no external API/database/broker."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta,timezone
import json

import pytest
from sqlalchemy import update

from service.llm_directional import runner,resume_failed as retry
from service.llm_directional.repository import Repository,digest,dumps,runs,assessments
from tests.test_llm_fresh_evidence import engine,NOW,ctx
from tests.test_llm_trend_evidence import CONFIG,answer


def parent_fixture(engine,monkeypatch):
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a,**k:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW)
    cfg=replace(CONFIG,enabled=True,oracle_top_n=2,max_selected=2)
    a=ctx(engine,cfg);b=deepcopy(a)
    for c,symbol,rank in [(a,'ABC',1),(b,'VICR',2)]:
        c.update(symbol=symbol,oracle_rank=rank,oracle_score=.9-rank*.1)
    def old_client(req):
        c=json.loads(req['input'])
        if c['symbol']=='VICR':raise RuntimeError('OpenAI transport ReadTimeout; pas de retry automatique')
        raw=answer(c)
        val=json.loads(raw['output'][-1]['content'][0]['text']);val['symbol']=c['symbol']
        raw['output'][-1]['content'][0]['text']=json.dumps(val)
        return raw
    with pytest.raises(RuntimeError,match='1 réponses invalides'):
        runner.analyze(engine=engine,batch_id='oracle',trade_date=NOW.date(),symbol_source='universe',
            run_id='parent',config=cfg,inputs=[a,b],client=old_client,check_account=False)
    # Repository finish stamps real UTC in normal operation; deterministic fixture only.
    with engine.begin() as conn:
        conn.execute(update(runs).where(runs.c.run_id=='parent').values(completed_at=NOW))
    return cfg


def new_answer(req):
    c=json.loads(req['input']);raw=answer(c)
    val=json.loads(raw['output'][-1]['content'][0]['text']);val['symbol']=c['symbol']
    raw['output'][-1]['content'][0]['text']=json.dumps(val)
    return raw


def resume(engine,monkeypatch,tmp_path,*,bad_client=False):
    parent_fixture(engine,monkeypatch)
    before=deepcopy(Repository(engine).get('parent'));calls=[]
    def client(req):
        calls.append(json.loads(req['input'])['symbol'])
        if bad_client:raise RuntimeError('ReadTimeout again')
        return new_answer(req)
    def refresh(engine,c,cfg,now):
        result=deepcopy(c);result['evidence_cutoff_utc']=now.replace(tzinfo=timezone.utc).isoformat()
        return result
    kwargs=dict(engine=engine,parent_id='parent',expected_symbols=['VICR'],run_id='child',
        output_dir=tmp_path/'child',client=client,refresher=refresh,now=NOW+timedelta(hours=6),check_account=False)
    return before,calls,kwargs


def test_retry_refreshes_only_failed_context_reuses_others_and_preserves_parent(engine,monkeypatch,tmp_path):
    before,calls,kwargs=resume(engine,monkeypatch,tmp_path)
    view=retry.resume(**kwargs)
    assert calls==['VICR'] and view['status']=='COMPLETED'
    assert Repository(engine).get('parent')==before
    child,items=Repository(engine).get('child');snap=json.loads(child['input_json'])
    assert snap['resume']['reused_symbols']==['ABC']
    assert snap['resume']['retried_symbols']==['VICR']
    assert json.loads(child['config_json'])['timeout_seconds']==300
    assert all(i['status']=='VALID' for i in items)
    retry.validate_resume_lineage(engine,child,snap,NOW+timedelta(hours=7))
    with pytest.raises(ValueError,match='expired'):
        retry.validate_resume_lineage(engine,child,snap,NOW+timedelta(hours=25))
    with pytest.raises(ValueError,match='already exists'):retry.resume(**kwargs)
    assert calls==['VICR']


def test_second_timeout_archived_no_retry_no_selection(engine,monkeypatch,tmp_path):
    before,calls,kwargs=resume(engine,monkeypatch,tmp_path,bad_client=True)
    with pytest.raises(RuntimeError,match='Bounded GPT retry failed'):retry.resume(**kwargs)
    child,items=Repository(engine).get('child')
    assert child['status']=='FAILED' and json.loads(child['selected_json'])==[]
    assert calls==['VICR'] and Repository(engine).get('parent')==before
    assert {i['symbol']:i['status'] for i in items}=={'ABC':'VALID','VICR':'FAILED'}


@pytest.mark.parametrize('fault',['expired','symbol','request','raw','rank'])
def test_invalid_resume_refused_before_any_paid_call(engine,monkeypatch,tmp_path,fault):
    before,calls,kwargs=resume(engine,monkeypatch,tmp_path)
    if fault=='expired':kwargs['now']=NOW+timedelta(hours=25)
    elif fault=='symbol':kwargs['expected_symbols']=['ABC']
    else:
        with engine.begin() as conn:
            changes={'request':dict(request_json='{}'),'raw':dict(response_sha256='0'*64),'rank':dict(oracle_rank=20)}[fault]
            conn.execute(update(assessments).where(assessments.c.run_id=='parent',assessments.c.symbol=='ABC').values(**changes))
    with pytest.raises(ValueError):retry.resume(**kwargs)
    assert calls==[]
    assert not (tmp_path/'child').exists()


def test_modified_reused_observation_or_deadline_cannot_pass_downstream(engine,monkeypatch,tmp_path):
    before,calls,kwargs=resume(engine,monkeypatch,tmp_path);retry.resume(**kwargs)
    child,_=Repository(engine).get('child');snap=json.loads(child['input_json'])
    forged=deepcopy(snap);forged['resume']['inherited_valid_until_utc']=(NOW+timedelta(days=2)).isoformat()
    with pytest.raises(ValueError,match='deadline'):
        retry.validate_resume_lineage(engine,child,forged,NOW+timedelta(hours=7))
    with engine.begin() as conn:
        conn.execute(update(assessments).where(assessments.c.run_id=='child',assessments.c.symbol=='ABC').values(observed_at=NOW+timedelta(hours=6)))
    with pytest.raises(ValueError,match='Reused answer changed'):
        retry.validate_resume_lineage(engine,child,snap,NOW+timedelta(hours=7))


@pytest.mark.parametrize('fault',['private_field','secret','unknown_context','web','unknown_source'])
def test_outbound_guard_rejects_private_or_unexpected_payload(fault):
    context=dict(symbol='VICR',issuer_reference={'company_name':'Vicor','exchange':'NASDAQ'},
        analysis_mode='local_data_only',local_evidence=[dict(kind='news',text='Public issuer release')])
    request=dict(model='gpt-6-luna',tools=[],tool_choice='none',max_output_tokens=20000)
    if fault=='private_field':context['local_evidence'][0]['holdings']=[{'quantity':2}]
    elif fault=='secret':context['local_evidence'][0]['text']='sk-proj-'+'x'*30
    elif fault=='unknown_context':context['portfolio_cash']=4000
    elif fault=='web':request['tools']=[{'type':'web_search'}]
    elif fault=='unknown_source':context['local_evidence'][0]['kind']='broker_account'
    with pytest.raises(ValueError):retry.public_payload_check(context,request)


@pytest.mark.parametrize('fault',[None,'model','instructions','schema','tokens','data','duplicate','nonfinite','boolean'])
def test_request_equivalence_permits_only_json_object_order(fault):
    expected=dict(model='same',instructions='same',text={'schema':'same'},max_output_tokens=20000,
        input='{"a":1,"b":{"x":2,"y":3}}')
    actual=deepcopy(expected);actual['input']='{"b":{"y":3,"x":2},"a":1}'
    if fault=='model':actual['model']='other'
    elif fault=='instructions':actual['instructions']='other'
    elif fault=='schema':actual['text']={'schema':'other'}
    elif fault=='tokens':actual['max_output_tokens']=20001
    elif fault=='data':actual['input']='{"a":2,"b":{"x":2,"y":3}}'
    elif fault=='duplicate':actual['input']='{"a":0,"a":1,"b":{"x":2,"y":3}}'
    elif fault=='nonfinite':actual['input']='{"a":NaN,"b":{"x":2,"y":3}}'
    elif fault=='boolean':actual['input']='{"a":true,"b":{"x":2,"y":3}}'
    assert retry.equivalent_resumed_request(actual,expected)==(fault is None)


@pytest.mark.parametrize('symbol',['VICR','ABC'])
def test_downstream_input_order_compatibility_is_scoped_to_retried_symbol(engine,monkeypatch,tmp_path,symbol):
    before,calls,kwargs=resume(engine,monkeypatch,tmp_path);retry.resume(**kwargs)
    child,items=Repository(engine).get('child')
    item=next(i for i in items if i['symbol']==symbol)
    request=json.loads(item['request_json']);context=json.loads(request['input'])
    request['input']=json.dumps(dict(reversed(list(context.items()))),ensure_ascii=False)
    completed=retry.naive_utc(NOW+timedelta(hours=6))
    with engine.begin() as conn:
        conn.execute(update(runs).where(runs.c.run_id=='child').values(completed_at=completed))
        conn.execute(update(assessments).where(assessments.c.run_id=='child',assessments.c.symbol==symbol)
            .values(request_json=dumps(request)))
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    if symbol=='ABC':
        with pytest.raises(ValueError,match='Reused answer changed'):
            runner.qualified_selection(engine,'child',child['trade_date'],'default',now=completed+timedelta(minutes=1))
    else:
        result,_=runner.qualified_selection(engine,'child',child['trade_date'],'default',now=completed+timedelta(minutes=1))
        assert result['status']=='COMPLETED'
    assert calls==['VICR'] and Repository(engine).get('parent')==before
