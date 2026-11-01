"""Isolation enforcement and coexistence; no production DB or broker calls."""
import json
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine,text

from backtesting.isolation import ReadOnlyReplay,IsolationViolation,read_statement,readonly_run_options


@pytest.mark.parametrize('sql',[
    'SELECT 1','SELECT @@session.transaction_read_only','SHOW FULL TABLES','DESCRIBE stock_bars_daily',
    'WITH x AS (SELECT 1) SELECT * FROM x','SET SESSION TRANSACTION READ ONLY',
    'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY','SET NAMES utf8mb4',
    "SELECT 'update me' AS name",'SELECT `update` FROM t',
    'SHOW CREATE TABLE `stock_bars_daily`',
])
def test_sql_reads_and_readonly_setup_are_allowed(sql):assert read_statement(sql)


@pytest.mark.parametrize('sql',[
    'INSERT INTO t VALUES (1)','UPDATE t SET value=1','DELETE FROM t','CREATE TABLE t(id INT)',
    'DROP DATABASE alpha_trade','CALL stored_proc()','SET SESSION TRANSACTION READ WRITE',
    'SELECT 1; DELETE FROM t',"SELECT 1 INTO OUTFILE '/tmp/x'",'SELECT * FROM t FOR UPDATE',
    'SELECT GET_LOCK(\'x\',1)','SELECT @x:=1','WITH x AS (SELECT 1) DELETE FROM t',
    '/*! DELETE FROM t */ SELECT 1',
])
def test_write_and_side_effect_sql_is_rejected(sql):assert not read_statement(sql)


def test_file_writes_are_scoped_and_swallowed_error_still_fails(tmp_path):
    root=tmp_path/'run';outside=tmp_path/'outside.txt'
    with pytest.raises(IsolationViolation,match='helper caught'):
        with ReadOnlyReplay(root).install():
            (root/'report.json').write_text('{}')
            try:outside.write_text('bad')
            except IsolationViolation:pass
    assert not outside.exists() and (root/'report.json').is_file()
    receipt=json.loads((root/'isolation.json').read_text())
    assert receipt['status']=='FAILED' and receipt['violations'][0]['kind']=='SHARED_FILE_WRITE'
    outside.write_text('guard removed after exit')


def test_shared_sqlite_cannot_mutate_but_run_local_simulation_can(tmp_path):
    shared=create_engine('sqlite:///'+str(tmp_path/'shared.db'))
    with shared.begin() as c:
        c.execute(text('CREATE TABLE t(value INT)'));c.execute(text('INSERT INTO t VALUES (1)'))
    root=tmp_path/'run'
    with pytest.raises(IsolationViolation):
        with ReadOnlyReplay(root).install():
            with shared.connect() as c:assert c.execute(text('SELECT value FROM t')).scalar()==1
            local=create_engine('sqlite:///'+str(root/'simulation.db'))
            with local.begin() as c:
                c.execute(text('CREATE TABLE trades(id INT)'));c.execute(text('INSERT INTO trades VALUES (2)'))
            with shared.begin() as c:c.execute(text('UPDATE t SET value=999'))
    with shared.connect() as c:assert c.execute(text('SELECT value FROM t')).scalar()==1


def test_mysql_connections_are_readonly_including_direct_dbapi(tmp_path,monkeypatch):
    import pymysql.connections
    seen=[]
    monkeypatch.setattr(pymysql.connections.Connection,'__init__',lambda self,*a,**kw:seen.append(kw))
    with pytest.raises(IsolationViolation):
        with ReadOnlyReplay(tmp_path/'run').install():
            connection=pymysql.connections.Connection()
            assert seen[0]['init_command']=='SET SESSION TRANSACTION READ ONLY'
            connection.query('DELETE FROM portfolio_targets')


def test_broker_posts_and_child_processes_are_not_allowed(tmp_path):
    import http.client
    with pytest.raises(IsolationViolation):
        with ReadOnlyReplay(tmp_path/'run').install():
            http.client.HTTPConnection('paper-api.alpaca.markets').putrequest('POST','/v2/orders')


def test_unqualified_child_is_not_started(tmp_path):
    import subprocess
    with pytest.raises(IsolationViolation):
        with ReadOnlyReplay(tmp_path/'run').install():
            subprocess.Popen([sys.executable,'-c','print(123)'])


def test_same_price_sources_read_metadata_without_git_status(tmp_path):
    from backtesting.run_metadata import collect_git_info
    with ReadOnlyReplay(tmp_path/'run').install():
        result=collect_git_info()
        assert result['git_dirty'] is None


def test_only_the_inherited_tls_pipe_is_exempt_from_file_writes(tmp_path,monkeypatch):
    guard=ReadOnlyReplay(tmp_path/'run')
    pipe=r'\\.\nllMonFltProxy\synthetic'
    monkeypatch.setenv('SSLKEYLOGFILE',pipe)
    guard.require_path(pipe)
    monkeypatch.setenv('SSLKEYLOGFILE',str(tmp_path/'shared.txt'))
    with pytest.raises(IsolationViolation):guard.require_path(tmp_path/'shared.txt')


def test_parquet_and_recovery_caches_are_run_local(tmp_path):
    import pandas as pd
    from backtesting.cache import ParquetCache
    from backtesting.winner_intraday_recovery import RecoveringIntradaySource
    from common.winner_pyramiding import WinnerPyramidingConfig
    from datetime import date
    root=tmp_path/'run';shared=tmp_path/'shared-cache'
    with ReadOnlyReplay(root).install():
        cache=ParquetCache(shared)
        cache.put('data',pd.DataFrame({'a':[1]}))
        recovery=RecoveringIntradaySource(lambda *a:pd.DataFrame(),date(2026,10,30),WinnerPyramidingConfig())
        assert recovery.cache_dir.is_relative_to(root)
    assert cache.cache_dir.is_relative_to(root) and not shared.exists()


def test_only_qualified_simulation_options_can_use_readonly_lock():
    from ihm.services.backtesting_runner import BacktestRunOptions
    from dataclasses import replace
    base=BacktestRunOptions(start='2026-01-01')
    assert readonly_run_options('run',base)
    assert readonly_run_options('run',replace(base,winner_enabled=True))
    for field in ('ml_mode','sentiment_mode','ml_pit_strategy'):
        assert not readonly_run_options('run',replace(base,**{field:'rebuild-missing'}))
    assert not readonly_run_options('backfill-scores-history',base)
    assert not readonly_run_options('fr-research-replay',base)


def test_dispatch_guard_installed_before_module_and_receipt_written(tmp_path,monkeypatch):
    from backtesting import isolated_run
    from backtesting.isolation import active
    def run(module,**kwargs):
        assert active() and module=='backtesting'
        output=Path(sys.argv[sys.argv.index('--output-dir')+1]);output.mkdir()
        (output/'report.json').write_text('{}')
    monkeypatch.setattr(isolated_run.runpy,'run_module',run)
    root=tmp_path/'run'
    isolated_run.main(['--workspace',str(root),'--module','backtesting','--','run','--output-dir',str(root/'artifacts')])
    assert json.loads((root/'isolation.json').read_text())['status']=='COMPLETED'


def test_escaping_output_or_maintenance_dispatch_is_rejected(tmp_path):
    from backtesting.isolated_run import main
    for args in (['run','--output-dir',str(tmp_path/'outside')],['backfill-scores-history','--output-dir',str(tmp_path/'run/out')]):
        with pytest.raises(SystemExit):
            main(['--workspace',str(tmp_path/'run'),'--module','backtesting','--',*args])
