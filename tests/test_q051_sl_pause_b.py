import json
from pathlib import Path
import pytest
from scripts.research import us_q051_sl_pause_b_20261116 as b


def test_b_control_comparison_routes_only_exact_t0_reference(monkeypatch,tmp_path):
    monkeypatch.setattr(b.pause,'REFERENCE',tmp_path/'lot1')
    monkeypatch.setattr(b,'BASELINE',tmp_path/'lot1/variants/B/cases/B_SIMPLE')
    routed=b.baseline_csv_reader(lambda file,*a,**kw:Path(file))
    original=tmp_path/'lot1/variants/T0/cases/T0_SIMPLE/result/equity-daily.csv'
    assert routed(original)==b.BASELINE/'result/equity-daily.csv'
    other=tmp_path/'own-case/result/equity-daily.csv'
    assert routed(other)==other


def test_launch_waits_for_validated_t0_control(tmp_path):
    (tmp_path/'progress.json').write_text(json.dumps(dict(status='REPLAYING')))
    assert not b.reference_ready(tmp_path)
    f=tmp_path/'cases/CONTROL/validation.json';f.parent.mkdir(parents=True)
    f.write_text(json.dumps(dict(status='PASS',control_equivalence=True)))
    assert b.reference_ready(tmp_path)


def test_failed_control_cannot_release_b_pause(tmp_path):
    (tmp_path/'progress.json').write_text(json.dumps(dict(status='FAILED',error='example')))
    with pytest.raises(ValueError,match='T0 campaign failed'):b.reference_ready(tmp_path)


def test_local_report_is_not_control_validation(tmp_path):
    (tmp_path/'progress.json').write_text(json.dumps(dict(status='REPLAYING')))
    f=tmp_path/'cases/CONTROL/result/report.json';f.parent.mkdir(parents=True)
    f.write_text(json.dumps(dict(status='INCOMPLETE_COVERAGE')))
    assert not b.reference_ready(tmp_path)
