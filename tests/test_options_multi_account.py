"""Shared selection, independent PAPER portfolios; all financial boundaries mocked."""
import json
from types import SimpleNamespace

import pytest

from service.options_directional import store
from service.options_directional.accounts import (
    consumer_directory, require_paper_account, shared_latest_matching,
    shared_qualified, validate_risk_binding,
)
from service.options_directional.execution_attempts import (
    execution_attempt, execution_child_guard, mark_execution_effects_possible,
)
from service.options_directional.risk_attempts import risk_attempt,record_universe_lookup_failure
from tests.test_options_directional_orchestration import env, RUN


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def prepare(env, account):
    env[0]('risk',['python','-u','-m','risk_management'],account_id=account)
    folder=consumer_directory(RUN,account)
    return folder,read(folder/'risk_binding.json')


def test_one_selection_three_independent_risk_and_execution_runs(env,monkeypatch):
    invoke,calls,engine,report=env
    market_files={name:(store.directory(RUN)/name).read_bytes()
        for name in ('report.json','inputs.json','seal.json')}
    broker_accounts=[]
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def execute(self,query,params):
            account='default' if params['run']=='risk-exact' else params['run'].removeprefix('risk-')
            return SimpleNamespace(mappings=lambda:[dict(symbol='A',side='long',shares=1,
                trade_date=report['trade_date'],account_id=account)])
    engine.connect=lambda:Connection()
    monkeypatch.setattr('service.alpaca.trading_client.AlpacaTradingClient',
        lambda **kw:broker_accounts.append(kw['account_id']) or SimpleNamespace(get_positions=lambda:[]))
    default_claim=None
    for account in ('default','test1','test2'):
        folder,binding=prepare(env,account)
        assert binding['account_id']==account
        assert read(folder/'risk_summary.json')['account_id']==account
        invoke('execute',['python','-u','run_execution.py','paper'],account_id=account)
        execution=calls[-1]
        assert execution[execution.index('--account')+1]==account
        assert execution[execution.index('--run-id')+1]==binding['risk_run_id']
        assert read(folder/'execution.claim.json')['account_id']==account
        assert read(folder/'execution.result.json')['account_id']==account
        with pytest.raises(FileExistsError):
            invoke('execute',['python','-u','run_execution.py','paper'],account_id=account)
        if account=='default':
            default_claim=(folder/'execution.claim.json').read_bytes()
        assert (store.directory(RUN)/'execution.claim.json').read_bytes()==default_claim
    assert len(calls)==6 and not any('modelFactory' in cmd for cmd in calls)
    assert set(broker_accounts)=={'default','test1','test2'}
    for name,body in market_files.items():
        assert (store.directory(RUN)/name).read_bytes()==body


def test_ambiguous_execution_on_one_account_does_not_block_another(env):
    report=env[3]
    first,binding=prepare(env,'default')
    with pytest.raises(TimeoutError):
        with execution_attempt(first,report,binding):
            raise TimeoutError('No receipt: outcome unknown')
    other,other_binding=prepare(env,'test1')
    with execution_attempt(other,report,other_binding) as attempt:
        with execution_child_guard(RUN,attempt['attempt_id'],risk_run_id='risk-test1',
                mode='paper',account_id='test1',trade_date=report['trade_date']):
            with pytest.raises(ValueError):
                mark_execution_effects_possible(risk_run_id='risk-test1',mode='paper',account_id='default')
            mark_execution_effects_possible(risk_run_id='risk-test1',mode='paper',account_id='test1')
    with pytest.raises(FileExistsError):
        with execution_attempt(first,report,binding):
            pytest.fail('Ambiguous default attempt was released')


def test_copied_account_binding_is_rejected_before_executor(env):
    invoke,calls,_,_=env
    source,_=prepare(env,'default')
    destination=consumer_directory(RUN,'test1',create=True)
    for name in ('risk_binding.json','risk_summary.json'):
        (destination/name).write_bytes((source/name).read_bytes())
    with pytest.raises(ValueError,match='compte'):
        invoke('execute',['python','-u','run_execution.py','paper'],account_id='test1')
    assert len(calls)==1 and not (destination/'execution.claim.json').exists()


def test_sql_target_for_other_account_is_rejected(env,monkeypatch):
    invoke,calls,engine,report=env
    folder,_=prepare(env,'test1')
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def execute(self,*a):
            return SimpleNamespace(mappings=lambda:[dict(symbol='A',side='long',shares=1,
                trade_date=report['trade_date'],account_id='default')])
    engine.connect=lambda:Connection()
    monkeypatch.setattr('service.alpaca.trading_client.AlpacaTradingClient',
        lambda **kw:SimpleNamespace(get_positions=lambda:[]))
    with pytest.raises(ValueError,match='compte'):
        invoke('execute',['python','-u','run_execution.py','paper'],account_id='test1')
    assert len(calls)==1 and not (folder/'execution.claim.json').exists()


@pytest.mark.parametrize('account',['live-account','unknown'])
def test_live_and_undeclared_accounts_cannot_start_risk(env,account):
    with pytest.raises(ValueError):
        env[0]('risk',['python','-u','-m','risk_management'],account_id=account)
    assert not env[1]


def test_conflicting_nested_account_cannot_route_to_default(env):
    with pytest.raises(ValueError,match='Compte imbriqué'):
        env[0]('risk',['python','-u','-m','risk_management','--account','default'],account_id='test1')
    assert not env[1]


def test_legacy_default_binding_stays_default_only(env):
    _,binding=prepare(env,'default')
    summary=read(store.directory(RUN)/'risk_summary.json')
    legacy={k:v for k,v in binding.items() if k not in ('account_id','binding_protocol')}
    validate_risk_binding(env[3],legacy,summary,'default')
    with pytest.raises(ValueError):
        validate_risk_binding(env[3],legacy,summary,'test1')


def test_shared_latest_does_not_hide_newer_failure_on_another_account(env):
    newer='opt-'+'c'*32
    folder=store.directory(newer);folder.mkdir()
    store.write_new(folder/'failure.json',dict(env[3],run_id=newer,status='FAILED',account_id='test2'))
    with pytest.raises(ValueError,match='échouée'):
        shared_latest_matching(trade_date=env[3]['trade_date'],batch_id='model-test',
            symbol_source='universe-file:test.txt',account_id='test1')


def test_shared_selection_does_not_change_archived_preset(env):
    report=shared_qualified(RUN,trade_date=env[3]['trade_date'],account_id='test1',
        capital_preset_key='capital_0_2000')
    assert report==env[3] and report['capital_preset_key']=='capital_2001_5000'


@pytest.mark.parametrize('account',['../default','..','x/y','x\\y','C:default','',None,'a'*65])
def test_invalid_account_path_is_rejected(env,account):
    with pytest.raises(ValueError):
        consumer_directory(RUN,account,create=True)


def test_case_different_account_directories_do_not_collide_on_windows(env):
    assert str(consumer_directory(RUN,'TEST1')).lower()!=str(consumer_directory(RUN,'test1')).lower()
    assert consumer_directory(RUN,'default')==store.directory(RUN)


def test_pre_effect_execution_retry_is_proven_for_its_account_only(env):
    folder,binding=prepare(env,'test1')
    report=env[3]
    with pytest.raises(ImportError):
        with execution_attempt(folder,report,binding) as first:
            with execution_child_guard(RUN,first['attempt_id'],risk_run_id=binding['risk_run_id'],
                    mode='paper',account_id='test1',trade_date=report['trade_date']):
                raise ImportError('Failure before financial effects')
    proof_path=folder/f'execution.pre_effect_failure.{first["attempt_id"]}.json'
    proof=read(proof_path)
    assert proof['account_id']=='test1'
    proof_path.write_text(store.dumps({**proof,'account_id':'test2'}),encoding='utf-8')
    with pytest.raises(ValueError,match='altérée'):
        with execution_attempt(folder,report,binding):
            pytest.fail('Other account proof reused')
    proof_path.write_text(store.dumps(proof),encoding='utf-8')
    with execution_attempt(folder,report,binding) as second:
        assert second['attempt_id']!=first['attempt_id'] and second['account_id']=='test1'


def test_prepublication_risk_proof_cannot_cross_account(env):
    report=env[3]
    folder=consumer_directory(RUN,'test1',create=True)
    with pytest.raises(LookupError):
        with risk_attempt(folder,report,account_id='test1') as claim:
            with pytest.raises(ValueError):
                record_universe_lookup_failure(folder,claim['attempt_id'],report,LookupError(),account_id='test2')
            record_universe_lookup_failure(folder,claim['attempt_id'],report,LookupError(),account_id='test1')
            raise LookupError('No publication')
    with pytest.raises(ValueError,match='altérée'):
        with risk_attempt(folder,report,account_id='test2'):
            pytest.fail('Other account risk claim reused')
    with risk_attempt(folder,report,account_id='test1') as retry:
        assert retry['attempt_id']!=claim['attempt_id']


@pytest.mark.parametrize('wrong_path',[False,True])
def test_actual_risk_cli_checks_account_attempt_before_broker_capture(env,monkeypatch,wrong_path):
    from risk_management import cli,broker_account
    monkeypatch.setattr(cli,'configure_root_logging',lambda **kw:None)
    class CaptureReached(Exception): pass
    captures=[]
    def capture(account,mode):
        captures.append((account,mode))
        raise CaptureReached()
    monkeypatch.setattr(broker_account,'capture_current_account',capture)
    folder=consumer_directory(RUN,'test1',create=True)
    with risk_attempt(folder,env[3],account_id='test1') as attempt:
        summary=(store.directory(RUN) if wrong_path else folder)/'risk_summary.json'
        with pytest.raises(ValueError if wrong_path else CaptureReached):
            cli.main(['--run-mode','paper','--account','test1','--trade-date',env[3]['trade_date'],
                '--options-filter-run-id',RUN,'--oracle-batch-id','model-test',
                '--options-risk-attempt-id',attempt['attempt_id'],'--summary-path',str(summary)])
    assert captures==([] if wrong_path else [('test1','paper')])
