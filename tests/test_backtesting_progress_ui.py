"""The progress/error panel renders even when detailed logs are not loaded."""
from streamlit.testing.v1 import AppTest


def app():
    from ihm.components.backtesting_progress import render_backtesting_progress
    render_backtesting_progress({'run_id': 'fixture', 'status': 'running'})


def test_progress_counts_and_session_are_visible(monkeypatch):
    monkeypatch.setattr('ihm.components.backtesting_progress.read_backtesting_progress',
        lambda record: dict(status='RUNNING', completed=12, total=24, last_date='2025-01-20'))
    at = AppTest.from_function(app).run()
    assert not at.exception
    assert '12 / 24' in at.get('progress')[0].proto.text
    assert '2025-01-20' in at.get('progress')[0].proto.text


def test_failed_run_shows_reason_and_prediction_prerequisite(monkeypatch):
    monkeypatch.setattr('ihm.components.backtesting_progress.read_backtesting_progress',
        lambda record: dict(status='FAILED', error_type='ValueError', error='Empty or duplicate Oracle predictions'))
    at = AppTest.from_function(app).run()
    assert not at.exception
    assert 'Empty or duplicate Oracle predictions' in at.error[0].value
    assert 'ML Predict' in at.info[0].value
