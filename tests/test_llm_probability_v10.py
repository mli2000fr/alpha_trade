"""Probability event/schema/Web provenance and archived validation, offline."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest
from jsonschema import ValidationError

from service.llm_directional import runner
from service.llm_directional.prompts import PROBABILITY_VERSION,instructions,response_schema
from service.llm_directional.openai_client import SCHEMA,build_request
from service.llm_directional.validation import parse_response
from tests.test_llm_fresh_evidence import engine,ctx,CFG,NOW,response

CONFIG=replace(CFG,analysis_mode='web_search',scoring_mode='long_without_stop_probability',
               separate_trend_evidence=False,allow_short=False,min_confidence=0.,horizon=10)


def packet(engine,cfg=CONFIG):
    value=ctx(engine,cfg)
    value.update(analysis_protocol=PROBABILITY_VERSION,horizon_sessions=10,
                 long_without_stop_contract={'horizon_sessions':10,'stop_loss_pct':.05})
    return value


def answer(context,p=.65,**changes):
    raw=response(context,web=True)
    result=json.loads(raw['output'][-1]['content'][0]['text']);result.pop('decision')
    result.update(probability_up_without_stop=p,probability_status='ESTIMATED' if p is not None else 'UNDETERMINABLE',
                  horizon_sessions=10,stop_loss_pct=.05,evidence_quality='SUFFICIENT',
                  evidence_explanation='Dated Web releases and supplied local evidence.',
                  probability_explanation='Joint positive exit and untouched stop, with uncertainty.',
                  risk_factors=['Gap risk'])
    result.update(changes)
    raw['output'][-1]['content'][0]['text']=json.dumps(result)
    return raw


@pytest.mark.parametrize('probability',[0.,.1,.65,1.,None])
def test_probability_is_not_an_ordinal_trend_score(engine,probability):
    context=packet(engine)
    value=parse_response(answer(context,probability),'ABC',CONFIG,NOW,context=context)
    assert value['probability_up_without_stop']==probability
    assert value['eligible'] is (probability is not None)
    assert value['probability_is_calibrated'] is False
    assert 'direction_score' not in value


@pytest.mark.parametrize('changes',[dict(horizon_sessions=20),dict(stop_loss_pct=.07),
    dict(probability_up_without_stop=1.1),dict(probability_up_without_stop=True),
    dict(probability_status='UNDETERMINABLE'),dict(probability_up_without_stop=float('nan'))])
def test_invalid_or_different_event_is_rejected(engine,changes):
    context=packet(engine)
    with pytest.raises((ValueError,ValidationError)):
        parse_response(answer(context,**changes),'ABC',CONFIG,NOW,context=context)


def test_search_is_mandatory_and_missing_consensus_is_in_prompt(engine):
    context=packet(engine);request=build_request(context,CONFIG)
    assert request['tools'][0]['type']=='web_search' and request['tool_choice']=='required'
    assert 'consensus' in request['instructions'] and 'actively search' in request['instructions']
    assert 'actual entry fill' in request['instructions']
    assert 'direction_score' not in request['text']['format']['schema']['properties']
    raw=answer(context);raw['output']=raw['output'][1:]
    with pytest.raises(ValueError,match='recherche Web'):
        parse_response(raw,'ABC',CONFIG,NOW,context=context)


def test_partial_or_untraceable_evidence_cannot_authorize_human_choice(engine):
    context=packet(engine)
    value=parse_response(answer(context,evidence_quality='PARTIAL'),'ABC',CONFIG,NOW,context=context)
    assert not value['eligible']
    raw=answer(context)
    raw['output'][0]['action']['sources']=[]
    value=parse_response(raw,'ABC',CONFIG,NOW,context=context)
    assert not value['eligible'] and value['evidence_quality']!='SUFFICIENT'


def test_deepseek_uses_its_native_web_search_and_same_probability_schema(engine):
    cfg=replace(CONFIG,provider='deepseek');context=packet(engine,cfg)
    request=build_request(context,cfg)
    assert request['web_provider']=='deepseek' and 'web_request' not in request
    assert any('consensus' in q['query'] for q in request['search_requests'])
    value=json.loads(answer(context)['output'][-1]['content'][0]['text'])
    raw=dict(provider='deepseek',web_provider='deepseek',analysis_protocol=PROBABILITY_VERSION,
             analysis_mode='web_search',web_status='completed',status='completed',
             search_receipts=[{'response':{'results':[dict(url=s['url'],title=s['title'],date=s['published_at']) for s in value['sources']]}}],
             fetch_receipts=[],analysis_response={'choices':[dict(finish_reason='stop',message={'content':json.dumps(value)})]})
    parsed=parse_response(raw,'ABC',cfg,NOW,context=context)
    assert parsed['probability_up_without_stop']==.65 and parsed['eligible']


def test_probability_request_and_response_can_be_revalidated_from_sql(engine,monkeypatch):
    context=packet(engine)
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a,**k:None)
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW.replace(tzinfo=None))
    monkeypatch.setattr('service.llm_directional.repository.utcnow',lambda:NOW.replace(tzinfo=None))
    result=runner.analyze(engine=engine,batch_id='oracle-test',trade_date='2026-10-16',
        symbol_source='q051-selection:test',config=CONFIG,run_id='llm-probability-test',
        inputs=[context],client=lambda request:answer(context))
    run,items=runner.qualified_selection(engine,result['run_id'],__import__('datetime').date(2026,10,16),
                                        'default',now=NOW.replace(tzinfo=None))
    assert run['protocol_version']==PROBABILITY_VERSION and [i['symbol'] for i in items]==['ABC']
