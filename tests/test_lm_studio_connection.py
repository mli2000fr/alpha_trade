import json

import pytest
import requests

from service.local_ai.lm_studio import Client,Connection,IncompleteResponse,connectivity_test,load_connection


class Session:
    def __init__(self,responses):self.responses=iter(responses);self.calls=[];self.closed=False
    def request(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs));response=next(self.responses)
        if isinstance(response,Exception):raise response
        return type('Response',(),dict(status_code=response[0],json=lambda self:response[1]))()
    def close(self):self.closed=True


def test_configured_model_is_the_user_local_model():
    cfg=load_connection()
    assert cfg.model=='qwen3.5-9b' and cfg.base_url=='http://127.0.0.1:1234/v1'


@pytest.mark.parametrize('url',['https://api.openai.com/v1','http://192.168.1.9:1234/v1',
    'http://user:secret@localhost:1234/v1','http://localhost:1234/v1?x=1',
    'http://localhost:1234/anything','http://localhost/v1'])
def test_connector_never_targets_a_cloud_or_non_loopback_server(url):
    with pytest.raises(ValueError):Connection(base_url=url)


def test_real_client_protocol_uses_only_loopback_and_no_cloud_auth(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','must-not-be-forwarded')
    monkeypatch.delenv('LM_STUDIO_API_KEY',raising=False)
    session=Session([(200,dict(data=[dict(id='qwen3.5-9b')])),(200,dict(model='qwen3.5-9b',
        choices=[dict(message=dict(content='LM_STUDIO_OK'),finish_reason='stop')],usage=dict(total_tokens=10)))])
    client=Client(Connection(),session=session)
    result=connectivity_test(client)
    assert result['status']=='CONNECTED_AND_EXACT_RESPONSE' and result['cloud_calls']==0
    assert not session.trust_env
    assert [call[:2] for call in session.calls]==[
        ('GET','http://127.0.0.1:1234/v1/models'),('POST','http://127.0.0.1:1234/v1/chat/completions')]
    assert all(not call[2]['headers'] and call[2]['allow_redirects'] is False for call in session.calls)
    assert session.calls[1][2]['json']['model']=='qwen3.5-9b'
    assert session.calls[1][2]['json']['stream'] is False


def test_missing_model_is_not_replaced_by_another_loaded_model():
    session=Session([(200,dict(data=[dict(id='another-model')]))])
    with pytest.raises(RuntimeError,match='aucun remplacement'):connectivity_test(Client(Connection(),session=session))
    assert len(session.calls)==1


@pytest.mark.parametrize('reply',[(401,{}),(302,{}),requests.Timeout('local timeout')])
def test_failure_has_no_retry_redirect_or_cloud_fallback(reply):
    session=Session([reply])
    with pytest.raises(RuntimeError):Client(Connection(),session=session).models()
    assert len(session.calls)==1


def test_reasoning_without_final_text_is_not_a_successful_answer():
    session=Session([(200,dict(choices=[dict(message=dict(content='',reasoning_content='still thinking'),finish_reason='length')]))])
    with pytest.raises(IncompleteResponse,match='sans texte final') as caught:
        Client(Connection(),session=session).chat([dict(role='user',content='test')])
    assert caught.value.result['finish_reason']=='length'
    assert caught.value.result['response']['choices'][0]['message']['reasoning_content']=='still thinking'


def test_explicit_structured_format_is_forwarded_without_changing_default_calls():
    schema=dict(type='json_schema',json_schema=dict(name='test',schema=dict(type='object')))
    session=Session([(200,dict(choices=[dict(message=dict(content='{}'),finish_reason='stop')]))])
    value=Client(Connection(),session=session).chat([dict(role='user',content='test')],response_format=schema)
    assert value['request']['response_format']==schema
    assert session.calls[0][2]['json']['response_format']==schema


def test_unexpected_answer_is_distinct_from_successful_exact_response():
    session=Session([(200,dict(data=[dict(id='qwen3.5-9b')])),
        (200,dict(choices=[dict(message=dict(content='Bonjour'),finish_reason='stop')]))])
    assert connectivity_test(Client(Connection(),session=session))['status']=='CONNECTED_RESPONSE_DIFFERS'
