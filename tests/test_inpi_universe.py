from datetime import UTC, datetime
import json

import pytest

from service.inpi import universe_mapping as mapping
from service.inpi import universe_collection as collector
from service.inpi.client import InpiClient


def gleif():
    return {'meta':{'pagination':{'total':1}},'data':[{'attributes':{'lei':'969500QZC2Q0TK11NV07',
        'entity':{'legalName':{'name':'ACCOR'},'otherNames':[],'jurisdiction':'FR','category':'GENERAL',
                  'status':'ACTIVE','registeredAt':{'id':'RA000189'},'registeredAs':'602036444'},
        'registration':{'status':'ISSUED','corroborationLevel':'FULLY_CORROBORATED',
                        'validatedAt':{'id':'RA000189'},'validatedAs':'602036444'}}}]}


def test_strict_mapping_and_registry_checksum():
    result,reason=mapping.evaluate(gleif(),'FR0000120404')
    assert reason is None and result['siren']=='602036444'
    assert mapping.valid_siren('602036444') and not mapping.valid_siren('602036445')


@pytest.mark.parametrize('change,reason',[
    ({'jurisdiction':'NL'},'NON_FR_LEGAL_ENTITY'),
    ({'category':'BRANCH'},'NON_GENERAL_ENTITY_OR_BRANCH'),
    ({'registeredAt':{'id':'OTHER'}},'UNQUALIFIED_FR_REGISTRY'),
    ({'registeredAs':'602036445'},'INVALID_SIREN_CHECKSUM')])
def test_exclusions_not_fuzzy_name_matches(change,reason):
    payload=gleif(); payload['data'][0]['attributes']['entity'].update(change)
    assert mapping.evaluate(payload,'FR0000120404')[1]==reason


def test_ambiguity_and_reverse_relation_required():
    payload=gleif(); payload['data']*=2; payload['meta']['pagination']['total']=2
    assert mapping.evaluate(payload,'FR0000120404')[1]=='AMBIGUOUS_MULTIPLE_LEI'
    class Fake:
        calls=0
        def get(self,path):
            self.calls+=1
            return (gleif() if self.calls==1 else {'data':[], 'meta':{'pagination':{'currentPage':1,'lastPage':1}}}),'hash'
    assert mapping.lookup(Fake(),'FR0000120404')['reason']=='ISIN_NOT_FOUND_IN_REVERSE_RELATION'


def test_rcs_spaces_are_explicitly_normalized_not_fuzzy():
    payload=gleif(); attrs=payload['data'][0]['attributes']
    attrs['entity'].update(registeredAt={'id':'RA000192'},registeredAs='602 036 444')
    attrs['registration'].update(validatedAt={'id':'RA000192'},validatedAs='602 036 444')
    assert mapping.evaluate(payload,'FR0000120404')[0]['siren']=='602036444'
    assert mapping.registry_siren('RCS 602036444') is None


def cfg():
    return {'collection_mode':'quarantine_only','canonical_writes_enabled':False,'serving_enabled':False,
            'max_requests_per_run':10,'max_requests_per_day':10,'max_issuers_per_run':1,'refresh_days':7,
            'request_interval_seconds':.2,'max_archive_bytes_per_run':100000}


class FakeInpi:
    calls=0
    def _request(self): self.request_guard(); self.calls+=1
    def login(self): self._request()
    def accounts(self,*args,**kwargs):
        self._request(); return [{'id':'a','confidentiality':'Public'}],None
    def account(self,identifier):
        self._request()
        return {'id':identifier,'siren':'602036444','denomination':'ACCOR','confidentiality':'Public',
                'bilanSaisi':{'bilan':{'identite':{'codeConfidentialite':'0','siren':'602036444'},'detail':{'pages':[]}}}}
    def close(self): pass


def test_collection_resume_quarantine_and_recent_skip(tmp_path,monkeypatch):
    monkeypatch.setattr(collector,'validate',lambda _:None)
    monkeypatch.setattr(collector.time,'sleep',lambda _:None)
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'issuers':[{'symbol':'AC.PA','isin':'FR0000120404','siren':'602036444','name_aliases':['ACCOR']}]}))
    root=tmp_path/'out'; result={'failed_count':0}
    collector.collect(cfg(),result,root=root,manifest_path=manifest,client=FakeInpi())
    assert result['persisted_count']==1 and result['coverage_complete']
    assert not result['ml_usable'] and not result['historical_pit_qualified']
    state=json.loads((root/'collection_state.json').read_text())
    assert state['issuers']['FR0000120404-602036444']['done_ids']==['a']
    again={'failed_count':0}; client=FakeInpi()
    collector.collect(cfg(),again,root=root,manifest_path=manifest,client=client)
    assert client.calls==0 and again['requested_count']==0
    assert len(list((root/'quarantine/objects').glob('*.json')))==1


def test_request_guard_is_invoked_before_http_call():
    client=InpiClient(); client._token='dummy'
    def stop(): raise collector.QuotaPause('quota')
    client.request_guard=stop
    with pytest.raises(collector.QuotaPause): client._request('bilans-saisis/x')
    assert client.calls==0


def test_quota_pause_resumes_unfinished_document_queue(tmp_path,monkeypatch):
    monkeypatch.setattr(collector,'validate',lambda _:None)
    monkeypatch.setattr(collector.time,'sleep',lambda _:None)
    path=tmp_path/'manifest.json'
    path.write_text(json.dumps({'issuers':[{'symbol':'AC.PA','isin':'FR0000120404','siren':'602036444','name_aliases':['ACCOR']}]}))
    class Many(FakeInpi):
        def accounts(self,*args,**kwargs):
            self._request()
            return [{'id':str(n),'confidentiality':'Public'} for n in range(12)],None
    root=tmp_path/'out'; first={'failed_count':0}
    collector.collect(cfg(),first,root=root,manifest_path=path,client=Many())
    assert first['pause_reason']=='RUN_CALL_BUDGET' and first['persisted_count']==8
    assert not first['coverage_complete'] and first['pending_issuers']==1
    state=json.loads((root/'collection_state.json').read_text())
    assert len(state['issuers']['FR0000120404-602036444']['done_ids'])==8
    # New UTC allowance in this fixture; real reservations are never reset by the collector.
    (root/'request_quota.json').write_text(json.dumps({'day_utc':'2000-01-01','reserved_calls':10}))
    second={'failed_count':0}
    collector.collect(cfg(),second,root=root,manifest_path=path,client=Many())
    assert second['persisted_count']==4 and second['coverage_complete']


def test_windows_sharing_lock_retry_preserves_atomic_output(tmp_path,monkeypatch):
    from pathlib import Path
    from service.inpi import files
    original=Path.replace; attempts=[]
    def intermittent(self,target):
        attempts.append(target)
        if len(attempts)<3: raise PermissionError('sharing lock')
        return original(self,target)
    monkeypatch.setattr(Path,'replace',intermittent)
    monkeypatch.setattr(files.time,'sleep',lambda _:None)
    files.atomic(tmp_path/'state.json',{'counter':5})
    assert json.loads((tmp_path/'state.json').read_text())=={'counter':5}
    assert len(attempts)==3 and not list(tmp_path.glob('*.tmp'))


def test_ambiguous_document_is_excluded_then_next_document_collected(tmp_path,monkeypatch):
    monkeypatch.setattr(collector,'validate',lambda _:None)
    monkeypatch.setattr(collector.time,'sleep',lambda _:None)
    path=tmp_path/'manifest.json'
    path.write_text(json.dumps({'issuers':[{'symbol':'AC.PA','isin':'FR0000120404','siren':'602036444','name_aliases':['ACCOR']}]}))
    class Mixed(FakeInpi):
        def accounts(self,*args,**kwargs):
            self._request(); return [{'id':'bad','confidentiality':'Public'}, {'id':'good','confidentiality':'Public'}],None
        def account(self,identifier):
            value=super().account(identifier)
            if identifier=='bad': value['denomination']='OTHER ENTITY'
            return value
    result={'failed_count':0,'warning_count':0}; root=tmp_path/'out'
    collector.collect(cfg(),result,root=root,manifest_path=path,client=Mixed())
    assert result['persisted_count']==1 and result['failed_count']==0 and result['warning_count']==1
    state=json.loads((root/'collection_state.json').read_text())['issuers']['FR0000120404-602036444']
    assert state['skipped_documents']==[{'id':'bad','reason':'ACCOUNT_LEGAL_NAME_NOT_MATCHED'}]
    assert state['done_ids']==['bad','good'] and state['completed_at']


def test_never_collected_issuer_precedes_expired_refresh(tmp_path,monkeypatch):
    monkeypatch.setattr(collector,'validate',lambda _:None)
    monkeypatch.setattr(collector.time,'sleep',lambda _:None)
    old={'symbol':'OLD','isin':'OLD_ISIN','siren':'602036444','name_aliases':['ACCOR']}
    new={**old,'symbol':'NEW','isin':'NEW_ISIN'}
    path=tmp_path/'manifest.json'; path.write_text(json.dumps({'issuers':[old,new]}))
    root=tmp_path/'out'; root.mkdir()
    (root/'collection_state.json').write_text(json.dumps({'issuers':{
        'OLD_ISIN-602036444':{'completed_at':'2000-01-01T00:00:00+00:00'}}}))
    result={'failed_count':0}
    collector.collect(cfg(),result,root=root,manifest_path=path,client=FakeInpi())
    state=json.loads((root/'collection_state.json').read_text())
    assert state['issuers']['NEW_ISIN-602036444']['completed_at']
    assert state['issuers']['OLD_ISIN-602036444']['completed_at'].startswith('2000')
