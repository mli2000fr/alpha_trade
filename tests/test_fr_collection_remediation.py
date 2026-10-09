import json
from datetime import date

import pytest

from service.fr.collection_coverage_remediation import coverage, audit_sql, audit_files
from service.fr.event_data_qualification_11b import public_day
from tests.test_fr_eodhd_daily_15b import setup, execute, bar
from service.fr import eodhd_daily_15b as daily


def test_dila_known_sentinel_not_publication():
    assert public_day({'uin_dat_amf':'2026-10-05T14:46:00+00:00',
                       'uin_dat_mar':'8887-12-31T22:00:00+00:00'}) == '2026-10-05'
    assert public_day({'uin_dat_mar':'8887-12-31T22:00:00+00:00'}) is None
    assert public_day({'uin_dat_mar':'8888-01-01T00:00:00+01:00'}) is None
    assert public_day({'uin_dat_amf':'2026-10-05T14:46:00'}) is None


def test_coverage_does_not_count_versions_twice():
    result = coverage(['A.PA','B.PA'], [date(2026,10,2)], {'A.PA':['2026-10-02']*2})
    assert result['coverage_pct'] == 50
    assert result['present_symbol_sessions'] == 1
    assert result['tradability_inferred'] is False


def test_sql_refuses_wrong_database():
    class Result:
        def scalar(self): return 'alpha_trade'
    class Conn:
        def execute(self,*args): return Result()
    with pytest.raises(ValueError,match='another database'):
        audit_sql(Conn(), [], [date(2026,10,2)])


def test_resume_refetches_incomplete_windows(tmp_path, monkeypatch):
    ids,root,cfg=setup(tmp_path,monkeypatch)
    calls=[]
    monkeypatch.setattr(daily,'_fetch',lambda *a,**k:(calls.append(a[0]),[bar()])[1])
    execute(cfg,root,ids)
    state=json.loads(next((root/'windows').glob('*.json')).read_text())
    assert all(r['status']=='COMPLETED_WITH_GAPS' for r in state['symbols'].values())
    result=execute(cfg,root,ids,resume=True)
    assert result['resumed_symbols']==0
    assert len(calls)==4
    assert result['unchanged_rows']==2


def test_selected_symbols_bound_to_verified_universe(tmp_path, monkeypatch):
    ids,root,cfg=setup(tmp_path,monkeypatch)
    for selection in ([], ['US.US'], ['AB.PA','AB.PA']):
        with pytest.raises(ValueError,match='Sélection'):
            execute(cfg,root,ids,dry_run=True,selected_symbols=selection)
    result=execute(cfg,root,ids,dry_run=True,selected_symbols=['AB.PA'])
    assert result['requested_count']==1
    assert result['limited_smoke'] is True


def test_lineage(tmp_path, monkeypatch):
    ids,_,cfg=setup(tmp_path,monkeypatch)
    root=tmp_path/'daily'
    monkeypatch.setattr(daily,'_fetch',lambda *a,**k:[bar(),{**bar(),'date':'2026-10-05'}])
    execute(cfg,root,ids)
    monkeypatch.setattr(daily,'_fetch',lambda *a,**k:[bar()])
    execute(cfg,root,ids)
    sessions=[date(2026,10,2),date(2026,10,5)]
    report=audit_files(['AB.PA','AC.PA'],sessions,daily_root=root)
    assert report['present_symbol_sessions']==4
    assert report['current_response_confirmed_symbol_sessions']==2
    assert report['current_response_confirmed_coverage_pct']==50
    import hashlib
    path=root/'latest'/(hashlib.sha256(b'AB.PA').hexdigest()+'.json')
    latest=json.loads(path.read_text())
    latest['bars']['2026-10-02']['row']['close']=11
    daily.atomic(path,latest)
    report=audit_files(['AB.PA'],sessions,daily_root=root)
    assert report['malformed_or_unverifiable']==['AB.PA/2026-10-02']
