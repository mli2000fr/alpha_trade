"""Paid-pilot budget/journal tests: fake transport only, never SQL/API calls."""
from decimal import Decimal
import json

import pytest

from scripts.research import us_news_gpt_q1_2025_run as study


def packet():
    return dict(decision_date='2025-01-02',cutoff_utc='2025-01-02T21:00:00Z',symbol='TEST',oracle_rank=1,
        issuer_reference={'company_name':'Test'},articles=[dict(article_id='a',headline='New shares are being issued',
            summary='',body='The company issues new shares for cash.')])


def plan_item(p):
    return dict(packet=0,symbol=p['symbol'],decision_date=p['decision_date'],planned_call=True,
        payload_sha256=study.payload_hash(study.pilot.build_request(p,'gpt-6-luna')))


def response():
    value=dict(decision='BEARISH',confidence=.8,issuer_match='MATCH',basis='MATERIAL_FACT',
        reason='Cash financing.',evidence=[dict(article_id='a',kind='FINANCING',quote='issues new shares for cash')])
    return dict(id='fake',status='completed',model='gpt-6-luna',service_tier='default',
        usage={'input_tokens':100,'output_tokens':100},output=[dict(type='message',content=[
            dict(type='output_text',text=json.dumps(value))])])


def test_standard_tier_enforced_and_body_prompt_unchanged():
    p=packet();original=study.pilot.build_request(p,'gpt-6-luna');actual=study.paid_payload(p,'gpt-6-luna')
    assert actual.pop('service_tier')=='default'
    assert actual==original


def test_budget_inventory_before_any_call():
    p=packet();rows,total=study.request_inventory([p],[plan_item(p)],'gpt-6-luna')
    assert len(rows)==1 and Decimal(0)<total<Decimal('.50')
    assert rows[0]['prepared_request_sha256']!=rows[0]['request_sha256']


def test_changed_prepared_text_rejected():
    p=packet();plan=plan_item(p);p['articles'][0]['body']='Changed'
    with pytest.raises(ValueError,match='Prepared input changed'):
        study.request_inventory([p],[plan],'gpt-6-luna')


def test_over_budget_rejected_without_network(monkeypatch):
    p=packet();monkeypatch.setattr(study.pilot,'token_cost_bound',lambda payload:(100,.51))
    with pytest.raises(ValueError,match='exceeds'):
        study.request_inventory([p],[plan_item(p)],'gpt-6-luna')


@pytest.mark.parametrize('change',[
    {'service_tier':'priority'}, {'model':'another-model'}, {'usage':{}},
    {'usage':{'input_tokens':True,'output_tokens':100}},
    {'usage':{'input_tokens':100,'output_tokens':1801}},
    {'output':[{'type':'web_search_call'}]},
])
def test_wrong_tier_usage_tools_or_model_stop(change):
    value=response();value.update(change)
    with pytest.raises(ValueError):study.validate_usage(value,.01)


def test_usage_cost_is_accounted_conservatively():
    actual=study.validate_usage(response(),.01)
    assert actual['gross_cost_estimate_usd']==pytest.approx(.00006)


def fake_authorization(p):
    rows,total=study.request_inventory([p],[plan_item(p)],'gpt-6-luna')
    return dict(model='gpt-6-luna',request_inventory=rows,budget_usd=.5)


def setup_run(tmp_path,monkeypatch):
    p=packet()
    study.atomic_json(tmp_path/'packets.json',[p])
    study.atomic_json(tmp_path/'analysis-protocol.json',fake_authorization(p))
    monkeypatch.setattr(study,'freeze_authorization',lambda root,**kwargs:fake_authorization(p))
    return p


def test_cached_paid_response_not_charged_twice(tmp_path,monkeypatch):
    setup_run(tmp_path,monkeypatch);calls=[]
    def fake(payload):calls.append(payload);return response()
    first=study.run(tmp_path,budget_usd=.5,transport=fake)
    second=study.run(tmp_path,budget_usd=.5,transport=fake)
    assert len(calls)==1 and first==second and first['vetoed']==1


def test_timeout_has_journal_and_no_automatic_second_attempt(tmp_path,monkeypatch):
    setup_run(tmp_path,monkeypatch)
    def fail(payload):raise TimeoutError('fake')
    with pytest.raises(TimeoutError):study.run(tmp_path,budget_usd=.5,transport=fail)
    with pytest.raises(ValueError,match='Unresolved paid attempt'):
        study.run(tmp_path,budget_usd=.5,transport=lambda payload:pytest.fail('Must not pay again'))


def test_invalid_paid_quote_preserved_and_never_requeried(tmp_path,monkeypatch):
    setup_run(tmp_path,monkeypatch);calls=[]
    def fake(payload):
        calls.append(payload);value=response();parsed=json.loads(value['output'][0]['content'][0]['text'])
        parsed['evidence'][0]['quote']='Invented quote in no supplied article'
        value['output'][0]['content'][0]['text']=json.dumps(parsed);return value
    for _ in range(2):
        with pytest.raises(ValueError,match='Paid answer invalid'):
            study.run(tmp_path,budget_usd=.5,transport=fake)
    assert len(calls)==1
    assert len(list((tmp_path/'api').glob('*.response.json')))==1
    assert not (tmp_path/'analysis.json').exists()
