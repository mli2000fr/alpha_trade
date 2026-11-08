"""Bounded collector transport: real status, no secrets or false successful run."""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
import requests

from service.forward_pit import batch
from service.forward_pit.outcomes import BatchRunError


def response(status,body=b'{"ok":true}',headers=None):
    r=requests.Response();r.status_code=status;r._content=body;r._content_consumed=True
    r.url='https://data.alpaca.markets/v2/stocks/bars';r.headers.update(headers or {})
    return r


@pytest.fixture
def http(monkeypatch):
    pauses=[]
    monkeypatch.setattr('service._http_retry.time.sleep',pauses.append)
    monkeypatch.setattr('service._http_retry.random.random',lambda:.5)
    session=MagicMock(spec=requests.Session)
    return session,pauses


@pytest.mark.parametrize('code',[429,500,502,503,504])
def test_exhausted_transient_status_is_preserved_and_retries_are_bounded(http,caplog,code):
    session,pauses=http;session.request.side_effect=[response(code) for _ in range(4)]
    with pytest.raises(RuntimeError,match=str(code)) as caught:
        batch._request_json(session,'https://data.alpaca.markets/v2/stocks/bars',params={})
    assert 'erreur inconnue' not in str(caught.value)
    assert session.request.call_count==4 and len(pauses)==3
    assert str(code) in caplog.text


def test_rate_limit_honors_retry_after_and_returns_only_a_successful_response(http):
    session,pauses=http
    session.request.side_effect=[response(429,headers={'Retry-After':'7'}),response(200)]
    assert batch._request_json(session,'https://provider.example/data',params={})==({'ok':True},200)
    assert session.request.call_count==2 and pauses==[7.]


@pytest.mark.parametrize('code',[400,401,403,404,422])
def test_permanent_refusal_is_not_retried_or_returned_as_empty_success(http,code):
    session,pauses=http;session.request.return_value=response(code)
    with pytest.raises(RuntimeError,match=str(code)):
        batch._request_json(session,'https://provider.example/data',params={})
    assert session.request.call_count==1 and not pauses


def test_network_failure_keeps_its_cause_without_exposing_url_tokens(http,caplog):
    session,pauses=http
    session.request.side_effect=requests.ReadTimeout('read timeout https://provider.example?api_token=TOPSECRET')
    with pytest.raises(RuntimeError,match='ReadTimeout') as caught:
        batch._request_json(session,'https://provider.example?key=TOPSECRET',params={})
    assert session.request.call_count==4 and len(pauses)==3
    assert 'TOPSECRET' not in str(caught.value)+caplog.text
    assert caught.value.__suppress_context__


def test_invalid_json_is_a_clear_failure_not_an_empty_payload(http):
    session,_=http;session.request.return_value=response(200,b'not JSON')
    with pytest.raises(RuntimeError,match='HTTP 200, réponse JSON invalide'):
        batch._request_json(session,'https://provider.example',params={})
    assert session.request.call_count==1


@pytest.mark.parametrize('code',[403,404])
def test_optional_text_absence_still_returns_its_explicit_status(http,code):
    session,pauses=http;session.request.return_value=response(code)
    assert batch._request_text_optional(session,'https://provider.example')==(None,code)
    assert session.request.call_count==1 and not pauses


def test_optional_text_transient_failure_keeps_last_code(http):
    session,pauses=http;session.request.side_effect=[response(503) for _ in range(4)]
    with pytest.raises(RuntimeError,match='503'):
        batch._request_text_optional(session,'https://provider.example')
    assert session.request.call_count==4 and len(pauses)==3


def test_failed_reference_phase_preserves_diagnostics_and_does_not_start_options(http,monkeypatch):
    session,_=http;session.__enter__.return_value=session
    session.request.side_effect=[response(503) for _ in range(4)]
    monkeypatch.setattr(batch.requests,'Session',lambda:session)
    monkeypatch.setattr(batch,'_collection_symbols',lambda cfg:['AAA','BBB'])
    monkeypatch.setattr(batch,'get_alpaca_credentials',lambda:('fixture','fixture'))
    monkeypatch.setattr(batch,'_configure_alpaca_session',lambda *a,**kw:None)
    options=MagicMock();monkeypatch.setattr(batch,'_paginated_json',options)
    class Engine:
        @contextmanager
        def begin(self):yield MagicMock()
    with pytest.raises(BatchRunError,match='503') as caught:
        batch.options_snapshot(Engine(),{'request_interval_seconds':0},'fixture',True)
    details=caught.value.outcome.details
    assert details['phase']=='UNDERLYING_SIP_REFERENCES'
    assert details['reference_symbols_processed']==0 and details['reference_symbols_pending']==2
    assert details['reference_chunk_failed_symbols']==2
    assert caught.value.outcome.persisted==0
    options.assert_not_called()
