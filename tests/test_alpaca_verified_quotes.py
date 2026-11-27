from unittest.mock import Mock
import pytest
from service.alpaca import clientAlpaca as client


@pytest.mark.parametrize('supplied',[False,True])
def test_latest_quotes_uses_verified_tls_session_or_explicit_session(monkeypatch,supplied):
    http=Mock();factory=Mock(return_value=http)
    monkeypatch.setattr('common.verified_http.verified_session',factory)
    monkeypatch.setattr(client,'_build_headers',lambda account:{})
    request=Mock(return_value=Mock(json=lambda:dict(quotes={'AGX':dict(bp=100.,ap=101.)})))
    monkeypatch.setattr(client,'request_with_retry',request)
    result=client.fetch_latest_quotes(['AGX'],account_id='test1',session=http if supplied else None)
    assert result['AGX']['bp']==100. and request.call_args.args[0] is http
    assert request.call_args.kwargs['params']['feed']=='sip'
    assert factory.call_count==(0 if supplied else 1)
    assert http.close.call_count==(0 if supplied else 1)
