"""Three distinct events, coherent marginals, immutable legacy archives and UI."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from common.ia_prompts import load_prompt
from service.llm_directional.config import FilterConfig
from service.llm_directional.openai_client import build_request,SCHEMA
from service.llm_directional.prompts import PROBABILITY_BREAKDOWN_VERSION,response_schema
from service.llm_directional.validation import parse_response
from tests.test_llm_probability_v10 import engine,packet,answer,CONFIG,NOW
from tests.test_q051_human_selection import proposal


def context(engine,cfg=CONFIG):
    value=packet(engine,cfg)
    value.update(analysis_protocol=PROBABILITY_BREAKDOWN_VERSION,analysis_language='fr')
    return value


def response(value,**changes):
    raw=answer(value)
    parsed=json.loads(raw['output'][-1]['content'][0]['text'])
    parsed.update(probability_stop_touch=.25,probability_positive_exit=.8,
        stop_touch_explanation='Risque de parcours sur dix séances, gaps compris.',
        positive_exit_explanation='Hausse finale hypothétique même après une touche du stop.')
    parsed.update(changes)
    raw['output'][-1]['content'][0]['text']=json.dumps(parsed)
    return raw


def test_v11_prompt_and_both_provider_requests_are_unchanged():
    fixture=json.loads(Path('tests/fixtures/llm_probability_v11_prompt_hashes.json').read_text(encoding='utf-8'))
    sha=lambda s:hashlib.sha256(s.encode('utf-8')).hexdigest()
    for key,expected in fixture['prompts'].items():assert sha(load_prompt(key))==expected
    for provider,expected in fixture['requests'].items():
        cfg=FilterConfig(provider=provider,analysis_mode='web_search',scoring_mode='long_without_stop_probability',horizon=10)
        assert sha(json.dumps(build_request(fixture['context'],cfg),sort_keys=True,ensure_ascii=False))==expected


@pytest.mark.parametrize('provider',['openai','deepseek'])
@pytest.mark.parametrize('horizon',[10,15,20])
def test_both_providers_receive_three_precise_events_and_required_fields(engine,provider,horizon):
    cfg=replace(CONFIG,provider=provider,horizon=horizon)
    value=context(engine,cfg)
    value['horizon_sessions']=horizon
    value['long_without_stop_contract'].update(horizon_sessions=horizon,exit_session=horizon+1)
    request=build_request(value,cfg)
    prompt=request['instructions'] if provider=='openai' else request['analysis_instructions']
    schema=request['text']['format']['schema'] if provider=='openai' else response_schema(SCHEMA,PROBABILITY_BREAKDOWN_VERSION)
    if provider=='deepseek':assert json.dumps(schema,ensure_ascii=False) in prompt
    for name in ['probability_up_without_stop','probability_stop_touch','probability_positive_exit']:
        assert name in prompt and name in schema['required']
    assert 'Rédige en français' in prompt and 'MÊME SI le SL' in prompt
    assert "NE S'ADDITIONNENT PAS à 100 %" in prompt
    assert 'max(0, P(U)-P(S))' in prompt


@pytest.mark.parametrize('changes',[
    {},dict(probability_up_without_stop=.55),dict(probability_up_without_stop=.75),
    dict(probability_stop_touch=None),dict(probability_positive_exit=None),
    dict(probability_stop_touch=None,probability_positive_exit=None),
    dict(probability_up_without_stop=None,probability_status='UNDETERMINABLE')])
def test_coherent_probabilities_and_explicit_unknowns_survive_without_derivation(engine,changes):
    value=context(engine);raw=response(value,**changes)
    parsed=parse_response(raw,'ABC',CONFIG,NOW,context=value)
    for key in ['probability_up_without_stop','probability_stop_touch','probability_positive_exit']:
        assert parsed[key]==json.loads(raw['output'][-1]['content'][0]['text'])[key]
    assert parsed['eligible'] is (parsed['probability_up_without_stop'] is not None)


@pytest.mark.parametrize('changes',[
    dict(probability_stop_touch=-.1),dict(probability_stop_touch=1.1),
    dict(probability_positive_exit=True),dict(probability_positive_exit=float('nan')),
    dict(probability_up_without_stop=.1),dict(probability_positive_exit=.6),
    dict(probability_stop_touch=.5),dict(stop_touch_explanation=''),
    dict(positive_exit_explanation=' '),dict(horizon_sessions=20)])
def test_invalid_or_incoherent_probabilities_fail_closed(engine,changes):
    value=context(engine)
    with pytest.raises((ValueError,ValidationError)):
        parse_response(response(value,**changes),'ABC',CONFIG,NOW,context=value)


def test_missing_new_field_is_not_invented_and_partial_evidence_still_blocks(engine):
    value=context(engine)
    with pytest.raises(ValidationError):parse_response(answer(value),'ABC',CONFIG,NOW,context=value)
    result=parse_response(response(value,evidence_quality='PARTIAL'),'ABC',CONFIG,NOW,context=value)
    assert result['probability_stop_touch']==.25 and not result['eligible']


def test_deepseek_native_receipts_keep_all_three_probabilities(engine):
    cfg=replace(CONFIG,provider='deepseek');value=context(engine,cfg)
    parsed=json.loads(response(value)['output'][-1]['content'][0]['text'])
    raw=dict(provider='deepseek',web_provider='deepseek',analysis_protocol=PROBABILITY_BREAKDOWN_VERSION,
        analysis_mode='web_search',web_status='completed',status='completed',
        search_receipts=[{'response':{'results':[dict(url=s['url'],title=s['title'],date=s['published_at']) for s in parsed['sources']]}}],
        fetch_receipts=[],analysis_response={'choices':[dict(finish_reason='stop',message={'content':json.dumps(parsed)})]})
    result=parse_response(raw,'ABC',cfg,NOW,context=value)
    assert result['eligible'] and result['probability_up_without_stop']==.65
    assert result['probability_stop_touch']==.25 and result['probability_positive_exit']==.8


def test_sql_archive_roundtrip_keeps_three_probabilities_and_revalidates_without_call(engine,monkeypatch):
    from datetime import date
    from service.llm_directional import runner
    value=context(engine);calls=[]
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a,**k:None)
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW.replace(tzinfo=None))
    monkeypatch.setattr('service.llm_directional.repository.utcnow',lambda:NOW.replace(tzinfo=None))
    def client(request):calls.append(request);return response(value)
    result=runner.analyze(engine=engine,batch_id='oracle-test',trade_date='2026-10-16',
        symbol_source='q051-selection:triple-test',config=CONFIG,inputs=[value],client=client,
        run_id='llm-triple-probability-test')
    run,items=runner.qualified_selection(engine,result['run_id'],date(2026,10,16),'default',now=NOW.replace(tzinfo=None))
    data=json.loads(items[0]['assessment_json'])
    assert len(calls)==1 and run['protocol_version']==PROBABILITY_BREAKDOWN_VERSION
    assert data['probability_stop_touch']==.25 and data['probability_positive_exit']==.8


@pytest.mark.parametrize('legacy',[False,True])
def test_probability_table_shows_three_distinct_columns_and_no_invented_legacy_values(proposal,monkeypatch,legacy):
    from streamlit.testing.v1 import AppTest
    from ihm.components import probability_selection as ui
    folder,report,frame=proposal
    if not legacy:
        frame=frame.assign(llm_probability_stop_touch=[.3,.05,None],llm_probability_positive_exit=[.8,.95,None])
    monkeypatch.setattr(ui,'_test_proposal',(folder,report,frame),raising=False)
    app=AppTest.from_string('''
from ihm.components.probability_selection import render,_test_proposal
from ihm.components.prediction_review_table import _registered_table_component
_registered_table_component.clear()
render(*_test_proposal)
''').run(timeout=30)
    assert not app.exception
    payload=json.loads(app.get('bidi_component')[0].proto.json)
    columns={c['key']:i for i,c in enumerate(payload['columns'])}
    assert payload['columns'][0]['checkbox']
    assert [r['symbol'] for r in payload['rows']]==['B','A','C']
    for key in ['Probabilite','ToucheSL','HausseFinale']:assert key in columns
    top=payload['rows'][0]['cells']
    assert top[columns['ToucheSL']]['text']==('—' if legacy else '5.0 %')
    assert top[columns['HausseFinale']]['text']==('—' if legacy else '95.0 %')
    assert payload['selected_symbols']==[] and not (folder/'human_selection.json').exists()
