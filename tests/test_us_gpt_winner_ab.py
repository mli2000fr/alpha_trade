from decimal import Decimal
import json

import pytest

from scripts.research import us_gpt_winner_ab as module


def packet():
    return dict(key='packet-key',model=module.MODEL,symbol='ABC',signal_date='2025-01-02',
        request=dict(messages=[dict(role='system',content='Exact system\n'),dict(role='user',content='Exact dossier\n')]),
        context=dict(symbol='ABC',news=[dict(source_id='n',text='ABC announced lower guidance today.',primary_ticker_association=True)]))


def raw_reply():
    body=dict(symbol='ABC',assessment='UNFAVORABLE',evidence_quality='SUFFICIENT',reason='Guidance en baisse',
        facts=[dict(source_id='n',quote='ABC announced lower guidance',impact='BEARISH',issuer_is_subject=True)],counterarguments=[])
    return dict(id='response-test',model=module.MODEL,status='completed',service_tier='default',
        usage=dict(input_tokens=100,output_tokens=1000),output=[dict(type='message',
            content=[dict(type='output_text',text=json.dumps(body))])])


def test_cloud_request_copies_exact_instruction_and_dossier_and_enables_no_tools():
    p=packet();payload=module.payload_for(p)
    assert payload['instructions']==p['request']['messages'][0]['content']
    assert payload['input']==p['request']['messages'][1]['content']
    assert payload['tools']==[] and payload['tool_choice']=='none'
    assert payload['model']=='gpt-6-luna' and payload['service_tier']=='default'
    assert payload['max_output_tokens']==16384 and not payload['store']


def test_whole_cohort_budget_is_rejected_before_any_network_call():
    request=module.payload_for(packet())
    assert module.require_budget([request]*166)<Decimal('2')
    with pytest.raises(ValueError,match='budget'):
        module.require_budget([request]*300)


@pytest.mark.parametrize('change',[dict(model='another-model'),dict(service_tier='fast'),
    dict(output=[dict(type='web_search_call')])])
def test_model_tier_or_tool_drift_is_not_silently_accepted(change):
    raw=raw_reply();raw.update(change)
    with pytest.raises(ValueError):module.normalize(raw,module.payload_for(packet()))


def test_truncation_and_missing_usage_never_become_zero_cost_or_valid_output():
    raw=raw_reply();raw['status']='incomplete'
    assert module.normalize(raw,module.payload_for(packet()))['finish_reason']=='length'
    raw.pop('usage')
    with pytest.raises(ValueError,match='Consommation'):module.cost_for(raw,module.payload_for(packet()))


def test_cached_paid_response_is_reused_without_a_second_api_call(tmp_path,monkeypatch):
    p=packet();p['request']=module.payload_for(p)
    monkeypatch.setattr(module,'verify',lambda _: ({'maximum_reserved_usd':'1.9'},[p]))
    calls=[]
    def transport(request):calls.append(request);return raw_reply()
    first=module.analyze(tmp_path,transport=transport)
    second=module.analyze(tmp_path,transport=transport)
    assert len(calls)==1
    assert first['valid']==second['valid']==1 and first['vetoes']==second['vetoes']==1
    assert first['new_paid_calls']==1 and second['new_paid_calls']==0


def test_ambiguous_paid_attempt_is_journaled_and_never_automatically_repeated(tmp_path,monkeypatch):
    p=packet();p['request']=module.payload_for(p)
    monkeypatch.setattr(module,'verify',lambda _: ({'maximum_reserved_usd':'1.9'},[p]))
    calls=[]
    def unavailable(request):calls.append(request);raise TimeoutError('simulated transport failure')
    with pytest.raises(TimeoutError):module.analyze(tmp_path,transport=unavailable)
    with pytest.raises(ValueError,match='ambiguë'):module.analyze(tmp_path,transport=unavailable)
    assert len(calls)==1
    assert (tmp_path/'api/packet-key.request.json').exists()
    assert (tmp_path/'api/packet-key.error.json').exists()
