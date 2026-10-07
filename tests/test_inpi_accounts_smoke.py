import pytest
from service.inpi.client import InpiClient, InpiError, NoRedirect
from service.inpi.accounts_smoke import summary, run


def document():
    return {'siren':'438479941','confidentiality':'Public','deleted':False,
            'bilanSaisi':{'bilan':{'identite':{'siren':'438479941','codeTypeBilan':'K'},
            'detail':{'pages':[{'liasses':[{'code':'AA','m1':'123','m2':'0'}]}]}}}}


def test_public_summary_counts_and_hash():
    result=summary(document(),'438479941')
    assert result['nonempty_value_count']==2
    assert result['identity']['codeTypeBilan']=='K'
    assert len(result['source_payload_sha256'])==64


@pytest.mark.parametrize('change',[{'deleted':True},{'confidentiality':'Confidential'}, {'siren':'123456789'}])
def test_reject_unusable_document(change):
    payload=document(); payload.update(change)
    with pytest.raises(InpiError): summary(payload,'438479941')


def test_client_rejects_wrong_scope_and_malformed_rows():
    client=InpiClient()
    client._request=lambda *a,**k: ([None],None)
    with pytest.raises(InpiError): client.accounts('438479941')
    with pytest.raises(InpiError): client.account('../secret')
    with pytest.raises(InpiError): InpiClient()._request('https://other.test')
    with pytest.raises(InpiError): NoRedirect().redirect_request(None,None,302,'',{},'https://other.test')


def test_run_closes_client_and_does_not_expose_token():
    class Fake:
        calls=6
        closed=False
        def login(self): self.token='dummy-secret'
        def accounts(self,*a,kind=None): return ([{'id':'id','confidentiality':'Public'}], 'cursor')
        def account(self,*a): return document()
        def close(self): self.closed=True
    fake=Fake(); report=run(fake)
    assert fake.closed and report['status']=='ACCESS_VERIFIED'
    assert report['available_at']>=report['observed_at']
    assert 'dummy-secret' not in str(report)
    with pytest.raises(InpiError): run(fake,siren='123456789')


def test_login_profile_not_returned(monkeypatch):
    monkeypatch.setenv('INPI_USERNAME','dummy-user')
    monkeypatch.setenv('INPI_PASSWORD','dummy-password')
    client=InpiClient()
    client._request=lambda *a,**kw: ({'token':'dummy-token','profile':'private'},None)
    assert client.login() is None
    client.close(); assert client._token is None
