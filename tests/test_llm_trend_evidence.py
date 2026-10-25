"""V9 separation of tentative tendency and retention evidence; entirely offline."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError, validate
from sqlalchemy import text

from service.llm_directional.config import FilterConfig
from service.llm_directional import runner
from service.llm_directional.openai_client import SCHEMA, ResponsesClient, build_request
from service.llm_directional.prompts import (TREND_EVIDENCE_VERSION, SCORE_VERSION, FRESH_VERSION,
    response_schema, instructions)
from service.llm_directional.repository import Repository, digest
from service.llm_directional.validation import parse_response, select_symbols
from service.llm_directional.report import report
from ihm.services.llm_prediction_review import review_rows, display_review_frame, load_prediction_review
from ihm.services.risk_prediction_review import risk_review_rows
from tests.test_llm_fresh_evidence import engine, ctx, CFG, NOW, response
from tests.test_llm_prediction_review import fake_ui

CONFIG=replace(CFG,scoring_mode='direction_1_10',separate_trend_evidence=True)


def answer(context,score=9,quality='SUFFICIENT',*,web=False,kind='sec',identity=True):
    raw=response(context,kind=kind,web=web)
    value=json.loads(raw['output'][-1]['content'][0]['text'])
    value.pop('decision')
    value.update(direction_score=score,trend_status='UNDETERMINABLE' if score is None else 'ASSESSED',
        evidence_quality=quality,evidence_explanation='Quoted issuer evidence; limitations remain explicit.',
        identity_verified=identity)
    raw['output'][-1]['content'][0]['text']=json.dumps(value)
    return raw


def mutate(raw,**values):
    raw=deepcopy(raw)
    value=json.loads(raw['output'][-1]['content'][0]['text']);value.update(values)
    raw['output'][-1]['content'][0]['text']=json.dumps(value)
    return raw


def test_config_opt_in_and_old_snapshot_default():
    assert FilterConfig().separate_trend_evidence is False
    assert FilterConfig(**{'scoring_mode':'direction_1_10'}).separate_trend_evidence is False
    for bad in [1,'true',None]:
        with pytest.raises(ValueError):
            replace(CONFIG,separate_trend_evidence=bad)
    with pytest.raises(ValueError):
        FilterConfig(separate_trend_evidence=True)
    assert len(TREND_EVIDENCE_VERSION)<=40


def test_schema_nullable_and_v8_schema_unchanged():
    schema=response_schema(SCHEMA,TREND_EVIDENCE_VERSION)
    assert schema['properties']['direction_score']=={'type':['integer','null'],'enum':[*range(1,11),None]}
    assert {'direction_score','trend_status','evidence_quality','evidence_explanation'}<=set(schema['required'])
    assert 'decision' not in schema['properties']
    assert response_schema(SCHEMA,SCORE_VERSION)['properties']['direction_score']=={'type':'integer','enum':list(range(1,11))}
    assert 'trend_status' not in response_schema(SCHEMA,SCORE_VERSION)['properties']
    assert 'direction_score' not in response_schema(SCHEMA,FRESH_VERSION)['properties']


@pytest.mark.parametrize('web',[False,True])
@pytest.mark.parametrize('quality',['SUFFICIENT','PARTIAL','INSUFFICIENT'])
@pytest.mark.parametrize('score',[1,5,9,None])
def test_tendency_quality_and_retention_independent(engine,web,quality,score):
    cfg=replace(CONFIG,analysis_mode='web_search' if web else 'local_data_only')
    context=ctx(engine,cfg)
    result=parse_response(answer(context,score,quality,web=web),'ABC',cfg,NOW,context=context)
    assert result['direction_score']==score
    assert result['trend_status']==('UNDETERMINABLE' if score is None else 'ASSESSED')
    assert result['reported_evidence_quality']==quality
    effective='INSUFFICIENT' if score is None else quality
    assert result['evidence_quality']==effective
    assert result['eligible']==(score in (1,9) and quality=='SUFFICIENT')
    assert result['retention_evidence_verified']==(effective=='SUFFICIENT')
    if score is None:
        assert 'trend_undeterminable' in result['selection_blockers']
        assert 'direction_score_neutral' not in result['selection_blockers']
    if score==5:
        assert 'direction_score_neutral' in result['selection_blockers']
    assert select_symbols([dict(result,oracle_rank=1)],cfg)==(['ABC'] if result['eligible'] else [])


@pytest.mark.parametrize('web',[False,True])
def test_claim_sufficient_cannot_promote_unqualified_context(engine,web):
    cfg=replace(CONFIG,analysis_mode='web_search' if web else 'local_data_only')
    context=ctx(engine,cfg)
    raw=answer(context,9,kind='consensus',web=web)
    if web:
        raw=mutate(raw,sources=[])
    parsed=parse_response(raw,'ABC',cfg,NOW,context=context)
    assert parsed['direction_score']==9 and parsed['decision']=='LONG'
    assert parsed['reported_evidence_quality']=='SUFFICIENT'
    assert parsed['evidence_quality']=='PARTIAL' and not parsed['eligible']
    assert parsed['fresh_local_source_count']==0
    assert 'evidence_partial' in parsed['selection_blockers']
    with pytest.raises(ValueError,match='preuves insuffisantes'):
        select_symbols([dict(parsed,eligible=True,oracle_rank=1)],cfg)


@pytest.mark.parametrize('web',[False,True])
def test_unverified_identity_is_valid_but_insufficient_not_a_trade(engine,web):
    cfg=replace(CONFIG,analysis_mode='web_search' if web else 'local_data_only')
    context=ctx(engine,cfg)
    parsed=parse_response(answer(context,None,'INSUFFICIENT',web=web,identity=False),'ABC',cfg,NOW,context=context)
    assert parsed['trend_status']=='UNDETERMINABLE' and not parsed['eligible']
    assert 'identity_not_confirmed' in parsed['selection_blockers']
    assert parsed['evidence_quality']=='INSUFFICIENT'


def test_invented_quote_is_not_repaired_or_made_executable(engine):
    context=ctx(engine,CONFIG)
    raw=mutate(answer(context),local_evidence=[dict(source_id=context['local_evidence'][0]['source_id'],
        quote='A fabricated contiguous quote not present in any supplied document.')])
    parsed=parse_response(raw,'ABC',CONFIG,NOW,context=context)
    assert parsed['direction_score']==9 and not parsed['eligible']
    assert 'excluded_untraceable_local_sources' in parsed['selection_blockers']
    assert parsed['evidence_quality']=='INSUFFICIENT'


@pytest.mark.parametrize('score',[1,9])
@pytest.mark.parametrize('allow_long,allow_short',[(True,True),(True,False),(False,True),(False,False)])
def test_permissions_do_not_change_tendency_or_evidence_grade(engine,score,allow_long,allow_short):
    cfg=replace(CONFIG,allow_long=allow_long,allow_short=allow_short)
    context=ctx(engine,cfg)
    parsed=parse_response(answer(context,score),'ABC',cfg,NOW,context=context)
    assert parsed['direction_score']==score and parsed['evidence_quality']=='SUFFICIENT'
    assert parsed['eligible']==(allow_long if score==9 else allow_short)


@pytest.mark.parametrize('values',[
    {'direction_score':None,'trend_status':'ASSESSED'},
    {'direction_score':5,'trend_status':'UNDETERMINABLE'},
    {'direction_score':True},{'direction_score':0},{'direction_score':11},
    {'direction_score':9.0},{'evidence_quality':'CERTIFIED'},
    {'evidence_explanation':''},{'evidence_explanation':'  '},
])
def test_invalid_or_inconsistent_output_rejected(engine,values):
    context=ctx(engine,CONFIG)
    with pytest.raises((ValueError,ValidationError)):
        parse_response(mutate(answer(context),**values),'ABC',CONFIG,NOW,context=context)


@pytest.mark.parametrize('provider',['openai','deepseek'])
@pytest.mark.parametrize('mode',['web_search','local_data_only'])
def test_new_prompt_and_schema_routed_to_both_providers(engine,provider,mode):
    cfg=replace(CONFIG,provider=provider,analysis_mode=mode)
    context=ctx(engine,cfg)
    assert context['analysis_protocol']==TREND_EVIDENCE_VERSION
    request=build_request(context,cfg)
    if provider=='deepseek':
        system=request['analysis_instructions'] if mode=='web_search' else request['analysis_request']['messages'][0]['content']
    else:
        system=request['instructions']
        assert request['text']['format']['schema']['properties']['direction_score']['type']==['integer','null']
        assert (request['tools']==[])==(mode=='local_data_only')
    assert 'Never replace\nmissing information with 5' in system
    assert 'Provisional context' in system or 'tentative tendency' in system
    assert 'exact contiguous substring' in system
    assert 'Missing, stale or conflicting evidence should move the score toward 5-6' not in system


@pytest.mark.parametrize('mode',['web_search','local_data_only'])
def test_deepseek_mock_transport_v9(engine,monkeypatch,mode):
    from service.llm_directional import deepseek_search
    from tests.test_llm_deepseek_search import fake_session
    cfg=replace(CONFIG,provider='deepseek',analysis_mode=mode)
    context=ctx(engine,cfg)
    monkeypatch.setenv('DEEPSEEK_API_KEY','fake-local-test-key')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setattr(deepseek_search.time,'sleep',lambda _:None)
    if mode=='web_search':
        def revise(value):
            value.pop('decision');value.update(direction_score=None,trend_status='UNDETERMINABLE',
                evidence_quality='INSUFFICIENT',evidence_explanation='No usable directional basis.',context_analysis='Unknown tendency.')
        session,calls=fake_session(mutate=revise)
    else:
        content=answer(context,None,'INSUFFICIENT')['output'][-1]['content'][0]['text']
        calls=[]
        def post(url,**kwargs):
            calls.append(url)
            return SimpleNamespace(status_code=200,headers={},json=lambda:dict(choices=[
                dict(finish_reason='stop',message=dict(content=content))]))
        session=SimpleNamespace(post=post)
    raw=ResponsesClient(cfg,session)(build_request(context,cfg))
    parsed=parse_response(raw,'ABC',cfg,NOW,context=context)
    assert parsed['direction_score'] is None and not parsed['eligible']
    assert parsed['evidence_quality']=='INSUFFICIENT' and calls


@pytest.mark.parametrize('score,quality',[(9,'SUFFICIENT'),(9,'PARTIAL'),(None,'INSUFFICIENT'),(5,'SUFFICIENT')])
def test_immutable_sql_archive_risk_report_and_tables(engine,monkeypatch,fake_ui,score,quality):
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE stock_metadata (symbol TEXT PRIMARY KEY, company_name TEXT)'))
        conn.execute(text("INSERT INTO stock_metadata VALUES ('ABC','ABC Corporation')"))
    context=ctx(engine,CONFIG)
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW.replace(tzinfo=None))
    monkeypatch.setattr('service.llm_directional.repository.utcnow',lambda:NOW.replace(tzinfo=None))
    result=runner.analyze(engine=engine,batch_id='oracle-test',trade_date='2026-10-16',
        symbol_source='universe-file:test.txt',capital_preset_key='capital_2001_5000',config=CONFIG,
        run_id='v9-test',inputs=[context],client=lambda request:answer(context,score,quality),check_account=False)
    selected=['ABC'] if (score,quality)==(9,'SUFFICIENT') else []
    assert result['selected']==selected
    assert result['trend_undeterminable_count']==int(score is None)
    assert result['evidence_quality_counts'][quality]==1
    run,items=Repository(engine).get('v9-test')
    assert run['protocol_version']==TREND_EVIDENCE_VERSION
    assert json.loads(run['config_json'])['separate_trend_evidence'] is True
    parsed=json.loads(items[0]['assessment_json'])
    raw=json.loads(json.loads(items[0]['response_json'])['output'][-1]['content'][0]['text'])
    assert raw['direction_score']==score and raw['evidence_quality']==quality
    assert parsed['direction_score']==score and parsed['evidence_quality']==quality
    monkeypatch.setattr('service.llm_directional.config.load_filter_config',lambda *a:replace(
        CONFIG,separate_trend_evidence=False,allow_long=False))
    _,approved=runner.qualified_selection(engine,'v9-test',run['trade_date'],'default',
        now=NOW.replace(tzinfo=None)+timedelta(minutes=1))
    assert [r['symbol'] for r in approved]==selected
    assert report(engine,'v9-test')['candidates'][0]['trend_status']==parsed['trend_status']
    review=load_prediction_review(engine,trade_date=run['trade_date'],batch_id=run['batch_id'],
        symbol_source='universe-file:test.txt')
    assert review['separate_trend_evidence'] is True
    row=review['rows'][0]
    assert row['Score directionnel LLM (/10)']==score
    assert row['Qualité des preuves']=={'SUFFICIENT':'Suffisantes','PARTIAL':'Partielles','INSUFFICIENT':'Insuffisantes'}[quality]
    assert row['Avis LLM']==('INDÉTERMINABLE' if score is None else 'MIXTE / NEUTRE' if score==5 else 'HAUSSIÈRE')
    assert bool(row['Retenu par le filtre'])==bool(selected)
    frame=display_review_frame(review['rows'],'GPT','direction_1_10')
    assert 'Tendance GPT' in frame and 'Qualité des preuves' in frame
    pipeline,calls=fake_ui
    monkeypatch.setattr(pipeline,'_load_prediction_review_cached',lambda **kw:review)
    opts=pipeline.PipelineLaunchOptions(ml_predict_batch_id='oracle-test',llm_filter_enabled=True,llm_filter_run_id='v9-test')
    pipeline._render_ml_predict_review(opts)
    assert 'Tendance GPT' in calls['dataframe'][0]
    assert 'Qualité des preuves' in calls['dataframe'][0]
    assert any('Indéterminable' in c for c in calls['caption'])
    risk=risk_review_rows(review['rows'],[],[],status='NON LIÉ',selected_symbols=selected)
    assert len(risk)==len(selected)
    if risk:
        assert risk[0]['Qualité des preuves']=='Suffisantes'
        assert 'Tendance GPT' in display_review_frame(risk,'GPT','direction_1_10')
    else:
        assert not risk
    risk_view=dict(rows=risk,run_id=None,llm_run_id='v9-test',provider_label='GPT',scoring_mode='direction_1_10',
        separate_trend_evidence=True,trade_date=str(run['trade_date']),account_id='default',status='NON LIÉ')
    monkeypatch.setattr(pipeline,'_load_risk_prediction_review_cached',lambda **kw:risk_view)
    calls['dataframe'].clear()
    pipeline._render_risk_prediction_review(opts,[])
    assert len(calls['dataframe'])==int(bool(selected))
    if selected:
        assert 'Tendance GPT' in calls['dataframe'][0] and 'Qualité des preuves' in calls['dataframe'][0]


def test_indeterminate_table_score_is_empty_not_zero_or_five(engine):
    from ihm.components.prediction_review_table import table_payload
    context=ctx(engine,CONFIG)
    parsed=parse_response(answer(context,None,'INSUFFICIENT'),'ABC',CONFIG,NOW,context=context)
    rows=review_rows([context],[dict(symbol='ABC',status='VALID',selected=False,
        assessment_json=json.dumps(parsed))],run_status='COMPLETED',config=CONFIG.snapshot())
    payload=table_payload(display_review_frame(rows,'GPT','direction_1_10'))
    index=next(i for i,c in enumerate(payload['columns']) if c['label']=='Score GPT (/10)')
    assert payload['rows'][0]['cells'][index]['text']=='—'
    assert rows[0]['Avis LLM']=='INDÉTERMINABLE'


@pytest.mark.parametrize('score,quality',[(9,'SUFFICIENT'),(9,'PARTIAL'),(None,'INSUFFICIENT')])
def test_telegram_distinguishes_tendency_evidence_and_selection(engine,score,quality):
    from service.pipeline_telegram import llm_message
    context=ctx(engine,CONFIG)
    parsed=parse_response(answer(context,score,quality),'ABC',CONFIG,NOW,context=context)
    selected=['ABC'] if parsed['eligible'] else []
    run=dict(run_id='v9-test',trade_date='2026-10-16',account_id='default',status='COMPLETED',
        config_json=json.dumps(CONFIG.snapshot()),selected_json=json.dumps(selected))
    message=llm_message(run,[dict(symbol='ABC',status='VALID',assessment_json=json.dumps(parsed))])
    assert {'SUFFICIENT':'preuves suffisantes','PARTIAL':'preuves partielles','INSUFFICIENT':'preuves insuffisantes'}[quality] in message
    if score is None:
        assert 'INDÉTERMINABLE' in message and 'None/10' not in message and 'NEUTRE :' not in message
    if quality=='PARTIAL':
        assert '9/10' in message and 'Aucun titre publié' in message


def test_old_prompt_contracts_do_not_acquire_nullable_scores_or_quality_requirements():
    assert 'toward 5-6' in instructions('local_data_only',SCORE_VERSION)
    assert 'trend_status' not in instructions('web_search',SCORE_VERSION)
    assert 'UNDETERMINABLE' not in instructions('local_data_only',FRESH_VERSION)
