from datetime import date
import gzip
import json
import pytest
from service.fr import operational_collectors_15c as c


def fixture(tmp_path,monkeypatch):
    ids=tmp_path/'ids.gz'
    with gzip.open(ids,'wt') as s:
        s.write(json.dumps({'isin':'FR0010557264','provider_symbol':'AB.PA','identity_state':'VERIFIED_RESEARCH','provider_status_current':'active'})+'\n')
    monkeypatch.setenv('EODHD_API_TOKEN','secret')
    return ids,dict(lookback_days=7,request_interval_seconds=.1)


def result(): return dict(received_count=0,persisted_count=0,failed_count=0,warning_count=0)


def test_actions_empty_is_valid_dedup_and_correction(tmp_path,monkeypatch):
    ids,cfg=fixture(tmp_path,monkeypatch)
    rows=[{'date':'2026-10-02','value':1,'currency':'EUR'}]
    monkeypatch.setattr(c,'_fetch',lambda endpoint,*a,**kw: rows.copy() if endpoint.startswith('div/') else [])
    root=tmp_path/'actions'
    r=result(); c.corporate(cfg,r,root=root,identities=ids,today=date(2026,10,5))
    assert r['received_count']==r['persisted_count']==2
    r=result(); c.corporate(cfg,r,root=root,identities=ids,today=date(2026,10,5))
    assert r['persisted_count']==0 and r['unchanged_count']==2
    rows[0]['value']=2
    r=result(); c.corporate(cfg,r,root=root,identities=ids,today=date(2026,10,5))
    assert r['changed_count']==1
    assert len(list((root/'raw').glob('*.json')))==3


@pytest.mark.parametrize('kind,row',[('div',{'date':'2026-10-02','value':-1}),('splits',{'date':'2026-10-02','split':'0/1'}),('div',{'date':'2020-01-01','value':1})])
def test_invalid_action_rejected(kind,row):
    with pytest.raises((ValueError,ArithmeticError)):
        c.validate_actions([row],kind,date(2026,9,28),date(2026,10,5))


def test_dila_dedup_and_preserve_observation_not_publication(tmp_path,monkeypatch):
    ids,cfg=fixture(tmp_path,monkeypatch)
    row={'uin_idt_uin':'one','identificationsociete_iso_cd_isi':'FR0010557264','uin_dat_amf':'2026-10-02T17:00:00Z'}
    monkeypatch.setattr(c,'fetch',lambda url: json.dumps([row,row]).encode())
    root=tmp_path/'dila'
    r=result(); c.public_collection('fr_dila_disclosures_sync',cfg,r,root=root,identities=ids,today=date(2026,10,5))
    assert r['persisted_count']==1
    r=result(); c.public_collection('fr_dila_disclosures_sync',cfg,r,root=root,identities=ids,today=date(2026,10,5))
    assert r['persisted_count']==0
    saved=json.loads((root/'latest.json').read_text())
    assert len(saved['records'])==1
    assert list(saved['records'].values())[0]['available_at'] > row['uin_dat_amf']


def test_quality_excludes_itself_and_keeps_counts(tmp_path):
    cfg={'collection_dependencies':['fr_daily_bars_sync'],'max_run_age_hours':96}
    r=result()
    with pytest.raises(RuntimeError): c.quality(cfg,r,operations=tmp_path)
    assert r['requested_count']==r['received_count']==r['persisted_count']==r['failed_count']==1
    assert len(list((tmp_path/'quality').glob('*.json')))==1


def test_public_dryrun_no_network_or_files(tmp_path,monkeypatch):
    ids,cfg=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(c,'fetch',lambda *a:pytest.fail('network'))
    root=tmp_path/'empty'
    c.public_collection('fr_amf_short_sync',cfg,result(),root=root,identities=ids,dry_run=True)
    assert not root.exists()


def test_amf_catalog_and_snapshot_dedup(tmp_path,monkeypatch):
    ids,cfg=fixture(tmp_path,monkeypatch)
    csv=('Date de debut position;Date de debut de publication position;Date de fin de publication position;Detenteur de la position courte nette;code ISIN;Ratio\n'
         '2026-10-01;2026-10-02;;Holder;FR0010557264;0.5\n').encode()
    catalog={'license':'lov2','resources':[{'format':'csv','url':'https://object-api.infra.data.gouv.fr/amf/test.csv'}]}
    monkeypatch.setattr(c,'fetch',lambda url:json.dumps(catalog).encode() if url==c.CATALOG else csv)
    root=tmp_path/'amf'
    r=result(); c.public_collection('fr_amf_short_sync',cfg,r,root=root,identities=ids)
    assert r['persisted_count']==1
    r=result(); c.public_collection('fr_amf_short_sync',cfg,r,root=root,identities=ids)
    assert r['persisted_count']==0 and r['unique_records']==1
    catalog['resources'][0]['url']='http://untrusted.invalid/x'
    with pytest.raises(ValueError,match='Hôte'):
        c.public_collection('fr_amf_short_sync',cfg,result(),root=root,identities=ids)
