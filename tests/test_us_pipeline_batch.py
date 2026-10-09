from datetime import UTC, datetime, date
from pathlib import Path
from types import SimpleNamespace

import pytest

from service.forward_pit import us_pipeline
from service.forward_pit.batch import BatchRunError, HANDLERS
from ihm.services import process_registry
from ihm.services.pipeline_runner import PAGE_SENTIMENT_DEFAULTS, pipeline_page_default_options


def configured_policy():
    import yaml
    return yaml.safe_load((Path(__file__).resolve().parents[1] / 'batch.yaml').read_text(encoding='utf-8'))


def test_common_universe_and_collection_windows(monkeypatch):
    from ihm.services.pipeline_runner import build_pipeline_command
    monkeypatch.setattr('ihm.services.pipeline_runner._resolve_bars_provider_for_ihm', lambda: 'eodhd')
    cfg = configured_policy()
    policy = cfg['us_pipeline']
    options = us_pipeline.collection_options(pipeline_page_default_options(trade_date='2026-10-07'),
                                             policy, date(2026, 10, 7))
    path = 'config/univers_batch/univers_filtred_tradable.txt'
    source = 'universe-file:' + path
    assert options.screener_custom_universe_file == path
    assert options.sentiment_pipeline_symbol_source == source
    assert options.data_integrity_quotes_symbol_source == source
    assert options.data_integrity_earnings_symbol_source == source
    assert options.data_integrity_quotes_from_date == '2026-09-30'
    assert options.data_integrity_quotes_to_date == '2026-10-07'
    assert options.data_integrity_earnings_from_date == '2026-09-30'
    assert options.data_integrity_earnings_to_date == '2026-11-06'
    assert options.data_integrity_quotes_batch_size == 200
    assert options.data_integrity_earnings_batch_size == 50
    assert options.data_integrity_earnings_provider == 'finnhub'
    assert options.data_integrity_earnings_resume is True
    assert options.eodhd_import_target_date == '2026-10-07'
    assert options.eodhd_import_symbol_source == source
    assert options.eodhd_import_wait_for_publication
    assert options.eodhd_import_require_target_coverage
    command = build_pipeline_command('import_alpaca_bar', options)
    assert command[command.index('--target-date')+1] == '2026-10-07'
    assert command[command.index('--symbol-source')+1] == source
    assert '--require-target-coverage' in command and '--wait-for-publication' in command
    for step in ('stock_screener', 'sync_latest_quotes', 'sync_earnings_calendar'):
        assert path in ' '.join(build_pipeline_command(step, options))
    news = ' '.join(build_pipeline_command('sentiment_pipeline', options))
    # Ingestion, relevance, standard, contextual and ticker features share scope.
    assert news.count(source) >= 5
    assert '--symbol-source stock_scores_all' not in news
    assert '--symbol-source tradable-universe' not in news
    assert not cfg['latest_quotes_sync']['enabled']
    assert not cfg['earnings_calendar_sync']['enabled']


def test_interactive_sentiment_mixed_scope_unchanged():
    from ihm.services.pipeline_runner import build_pipeline_command
    command = ' '.join(build_pipeline_command('sentiment_pipeline',
        pipeline_page_default_options(trade_date='2026-10-07')))
    assert '--symbol-source stock_scores_all' in command
    assert '--symbol-source tradable-universe' in command


def calendar(close_hour=20, opened=True):
    return SimpleNamespace(sessions=lambda a, b: [SimpleNamespace(is_open=True,
        close_at_utc=datetime(a.year, a.month, a.day, close_hour, tzinfo=UTC))] if opened else [])


def test_default_first_nine_not_training_or_orders():
    steps = us_pipeline.selected_steps(list(range(1,10)))
    assert [s.num for s in steps] == [str(i) for i in range(1, 10)]
    assert not {'ml_train','ml_predict','risk','execution'} & {s.key for s in steps}
    assert 'us_pipeline' in HANDLERS


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
    monkeypatch.setattr(us_pipeline, 'session_plan', lambda now: (date(2026, 10, 7), None))
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: {'steps':list(range(1,10))})
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
    assert seen['selected_step_keys'] == tuple(s.key for s in us_pipeline.selected_steps(list(range(1,10))))
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
    spec = next(s for s in load_market_batch_specs('US_EQ') if s.name == 'us_pipeline')
    assert spec.enabled and spec.timezone == 'Europe/Paris'
    assert spec.run_hours == ('22',) and spec.run_minutes == ('45',)
    assert spec.run_days == ('1','2','3','4','5')
    assert 'us_pipeline' in build_install_command(spec)
    assert 'us_pipeline' in build_run_command(spec)


@pytest.mark.parametrize('numbers', [[], None, '1,2', [0], [13], [True], [1.0], ['10'], [1,1]])
def test_invalid_selection_rejected(numbers):
    with pytest.raises(ValueError, match='unique integers'):
        us_pipeline.selected_steps(numbers)


def test_selection_is_numeric_and_excludes_auxiliary_steps():
    steps = us_pipeline.selected_steps([12,10,11,3])
    assert [s.num for s in steps] == ['3','10','11','12']
    assert [s.key for s in steps] == ['stock_screener','ml_predict','risk_management','execution']
    assert 'us_pipeline_1_9' not in HANDLERS


def test_all_twelve_plan_without_execution(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: {'steps':list(range(1,13))})
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', lambda *a, **k: pytest.fail('started'))
    result = us_pipeline.execute_pipeline(engine, cfg, 'twelve-dry', True)
    assert result.requested == 12
    assert result.details['selected_step_numbers'] == list(range(1,13))
    assert not result.details['execution_orders']
    assert result.details['execution_mode'] == 'simulate'
    assert not result.details['training']
    assert not (tmp_path/'artifacts').exists()


def test_partial_success_uses_selected_count(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: {'steps':[9,3]})
    seen = {}
    def start(*args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(run_id='partial-workflow')
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', start)
    monkeypatch.setattr(process_registry, 'poll_pipeline_run',
        lambda run: dict(status='completed',workflow_completed_steps=2))
    result = us_pipeline.execute_pipeline(engine, cfg, 'partial', False)
    assert result.requested == result.received == result.persisted == 2
    assert seen['selected_step_keys'] == ('stock_screener','signal_aggregator')
    assert (tmp_path/'artifacts/operations/us_pipeline/partial/plan.json').exists()


def test_live_refused_before_workflow(monkeypatch, tmp_path):
    from dataclasses import replace
    engine, cfg = setup_run(monkeypatch, tmp_path)
    original = us_pipeline.pipeline_page_default_options
    monkeypatch.setattr(us_pipeline, 'pipeline_page_default_options',
        lambda **kwargs: replace(original(**kwargs), execution_mode='live'))
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', lambda *a, **k: pytest.fail('started'))
    with pytest.raises(ValueError, match='forbids LIVE'):
        us_pipeline.execute_pipeline(engine, cfg, 'live-forbidden', False)


def test_config_validation_before_workflow(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: {'steps':[13]})
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', lambda *a, **k: pytest.fail('started'))
    with pytest.raises(ValueError, match='unique integers'):
        us_pipeline.execute_pipeline(engine, cfg, 'invalid', False)


def test_twelve_success_and_failure_counts(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: {'steps':list(range(1,13))})
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow',
        lambda *a, **k: SimpleNamespace(run_id='full'))
    monkeypatch.setattr(process_registry, 'poll_pipeline_run',
        lambda run: dict(status='completed',workflow_completed_steps=12))
    assert us_pipeline.execute_pipeline(engine, cfg, 'full', False).persisted == 12
    monkeypatch.setattr(process_registry, 'poll_pipeline_run',
        lambda run: dict(status='failed',workflow_completed_steps=10))
    with pytest.raises(BatchRunError, match='10/12') as error:
        us_pipeline.execute_pipeline(engine, cfg, 'full-failure', False)
    assert error.value.outcome.persisted == 10
    assert error.value.outcome.requested == 12


def test_numbered_policy_reloaded_for_each_launch(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    current = {'steps':[1,2]}
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: current)
    assert us_pipeline.execute_pipeline(engine, cfg, 'first', True).requested == 2
    current['steps'] = [10]
    assert us_pipeline.execute_pipeline(engine, cfg, 'second', True).requested == 1


@pytest.mark.parametrize('day,key,numbers', [
    ('2026-10-05','steps',[1,2]), ('2026-10-06','steps',[1,2]),
    ('2026-10-07','steps',[1,2]), ('2026-10-08','steps',[1,2]),
    ('2026-10-09','steps_friday',[3,9]),
])
def test_step_list_chosen_from_session_weekday(day, key, numbers):
    chosen_key, steps = us_pipeline.session_steps({'steps':[2,1], 'steps_friday':[9,3]}, date.fromisoformat(day))
    assert chosen_key == key
    assert [int(s.num) for s in steps] == numbers


@pytest.mark.parametrize('numbers', [None, [], [1,1], [13], [True], ['8']])
def test_missing_or_invalid_friday_list_has_no_silent_fallback(numbers):
    with pytest.raises(ValueError, match='steps_friday.*unique integers'):
        us_pipeline.session_steps({'steps':[1,2], 'steps_friday':numbers}, date(2026, 10, 9))


def test_friday_workflow_keeps_choice_after_midnight_and_policy_edit(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    calls = []
    def session(now):
        calls.append(now)
        return date(2026,10,9), None
    monkeypatch.setattr(us_pipeline, 'session_plan', session)
    policy = {'steps':[1,2], 'steps_friday':[9,3]}
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: policy)
    seen = {}
    def start(options, **kwargs):
        seen.update(kwargs)
        assert options.trade_date == '2026-10-09'
        # Emulate a long run reaching Saturday, plus a config edit mid-run.
        policy['steps_friday'] = [8]
        return SimpleNamespace(run_id='friday-workflow')
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', start)
    monkeypatch.setattr(process_registry, 'poll_pipeline_run', lambda run: dict(status='completed',workflow_completed_steps=2))
    result = us_pipeline.execute_pipeline(engine, cfg, 'friday', False, now=datetime(2026,10,9,20,45,tzinfo=UTC))
    assert len(calls) == 1
    assert result.details['steps_configuration_source'] == 'config.yaml:us_pipeline.steps_friday'
    assert result.details['selected_step_numbers'] == [3,9]
    assert seen['selected_step_keys'] == ('stock_screener','signal_aggregator')
    assert result.persisted == result.requested == 2
    # A later run rereads the modified Friday list, the previous one stays pinned.
    assert us_pipeline.execute_pipeline(engine, cfg, 'friday-next', True).details['selected_step_numbers'] == [8]


def test_friday_holiday_still_skips_without_start(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'session_plan', lambda now: (date(2026,7,3),'NON_TRADING_DAY'))
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', lambda *a, **k: pytest.fail('holiday start'))
    assert us_pipeline.execute_pipeline(engine, cfg, 'holiday-friday', False).requested == 0


def test_installer_handles_legacy_task_without_touching_running_job():
    path = Path(__file__).resolve().parents[1]/'scripts/windows/install_forward_pit_task.ps1'
    source = path.read_text(encoding='utf-8')
    assert "if ($BatchName -eq 'us_pipeline')" in source
    assert "[string]$legacyTask.State -eq 'Running'" in source
    assert '$_.WorkingDirectory -eq $workspace' in source
    assert 'Stop-ScheduledTask' not in source


def test_paper_options_and_account_reach_workflow_and_commands(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: {
        'steps':[10,11,12], 'execution_mode':'paper', 'account_id':'default'})
    verified = []
    monkeypatch.setattr(us_pipeline, 'require_paper_account', verified.append)
    seen = {}
    def start(options, **kwargs):
        seen['options'] = options
        seen['before_step'] = kwargs['before_step']
        return SimpleNamespace(run_id='paper-test')
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', start)
    monkeypatch.setattr(process_registry, 'poll_pipeline_run',
        lambda run: dict(status='completed',workflow_completed_steps=3))
    result = us_pipeline.execute_pipeline(engine, cfg, 'paper', False)
    assert verified == ['default']
    assert seen['options'].execution_mode == 'paper'
    assert seen['options'].account_id == 'default'
    command = result.details['steps'][-1]['command']
    assert 'paper' in command
    assert command[command.index('--account')+1] == 'default'
    assert result.details['watcher_before_execution'] is True
    from service.forward_pit import watcher_startup
    import threading
    watcher = []
    monkeypatch.setattr(watcher_startup, 'ensure_watcher',
                        lambda engine, options, **kw: watcher.append(options.account_id) or {'status':'READY'})
    event = threading.Event()
    steps = us_pipeline.selected_steps([10,11,12])
    assert seen['before_step'](steps[0], seen['options'], event) is None
    assert seen['before_step'](steps[1], seen['options'], event) is None
    assert not watcher
    assert seen['before_step'](steps[2], seen['options'], event) == {'status':'READY'}
    assert watcher == ['default']


def test_paper_without_broker_steps_needs_no_credentials(monkeypatch, tmp_path):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: {
        'steps':[1,2], 'execution_mode':'paper', 'account_id':'default'})
    monkeypatch.setattr(us_pipeline, 'require_paper_account', lambda account: pytest.fail('broker lookup'))
    result = us_pipeline.execute_pipeline(engine, cfg, 'collect-only', True)
    assert result.details['execution_mode'] == 'paper'
    assert not result.details['execution_orders']


@pytest.mark.parametrize('mode', ['live', 'LIVE', None, True, 'unknown'])
def test_invalid_configured_execution_mode_blocked(monkeypatch, tmp_path, mode):
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: {
        'steps':[12], 'execution_mode':mode, 'account_id':'default'})
    with pytest.raises(ValueError, match='simulate or paper'):
        us_pipeline.execute_pipeline(engine, cfg, 'bad-mode', True)


@pytest.mark.parametrize('account', ['', ' ', None, True])
def test_invalid_account_identifier_blocked(account):
    with pytest.raises(ValueError, match='account_id'):
        us_pipeline.execution_options(pipeline_page_default_options(trade_date='2026-10-07'),
            {'execution_mode':'paper', 'account_id':account}, us_pipeline.selected_steps([12]))


def test_real_account_rejected_before_workflow(monkeypatch, tmp_path):
    from service.alpaca.accounts import AccountRegistry
    engine, cfg = setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(us_pipeline, 'load_pipeline_policy', lambda: {
        'steps':[12], 'execution_mode':'paper', 'account_id':'default'})
    monkeypatch.setattr(AccountRegistry, '__init__', lambda self: None)
    monkeypatch.setattr(AccountRegistry, 'resolve', lambda self, account: SimpleNamespace(mode='live'))
    monkeypatch.setattr(process_registry, 'start_pipeline_workflow', lambda *a, **k: pytest.fail('started'))
    with pytest.raises(ValueError, match='configured in paper'):
        us_pipeline.execute_pipeline(engine, cfg, 'real-account', False)


def test_paper_account_registry_resolution_without_network(monkeypatch):
    from service.alpaca.accounts import AccountRegistry
    monkeypatch.setattr(AccountRegistry, '__init__', lambda self: None)
    monkeypatch.setattr(AccountRegistry, 'resolve', lambda self, account: SimpleNamespace(mode='paper'))
    us_pipeline.require_paper_account('default')
