"""No real API, database or broker is used by these regression tests."""
import copy
import json
from dataclasses import replace
from datetime import datetime, date, timedelta, timezone
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine, update
from service.llm_directional.config import FilterConfig, load_filter_config
from service.llm_directional.openai_client import build_request, ResponsesClient
from service.llm_directional.repository import metadata, Repository, runs, assessments, dumps, digest
from service.llm_directional.validation import parse_response, select_symbols
from service.llm_directional import runner


NOW = datetime(2026, 10, 7, 22, 0)


def response(symbol='ABC', confidence=.9, decision='LONG'):
    sources = [{'url': f'https://example.com/{i}', 'title': f'Primary {i}',
                'published_at': '2026-10-07T18:00:00Z'} for i in range(2)]
    value = dict(symbol=symbol, issuer='ABC Corporation', identity_verified=True,
                 confidence=confidence, decision=decision, bull_case='New guidance',
                 bear_case='Execution risk', catalysts=['Results'], sources=sources)
    return {'id': 'resp_test', 'status': 'completed', 'model': 'gpt-6.1-sol', 'output': [
        {'type': 'web_search_call', 'status': 'completed', 'action': {'sources': sources}},
        {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


@pytest.mark.parametrize('kwargs', [
    {'oracle_top_n': 0}, {'oracle_top_n': True}, {'oracle_top_n': 101},
    {'max_selected': 11}, {'max_selected': -1}, {'max_selected': 2.5},
    {'min_confidence': float('nan')}, {'min_confidence': 1.1}, {'min_sources': 0},
    {'account_id': 'test1'}, {'timeout_seconds': 0}, {'enabled': 'true'},
    {'default_symbol_source': ''}, {'default_symbol_source': None},
    {'default_oracle_batch_id': ''}, {'default_oracle_batch_id': '../batch'},
])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        FilterConfig(**kwargs)


def test_parameters_and_zero_selection():
    cfg = FilterConfig(oracle_top_n=30, max_selected=7)
    items = [dict(symbol=f'S{i}', confidence=.9, oracle_rank=i, eligible=True) for i in range(20)]
    assert len(select_symbols(items, cfg)) == 7
    assert select_symbols(items, replace(cfg, max_selected=0)) == []
    assert select_symbols([], cfg) == []
    assert FilterConfig().oracle_top_n == 10
    assert FilterConfig().max_selected == 5


def test_actual_yaml_defaults():
    cfg = load_filter_config()
    assert (cfg.oracle_top_n, cfg.model) == (10, 'gpt-6.1-sol')
    # Deployment max_selected is user-configurable (currently 3); factory default
    # remains 5, tested separately. Never overwrite a user's YAML to satisfy a test.
    assert 0 <= cfg.max_selected <= cfg.oracle_top_n
    assert cfg.enabled
    assert cfg.default_symbol_source == 'universe-file:univers_filtred_tradable.txt'
    assert cfg.default_oracle_batch_id == 'model-factory-20261003082853-e98332'


def test_custom_selection_defaults_from_yaml(tmp_path):
    path = tmp_path / 'config.yaml'
    path.write_text('llm_directional_filter:\n  default_symbol_source: universe-file:other.txt\n'
                    '  default_oracle_batch_id: other-batch\n', encoding='utf-8')
    cfg = load_filter_config(path)
    assert cfg.default_symbol_source == 'universe-file:other.txt'
    assert cfg.default_oracle_batch_id == 'other-batch'


def test_llm_explicit_batch_and_universe_override_legacy_defaults():
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    cfg = load_filter_config()
    opts = PipelineLaunchOptions(llm_filter_enabled=True,
        ml_predict_batch_id=cfg.default_oracle_batch_id,
        ml_live_predict_batch_id='stale-legacy-batch',
        ml_predict_symbol_source=cfg.default_symbol_source)
    command = build_pipeline_command('ml_predict', opts)
    assert command[command.index('--batch-id') + 1] == cfg.default_oracle_batch_id
    assert command[command.index('--symbol-source') + 1] == cfg.default_symbol_source
    inner = json.loads(command[command.index('--command-json') + 1])
    assert inner[inner.index('--batch-id') + 1] == cfg.default_oracle_batch_id
    assert inner[inner.index('--symbol-source') + 1] == cfg.default_symbol_source
    manual = build_pipeline_command('ml_predict', replace(opts,
        ml_predict_batch_id='manual-batch', ml_predict_symbol_source='universe-file:manual.txt'))
    assert manual[manual.index('--batch-id') + 1] == 'manual-batch'
    assert manual[manual.index('--symbol-source') + 1] == 'universe-file:manual.txt'


def test_request_only_web_search_and_no_credentials(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'do-not-leak-test')
    request = build_request({'symbol': 'ABC'}, FilterConfig())
    assert request['model'] == 'gpt-6.1-sol'
    assert request['tools'][0]['type'] == 'web_search'
    assert request['tool_choice'] == 'required'
    assert request['store'] is False
    assert 'do-not-leak-test' not in dumps(request)
    assert 'do-not-leak-test' not in dumps(FilterConfig().snapshot())


def test_valid_response():
    result = parse_response(response(), 'ABC', FilterConfig(), NOW)
    assert result['eligible'] and not result['source_timestamps_verified']


@pytest.mark.parametrize('mutation', ['missing_search', 'wrong_symbol', 'unverified_identity',
    'fake_url', 'no_timezone', 'incomplete', 'nan', 'extra_field', 'refusal'])
def test_invalid_response(mutation):
    raw = response()
    value = json.loads(raw['output'][1]['content'][0]['text'])
    if mutation == 'missing_search':
        raw['output'][0]['status'] = 'failed'
    elif mutation == 'wrong_symbol':
        value['symbol'] = 'OTHER'
    elif mutation == 'unverified_identity':
        value['identity_verified'] = False
    elif mutation == 'fake_url':
        value['sources'][0]['url'] = 'https://invented.example/source'
    elif mutation == 'no_timezone':
        value['sources'][0]['published_at'] = '2026-10-07'
    elif mutation == 'incomplete':
        raw['status'] = 'incomplete'
    elif mutation == 'nan':
        value['confidence'] = float('nan')
    elif mutation == 'extra_field':
        value['place_order'] = True
    elif mutation == 'refusal':
        raw['output'][1]['content'].append({'type': 'refusal'})
    raw['output'][1]['content'][0]['text'] = json.dumps(value)
    with pytest.raises(Exception):
        parse_response(raw, 'ABC', FilterConfig(), NOW)


@pytest.mark.parametrize('kind', ['old', 'future', 'null', 'abstain', 'low_score'])
def test_unqualified_evidence_abstains(kind):
    raw = response(confidence=.5 if kind == 'low_score' else .9,
                   decision='ABSTAIN' if kind == 'abstain' else 'LONG')
    value = json.loads(raw['output'][1]['content'][0]['text'])
    if kind in {'old', 'future', 'null'}:
        for source in value['sources']:
            source['published_at'] = {'old': '2020-01-01T00:00:00Z',
                'future': '2027-01-01T00:00:00Z', 'null': None}[kind]
    raw['output'][1]['content'][0]['text'] = json.dumps(value)
    assert not parse_response(raw, 'ABC', FilterConfig(), NOW)['eligible']


@pytest.fixture
def isolated(monkeypatch):
    engine = create_engine('sqlite://')
    metadata.create_all(engine)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            aware = NOW.replace(tzinfo=timezone.utc)
            return aware.astimezone(tz) if tz else NOW
    monkeypatch.setattr(runner, 'datetime', Clock)
    monkeypatch.setattr(runner, 'utcnow', lambda: NOW)
    import service.llm_directional.repository as repository
    monkeypatch.setattr(repository, 'utcnow', lambda: NOW)
    monkeypatch.setattr(runner, 'assert_paper_account', lambda account='default': None)
    import common.market_calendar as calendar
    monkeypatch.setattr(calendar, 'is_trading_day', lambda day: True)
    monkeypatch.setattr(calendar, 'get_nyse_session_bounds', lambda day: (
        NOW.replace(hour=13, tzinfo=timezone.utc), NOW.replace(hour=20, tzinfo=timezone.utc)))
    yield engine
    engine.dispose()


def analyze(engine, client, run_id='test-run', **kwargs):
    contexts = [dict(symbol=symbol, oracle_rank=i+1, oracle_score=.9-i*.1)
                for i, symbol in enumerate(['ABC', 'XYZ'])]
    return runner.analyze(engine=engine, batch_id='batch-test', trade_date=date(2026, 10, 7),
        symbol_source='universe-file:test.txt', config=FilterConfig(enabled=True, max_selected=1),
        inputs=contexts, client=client, run_id=run_id, check_account=False, **kwargs)


def test_persist_all_candidates_and_selection(isolated):
    result = analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    assert result['selected'] == ['ABC']
    run, items = Repository(isolated).get('test-run')
    assert run['status'] == 'COMPLETED'
    assert len(items) == 2 and sum(i['selected'] for i in items) == 1
    assert all(i['response_sha256'] for i in items)
    _, selected = runner.qualified_selection(isolated, 'test-run', date(2026, 10, 7), 'default', now=NOW)
    assert selected[0]['symbol'] == 'ABC'


@pytest.mark.parametrize('field,value', [
    ('oracle_rank', 99), ('oracle_score', .01), ('request_json', '{}'),
])
def test_archived_ranking_and_request_match_input_snapshot(isolated, field, value):
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    with isolated.begin() as conn:
        conn.execute(update(assessments).where(assessments.c.symbol == 'ABC').values(**{field: value}))
    with pytest.raises(ValueError, match='snapshot'):
        runner.qualified_selection(isolated, 'test-run', date(2026, 10, 7), 'default', now=NOW)


def test_raw_persisted_before_validation(isolated, monkeypatch):
    original = runner.parse_response
    def parsing(raw, symbol, config, observed):
        _, items = Repository(isolated).get('test-run')
        item = next(i for i in items if i['symbol'] == symbol)
        assert item['status'] == 'RECEIVED'
        assert item['response_sha256'] == digest(raw)
        return original(raw, symbol, config, observed)
    monkeypatch.setattr(runner, 'parse_response', parsing)
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))


def test_partial_failure_fails_closed_and_keeps_raw(isolated):
    def client(request):
        symbol = json.loads(request['input'])['symbol']
        return response(symbol) if symbol == 'ABC' else {'status': 'incomplete'}
    with pytest.raises(RuntimeError):
        analyze(isolated, client)
    run, items = Repository(isolated).get('test-run')
    assert run['status'] == 'FAILED' and json.loads(run['selected_json']) == []
    assert len(items) == 2 and not any(i['selected'] for i in items)
    assert items[1]['response_json']
    with pytest.raises(ValueError):
        runner.qualified_selection(isolated, 'test-run', date(2026, 10, 7), 'default', now=NOW)


def test_no_duplicate_analysis_or_implicit_retry(isolated):
    calls = []
    def client(request):
        calls.append(request)
        return response(json.loads(request['input'])['symbol'])
    analyze(isolated, client)
    with pytest.raises(Exception):
        analyze(isolated, client)
    assert len(calls) == 2


def test_expired_and_wrong_scope_rejected(isolated):
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    for day, account, now in [(date(2026,10,6), 'default', NOW),
        (date(2026,10,7), 'test1', NOW), (date(2026,10,7), 'default', NOW+timedelta(days=2))]:
        with pytest.raises(ValueError):
            runner.qualified_selection(isolated, 'test-run', day, account, now=now)


def test_tampered_response_rejected(isolated):
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    with isolated.begin() as conn:
        conn.execute(update(assessments).where(assessments.c.symbol=='ABC').values(response_json='{}'))
    with pytest.raises(ValueError, match='altérée'):
        runner.qualified_selection(isolated, 'test-run', date(2026,10,7), 'default', now=NOW)


def test_no_risk_rebinding_or_double_execution(isolated):
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    repo = Repository(isolated)
    repo.bind_risk('test-run', 'risk-1')
    with pytest.raises(ValueError):
        repo.bind_risk('test-run', 'risk-2')
    repo.claim_execution('test-run')
    with pytest.raises(ValueError):
        repo.claim_execution('test-run')


def test_missing_key_and_sanitized_api_error(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='absente'):
        ResponsesClient(FilterConfig())
    monkeypatch.setenv('OPENAI_API_KEY', 'TEST-SECRET')
    import service.llm_directional.openai_client as module
    session = SimpleNamespace(post=lambda *a, **k: SimpleNamespace(
        status_code=401, headers={'x-request-id': 'req1'}, text='TEST-SECRET'))
    with pytest.raises(RuntimeError) as exc:
        ResponsesClient(FilterConfig(), session=session)({})
    assert '401' in str(exc.value) and 'TEST-SECRET' not in str(exc.value)


def test_account_live_forbidden(monkeypatch):
    from service.alpaca.accounts import AccountRegistry
    monkeypatch.setattr(AccountRegistry, 'get', lambda: SimpleNamespace(resolve=lambda account:
        SimpleNamespace(account_id='default', mode='live')))
    # Use imported original function: isolated fixture does not apply in this test.
    with pytest.raises(ValueError, match='PAPER'):
        runner.assert_paper_account()


def test_pipeline_opt_in_and_paper_command():
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    opts = PipelineLaunchOptions(ml_predict_batch_id='oracle-batch', trade_date='2026-10-07',
        llm_filter_enabled=True, llm_filter_run_id='llm-test', account_id='default')
    for step, phase in [('ml_predict', 'predict'), ('risk_management', 'risk'), ('execution', 'execute')]:
        command = build_pipeline_command(step, opts)
        assert 'service.llm_directional.pipeline' in command
        assert command[command.index('--phase')+1] == phase
        original = json.loads(command[command.index('--command-json')+1])
        if phase == 'execute':
            assert original[3] == 'paper'
    legacy = build_pipeline_command('ml_predict', replace(opts, llm_filter_enabled=False))
    assert 'service.llm_directional.pipeline' not in legacy


@pytest.mark.parametrize('override', [dict(execution_mode='live'), dict(account_id='test1'),
    dict(risk_enable_kelly=True), dict(allow_outside_rth=True), dict(auto_rebalance=True),
    dict(ml_oracle_shadow=True), dict(ml_predict_use_historical_range=True)])
def test_pipeline_unsafe_options_rejected(override):
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    opts = PipelineLaunchOptions(ml_predict_batch_id='batch', llm_filter_enabled=True, **override)
    with pytest.raises(ValueError):
        build_pipeline_command('ml_predict', opts)


def test_risk_adapter_never_makes_probability(isolated):
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    from service.llm_directional.risk_adapter import load_candidates
    candidates = load_candidates(isolated, 'test-run', date(2026,10,7), 'default', 'u1', ['ABC'])
    assert len(candidates) == 1
    assert candidates[0].p_side == candidates[0].p_long == 0
    assert candidates[0].lineage['confidence_uncalibrated'] == .9


def test_mysql_schema_compiles_and_has_no_secret():
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects.mysql import dialect
    sql = '\n'.join(str(CreateTable(t).compile(dialect=dialect())) for t in metadata.sorted_tables)
    assert sql.count('CREATE TABLE') == 3
    assert 'LONGTEXT' in sql and 'api_key' not in sql


def test_verified_tls_cannot_be_disabled():
    from common.verified_http import VerifiedTLSAdapter
    import ssl
    adapter = VerifiedTLSAdapter()
    assert adapter.context.verify_mode == ssl.CERT_REQUIRED
    assert adapter.context.check_hostname
    with pytest.raises(ValueError):
        adapter.build_connection_pool_key_attributes(None, False)


def test_risk_claim_is_single_use(isolated):
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    repo = Repository(isolated)
    repo.claim_risk('test-run')
    with pytest.raises(ValueError):
        repo.claim_risk('test-run')


def test_filtered_report_preserves_rejected_candidates(isolated):
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    from service.llm_directional.report import report
    result = report(isolated, 'test-run')
    assert len(result['candidates']) == 2
    assert result['candidates'][1]['selected'] is False
    assert result['configuration']['oracle_top_n'] == 10
    assert result['configuration']['max_selected'] == 1


def test_model_error_is_not_silently_retried(monkeypatch):
    import requests
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret')
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs)
        raise requests.Timeout('test-secret-must-not-be-echoed')
    with pytest.raises(RuntimeError) as exc:
        ResponsesClient(FilterConfig(), session=SimpleNamespace(post=post))({})
    assert len(calls) == 1 and 'test-secret' not in str(exc.value)


def test_raw_verdict_tamper_detected(isolated):
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    _, items = Repository(isolated).get('test-run')
    altered = json.loads(items[0]['assessment_json'])
    altered['confidence'] = .99
    with isolated.begin() as conn:
        conn.execute(update(assessments).where(assessments.c.symbol=='ABC').values(assessment_json=dumps(altered)))
    with pytest.raises(ValueError, match='incohérent'):
        runner.qualified_selection(isolated, 'test-run', date(2026,10,7), 'default', now=NOW)


def test_real_portfolio_adapter_has_no_probability_or_kelly():
    import pandas as pd
    from risk_management.config import RiskConfig
    from risk_management.models import PriceInfo
    from risk_management.portfolio_builder import PortfolioBuilder
    from risk_management.operational_data import BacktestOperationalDataAdapter
    from risk_management.selection_contract import MLRankedCandidate
    from service.market.models import neutral_snapshot
    from service.llm_directional.risk_adapter import build_entries
    day = date(2026,10,7)
    builder = PortfolioBuilder(RiskConfig(account_equity=4000, min_breakout_days=1,
        min_position_notional=0, max_positions=8, max_position_weight=.25, max_sector_weight=.5),
        regime_snapshot=neutral_snapshot(day), sector_map={'ABC': 'Tech'})
    builder.set_operational_snapshot(BacktestOperationalDataAdapter.build(account_id='default',
        account={'equity': 4000., 'cash': 4000., 'buying_power': 4000.},
        as_of=NOW.replace(tzinfo=timezone.utc)))
    candidate = MLRankedCandidate('ABC', day, 'long', model_run_id='oracle', side_rank=1,
        lineage={'confidence_uncalibrated': .9, 'llm_filter_run_id': 'llm-test'})
    entries = build_entries(builder, [candidate], {'ABC': PriceInfo('ABC', 100., 2., day, day, 1000000.)},
                            {'ABC': 'Tech'}, day, pd.DataFrame())
    assert entries and entries[0].approved_shares > 0
    assert entries[0].predicted_proba is None
    assert entries[0].effective_probability is None and entries[0].kelly_fraction is None
    assert entries[0].score_source == 'llm_confidence_uncalibrated'


def test_pipeline_risk_to_execution_uses_exact_run_and_cannot_double_send(isolated, monkeypatch, tmp_path):
    import sys
    from sqlalchemy import text
    from service.llm_directional import pipeline
    import database.connection as connection
    import service.alpaca.trading_client as trading
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    monkeypatch.setattr(pipeline, 'assert_paper_account', lambda: None)
    monkeypatch.setattr(connection, 'get_sqlalchemy_engine', lambda: isolated)
    monkeypatch.setattr(trading, 'AlpacaTradingClient', lambda **kwargs: SimpleNamespace(get_positions=lambda: []))
    monkeypatch.chdir(tmp_path)
    calls = []
    def launch(command, **kwargs):
        calls.append(command)
        if '--summary-path' in command:
            from pathlib import Path
            path = Path(command[command.index('--summary-path')+1])
            path.write_text(json.dumps({'run_id': 'risk-exact', 'dry_run': False, 'run_mode': 'paper'}), encoding='utf-8')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(pipeline.subprocess, 'run', launch)
    base = ['program', '--run-id', 'test-run', '--trade-date', '2026-10-07']
    monkeypatch.setattr(sys, 'argv', [*base, '--phase', 'risk', '--command-json',
        json.dumps([sys.executable, '-u', '-m', 'risk_management'])])
    pipeline.main()
    run, _ = Repository(isolated).get('test-run')
    assert run['risk_run_id'] == 'risk-exact'
    with isolated.begin() as conn:
        conn.execute(text('CREATE TABLE portfolio_targets (run_id TEXT, symbol TEXT, side TEXT, shares REAL, trade_date TEXT, account_id TEXT)'))
        conn.execute(text("INSERT INTO portfolio_targets VALUES ('risk-exact','ABC','long',1,'2026-10-07','default')"))
    monkeypatch.setattr(sys, 'argv', [*base, '--phase', 'execute', '--command-json',
        json.dumps([sys.executable, '-u', 'run_execution.py', 'paper'])])
    pipeline.main()
    assert calls[-1][calls[-1].index('--run-id')+1] == 'risk-exact'
    assert calls[-1][3] == 'paper'
    with pytest.raises(ValueError):
        pipeline.main()
    assert len(calls) == 2  # One risk + one mock execution, no duplicate broker submission.


def test_historical_web_analysis_rejected_before_calls(isolated):
    with pytest.raises(ValueError, match='prospective'):
        runner.analyze(engine=isolated, batch_id='b', trade_date='2025-01-02',
            symbol_source='stock-bars-daily', config=FilterConfig(enabled=True),
            client=lambda request: pytest.fail('No historical web calls'))


def test_preclose_analysis_rejected(isolated, monkeypatch):
    class PrecloseClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 7, 19, tzinfo=timezone.utc)
    monkeypatch.setattr(runner, 'datetime', PrecloseClock)
    with pytest.raises(ValueError, match='clôture'):
        analyze(isolated, lambda request: pytest.fail('No preclose calls'))


@pytest.mark.parametrize('day,instant', [
    ('2026-10-08', '2026-10-09T08:00:00+02:00'),
    ('2026-10-09', '2026-10-12T08:00:00+02:00'),
    ('2026-01-16', '2026-01-20T08:00:00+01:00'),
    ('2026-10-30', '2026-11-02T08:00:00+01:00'),
])
def test_analysis_accepts_overnight_weekend_holiday_and_dst(day, instant):
    runner.validate_analysis_window(date.fromisoformat(day), now=datetime.fromisoformat(instant))


@pytest.mark.parametrize('instant', ['2026-10-09T15:30:00+02:00', '2026-10-09T16:00:00+02:00'])
def test_analysis_rejects_at_or_after_next_open(instant):
    with pytest.raises(ValueError, match='suivante'):
        runner.validate_analysis_window(date(2026, 10, 8), now=datetime.fromisoformat(instant))


def test_analysis_rejects_non_session_and_naive_time():
    with pytest.raises(ValueError, match='hors séance'):
        runner.validate_analysis_window(date(2026, 10, 10), now=datetime(2026, 10, 11, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match='timezone'):
        runner.validate_analysis_window(date(2026, 10, 8), now=NOW)


def test_analysis_crossing_next_open_never_publishes(isolated, monkeypatch):
    checks = []
    def window(day):
        checks.append(day)
        if len(checks) == 2:
            raise ValueError('La séance suivante a déjà ouvert')
    monkeypatch.setattr(runner, 'validate_analysis_window', window)
    with pytest.raises(ValueError, match='suivante'):
        analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    run, _ = Repository(isolated).get('test-run')
    assert run['status'] == 'FAILED'
    assert json.loads(run['selected_json']) == []


def test_inputs_rank_predicted_score_not_future_returns_and_respect_scope(isolated, monkeypatch):
    from sqlalchemy import text
    import modelFactory.db_registry as registry
    import modelFactory.oracle.artifact_contract as artifact
    monkeypatch.setattr(registry, 'load_symbols_for_source', lambda *a, **k: ['AAA', 'BBB', 'CCC'])
    monkeypatch.setattr(artifact, 'resolve_oracle_artifact_horizon', lambda *a: 20)
    with isolated.begin() as conn:
        conn.execute(text('CREATE TABLE oracle_extreme_predictions (symbol TEXT, proba_extreme REAL, prediction_date TEXT, batch_id TEXT, future_return REAL)'))
        conn.execute(text('CREATE TABLE stock_bars_daily (symbol TEXT, date TEXT, close REAL, is_filled INT)'))
        conn.execute(text('CREATE TABLE stock_metadata (symbol TEXT, company_name TEXT, exchange TEXT)'))
        for symbol, score, future in [('AAA', .8, 100.), ('BBB', .9, -5.), ('CCC', .9, 2.), ('OTHER', 1., 10.)]:
            conn.execute(text('INSERT INTO oracle_extreme_predictions VALUES (:s,:p,:d,:b,:r)'),
                {'s':symbol,'p':score,'d':'2026-10-07','b':'b','r':future})
            conn.execute(text('INSERT INTO stock_bars_daily VALUES (:s,:d,100,0)'), {'s':symbol,'d':'2026-10-07'})
            conn.execute(text('INSERT INTO stock_bars_daily VALUES (:s,:d,999,0)'), {'s':symbol,'d':'2027-01-01'})
            conn.execute(text('INSERT INTO stock_metadata VALUES (:s,:n,:e)'), {'s':symbol,'n':symbol+' Corp','e':'NASDAQ'})
    contexts = runner.load_inputs(isolated, 'b', date(2026,10,7), 'test',
        FilterConfig(oracle_top_n=2,max_selected=1), 'capital_2001_5000')
    assert [item['symbol'] for item in contexts] == ['BBB', 'CCC']
    assert 'future_return' not in dumps(contexts) and '999' not in dumps(contexts)
    with isolated.begin() as conn:
        conn.execute(text("DELETE FROM oracle_extreme_predictions WHERE symbol='AAA'"))
    with pytest.raises(ValueError, match='Couverture Oracle'):
        runner.load_inputs(isolated, 'b', date(2026,10,7), 'test', FilterConfig(), 'capital_2001_5000')


def test_wrong_oracle_horizon_is_not_silently_used(isolated, monkeypatch):
    import modelFactory.oracle.artifact_contract as artifact
    monkeypatch.setattr(artifact, 'resolve_oracle_artifact_horizon', lambda *a: 5)
    with pytest.raises(ValueError, match='Horizon Oracle'):
        runner.load_inputs(isolated, 'b', date(2026,10,7), 'test', FilterConfig(), 'capital_2001_5000')


def test_evaluation_all_candidates_maturity_and_no_duplicates(isolated, monkeypatch):
    import pandas as pd
    from sqlalchemy import text
    import common.market_calendar as calendar
    from service.llm_directional.evaluate import evaluate
    analyze(isolated, lambda request: response(json.loads(request['input'])['symbol']))
    monkeypatch.setattr(calendar, '_get_nyse_calendar', lambda: SimpleNamespace(
        schedule=lambda start_date,end_date: pd.DataFrame(index=pd.bdate_range(start_date,end_date))))
    days = pd.bdate_range('2026-10-07', periods=6)
    with isolated.begin() as conn:
        conn.execute(text('CREATE TABLE stock_bars_daily (symbol TEXT, date TEXT, open REAL, close REAL, adj_close REAL, is_filled INT)'))
        conn.execute(text('CREATE TABLE global_oracle_labels (symbol TEXT, prediction_date TEXT, batch_id TEXT, horizon INT, oracle_decile INT, oracle_available_date TEXT, target_quality_valid INT)'))
        for symbol in ['ABC', 'XYZ']:
            for i, day in enumerate(days):
                price = 110. if i == 5 else 100.
                conn.execute(text('INSERT INTO stock_bars_daily VALUES (:s,:d,100,:p,:p,0)'),
                    {'s':symbol,'d':day.date().isoformat(),'p':price})
            conn.execute(text('INSERT INTO global_oracle_labels VALUES (:s,:d,:b,5,10,:a,1)'),
                {'s':symbol,'d':'2026-10-07','b':'batch-test','a':'2026-10-15'})
    pending = evaluate(isolated, 'test-run', as_of=date(2026,10,10), horizons=(5,))
    assert len(pending['pending']) == 2 and not pending['evaluated']
    result = evaluate(isolated, 'test-run', as_of=date(2026,10,30), horizons=(5,))
    assert len(result['evaluated']) == 2
    assert result['evaluated'][0][2] == pytest.approx(10.)
    assert result['evaluated'][0][3] == 10
    assert sum(row[4] for row in result['evaluated']) == 1
    again = evaluate(isolated, 'test-run', as_of=date(2026,10,30), horizons=(5,))
    assert not again['evaluated']  # already archived evaluations are not reinserted
