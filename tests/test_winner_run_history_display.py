"""Dates and qualification must describe the saved replay, including old runs."""
import json

import pytest

from ihm.pages import backtesting as page


@pytest.mark.parametrize('flags',[
    ['--start','2025-01-01','--end','2025-06-30'],
    ['--start-date','2025-01-01','--end-date','2025-06-30'],
    ['--start-date=2025-01-01','--end-date=2025-06-30'],
])
def test_dates_use_exact_complete_flags(flags):
    assert page._extract_run_dates({'command':['python','-m','backtesting.winner_campaign_replay',*flags]})==('2025-01-01','2025-06-30')


@pytest.mark.parametrize('display',[
    'python -m x --start-date 2025-01-01 --end-date 2025-06-30',
    'python -m x --start="2025-01-01" --end="2025-06-30"',
    "python -m x --start-date '2025-01-01' --end-date '2025-06-30'",
])
def test_display_only_legacy_records_still_work(display):
    assert page._extract_run_dates({'command_display':display})==('2025-01-01','2025-06-30')


def test_date_parser_never_confuses_prefix_with_value():
    assert page._extract_run_dates({'command_display':'python --start-date-workers 5 --end-date-policy 2'})==(None,None)
    assert page._extract_run_dates({'command':['python','--start','--end','2025-99-99']})==(None,None)


def test_partial_list_date_can_use_missing_end_from_display():
    run=dict(command=['--start','2025-01-01'],command_display='python --end-date 2025-06-30')
    assert page._extract_run_dates(run)==('2025-01-01','2025-06-30')


def run_record(tmp_path):
    root=tmp_path/'run';(root/'artifacts').mkdir(parents=True)
    (root/'stdout.log').touch()
    return dict(status='completed',run_id='example',executed_at='2026-10-31T12:58:41',
        stdout_path=str(root/'stdout.log'),command=['python','-m','backtesting.winner_campaign_replay',
            '--start-date','2025-01-01','--end-date','2025-06-30'])


def test_completed_process_with_incomplete_replay_is_not_green(tmp_path):
    record=run_record(tmp_path)
    (tmp_path/'run/artifacts/progress.json').write_text(json.dumps({'status':'INCOMPLETE_COVERAGE'}))
    label=page._format_run_inspect_label(record,{})
    assert label.startswith('2025-01-01 -- 2025-06-30 |')
    assert '🟠' in label and 'couverture incomplète' in label and '🟢' not in label
    assert record['status']=='completed'  # Process history remains unchanged.


def test_missing_progress_can_use_saved_report(tmp_path):
    record=run_record(tmp_path)
    (tmp_path/'run/artifacts/report.json').write_text(json.dumps({'status':'INCOMPLETE_COVERAGE'}))
    assert page._run_qualification_status(record)=='INCOMPLETE_COVERAGE'


def test_qualified_or_active_runs_keep_correct_badges(tmp_path):
    record=run_record(tmp_path)
    (tmp_path/'run/artifacts/progress.json').write_text(json.dumps({'status':'COMPLETED_EXPLORATORY'}))
    assert page._run_status_badge(record)=='🟢 Terminé'
    record['status']='running'
    assert page._run_qualification_status(record) is None
    assert page._run_status_badge(record)=='🟨 En cours'
