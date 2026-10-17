"""Telegram stage details: local SQL fixtures and fake transport, never real orders/API."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text

from service import pipeline_telegram as alerts


@pytest.fixture(autouse=True)
def transport(monkeypatch, tmp_path):
    monkeypatch.setattr(alerts, 'OUTBOX', tmp_path / 'outbox')
    monkeypatch.setattr(alerts.telegram, 'is_telegram_configured', lambda: True)
    monkeypatch.setattr(alerts.telegram, 'get_default_chat_id', lambda: 'test-chat')
    sender = Mock(return_value=True)
    monkeypatch.setattr(alerts.telegram, 'send_telegram_message', sender)
    monkeypatch.setattr(alerts.time, 'sleep', lambda seconds: None)
    return sender


def archived(provider='openai', selected=('ABC',)):
    run = dict(run_id='llm-test', trade_date='2026-10-16', account_id='default',
               status='COMPLETED', config_json=json.dumps(dict(provider=provider,
               model='gpt-test', deepseek_model='deepseek-test', max_selected=3)),
               selected_json=json.dumps(list(selected)))
    return run


def assessment(symbol='ABC', decision='LONG', blockers=(), status='VALID'):
    return dict(symbol=symbol, status=status, assessment_json=json.dumps(dict(
        decision=decision, confidence=.82, selection_blockers=list(blockers))))


def execution_summary(**updates):
    return dict(run_id='exec-1', risk_run_id='risk-1', trade_date='2026-10-16',
                account_id='default', execution_mode='paper', broker_mode='paper',
                dry_run=False, status='COMPLETED', submitted_orders=2, failed_orders=0,
                **updates)


def order(**updates):
    row = dict(symbol='ABC', side='buy', intent_role='entry', target_qty=10,
               broker_order_id='broker-1', broker_status='FILLED', request_status='SUBMITTED',
               filled_qty=10, avg_fill_price=12.5)
    return dict(row, **updates)


@pytest.mark.parametrize('provider,label,model', [('openai', 'GPT', 'gpt-test'),
                                                ('deepseek', 'DeepSeek', 'deepseek-test')])
def test_provider_and_selection_order(provider, label, model):
    run = archived(provider, ('XYZ', 'ABC'))
    message = alerts.llm_message(run, [assessment(), assessment('XYZ', 'SHORT')])
    assert label in message and model in message
    assert message.index('XYZ — SHORT') < message.index('ABC — LONG')
    assert '0.82' in message and 'pas une probabilité calibrée' in message


def test_no_selection_explains_abstentions_and_qualification():
    message = alerts.llm_message(archived(selected=()), [
        assessment(decision='ABSTAIN'),
        assessment('XYZ', blockers=('confidence_below_threshold', 'insufficient_fresh_sources',
                                   'excluded_untraceable_sources', 'short_not_allowed'))])
    assert 'Aucun titre publié' in message
    for phrase in ('ABSTAIN', 'sous le seuil', 'sources récentes', 'non traçables', 'SHORT non autorisé'):
        assert phrase in message


def test_technical_failure_is_not_valid_abstention():
    run = dict(archived(selected=()), status='FAILED')
    item = dict(symbol='XYZ', status='ERROR', assessment_json=None,
                error_message='https://secret-token.example/key')
    message = alerts.llm_message(run, [item])
    assert 'Échec technique' in message and 'pas une abstention' in message
    assert 'secret-token' not in message


def test_abstention_keeps_the_archived_arguments():
    item = assessment(decision='ABSTAIN')
    parsed = json.loads(item['assessment_json'])
    parsed.update(bull_case='Catalyseur positif mais déjà attendu.', bear_case='Risques contradictoires.')
    item['assessment_json'] = json.dumps(parsed)
    message = alerts.llm_message(archived(selected=()), [item])
    assert 'Catalyseur positif mais déjà attendu.' in message
    assert 'Risques contradictoires.' in message


def test_zero_cap_and_no_assessment():
    run = archived(selected=())
    run['config_json'] = json.dumps(dict(max_selected=0))
    message = alerts.llm_message(run, [])
    assert 'Aucune évaluation archivée' in message and 'configuré à zéro' in message


@pytest.mark.parametrize('side,role,expected', [
    ('buy', 'entry', 'LONG'), ('sell', 'entry', 'SHORT'),
    ('sell', 'exit', 'clôture/réduction LONG'),
    ('buy', 'exit', 'clôture/réduction SHORT'),
    ('sell', 'take_profit', 'clôture/réduction LONG'),
    ('buy', 'initial_stop', 'clôture/réduction SHORT'),
    ('sell', 'trailing_stop', 'clôture/réduction LONG'),
    ('sell', 'mystery', 'sens de position non qualifié'),
])
def test_direction_not_inferred_from_sell_alone(side, role, expected):
    assert expected in alerts._direction(side, role)


def test_execution_real_fills_partial_pending_and_gross_amount():
    message = alerts.execution_message(execution_summary(), [order(),
        order(symbol='XYZ', side='sell', filled_qty=2.5, avg_fill_price=20,
              target_qty=8, broker_status='PARTIALLY_FILLED'),
        order(symbol='WAIT', filled_qty=0, avg_fill_price=None, broker_status='ACCEPTED')])
    assert 'ABC — LONG — exécuté 10 à 12.5 USD — montant 125.00 USD' in message
    assert 'XYZ — SHORT — exécuté 2.5 à 20 USD — montant 50.00 USD' in message
    assert 'Total brut des exécutions à prix qualifié : 175.00 USD' in message
    assert 'WAIT — LONG — soumis, état ACCEPTED' in message
    assert 'Photographie de fin' in message and 'pas un PnL' in message


def test_pending_does_not_use_decision_or_limit_price():
    row = order(filled_qty=0, avg_fill_price=None, decision_price=999, limit_price=998,
                broker_status='NEW')
    message = alerts.execution_message(execution_summary(), [row])
    assert '999' not in message and '998' not in message
    assert 'Prix et montant exécutés encore indisponibles' in message


@pytest.mark.parametrize('bad_price', [None, 0, -1, float('nan'), float('inf')])
def test_unqualified_fill_price_never_fabricated(bad_price):
    message = alerts.execution_message(execution_summary(), [order(avg_fill_price=bad_price)])
    assert 'prix non qualifié ; montant indisponible' in message
    assert 'à prix qualifié : 0.00 USD' in message


def test_risk_no_selection_and_rejections():
    message = alerts.risk_message(dict(run_id='r', trade_date='2026-10-16',
        rejection_reason_code_counts={'REGIME_BLOCK': 2}), [], 'default')
    assert 'Aucune cible publiée' in message and 'REGIME_BLOCK : 2' in message
    assert 'pas des ordres' in message


def test_delivery_once_per_stage_run_account_and_plain_text(transport):
    for _ in range(2):
        assert alerts._deliver('10', 'run', 'default', 'ABC_LONG')
    assert transport.call_count == 1
    assert transport.call_args.kwargs['parse_mode'] is None
    alerts._deliver('11', 'run', 'default', 'risk')
    alerts._deliver('10', 'run', 'secondary', 'llm')
    assert transport.call_count == 3


def test_chunks_not_truncated_retry_only_unconfirmed_chunk(transport):
    message = '🧪' * 4000
    transport.side_effect = [True, False]
    assert not alerts._deliver('10', 'run', 'default', message)
    first = transport.call_args_list[0].args[0]
    transport.side_effect = None
    assert alerts._deliver('10', 'run', 'default', 'must not replace frozen payload')
    all_calls = [call.args[0] for call in transport.call_args_list]
    assert all_calls.count(first) == 1
    assert 'must not replace' not in ''.join(all_calls)
    assert all(len(chunk.encode('utf-16-le')) // 2 <= 3600 for chunk in all_calls)
    delivered = [first] + all_calls[2:]
    assert ''.join(chunk.split('\n', 1)[1] for chunk in delivered) == message


def test_missing_configuration_no_send(transport, monkeypatch):
    monkeypatch.setattr(alerts.telegram, 'get_default_chat_id', lambda: None)
    assert not alerts._deliver('10', 'run', 'default', 'text')
    transport.assert_not_called()


def test_transport_exception_is_redacted_and_best_effort(transport, caplog):
    transport.side_effect = RuntimeError('secret-url/bot-private-token')
    assert not alerts.notify_execution_skipped('llm', '2026-10-16', 'abstention')
    assert 'private-token' not in caplog.text


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE portfolio_targets (
            run_id TEXT, account_id TEXT, trade_date TEXT, symbol TEXT, side TEXT, shares REAL)'''))
        conn.execute(text('''CREATE TABLE execution_order_requests (
            request_id TEXT PRIMARY KEY, exec_run_id TEXT, account_id TEXT,
            symbol TEXT, side TEXT, target_qty REAL, intent_role TEXT, status TEXT, created_at TEXT)'''))
        conn.execute(text('''CREATE TABLE execution_broker_orders (
            request_id TEXT, exec_run_id TEXT, account_id TEXT, broker_order_id TEXT,
            normalized_status TEXT, filled_qty REAL, avg_fill_price REAL)'''))
    yield engine
    engine.dispose()


def test_risk_reads_exact_run_account_date(db, transport):
    with db.begin() as conn:
        for run, account, day, symbol, side, qty in [
            ('r1', 'default', '2026-10-16', 'YES', 'sell', 3),
            ('other', 'default', '2026-10-16', 'WRONGRUN', 'buy', 1),
            ('r1', 'second', '2026-10-16', 'WRONGACCOUNT', 'buy', 1),
            ('r1', 'default', '2026-10-15', 'WRONGDAY', 'buy', 1),
            ('r1', 'default', '2026-10-16', 'ZERO', 'buy', 0)]:
            conn.execute(text('INSERT INTO portfolio_targets VALUES (:r,:a,:d,:s,:side,:q)'),
                         dict(r=run, a=account, d=day, s=symbol, side=side, q=qty))
    assert alerts.notify_risk(db, dict(run_id='r1', trade_date='2026-10-16',
                                      run_mode='paper', dry_run=False), 'default')
    message = transport.call_args.args[0]
    assert 'YES — SHORT' in message
    for symbol in ('WRONGRUN', 'WRONGACCOUNT', 'WRONGDAY', 'ZERO'):
        assert symbol not in message


def test_execution_reads_exact_oms_run_account_and_no_writes(db, transport):
    with db.begin() as conn:
        for request, run, account, symbol in [('q1', 'exec-1', 'default', 'YES'),
            ('q2', 'other', 'default', 'WRONGRUN'), ('q3', 'exec-1', 'other', 'WRONGACCOUNT')]:
            conn.execute(text('INSERT INTO execution_order_requests VALUES '
                '(:q,:r,:a,:s,"buy",10,"entry","SUBMITTED","now")'),
                dict(q=request, r=run, a=account, s=symbol))
            conn.execute(text('INSERT INTO execution_broker_orders VALUES '
                '(:q,:r,:a,:q,"FILLED",10,12.5)'), dict(q=request, r=run, a=account))
    assert alerts.notify_execution(db, execution_summary())
    message = transport.call_args.args[0]
    assert 'YES — LONG — exécuté 10 à 12.5' in message
    assert 'WRONGRUN' not in message and 'WRONGACCOUNT' not in message
    with db.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM execution_order_requests')).scalar() == 3


@pytest.mark.parametrize('kind', ['dry', 'live', 'simulate', 'non-us'])
def test_execution_guards(db, transport, kind):
    summary = execution_summary()
    if kind == 'dry':
        summary['dry_run'] = True
    elif kind == 'live':
        summary['broker_mode'] = 'live'
    elif kind == 'simulate':
        summary['execution_mode'] = 'simulate'
    else:
        db = SimpleNamespace(dialect=SimpleNamespace(name='mysql'),
                             url=SimpleNamespace(database='alpha_trade_fr'))
    assert not alerts.notify_execution(db, summary)
    transport.assert_not_called()


@pytest.mark.parametrize('mode,dry', [('shadow', True), ('live', False), ('backtest', False), ('paper', True)])
def test_risk_guards(db, transport, mode, dry):
    assert not alerts.notify_risk(db, dict(run_id='r', trade_date='2026-10-16',
                                         run_mode=mode, dry_run=dry), 'default')
    transport.assert_not_called()


def test_missing_oms_is_not_a_false_zero_execution(transport):
    engine = create_engine('sqlite://')
    assert not alerts.notify_execution(engine, execution_summary())
    transport.assert_not_called()
    engine.dispose()


def test_llm_notification_uses_archived_run_only(db, transport, monkeypatch):
    repo = Mock()
    repo.get.return_value = archived('deepseek'), [assessment()]
    monkeypatch.setattr('service.llm_directional.repository.Repository', lambda engine: repo)
    assert alerts.notify_llm(db, 'llm-test')
    repo.get.assert_called_once_with('llm-test')
    assert 'DeepSeek' in transport.call_args.args[0]


def test_failed_retry_does_not_announce_an_old_selection(db, transport, monkeypatch):
    from datetime import datetime
    run = dict(archived(), started_at=datetime(2026, 10, 15))
    repo = Mock()
    repo.get.return_value = run, [assessment()]
    monkeypatch.setattr('service.llm_directional.repository.Repository', lambda engine: repo)
    assert alerts.notify_llm(db, 'llm-test', attempted_at=datetime(2026, 10, 16),
                            trade_date='2026-10-16', provider_label='GPT')
    message = transport.call_args.args[0]
    assert 'Aucune nouvelle sélection confirmée' in message
    assert 'ABC — LONG' not in message


def test_mysql_second_precision_is_not_a_stale_analysis(db, transport, monkeypatch):
    from datetime import datetime
    repo = Mock()
    repo.get.return_value = dict(archived(), started_at=datetime(2026, 10, 16)), [assessment()]
    monkeypatch.setattr('service.llm_directional.repository.Repository', lambda engine: repo)
    assert alerts.notify_llm(db, 'llm-test', attempted_at=datetime(2026, 10, 16, microsecond=420000))
    assert 'ABC — LONG' in transport.call_args.args[0]


@pytest.mark.parametrize('fails', [False, True])
def test_predict_hook_success_and_failure(monkeypatch, fails):
    import sys
    import service.llm_directional.pipeline as pipeline
    import database.connection
    monkeypatch.setattr(sys, 'argv', ['pipeline', '--phase', 'predict', '--run-id', 'llm-test',
        '--trade-date', '2026-10-16', '--batch-id', 'test-batch', '--command-json',
        json.dumps(['python', '-u', '-m', 'modelFactory', '--mode', 'predict'])])
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date', lambda d: SimpleNamespace(isoformat=lambda: d))
    monkeypatch.setattr(pipeline, 'validate_analysis_window', lambda *a: None)
    monkeypatch.setattr(pipeline, 'assert_paper_account', lambda *a: None)
    monkeypatch.setattr(pipeline.subprocess, 'run', Mock())
    engine = object()
    monkeypatch.setattr(database.connection, 'get_sqlalchemy_engine', lambda: engine)
    monkeypatch.setattr(pipeline, 'Repository', Mock())
    analyze = Mock(side_effect=RuntimeError('invalid responses')) if fails else Mock(return_value={'selected': []})
    monkeypatch.setattr(pipeline, 'analyze', analyze)
    notify = Mock(return_value=False)
    monkeypatch.setattr(alerts, 'notify_llm', notify)
    if fails:
        with pytest.raises(RuntimeError, match='invalid responses'):
            pipeline.main()
    else:
        pipeline.main()
    notify.assert_called_once()
    assert notify.call_args.args == (engine, 'llm-test')
    assert notify.call_args.kwargs['trade_date'] == '2026-10-16'
    assert notify.call_args.kwargs['attempted_at'] is not None
