from dataclasses import replace
from datetime import timedelta
import json

import pytest
from jsonschema import ValidationError

from service.llm_directional import runner
from service.llm_directional.config import FilterConfig
from service.llm_directional.direction_score import score_decision, score_policy
from service.llm_directional.openai_client import build_request, SCHEMA
from service.llm_directional.prompts import SCORE_VERSION, FRESH_VERSION, response_schema
from service.llm_directional.validation import parse_response, select_symbols
from service.llm_directional.repository import Repository
from ihm.services.llm_prediction_review import review_rows, display_review_frame
from ihm.services.risk_prediction_review import risk_review_rows
from tests.test_llm_fresh_evidence import engine, ctx, response, NOW, CFG

CONFIG=replace(CFG,scoring_mode='direction_1_10',allow_short=True)


def answer(context,score=9,*,web=False,confidence=.01):
    raw=response(context,web=web)
    value=json.loads(raw['output'][-1]['content'][0]['text'])
    value.pop('decision')
    value.update(direction_score=score,confidence=confidence)
    raw['output'][-1]['content'][0]['text']=json.dumps(value)
    return raw


@pytest.mark.parametrize('score,decision',[(1,'SHORT'),(2,'SHORT'),(3,'ABSTAIN'),(5,'ABSTAIN'),
    (6,'ABSTAIN'),(8,'ABSTAIN'),(9,'LONG'),(10,'LONG')])
def test_strict_thresholds_and_new_confidence_not_a_selection_gate(engine,score,decision):
    context=ctx(engine,CONFIG)
    assert context['analysis_protocol']==SCORE_VERSION
    result=parse_response(answer(context,score), 'ABC',CONFIG,NOW,context=context)
    assert result['direction_score']==score and result['decision']==decision
    assert result['direction_score_policy']==score_policy(CONFIG)
    assert result['eligible']==(decision!='ABSTAIN')
    assert 'confidence_below_threshold' not in result['selection_blockers']
    if decision=='ABSTAIN':
        assert 'direction_score_neutral' in result['selection_blockers']


@pytest.mark.parametrize('score',[0,11,True,None,'9',9.0,9.5])
def test_invalid_or_non_integer_score_rejected(engine,score):
    context=ctx(engine,CONFIG)
    with pytest.raises((ValueError,ValidationError)):
        parse_response(answer(context,score),'ABC',CONFIG,NOW,context=context)


def test_custom_thresholds_both_strict_and_invalid_configuration():
    config=replace(CONFIG,short_score_threshold=4,long_score_threshold=7)
    assert [score_decision(n,config) for n in [3,4,7,8]]==['SHORT','ABSTAIN','ABSTAIN','LONG']
    for low,high in [(8,3),(3,3),(0,8),(3,11),(True,8),(3,8.0)]:
        with pytest.raises(ValueError,match='Seuils'):
            replace(CONFIG,short_score_threshold=low,long_score_threshold=high)
    with pytest.raises(ValueError):
        replace(CONFIG,scoring_mode='unknown')


def test_subjective_score_never_bypasses_local_evidence_or_short_permission(engine):
    context=ctx(engine,CONFIG)
    raw=answer(context,10)
    value=json.loads(raw['output'][-1]['content'][0]['text'])
    value['local_evidence']=[]
    raw['output'][-1]['content'][0]['text']=json.dumps(value)
    result=parse_response(raw,'ABC',CONFIG,NOW,context=context)
    assert not result['eligible'] and 'insufficient_qualified_local_sources' in result['selection_blockers']
    config=replace(CONFIG,allow_short=False)
    result=parse_response(answer(context,1),'ABC',config,NOW,context=context)
    assert result['decision']=='SHORT' and not result['eligible']
    assert 'short_not_allowed' in result['selection_blockers']


@pytest.mark.parametrize('allow_long,allow_short',[(True,True),(True,False),(False,True),(False,False)])
@pytest.mark.parametrize('web',[False,True])
def test_independent_direction_permissions_keep_scores_but_filter_selection(engine,allow_long,allow_short,web):
    config=replace(CONFIG,allow_long=allow_long,allow_short=allow_short,
                   analysis_mode='web_search' if web else 'local_data_only')
    context=ctx(engine,config)
    items=[]
    for score,direction,allowed in [(9,'LONG',allow_long),(1,'SHORT',allow_short)]:
        parsed=parse_response(answer(context,score,web=web),'ABC',config,NOW,context=context)
        assert parsed['direction_score']==score and parsed['decision']==direction
        assert parsed['eligible']==allowed
        blocker=direction.lower()+'_not_allowed'
        assert (blocker in parsed['selection_blockers'])==(not allowed)
        items.append(dict(parsed,symbol=direction,oracle_rank=len(items)+1))
    assert set(select_symbols(items,config))=={d for d,a in [('LONG',allow_long),('SHORT',allow_short)] if a}
    blocked=next((i for i in items if not i['eligible']),None)
    if blocked:
        with pytest.raises(ValueError,match='non autorisée'):
            select_symbols([dict(blocked,eligible=True)],config)


@pytest.mark.parametrize('provider',['openai','deepseek'])
@pytest.mark.parametrize('mode',['local_data_only','web_search'])
def test_both_providers_and_modes_send_new_schema_and_frozen_thresholds(engine,provider,mode):
    config=replace(CONFIG,provider=provider,analysis_mode=mode,long_score_threshold=7,short_score_threshold=4)
    context=ctx(engine,config)
    request=build_request(context,config)
    if provider=='deepseek':
        if mode=='web_search':
            assert request['web_provider']=='deepseek' and request['analysis_protocol']==SCORE_VERSION
            system=request['analysis_instructions']
            assert request['web_freshness']['max_age_days']==config.evidence_news_max_age_days
        else:
            system=request['analysis_request']['messages'][0]['content']
            assert 'web_request' not in request
    else:
        system=request['instructions']
        schema=request['text']['format']['schema']
        assert schema['properties']['direction_score']=={'type':'integer','enum':list(range(1,11))}
        assert 'decision' not in schema['properties'] and 'direction_score' in schema['required']
    assert 'INTEGER from 1 to 10' in system and 'STRICT' in system
    assert context['direction_score_policy']['long_score_threshold']==7
    assert context['direction_score_policy']['short_score_threshold']==4


def test_gpt_web_score_preserves_traceability(engine):
    config=replace(CONFIG,analysis_mode='web_search')
    context=ctx(engine,config)
    result=parse_response(answer(context,9,web=True),'ABC',config,NOW,context=context)
    assert result['eligible'] and result['fresh_source_count']==2
    bad=answer(context,10,web=True)
    value=json.loads(bad['output'][-1]['content'][0]['text'])
    value['sources'][0]['url']='https://invented.example/not-opened'
    bad['output'][-1]['content'][0]['text']=json.dumps(value)
    result=parse_response(bad,'ABC',config,NOW,context=context)
    assert not result['eligible'] and 'excluded_untraceable_sources' in result['selection_blockers']


@pytest.mark.parametrize('mode',['web_search','local_data_only'])
def test_deepseek_score_mock_transport_end_to_end(engine,monkeypatch,mode):
    from types import SimpleNamespace
    from service.llm_directional.openai_client import ResponsesClient
    from service.llm_directional import deepseek_search
    from tests.test_llm_deepseek_search import fake_session
    monkeypatch.setenv('DEEPSEEK_API_KEY','fake-test-score-key')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setattr(deepseek_search.time,'sleep',lambda _n:None)
    config=replace(CONFIG,provider='deepseek',analysis_mode=mode)
    context=ctx(engine,config)
    if mode=='web_search':
        def mutate(value):
            value.pop('decision');value['direction_score']=1
            value['context_analysis']='Current facts and opposing execution risks.'
        session,calls=fake_session(mutate=mutate)
    else:
        value=answer(context,1)['output'][-1]['content'][0]['text']
        calls=[]
        def post(url,**kw):
            calls.append((url,kw))
            return SimpleNamespace(status_code=200,headers={},json=lambda:dict(choices=[
                dict(finish_reason='stop',message=dict(content=value))]))
        session=SimpleNamespace(post=post)
    raw=ResponsesClient(config,session)(build_request(context,config))
    result=parse_response(raw,'ABC',config,NOW,context=context)
    assert result['direction_score']==1 and result['decision']=='SHORT' and result['eligible']
    assert calls and all('api.deepseek.com' in url for url,_ in calls)
    assert len(calls)==(1 if mode=='local_data_only' else 5)


def test_rank_is_direction_strength_symmetric_then_oracle_rank():
    rows=[dict(symbol=s,direction_score=score,decision=score_decision(score,CONFIG),
        confidence=confidence,eligible=True,oracle_rank=rank) for s,score,rank,confidence in
        [('L9',9,1,.99),('S1',1,3,.01),('L10',10,2,.1),('S2',2,4,.95)]]
    assert select_symbols(rows,replace(CONFIG,max_selected=3))==['L10','S1','L9']
    rows[0]['decision']='SHORT'
    with pytest.raises(ValueError,match='incohérente'):
        select_symbols(rows,CONFIG)


def test_archive_keeps_score_and_thresholds_for_exact_risk_handoff(engine,monkeypatch):
    context=ctx(engine,CONFIG)
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW.replace(tzinfo=None))
    monkeypatch.setattr('service.llm_directional.repository.utcnow',lambda:NOW.replace(tzinfo=None))
    runner.analyze(engine=engine,batch_id='oracle-test',trade_date='2026-10-16',
        symbol_source='universe-file:test.txt',capital_preset_key='capital_2001_5000',
        config=CONFIG,run_id='v8-test',inputs=[context],client=lambda request:answer(context,9),check_account=False)
    run,items=Repository(engine).get('v8-test')
    assert run['protocol_version']==SCORE_VERSION
    assert json.loads(run['selected_json'])==['ABC']
    assert json.loads(run['config_json'])['long_score_threshold']==8
    assessment=json.loads(items[0]['assessment_json'])
    assert assessment['direction_score']==9 and assessment['decision']=='LONG'
    assert 'decision' not in json.loads(items[0]['response_json'])['output'][-1]['content'][0]['text']
    # Changing current defaults cannot reclassify the archived exact run.
    monkeypatch.setattr('service.llm_directional.config.load_filter_config',lambda *a:replace(
        CONFIG,long_score_threshold=9,allow_long=False,allow_short=False))
    _,selected=runner.qualified_selection(engine,'v8-test',run['trade_date'],'default',
        now=NOW.replace(tzinfo=None)+timedelta(minutes=1))
    assert [i['symbol'] for i in selected]==['ABC']


def test_legacy_format_not_converted_and_rendering_both_tables_uses_score(engine):
    context=ctx(engine,CFG)
    assert context['analysis_protocol']==FRESH_VERSION
    assert 'direction_score' not in response_schema(SCHEMA,FRESH_VERSION)['properties']
    candidate=dict(symbol='ABC',oracle_rank=1,oracle_score=.9)
    parsed=dict(direction_score=9,confidence=.2,decision='LONG',eligible=True,selection_blockers=[])
    rows=review_rows([candidate],[dict(symbol='ABC',status='VALID',selected=True,
        assessment_json=json.dumps(parsed))],run_status='COMPLETED',config=CONFIG.snapshot())
    assert rows[0]['Score directionnel LLM (/10)']==9
    step10=display_review_frame(rows,'GPT','direction_1_10')
    assert step10.iloc[0]['Score GPT (/10)']==9 and 'Confiance LLM (%)' not in step10
    risk=risk_review_rows(rows,[],[],status='NON LIÉ',selected_symbols=['ABC'])
    step11=display_review_frame(risk,'GPT','direction_1_10')
    assert step11.iloc[0]['Score GPT (/10)']==9 and step11.iloc[0]['Avis GPT']=='LONG'
    legacy=display_review_frame(rows,'GPT','legacy_confidence')
    assert 'Score GPT (/10)' not in legacy and 'Confiance historique GPT (%)' in legacy


def test_changed_frozen_score_policy_is_rejected(engine):
    context=ctx(engine,CONFIG)
    context['direction_score_policy']['long_score_threshold']=9
    with pytest.raises(ValueError,match='snapshot'):
        parse_response(answer(context,10),'ABC',CONFIG,NOW,context=context)


def test_actual_table_cells_display_integer_score_not_percent():
    from ihm.components.prediction_review_table import table_payload
    rows=[{'Symbole':'ABC','Score directionnel LLM (/10)':9,'Confiance LLM (%)':90.},
          {'Symbole':'XYZ','Score directionnel LLM (/10)':None,'Confiance LLM (%)':None}]
    payload=table_payload(display_review_frame(rows,'GPT','direction_1_10'))
    index=next(i for i,c in enumerate(payload['columns']) if c['label']=='Score GPT (/10)')
    assert payload['rows'][0]['cells'][index]['text']=='9'
    assert payload['rows'][1]['cells'][index]['text']=='—'
