"""French short-horizon instructions; preserve the live v10 approval contract."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from common.ia_prompts import load_prompt
from service.llm_directional.config import FilterConfig
from service.llm_directional.openai_client import build_request
from service.llm_directional.prompts import PROBABILITY_FR_VERSION,probability_protocol
from service.llm_directional.validation import parse_response
from tests.test_llm_probability_v10 import engine,packet,answer,CONFIG,NOW

FIXTURE=json.loads((Path(__file__).parent/'fixtures/llm_probability_v10_prompt_hashes.json').read_text(encoding='utf-8'))
sha=lambda value:hashlib.sha256(value.encode('utf-8')).hexdigest()


def test_v10_files_and_provider_requests_remain_identical_for_pending_selection():
    for key,checksum in FIXTURE['prompts'].items():
        assert sha(load_prompt(key,runtime='cloud'))==checksum
    for provider,checksum in FIXTURE['requests'].items():
        config=FilterConfig(provider=provider,analysis_mode='web_search',scoring_mode='long_without_stop_probability',horizon=10)
        request=build_request(FIXTURE['context'],config)
        assert sha(json.dumps(request,sort_keys=True,ensure_ascii=False))==checksum
        assert probability_protocol(FIXTURE['context']['analysis_protocol'])


@pytest.mark.parametrize('provider',['openai','deepseek'])
@pytest.mark.parametrize('horizon',[10,15,20])
def test_new_requests_ask_french_short_term_and_exact_model_horizon(engine,provider,horizon):
    config=replace(CONFIG,provider=provider,horizon=horizon)
    context=packet(engine,config)
    context.update(analysis_protocol=PROBABILITY_FR_VERSION,analysis_language='fr',horizon_sessions=horizon)
    context['long_without_stop_contract']['horizon_sessions']=horizon
    context['long_without_stop_contract']['exit_session']=horizon+1
    request=build_request(context,config)
    prompt=request['instructions'] if provider=='openai' else request['analysis_instructions']
    assert 'Rédige en français' in prompt and 'dix SÉANCES BOURSIÈRES' in prompt
    assert 'objectifs de cours' in prompt and 'douze mois' in prompt
    assert '8 à 800 caractères' in prompt and 'langue originale' in prompt
    payload=json.loads(request['input']) if provider=='openai' else request['context']
    assert payload['horizon_sessions']==horizon and payload['analysis_language']=='fr'
    assert payload['long_without_stop_contract']['exit_session']==horizon+1


def test_new_french_protocol_retains_event_validation_and_evidence_gate(engine):
    context=packet(engine)
    context.update(analysis_protocol=PROBABILITY_FR_VERSION,analysis_language='fr')
    raw=answer(context,probability_explanation='Sortie positive sans toucher le stop sur dix séances.',
               evidence_explanation='Sources datées, mais prévision non calibrée.')
    result=parse_response(raw,'ABC',CONFIG,NOW,context=context)
    assert result['probability_up_without_stop']==.65 and result['eligible']
    with pytest.raises(ValueError,match='Horizon'):
        parse_response(answer(context,horizon_sessions=20),'ABC',CONFIG,NOW,context=context)
    partial=parse_response(answer(context,evidence_quality='PARTIAL'),'ABC',CONFIG,NOW,context=context)
    assert not partial['eligible']


def test_french_request_can_be_archived_and_revalidated_without_another_provider_call(engine,monkeypatch):
    from service.llm_directional import runner
    from datetime import date
    context=packet(engine)
    context.update(analysis_protocol=PROBABILITY_FR_VERSION,analysis_language='fr')
    monkeypatch.setattr(runner,'validate_analysis_window',lambda *a,**k:None)
    monkeypatch.setattr(runner,'assert_paper_account',lambda *a:None)
    monkeypatch.setattr(runner,'utcnow',lambda:NOW.replace(tzinfo=None))
    monkeypatch.setattr('service.llm_directional.repository.utcnow',lambda:NOW.replace(tzinfo=None))
    calls=[]
    def client(request):
        calls.append(request)
        return answer(context,probability_explanation='Événement de court terme sur dix séances.',
            evidence_explanation='Sources qualifiées dans ce test hors réseau.')
    result=runner.analyze(engine=engine,batch_id='oracle-test',trade_date='2026-10-16',
        symbol_source='q051-selection:fr-test',config=CONFIG,inputs=[context],client=client,
        run_id='llm-fr-probability-test')
    run,items=runner.qualified_selection(engine,result['run_id'],date(2026,10,16),'default',now=NOW.replace(tzinfo=None))
    assert len(calls)==1 and run['protocol_version']==PROBABILITY_FR_VERSION
    assert [i['symbol'] for i in items]==['ABC']
