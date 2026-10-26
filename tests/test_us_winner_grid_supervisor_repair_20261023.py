import json
from pathlib import Path
import pytest
from scripts.research import us_winner_grid_supervisor_repair_20261023 as s


def test_completed_2017_releases_slot_for_2020():
    assert s.next_ready([2017,2019,2020],{2017:300,2019:150},{2019:object()},lambda y:True,300)==2020


def test_reference_not_ready_does_not_occupy_worker_slot():
    assert s.next_ready([2020,2021],{}, {},lambda y:y==2021,300)==2021
    assert s.next_ready([2020],{}, {},lambda y:False,300) is None


def test_json_permission_is_retried(monkeypatch):
    calls=[]
    def read(self,**kwargs):
        calls.append(self)
        if len(calls)<3:raise PermissionError('Windows atomic replace')
        return '{"status":"RUNNING"}'
    monkeypatch.setattr(Path,'read_text',read);monkeypatch.setattr(s.time,'sleep',lambda _:None)
    assert s.read_json('test.json')['status']=='RUNNING'
    assert len(calls)==3


def test_corrupt_persistent_json_is_not_silently_accepted(monkeypatch):
    monkeypatch.setattr(Path,'read_text',lambda *a,**k:'{bad')
    monkeypatch.setattr(s.time,'sleep',lambda _:None)
    with pytest.raises(json.JSONDecodeError):s.read_json('test.json',attempts=2)


def test_monitor_failure_preserves_last_state(monkeypatch):
    monkeypatch.setattr(Path,'exists',lambda _:True)
    monkeypatch.setattr(s,'read_json',lambda *a,**k:(_ for _ in ()).throw(PermissionError('busy')))
    warnings=[];old={'completed_runs':12}
    assert s.status_read('year.json',old,warnings)==old
    assert warnings[0]['error_type']=='PermissionError'


def test_missing_status_does_not_delay_scheduler(monkeypatch):
    monkeypatch.setattr(Path,'exists',lambda _:False)
    monkeypatch.setattr(s,'read_json',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No retry for an absent optional status')))
    assert s.status_read('not-started-year.json',None,[]) is None


def test_safe_reader_restored_on_error():
    before=s.grid.base.read
    with pytest.raises(RuntimeError):
        with s.safe_reads():
            assert s.grid.base.read is s.read_json
            raise RuntimeError('test')
    assert s.grid.base.read is before


def test_commands_are_scoped_and_do_not_use_process_pool():
    command=s.annual_command(s.grid.ROOT,'1x',2020,1)
    assert command[command.index('--phase')+1]=='year'
    assert command[command.index('--year')+1]=='2020'
    assert str(s.grid.ROOT) in command


def test_completed_record_requires_exact_parameters_and_files(tmp_path):
    p=dict(profiles=[{'name':'P','stop_loss_pct':.03}],years=[2017],effective_gross_cap=1.)
    folder=tmp_path/'cases'/'2017-P';folder.mkdir(parents=True)
    data=folder/'data.txt';data.write_text('fixed',encoding='utf-8')
    report=dict(year=2017,profile='P',status='COMPLETED_EXPLORATORY',smoke=False,
        parameters=p['profiles'][0],effective_gross_cap=1.,audit=dict(status='PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES'),
        files={'data.txt':s.grid.base.digest(data)})
    (folder/'report.json').write_text(json.dumps(report),encoding='utf-8')
    records,counts=s.completed_records(tmp_path,p,verify_files=True)
    assert counts=={2017:1} and '2017-P' in records
    data.write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError,match='Immutable input changed'):s.completed_records(tmp_path,p,verify_files=True)
