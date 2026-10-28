"""Mock subprocess/SQL/broker boundary, asserting exact PAPER run binding."""
from datetime import date, datetime, timezone
import json
from types import SimpleNamespace

import pytest

from service.options_directional import pipeline, store
from service.options_directional.config import OptionsFilterConfig

RUN = 'opt-'+'b'*32
NOW = datetime(2026,10,16,23,tzinfo=timezone.utc)


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    monkeypatch.setattr(store, 'validate_window', lambda *a, **k: None)
    monkeypatch.setattr(pipeline, 'validate_window', lambda *a, **k: None)
    monkeypatch.setattr(pipeline, 'load_options_filter_config', lambda: OptionsFilterConfig(enabled=True))
    monkeypatch.setattr('service.llm_directional.runner.assert_paper_account', lambda *a: None)
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date', lambda *a: date(2026,10,16))
    engine = SimpleNamespace(url=SimpleNamespace(database='alpha_trade'))
    monkeypatch.setattr('database.connection.get_sqlalchemy_engine', lambda: engine)
    report = store.seal(RUN, dict(run_id=RUN, status='COMPLETED', trade_date='2026-10-16',
        batch_id='model-test', account_id='default', symbol_source='universe-file:test.txt',
        capital_preset_key='capital_2001_5000', cutoff_utc=NOW.isoformat(),
        config=OptionsFilterConfig().snapshot(), rows=[dict(symbol='A',selected=True)], selected=['A']),
        {'raw': []})
    # Freeze the reader clock, not the qualification/hash implementation.
    real_qualified = store.qualified
    monkeypatch.setattr(store, 'qualified', lambda run_id, **kwargs: real_qualified(run_id, now=NOW, **kwargs))
    monkeypatch.setattr(pipeline, 'qualified', store.qualified)
    calls = []
    def fake_subprocess(command, check):
        assert check is True
        calls.append(command)
        if 'risk_management' in command:
            path = command[command.index('--summary-path')+1]
            store.write_new(__import__('pathlib').Path(path), dict(run_id='risk-exact', run_mode='paper',
                dry_run=False, options_filter_run_id=RUN))
    monkeypatch.setattr(pipeline.subprocess, 'run', fake_subprocess)
    def invoke(phase, command, run_id=RUN):
        import sys
        monkeypatch.setattr(sys, 'argv', ['options', '--phase',phase,'--run-id',run_id,
            '--trade-date','2026-10-16','--batch-id','model-test','--symbol-source','universe-file:test.txt',
            '--command-json',json.dumps(command)])
        pipeline.main()
    return invoke, calls, engine, report


def test_risk_is_exact_and_execution_cannot_fall_back_to_latest(env, monkeypatch):
    invoke, calls, engine, report = env
    invoke('risk', ['python','-u','-m','risk_management'])
    risk = calls[-1]
    assert risk[risk.index('--options-filter-run-id')+1] == RUN
    assert risk[risk.index('--oracle-batch-id')+1] == 'model-test'
    assert risk[risk.index('--run-mode')+1] == 'paper'
    assert (store.directory(RUN)/'risk_binding.json').exists()
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def execute(self, query, params):
            assert params == dict(run='risk-exact')
            return SimpleNamespace(mappings=lambda: [dict(symbol='A',side='long',shares=1,
                trade_date='2026-10-16',account_id='default')])
    engine.connect = lambda: Connection()
    monkeypatch.setattr('service.alpaca.trading_client.AlpacaTradingClient',
        lambda **k: SimpleNamespace(get_positions=lambda: []))
    invoke('execute', ['python','-u','run_execution.py','paper','--run-id','stale'])
    execute = calls[-1]
    assert execute[execute.index('--run-id')+1] == 'risk-exact'
    with pytest.raises(FileExistsError):
        invoke('execute', ['python','-u','run_execution.py','paper'])
    assert len(calls) == 2  # no duplicate execution


def test_non_selected_new_exposure_is_blocked_before_executor(env, monkeypatch):
    invoke, calls, engine, report = env
    invoke('risk', ['python','-u','-m','risk_management'])
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def execute(self,*a):
            return SimpleNamespace(mappings=lambda: [dict(symbol='B',side='long',shares=1,
                trade_date='2026-10-16',account_id='default')])
    engine.connect = lambda: Connection()
    monkeypatch.setattr('service.alpaca.trading_client.AlpacaTradingClient',
        lambda **k: SimpleNamespace(get_positions=lambda: []))
    with pytest.raises(ValueError, match='hors sélection'):
        invoke('execute', ['python','-u','run_execution.py','paper'])
    assert len(calls) == 1
    assert not (store.directory(RUN)/'execution.claim.json').exists()


def test_no_targets_is_valid_abstention_without_broker_or_executor(env, monkeypatch):
    invoke,calls,engine,_ = env
    invoke('risk',['python','-u','-m','risk_management'])
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def execute(self,*a): return SimpleNamespace(mappings=lambda: [])
    engine.connect = lambda: Connection()
    monkeypatch.setattr('service.alpaca.trading_client.AlpacaTradingClient',
        lambda **k:pytest.fail('broker called despite no targets'))
    invoke('execute',['python','-u','run_execution.py','paper'])
    assert len(calls)==1
    assert not (store.directory(RUN)/'execution.claim.json').exists()


@pytest.mark.parametrize('command', [['python','-u','run_execution.py','live'],
    ['python','-u','run_execution.py','paper','--run-plan-file','external.json']])
def test_no_live_or_external_plan(env, command):
    invoke,calls,_,_ = env
    with pytest.raises(ValueError):
        invoke('execute',command)
    assert calls == []


def test_technical_prediction_failure_never_runs_filter(env, monkeypatch):
    invoke,calls,_,_ = env
    import subprocess
    def fail(*a,**k): raise subprocess.CalledProcessError(1,a[0])
    monkeypatch.setattr(pipeline.subprocess,'run',fail)
    monkeypatch.setattr('service.options_directional.runner.analyze',lambda **k:pytest.fail('filter called'))
    with pytest.raises(subprocess.CalledProcessError):
        invoke('predict',['python','-u','-m','modelFactory'],run_id='opt-'+'c'*32)


def test_failed_coverage_keeps_diagnostics_without_publishing_or_reusing_old_selection(env, monkeypatch):
    from service.options_directional.runner import OracleCoverageError
    invoke,calls,_,_ = env
    failed_id = 'opt-'+'e'*32
    def fail(*args, **kwargs):
        raise OracleCoverageError(rows=[dict(symbol='A')], symbols=['A','B'],
            batch_id='model-test', trade_date='2026-10-16', required_ratio=.95)
    monkeypatch.setattr('service.options_directional.runner.analyze', fail)
    with pytest.raises(OracleCoverageError):
        invoke('predict', ['python','-u','-m','modelFactory'], run_id=failed_id)
    folder = store.directory(failed_id)
    failure = json.loads((folder/'failure.json').read_text(encoding='utf-8'))
    assert failure['status'] == 'FAILED' and not failure['selection_published']
    assert failure['diagnostics']['missing_symbols'] == ['B']
    assert not (folder/'report.json').exists() and not (folder/'risk.claim.json').exists()
    with pytest.raises(ValueError, match='Dernière analyse options échouée'):
        store.latest_matching(trade_date='2026-10-16',batch_id='model-test',account_id='default',
            symbol_source='universe-file:test.txt',capital_preset_key='capital_2001_5000')


def test_latest_exact_run_is_not_replaced_by_older_if_corrupted(env):
    invoke,calls,_,report = env
    newer = 'opt-'+'d'*32
    store.seal(newer, {**report,'run_id':newer,'cutoff_utc':NOW.replace(minute=1).isoformat()}, {'raw': []})
    (store.directory(newer)/'inputs.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='altérée'):
        store.latest_matching(trade_date='2026-10-16',batch_id='model-test',account_id='default',
                              symbol_source='universe-file:test.txt',capital_preset_key='capital_2001_5000')


def test_scheduled_plan_activates_filter_without_starting_orders(monkeypatch):
    from service.forward_pit import us_pipeline
    from service.llm_directional.config import FilterConfig
    monkeypatch.setattr(us_pipeline,'session_plan',lambda now:(date(2026,10,16),None))
    monkeypatch.setattr(us_pipeline,'load_pipeline_policy',lambda:dict(steps_friday=[10,11,12],
                         execution_mode='paper',account_id='default'))
    monkeypatch.setattr(us_pipeline,'load_filter_config',lambda:FilterConfig(enabled=False))
    monkeypatch.setattr(us_pipeline,'require_paper_account',lambda *a:None)
    monkeypatch.setattr('common.us_signal_date.resolve_us_signal_date',lambda *a:date(2026,10,16))
    monkeypatch.setattr('ihm.services.process_registry.start_pipeline_workflow',lambda *a,**k:pytest.fail('orders'))
    result = us_pipeline.execute_pipeline(SimpleNamespace(url=SimpleNamespace(database='alpha_trade')),
        dict(market_code='US_EQ',symbols_file='config/univers_batch/univers_filtred_tradable.txt'),'test',True)
    assert result.details['options']['options_filter_enabled']
    assert not result.details['options']['llm_filter_enabled']
    assert all(s['command'][3]=='service.options_directional.pipeline' for s in result.details['steps'])
