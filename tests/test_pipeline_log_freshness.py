"""Fast completed launches must replace stale automatic log selection, not manual history."""
import os

import pytest

from ihm.pages import _workflow as page
from ihm.services import process_registry


@pytest.fixture(autouse=True)
def clean_history_cache(monkeypatch):
    cached_history = page._cached_history
    cached_history.clear()
    monkeypatch.setattr(page.st, 'session_state', {})
    yield
    cached_history.clear()


def run(run_id, started, *, status='completed', finished=None, **kwargs):
    return dict(run_id=run_id, step_key='risk_management', executed_at=started,
                finished_at=finished or started, status=status, **kwargs)


def prime(runs):
    ids = [r['run_id'] for r in runs]
    page._prime_runtime_center_state(runs, ids, {rid:rid for rid in ids})


def test_fast_run_finishing_between_ticks_invalidates_history_cache(monkeypatch, tmp_path):
    path = tmp_path/'history_index.json'
    path.write_text('{}', encoding='utf-8')
    os.utime(path, ns=(1000000000,1000000000))
    monkeypatch.setattr(process_registry, 'HISTORY_INDEX_PATH', path)
    monkeypatch.setattr(page, 'list_active_pipeline_runs', lambda: [])
    old = run('old', '2026-10-27T07:59:07')
    new = run('new', '2026-10-27T08:04:15')
    disk, calls = [old], []
    def load():
        calls.append(True)
        return list(disk)
    monkeypatch.setattr(page, 'load_pipeline_history', load)
    assert page._merge_runs()[1] == [old]
    assert page._merge_runs()[1] == [old]
    assert len(calls) == 1
    disk.append(new)
    # Same byte length, but new file revision: no TTL wait needed.
    os.utime(path, ns=(2000000000,2000000000))
    active, merged = page._merge_runs()
    assert active == [] and merged == [new,old]
    assert len(calls) == 2


def test_new_pending_launch_is_read_even_if_index_has_not_caught_up(monkeypatch):
    old = run('old', '2026-10-27T07:59:07')
    new = run('new', '2026-10-27T08:04:15')
    monkeypatch.setattr(page, '_cached_history', lambda revision: [old])
    monkeypatch.setattr(page, 'list_active_pipeline_runs', lambda: [])
    monkeypatch.setattr(page, 'get_pipeline_run_record', lambda rid: new if rid == 'new' else None)
    page.st.session_state[page.PENDING_SELECTED_RUN_KEY] = 'new'
    runs = page._merge_runs()[1]
    assert runs == [new,old]
    prime(runs)
    assert page.st.session_state[page.SELECTED_RUN_KEY] == 'new'
    assert page.PENDING_SELECTED_RUN_KEY not in page.st.session_state


def test_invisible_pending_run_is_not_discarded():
    old = run('old', '2026-10-27T07:59:07')
    page.st.session_state[page.PENDING_SELECTED_RUN_KEY] = 'new'
    prime([old])
    assert page.st.session_state[page.PENDING_SELECTED_RUN_KEY] == 'new'
    prime([run('new','2026-10-27T08:04:15'),old])
    assert page.st.session_state[page.SELECTED_RUN_KEY] == 'new'
    assert page.PENDING_SELECTED_RUN_KEY not in page.st.session_state


def test_automatic_view_follows_next_completed_launch():
    old = run('old','2026-10-27T07:59:07')
    new = run('new','2026-10-27T08:04:15')
    prime([old])
    prime([new,old])
    assert page.st.session_state[page.SELECTED_RUN_KEY] == 'new'
    assert page.st.session_state[page.WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY] == 'new'


def test_manual_history_selection_is_preserved():
    oldest = run('oldest','2026-10-26T07:59:07')
    old = run('old','2026-10-27T07:59:07')
    new = run('new','2026-10-27T08:04:15')
    prime([old,oldest])
    page.st.session_state[page.SELECTED_RUN_KEY] = 'oldest'
    prime([new,old,oldest])
    assert page.st.session_state[page.SELECTED_RUN_KEY] == 'oldest'


def test_explicit_pending_history_choice_wins_over_latest():
    old = run('old','2026-10-27T07:59:07')
    new = run('new','2026-10-27T08:04:15')
    page.st.session_state[page.PENDING_SELECTED_RUN_KEY] = 'old'
    prime([new,old])
    assert page.st.session_state[page.SELECTED_RUN_KEY] == 'old'
    prime([new,old])
    assert page.st.session_state[page.SELECTED_RUN_KEY] == 'old'


def test_latest_step_is_by_launch_not_old_runs_late_finish(monkeypatch):
    old = run('old','2026-10-27T07:00:00',finished='2026-10-27T09:00:00')
    new = run('new','2026-10-27T08:00:00',finished='2026-10-27T08:04:00')
    monkeypatch.setattr(page, '_cached_history', lambda revision: [old,new])
    monkeypatch.setattr(page, 'list_active_pipeline_runs', lambda: [])
    runs = page._merge_runs()[1]
    assert page._latest_run_by_step(runs)['risk_management']['run_id'] == 'new'


def test_active_record_wins_over_cached_old_state(monkeypatch):
    cached = run('new','2026-10-27T08:00:00',status='starting')
    live = {**cached, 'status':'running', 'stdout_lines':10}
    monkeypatch.setattr(page, '_cached_history', lambda revision: [cached])
    monkeypatch.setattr(page, 'list_active_pipeline_runs', lambda: [live])
    assert page._merge_runs()[1] == [live]
