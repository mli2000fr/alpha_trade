from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import math
import pytest

from scripts.research import us_winner_consolidation_resume_20261026 as study


def payload():
    return dict(status='COMPLETED',best_2017_descriptive_only=[dict(return_pct=12.5,
        fill_price_correction=float('nan'),correction_amendment_sha256=float('nan'))])


def test_only_optional_absent_metadata_normalized_without_mutation():
    p=payload();r,changes=study.clean_descriptive_report(p)
    assert r['best_2017_descriptive_only'][0]==dict(return_pct=12.5,
        fill_price_correction=None,correction_amendment_sha256=None)
    assert len(changes)==2 and math.isnan(p['best_2017_descriptive_only'][0]['fill_price_correction'])


def test_present_provenance_retained_exactly():
    p=payload();p['best_2017_descriptive_only'][0].update(
        fill_price_correction='FIRST_FULL_FILL_AVERAGE_V1',correction_amendment_sha256='abc')
    assert study.clean_descriptive_report(p)==(p,[])


@pytest.mark.parametrize('field,value',[('return_pct',float('nan')),('final_equity',float('inf')),
    ('fill_price_correction',float('inf'))])
def test_financial_nan_and_any_infinity_still_rejected(field,value):
    p=payload();p['best_2017_descriptive_only'][0][field]=value
    with pytest.raises(ValueError):study.clean_descriptive_report(p)


def test_no_global_json_weakening_and_scope_restored(tmp_path):
    calls=[]
    def save(path,p):calls.append((path,p))
    base=SimpleNamespace(save_new=save);changes=[]
    with study.serialization_scope(base,tmp_path,changes):
        base.save_new(tmp_path/'report.json',payload())
        base.save_new(tmp_path/'cases/old/report.json',payload())
    assert base.save_new is save
    assert calls[0][1]['best_2017_descriptive_only'][0]['fill_price_correction'] is None
    assert math.isnan(calls[1][1]['best_2017_descriptive_only'][0]['fill_price_correction'])


def job(name,**kw):
    return dict(name=name,qualified=True,blocked=False,resolved=False)|kw


def test_adopted_worker_occupies_slot_and_is_never_selected_again():
    jobs=[job('2x-2024'),job('1x-2023'),job('2x-2020')];memory=10*2**30
    assert study.choose_job(jobs,{}, {'2x-2024':{}},available_bytes=memory)==('1x-2023','resume')
    assert study.choose_job(jobs,{'1x-2023':{}},{'2x-2024':{}},available_bytes=memory)==('2x-2020','resume')
    assert study.choose_job(jobs,{'1x-2023':{},'2x-2020':{}},{'2x-2024':{}},available_bytes=memory) is None


def test_memory_guard_and_blocked_resolved_jobs_never_retried():
    assert study.choose_job([job('a')],{}, {},available_bytes=1) is None
    assert study.choose_job([job('a',blocked=True),job('b',resolved=True)],{}, {},available_bytes=10*2**30) is None


def command():
    return ['python','-u','-m',study.LEGACY,'--target',study.TARGET,'--phase','resume','--kind','2x','--year','2024']


def test_exact_adopted_command_required():
    assert study.command_job(command())=='2x-2024'
    c=command();c[c.index('resume')]='qualify'
    with pytest.raises(ValueError):study.command_job(c)
    with pytest.raises(ValueError):study.command_job(['python','--kind','2x'])


def test_pid_reuse_rejected_before_duplicate_work(tmp_path):
    c=SimpleNamespace(ROOT=tmp_path)
    adopted={'2x-2024':dict(pid=10,created=1.)}
    p=SimpleNamespace(create_time=lambda:2.,is_running=lambda:True,status=lambda:'running')
    with pytest.raises(ValueError,match='identity'):
        study.living_adopted(c,adopted,lambda _:p)


def test_resolved_adopted_job_releases_slot_without_inspecting_reused_pid(tmp_path):
    folder=tmp_path/'2x-2024';folder.mkdir();(folder/'resolution.json').touch()
    def forbidden(_):raise AssertionError('No PID should be consulted after audited resolution')
    assert study.living_adopted(SimpleNamespace(ROOT=tmp_path),{'2x-2024':dict(pid=10,created=1.)},forbidden)=={}
