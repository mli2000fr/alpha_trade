"""Pure tests; never use real API credentials, MySQL or price outcomes."""
import json
import math

import pytest

from scripts.research import us_news_gpt_september_pilot as study


def packet():
    return dict(decision_date='2026-09-01',cutoff_utc='2026-09-01T20:00:00Z',symbol='TEST',
        oracle_rank=1,oracle_score=.99,future_return=99,
        issuer_reference={'company_name':'Test Company'},articles=[dict(article_id='test:1',
            headline='Test Company announces a primary equity offering',summary='',
            body='Test Company is issuing new shares to raise capital.',publication_utc='2026-09-01T12:00:00Z')])


def answer(**changes):
    result=dict(decision='BEARISH',confidence=.8,issuer_match='MATCH',basis='MATERIAL_FACT',
        reason='New primary issuance.',evidence=[dict(article_id='test:1',kind='FINANCING',
            quote='issuing new shares to raise capital')])
    result.update(changes)
    return dict(status='completed',output=[dict(type='message',content=[
        dict(type='output_text',text=json.dumps(result))])])


def test_allowlist_never_sends_scores_or_future_values():
    request=study.build_request(packet(),'gpt-6-luna')
    data=json.loads(request['input'])
    assert set(data)=={'decision_date','cutoff_utc','symbol','issuer_reference','articles'}
    assert request['tools']==[] and request['store'] is False
    assert 'future_return' not in request['input'] and 'oracle_score' not in request['input']


def test_no_web_no_tools_no_execution_no_schema_extras():
    request=study.build_request(packet(),'gpt-6-luna')
    assert request['reasoning']=={'effort':'none'}
    assert request['max_output_tokens']==1800
    assert request['text']['format']['strict'] is True
    assert study.schema()['additionalProperties'] is False


def test_material_bearish_exact_evidence_is_veto():
    value=study.parse_assessment(answer(),packet())
    assert value['veto_long'] is True


@pytest.mark.parametrize('confidence',[.74,0.])
def test_low_confidence_not_veto(confidence):
    assert not study.parse_assessment(answer(confidence=confidence),packet())['veto_long']


@pytest.mark.parametrize('decision',['BULLISH','ABSTAIN'])
def test_positive_or_abstain_not_short(decision):
    assert not study.parse_assessment(answer(decision=decision),packet())['veto_long']


def test_abstain_with_no_fact_valid_not_technical_error():
    value=study.parse_assessment(answer(decision='ABSTAIN',issuer_match='UNCERTAIN',
        basis='INSUFFICIENT',evidence=[]),packet())
    assert value['decision']=='ABSTAIN' and not value['veto_long']


@pytest.mark.parametrize('change',[
    {'evidence':[dict(article_id='invented',quote='issuing new shares to raise capital',kind='FINANCING')]},
    {'evidence':[dict(article_id='test:1',quote='invented future share price',kind='FINANCING')]},
    {'evidence':[]},{'issuer_match':'MISMATCH'},{'issuer_match':'UNCERTAIN'},
    {'basis':'OPINION_OR_OLD'},{'confidence':True},{'confidence':math.nan},
    {'decision':'SELL_NOW'},{'confidence':1.01}])
def test_unqualified_answer_rejected(change):
    with pytest.raises(ValueError):
        study.parse_assessment(answer(**change),packet())


def test_incomplete_response_never_retry_or_decision():
    value=answer();value['status']='incomplete'
    with pytest.raises(ValueError,match='no automatic retry'):
        study.parse_assessment(value,packet())


def test_html_clean_and_scripts_untrusted_not_executed():
    assert study.clean('<p>Hello &amp; world.</p><script>evil()</script>')=='Hello & world.'


def test_budget_is_bounded_by_payload_utf8_and_output_limit():
    payload=study.build_request(packet(),'gpt-6-luna')
    size,cost=study.token_cost_bound(payload)
    assert size>=len(payload['input'].encode('utf-8'))
    assert 8*cost<study.BUDGET_USD
    assert 8*study.MAX_OUTPUT_TOKENS==14400


def test_frozen_sessions_use_trading_days_not_holiday():
    assert study.SESSIONS==('2026-09-01','2026-09-02','2026-09-03','2026-09-04','2026-09-08')


def prepared_root(tmp_path):
    study.atomic_json(tmp_path/'protocol.json',{'sources':{},'gpt_model':'gpt-6-luna'})
    study.atomic_json(tmp_path/'packets.json',[packet()])
    study.atomic_json(tmp_path/'prepare.json',{'files':{n:study.digest(tmp_path/n)
        for n in ['protocol.json','packets.json']}})
    return tmp_path


def test_paid_answer_saved_then_reused_no_second_charge(tmp_path):
    root=prepared_root(tmp_path);calls=[]
    def fake(request):
        calls.append(request)
        return dict(answer(),id='fake',model='gpt-6-luna',usage={'input_tokens':100,'output_tokens':100})
    first=study.analyze(root,transport=fake)
    assert first['actual_calls']==1 and first['vetoed']==1
    assert first['estimated_cost_usd']==pytest.approx(.00006)
    again=study.analyze(root,transport=fake)
    assert len(calls)==1 and again==first
    assert len(list((root/'api').glob('*.response.json')))==1


def test_unresolved_paid_attempt_never_retried(tmp_path):
    root=prepared_root(tmp_path)
    def timeout(request):
        raise TimeoutError('synthetic')
    with pytest.raises(TimeoutError):
        study.analyze(root,transport=timeout)
    with pytest.raises(ValueError,match='Unresolved previous paid attempt'):
        study.analyze(root,transport=lambda request:pytest.fail('No automatic retry allowed'))


def test_invalid_quote_keeps_paid_response_but_publishes_no_analysis(tmp_path):
    root=prepared_root(tmp_path)
    def fake(request):
        return dict(answer(evidence=[dict(article_id='test:1',quote='invented future share price',kind='FINANCING')]),
            usage={'input_tokens':100,'output_tokens':100})
    with pytest.raises(ValueError,match='Quote not present'):
        study.analyze(root,transport=fake)
    assert len(list((root/'api').glob('*.response.json')))==1
    assert not (root/'analysis.json').exists()


def test_no_article_unknown_is_not_neutral_and_has_no_api_call(tmp_path):
    root=prepared_root(tmp_path);empty=packet();empty['articles']=[]
    study.atomic_json(root/'packets.json',[empty])
    study.atomic_json(root/'prepare.json',{'files':{n:study.digest(root/n)
        for n in ['protocol.json','packets.json']}})
    result=study.analyze(root,transport=lambda request:pytest.fail('No API for absent news'))
    assert result['actual_calls']==0 and result['decisions']=={'UNKNOWN_NO_QUALIFIED_TEXT':1}
