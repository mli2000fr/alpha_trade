import copy
import json

import pytest

from service.inpi import secure_collection as secure
from service.inpi.client import InpiError
from service.fr import operational_batch_15a as runner


def payload():
    return {'id':'account1','siren':'438479941','denomination':'AB SCIENCE',
            'confidentiality':'Public','deleted':False,'bilanSaisi':{'bilan':{
                'identite':{'siren':'438479941','codeConfidentialite':'0'},'detail':{'pages':[]}}}}


def manifest():
    return {'issuers':[{'symbol':'AB.PA','siren':'438479941','name_aliases':['AB SCIENCE']}]}


class Fake:
    calls=0
    closed=False
    def __init__(self,document=None): self.document=document or payload()
    def account(self,identifier):
        self.calls+=1; return copy.deepcopy(self.document)
    def close(self): self.closed=True


def test_archive_idempotent_objects_distinct_observations_and_no_promotion(tmp_path):
    fake=Fake(); archive=secure.ArchiveClient(fake,manifest(),tmp_path,max_requests=10,max_bytes=10000)
    archive.account('account1'); archive.account('account1')
    assert len(list((tmp_path/'quarantine/objects').glob('*.json')))==1
    assert archive.new_documents==1 and len(archive.observations)==2
    assert archive.observations[1]['available_at']>=archive.observations[0]['available_at']
    assert all(not x['ml_usable'] and not x['historical_pit_qualified'] for x in archive.observations)
    assert archive.observations[0]['qualification_state']=='QUARANTINED_UNQUALIFIED'
    assert archive.observations[0]['archive_version']=='inpi-structured-v2'
    assert archive.observations[0]['request_started_at']<=archive.observations[0]['available_at']
    saved=json.loads(next((tmp_path/'quarantine/objects').glob('*.json')).read_text(encoding='utf-8'))
    assert saved==payload()
    archive.close(); assert fake.closed


@pytest.mark.parametrize('change',[{'confidentiality':'Confidential'},{'deleted':True},
    {'siren':'123456789'},{'denomination':'OTHER COMPANY'}])
def test_reject_public_scope_identity_failures_without_archiving(tmp_path,change):
    document=payload(); document.update(change)
    archive=secure.ArchiveClient(Fake(document),manifest(),tmp_path,max_requests=10,max_bytes=10000)
    with pytest.raises(InpiError): archive.account('account1')
    assert not tmp_path.joinpath('quarantine').exists()


def test_internal_confidentiality_rejected(tmp_path):
    document=payload(); document['bilanSaisi']['bilan']['identite']['codeConfidentialite']='1'
    archive=secure.ArchiveClient(Fake(document),manifest(),tmp_path,max_requests=10,max_bytes=10000)
    with pytest.raises(InpiError): archive.account('account1')
    assert not archive.observations


def test_budgets_and_corrupt_archive_fail_closed(tmp_path):
    fake=Fake(); archive=secure.ArchiveClient(fake,manifest(),tmp_path,max_requests=1,max_bytes=10000)
    archive.account('account1')
    with pytest.raises(InpiError,match='appels'): archive.account('account1')
    assert fake.calls==1
    other=secure.ArchiveClient(Fake(),manifest(),tmp_path,max_requests=10,max_bytes=1)
    with pytest.raises(InpiError,match='octets'): other.account('account1')
    obj=next((tmp_path/'quarantine/objects').glob('*.json'))
    obj.write_text('corrupt',encoding='utf-8')
    other=secure.ArchiveClient(Fake(),manifest(),tmp_path,max_requests=10,max_bytes=10000)
    with pytest.raises(InpiError,match='corrompue'): other.account('account1')


def test_dry_run_no_credentials_network_or_files(tmp_path):
    cfg=runner.load_section('fr_fundamentals_sync',runner.ROOT/'batch_fr.yaml')
    cfg['max_requests_per_run']=130
    result={}
    secure.collect(cfg,result,root=tmp_path/'out',
        manifest_path=runner.ROOT/'config/inpi_pilot_fr.json',dry_run=True,max_symbols=1)
    assert result['requested_count']==1 and not result['ml_usable']
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('changes',[{'collection_mode':'canonical'},
    {'canonical_writes_enabled':True},{'serving_enabled':True},{'max_requests_per_run':131}])
def test_bad_config_refused(tmp_path,changes):
    cfg=runner.load_section('fr_fundamentals_sync',runner.ROOT/'batch_fr.yaml'); cfg['max_requests_per_run']=130; cfg.update(changes)
    with pytest.raises(ValueError): secure.collect(cfg,{},root=tmp_path/'out',
        manifest_path=runner.ROOT/'config/inpi_pilot_fr.json',dry_run=True)


def test_inpi_wrapper_dry_run_and_catalog_notice():
    from ihm.services.batch_management import load_market_batch_specs
    result=runner.run('fr_fundamentals_sync',dry_run=True,max_symbols=1)
    assert result['status']=='DRY_RUN' and not result['canonical_writes'] and not result['serving_enabled']
    spec=next(s for s in load_market_batch_specs('FR_EQ') if s.name=='fr_fundamentals_sync')
    assert spec.runnable and 'QUARANTAINE' in spec.research_notice and '330' in spec.universe_scope
