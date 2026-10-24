from pathlib import Path
import pandas as pd
import pytest
from scripts.research import us_winner_cent_qualification_20261024 as s


@pytest.mark.parametrize('message,expected',[('9.08 != 9.09',True),('45.27 != 45.26',True),
    ('14.25 != 14.24',True),('10.73 != 10.75',False),('Coverage incomplete',False)])
def test_only_cent_price_errors_are_candidates(message,expected):
    assert s.cent_error(message)==expected


def mismatch():
    return dict(same_time_reason=True,scalar_price=9.08,actual_price=9.09,actual_reason='TP',
        fills=[dict(tp=9.09,canonical_tp=9.08,stop=6.,canonical_stop=6.,native_price=7.900000000000001,raw_average='7.9')])


def test_explanation_requires_the_actual_fill_rounding_mechanism():
    m=mismatch();assert s.explained(m)
    m['fills'][0]['native_price']=7.9;assert not s.explained(m)


def test_never_waive_different_exit_time_or_trailing_mismatch():
    m=mismatch();m['same_time_reason']=False;assert not s.explained(m)
    m=mismatch();m['actual_reason']='TIGHTENED_STOP_GAP';assert not s.explained(m)


def test_qualifications_before_resumptions(tmp_path,monkeypatch):
    monkeypatch.setattr(s,'ROOT',tmp_path)
    for kind in ['1x','2x']:
        folder=s.job_root(kind,2021);folder.mkdir();s.grid.base.save_new(folder/'request.json',dict(kind=kind,year=2021))
    s.grid.base.save_new(s.job_root('1x',2021)/'qualified.json',dict(status='QUALIFIED'))
    _,phase,q=s.next_task({});assert phase=='qualify' and q['kind']=='2x'
    s.grid.base.save_new(s.job_root('2x',2021)/'blocked.json',dict(status='BLOCKED'))
    _,phase,q=s.next_task({});assert phase=='resume' and q['kind']=='1x'


def test_source_preservation_and_all_four_grids():
    assert set(s.RUNS)=={'1x','2x','top20','top50'}
    assert s.correction.ORIGINAL_BOOK is s.correction.runtime.WinnerCampaignRuntime.book_buy
    assert s.ORIGINAL_WORKER is s.grid.worker


def test_completed_reports_never_overwritten(tmp_path,monkeypatch):
    monkeypatch.setitem(s.RUNS,'1x',tmp_path)
    case=tmp_path/'cases/2021-TEST';case.mkdir(parents=True)
    s.grid.base.save_new(case/'report.json',dict(status='OLD'))
    with pytest.raises(FileExistsError):s.install_validated('1x',2021,'TEST',tmp_path/'unused')
    assert s.read_json(case/'report.json')==dict(status='OLD')


def test_unequal_completed_account_is_blocked(tmp_path):
    old=tmp_path/'old';new=tmp_path/'new';old.mkdir();new.mkdir()
    s.grid.base.save_new(old/'report.json',dict(final_equity=4000))
    s.grid.base.save_new(new/'report.json',dict(final_equity=4001))
    with pytest.raises(ValueError,match='materially changes'):s.equivalent_accounts(old,new)
