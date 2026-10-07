from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from service.forward_pit import us_pipeline
from service.forward_pit.batch import BatchRunError, HANDLERS
from ihm.services import process_registry
from ihm.services.pipeline_runner import PAGE_SENTIMENT_DEFAULTS, pipeline_page_default_options


def calendar(close_hour=20, opened=True):
    return SimpleNamespace(sessions=lambda a, b: [SimpleNamespace(is_open=True,
        close_at_utc=datetime(a.year, a.month, a.day, close_hour, tzinfo=UTC))] if opened else [])


def test_exact_first_nine_not_training_or_orders():
    steps = us_pipeline.first_nine()
    assert [s.num for s in steps] == [str(i) for i in range(1, 10)]
    assert not {'ml_train','ml_predict','risk','execution'} & {s.key for s in steps}
    assert 'us_pipeline_1_9' in HANDLERS


@pytest.mark.parametrize('stamp,close', [('2026-10-07T20:45:00+00:00',20),
    ('2026-10-28T21:45:00+00:00',20), ('2026-11-04T21:45:00+00:00',21)])
def test_paris_2245_after_ny_close_including_dst_mismatch(stamp, close):
    now = datetime.fromisoformat(stamp)
    day, skip = us_pipeline.session_plan(now, calendar=calendar(close))
    assert str(day) == stamp[:10]
    assert skip is None


def test_holiday_and_before_close_skip():
    now = datetime(2026, 7, 3, 20, 45, tzinfo=UTC)
    assert us_pipeline.session_plan(now, calendar=calendar(opened=False))[1] == 'NON_TRADING_DAY'
    assert us_pipeline.session_plan(now, calendar=calendar(21))[1] == 'SESSION_NOT_CLOSED'
    with pytest.raises(ValueError):
        us_pipeline.session_plan(datetime(2026, 7, 3), calendar=calendar())


def test_calendar_fallback_disabled(monkeypatch):
    seen = {}
    def factory(code, **kwargs):
        seen.update(code=code, **kwargs)
        return calendar()
    monkeypatch.setattr(us_pipeline, 'get_market_calendar', factory)
    us_pipeline.session_plan(datetime(2026, 10, 7, 20, 45, tzinfo=UTC))
    assert seen == dict(code='US_EQ', allow_us_weekday_fallback=False)


def test_default_options_match_page_preset_and_sentiment():
    options = pipeline_page_default_options(trade_date='2026-10-07')
    assert options.capital_preset_key == 'capital_2001_5000'
    assert options.selector_selection_size == 20
    assert options.screener_liquidity_threshold_usd == 5000000
    for key, value in PAGE_SENTIMENT_DEFAULTS.items():
        assert getattr(options, key) == value
    assert options.trade_date == '2026-10-07'
    assert options.force_trade_date_to_latest_snapshot is False


def setup_run(monkeypatch, tmp_path):
    monkeypatch.setattr(us_pipeline, 'ROOT', tmp_path)
    monkeypatch.setattr(us_pipeline, 'session_plan', lambda now: (now.date(), None))
    return SimpleNamespace(url=SimpleNamespace(database='alpha_trade')), {'market_code':'US_EQ'}


def test_dry_run_does_not_start_workflow(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', lambda *a, **k: pytest.fail('started'))
    result = us_pipeline.execute_pipeline(engine, cfg, 'dry', True)
    assert result.requested == 9
    assert result.persisted == 0
    assert not (tmp_path / 'artifacts').exists()


def test_workflow_success_uses_shared_engine_and_all_nine(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    seen = {}
    def start(options, **kwargs):
        seen.update(options=options, **kwargs)
        return SimpleNamespace(run_id='workflow-test')
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', start)
    monkeypatch.setattr(process_registry, 'poll_pipeline_run', lambda run: dict(status='completed',workflow_completed_steps=9))
    result = us_pipeline.execute_pipeline(engine, cfg, 'success', False,
        now=datetime(2026, 10, 7, 20, 45, tzinfo=UTC))
    assert result.persisted == result.received == 9
    assert seen['selected_step_keys'] == tuple(s.key for s in us_pipeline.first_nine())
    assert seen['db_config'] == {'name':'alpha_trade'}
    assert seen['options'].trade_date == '2026-10-07'


def test_failure_keeps_counters_and_does_not_restart(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    starts = []
    def start(*a, **k):
        starts.append(k)
        return SimpleNamespace(run_id='workflow-test')
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', start)
    monkeypatch.setattr(process_registry, 'poll_pipeline_run', lambda run: dict(status='failed',workflow_completed_steps=2))
    with pytest.raises(BatchRunError, match='2/9') as error:
        us_pipeline.execute_pipeline(engine, cfg, 'failure', False)
    assert error.value.outcome.requested == 9
    assert error.value.outcome.persisted == 2
    assert error.value.outcome.failed == 1
    assert len(starts) == 1


def test_other_database_rejected_before_workflow(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    engine.url.database = 'alpha_trade_fr'
    with pytest.raises(ValueError, match='alpha_trade'):
        us_pipeline.execute_pipeline(engine, cfg, 'wrong', False)


def test_non_trading_day_never_starts_workflow(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'session_plan', lambda now: (now.date(), 'NON_TRADING_DAY'))
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', lambda *a, **k: pytest.fail('started'))
    result = us_pipeline.execute_pipeline(engine, cfg, 'holiday', False)
    assert result.details['skip_reason'] == 'NON_TRADING_DAY'
    assert result.requested == result.persisted == 0
    assert not (tmp_path / 'artifacts').exists()


def test_busy_workflow_preserves_batch_error_counters(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    def busy(*a, **k):
        raise RuntimeError('pipeline already running')
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', busy)
    with pytest.raises(BatchRunError, match='already running') as error:
        us_pipeline.execute_pipeline(engine, cfg, 'busy', False)
    assert error.value.outcome.requested == 9
    assert error.value.outcome.persisted == 0
    assert error.value.outcome.failed == 1


def test_catalogue_has_schedule_and_generic_commands():
    from ihm.services.batch_management import load_market_batch_specs, build_install_command, build_run_command
    spec = next(s for s in load_market_batch_specs('US_EQ') if s.name == 'us_pipeline_1_9')
    assert spec.enabled and spec.timezone == 'Europe/Paris'
    assert spec.run_hours == ('22',) and spec.run_minutes == ('45',)
    assert spec.run_days == ('1','2','3','4','5')
    assert 'us_pipeline_1_9' in build_install_command(spec)
    assert 'us_pipeline_1_9' in build_run_command(spec)
