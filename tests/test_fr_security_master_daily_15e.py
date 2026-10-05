from datetime import date
import json

import pytest

from service.fr import security_master_daily_15e as master


def item(day='2026-10-02',part='01of01'):
    name='DLTINS_'+day.replace('-','')+'_'+part+'.zip'
    return dict(file=name,date=day,url='https://firds.esma.europa.eu/firds/'+name,md5=None)


def test_all_fragments_and_missing_days_explicit():
    rows=[item(part='01of02'),item(part='02of02')]
    assert master.validate_index(rows,date(2026,10,2),date(2026,10,3))==['2026-10-03']
    with pytest.raises(ValueError,match='incomplets'):
        master.validate_index(rows[:1],date(2026,10,2),date(2026,10,2))


@pytest.mark.parametrize('change',[{'url':'http://firds.esma.europa.eu/file.zip'},
    {'url':'https://evil.test/firds/DLTINS_20261002_01of01.zip'}, {'date':'2026-10-01'}])
def test_untrusted_index_rejected(change):
    with pytest.raises(ValueError): master.validate_index([{**item(),**change}],date(2026,10,2),date(2026,10,2))


def prior():
    return dict(end='2026-10-01',files=[],symbols=[dict(isin='FR0000000001',market_reference=[])],
        target_mics=['XPAR'],anomalies=[],historical_continuity_confirmed=False,
        canonical_go=False,tradable_enabled=False)


def test_versions_pit_termination_resume_and_source_immutable(monkeypatch):
    record=dict(isin='FR0000000001',mic='XPAR',event='NewRcrd',
        first_trade_reported='2026-10-02',termination_reported=None,publication_from_reported='2026-10-02')
    monkeypatch.setattr(master,'archive_records',lambda *args:iter([record]))
    initial=prior(); original=json.dumps(initial)
    paths=[(item(),None,dict(sha256='one'))]
    first,n=master.advance(initial,paths,end=date(2026,10,2),observed_at='2026-10-05T20:00:00Z')
    second,n2=master.advance(first,paths,end=date(2026,10,2),observed_at='2026-10-05T21:00:00Z')
    assert n==1 and n2==0 and first==second
    assert json.dumps(initial)==original
    version=first['symbols'][0]['market_reference'][0]['versions'][0]
    assert version['available_at']=='2026-10-05T20:00:00Z'
    assert not first['historical_continuity_confirmed'] and not first['tradable_enabled']
    record.update(event='TermntdRcrd',termination_reported='2026-10-03')
    final,n=master.advance(first,[(item('2026-10-03'),None,dict(sha256='two'))],end=date(2026,10,3),observed_at='2026-10-05T21:00:00Z')
    assert final['symbols'][0]['market_reference'][0]['trading_episodes'][0]['observed_to']=='2026-10-02'
    with pytest.raises(ValueError,match='Correction'):
        master.advance(first,[(item(),None,dict(sha256='changed'))],end=date(2026,10,2),observed_at='later')


def test_missing_publication_never_advances_checkpoint(tmp_path,monkeypatch):
    import gzip
    base=tmp_path/'base.json'
    base.write_text(json.dumps({**prior(),'complete':True,'publication_continuity_confirmed':False}))
    identities=tmp_path/'ids.gz'
    with gzip.open(identities,'wt') as stream:
        stream.write(json.dumps(dict(isin='FR0000000001',identity_state='VERIFIED_RESEARCH'))+'\n')
    monkeypatch.setattr(master,'_tls_context',lambda:None)
    monkeypatch.setattr(master,'delta_index',lambda *args:[])
    result=dict(requested_count=0,received_count=0,persisted_count=0,failed_count=0,warning_count=0)
    with pytest.raises(ValueError,match='absentes'):
        master.collect({},result,root=tmp_path/'out',identities=identities,base_path=base,today=date(2026,10,3))
    assert result['missing_publication_days']==['2026-10-02']
    assert not (tmp_path/'out/checkpoint.json').exists()
