"""Reduced daily packages: synthetic fixtures, never replace real databases."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
from types import SimpleNamespace
from unittest.mock import Mock,MagicMock

import pytest
import yaml
from streamlit.testing.v1 import AppTest

from service.migration import engine, inventory, environment, profiles, daily_sql, cli
from service.migration.mysql import DATABASES, Connection, MySQL
from ihm.services import migration_runner
from test_migration_complete import FakeDB, PASSWORD, quiet

BATCH = 'model-factory-20261125000000-test'


def model_tree(root):
    folder=root/'artifacts/models'/BATCH/'oracle_path'
    folder.mkdir(parents=True)
    protocol=dict(batch_id=BATCH,serving_ready=True,horizon=10,universe=['A','B'],
        training_config=dict(oracle_path_directional_enabled=True,oracle_path_anti_sl_enabled=True),
        directional_contract=dict(feature_mode='compact_volatility'))
    protocol['fingerprint']=hashlib.sha256(json.dumps(protocol,sort_keys=True,default=str).encode()).hexdigest()
    (folder/'protocol.json').write_text(json.dumps(protocol))
    (folder/'report.json').write_text(json.dumps(dict(status='completed',serving_ready=True)))
    for name in ('weights.bin','chunks/0001/features.parquet','labels.parquet','anti_sl/training-panel.parquet'):
        path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'test-model')
    cfg=dict(us_pipeline=dict(b_anti_sl_reference=dict(enabled=True,apply_anti_sl=True,
        model_batch_id='old-model',artifacts_dir='old-path')),batch_diagnostics=dict(live_batch_id='old-model'))
    (root/'config.yaml').write_text(yaml.safe_dump(cfg),encoding='utf-8')
    for name in ('app.py','artifacts/models/other/weights.bin','artifacts/research/huge.parquet',
                 'artifacts/intraday_backfill/raw/old.gz','artifacts/q051_paper/run/execution.claim.json',
                 'artifacts/protection_states/account.json','config/ia/prompt/cloud/prompt.txt'):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
    return folder


def versions(root):
    return dict(python=platform.python_version(),system=platform.system(),machine=platform.machine(),requirements='pytest==8.0.0\n')


@pytest.fixture
def daily_backup(tmp_path, monkeypatch):
    root=tmp_path/'source';root.mkdir();model_tree(root)
    source=FakeDB();source.database_names=('alpha_trade',)
    def filtered(db,name,output,**kwargs):
        assert name=='alpha_trade'
        row=dict(db.state[name],rows=2)
        output.write(gzip.compress(json.dumps(row).encode()))
        return dict(rows=dict(items=2),row_policy=dict(items='recent'),snapshot='single_read_only_transaction')
    monkeypatch.setattr(daily_sql,'dump_daily',filtered)
    captured=dict(values=dict(ALPACA_API_KEY='synthetic-alpaca',PASSWORD_DB_FR='synthetic-fr'),
        variables=[dict(name='ALPACA_API_KEY',present=True),dict(name='PASSWORD_DB_FR',present=True)])
    folder=tmp_path/'backup'
    def source_must_continue(*args,**kwargs):raise AssertionError('Source services must not be stopped or inspected')
    payload=engine.export(root,folder,PASSWORD,source,backup_profile=profiles.US_DAILY,selected_model=BATCH,
        versions=versions,captured=captured,quiet=source_must_continue)
    return root,folder,payload


def test_selected_model_files_pruned_before_walking_and_config_source_untouched(tmp_path):
    root=tmp_path/'project';root.mkdir();folder=model_tree(root)
    original=(root/'config.yaml').read_bytes()
    packed=profiles.selected_config(root,BATCH)
    assert (root/'config.yaml').read_bytes()==original
    assert yaml.safe_load(packed)['us_pipeline']['b_anti_sl_reference']['model_batch_id']==BATCH
    rows=inventory.scan(root,include=lambda p:profiles.file_included(p,BATCH))
    paths={r['path'] for group in rows.values() for r in group}
    assert f'artifacts/models/{BATCH}/oracle_path/weights.bin' in paths
    assert 'artifacts/q051_paper/run/execution.claim.json' in paths
    assert 'artifacts/protection_states/account.json' in paths
    assert 'config/ia/prompt/cloud/prompt.txt' in paths
    assert not any('research' in p or 'chunks' in p or 'training-panel' in p or '/other/' in p for p in paths)


def test_package_verified_scope_and_reduced_row_counts(daily_backup):
    _,folder,_=daily_backup
    result=engine.verify(folder,PASSWORD)
    assert profiles.payload_scope(result)==('alpha_trade',)
    assert [p['database'] for p in result['packages'] if p['kind']=='sql']==['alpha_trade']
    assert result['row_counts_authoritative'] and result['source_services_unchanged']
    assert result['databases']['alpha_trade']['tables'][0]['rows']==2
    env=engine.private_json(folder,result,'environment',PASSWORD)
    assert 'ALPACA_API_KEY' in env['values'] and 'PASSWORD_DB_FR' not in env['values']
    assert (folder/'restaurer.ps1').is_file()


def test_restore_only_replaces_us_and_retains_target_fr_cn(daily_backup,tmp_path,monkeypatch):
    root,folder,payload=daily_backup
    db=FakeDB('destination');db.database_names=('alpha_trade',)
    fr=deepcopy(db.state['alpha_trade_fr']);cn=deepcopy(db.state['alpha_trade_cn'])
    target=tmp_path/'target';target.mkdir();(target/'old.txt').write_text('old')
    monkeypatch.setattr(environment,'registry_values',lambda scope:{})
    plan=engine.inspect_restore(folder,target,PASSWORD,db,quiet=quiet)
    assert plan['target_database_names']==['alpha_trade']
    writes={}
    result=engine.restore(folder,target,PASSWORD,db,tmp_path/'report',approved_plan=plan['fingerprint'],
        quiet=quiet,env_writer=writes.update,env_reader=lambda:{})
    assert result['databases']==['alpha_trade']
    assert db.state['alpha_trade']['rows']==2
    assert db.state['alpha_trade_fr']==fr and db.state['alpha_trade_cn']==cn
    assert not any(c[0] in ('drop','recreate') and c[1]!='alpha_trade' for c in db.calls)
    assert not any(n.endswith(('_FR','_CN')) for n in writes)
    restored=yaml.safe_load((target/'config.yaml').read_text(encoding='utf-8'))
    assert restored['us_pipeline']['b_anti_sl_reference']['model_batch_id']==BATCH
    assert yaml.safe_load((root/'config.yaml').read_text())['us_pipeline']['b_anti_sl_reference']['model_batch_id']=='old-model'


def test_us_failed_import_rolls_back_only_us(daily_backup,tmp_path,monkeypatch):
    _,folder,_=daily_backup
    db=FakeDB('destination');db.database_names=('alpha_trade',)
    initial=deepcopy(db.state);db.fail_load='alpha_trade'
    target=tmp_path/'target';target.mkdir()
    monkeypatch.setattr(environment,'registry_values',lambda scope:{})
    plan=engine.inspect_restore(folder,target,PASSWORD,db,quiet=quiet)
    with pytest.raises(RuntimeError,match='Synthetic import failure'):
        engine.restore(folder,target,PASSWORD,db,tmp_path/'report',approved_plan=plan['fingerprint'],
            quiet=quiet,env_writer=lambda values:None,env_reader=lambda:{})
    assert db.state==initial
    assert all(c[1]=='alpha_trade' for c in db.calls if c[0] in ('drop','recreate'))


def test_authenticated_us_recovery_leaves_fr_cn_unchanged(daily_backup,tmp_path,monkeypatch):
    _,folder,_=daily_backup
    db=FakeDB('destination');db.database_names=('alpha_trade',)
    initial=deepcopy(db.state)
    target=tmp_path/'target';target.mkdir()
    monkeypatch.setattr(environment,'registry_values',lambda scope:{})
    plan=engine.inspect_restore(folder,target,PASSWORD,db,quiet=quiet)
    report=tmp_path/'report'
    engine.restore(folder,target,PASSWORD,db,report,approved_plan=plan['fingerprint'],quiet=quiet,
        env_writer=lambda values:None,env_reader=lambda:{})
    result=engine.recover(report/'existant-chiffre',PASSWORD,db,tmp_path/'recovered',quiet=quiet,
        env_writer=lambda values:None,expected_target=target)
    assert result['status']=='RECOVERED_PAUSED' and db.state==initial
    assert all(c[1]=='alpha_trade' for c in db.calls if c[0] in ('drop','recreate'))


def test_model_integrity_accepts_legacy_windows_relative_manifest_paths(tmp_path):
    root=tmp_path/'source';root.mkdir();folder=model_tree(root)
    file=folder/'directional/models/A.joblib';file.parent.mkdir(parents=True);file.write_bytes(b'weights')
    record=dict(file='directional\\models\\A.joblib',sha256=hashlib.sha256(file.read_bytes()).hexdigest())
    (folder/'directional/manifest.json').write_text(json.dumps(dict(models=[record])))
    engine.model_checks(root,selected_model=BATCH)


def test_news_retention_adapts_to_configured_recalculation_context(tmp_path):
    (tmp_path/'config.yaml').write_text('sentiment_news_ingestion:\n  pipeline_feature_recalc_days: 100\n')
    assert profiles.news_context_days(tmp_path)==148
    assert profiles.news_context_days()==100


def test_freshness_retention_expands_for_nondefault_llm_settings(tmp_path):
    (tmp_path/'config.yaml').write_text('llm_directional_filter:\n  consensus_max_age_days: 30\n  evidence_sec_max_age_days: 60\n')
    assert profiles.evidence_windows(tmp_path)==dict(consensus_days=33,sec_days=63)
    assert profiles.evidence_windows()==dict(consensus_days=14,sec_days=30)


def test_partial_scope_rejects_missing_or_extra_schema_and_unknown_profile():
    for data in ({},dict(alpha_trade={},alpha_trade_fr={})):
        with pytest.raises(ValueError):profiles.payload_scope(dict(backup_profile='us_daily',databases=data))
    with pytest.raises(ValueError):profiles.scope('arbitrary')
    assert profiles.payload_scope(dict(databases={n:{} for n in DATABASES}))==DATABASES


def test_model_selection_rejects_traversal_and_incompatible_horizon(tmp_path):
    root=tmp_path/'source';root.mkdir();folder=model_tree(root)
    for invalid in ('../model','model-factory-../other',''):
        with pytest.raises(ValueError):profiles.model_folder(root,invalid)
    p=json.loads((folder/'protocol.json').read_text());p['horizon']=20
    (folder/'protocol.json').write_text(json.dumps(p))
    with pytest.raises(ValueError,match='H10'):profiles.selected_config(root,BATCH)


@pytest.mark.parametrize('value,expected',[(None,'NULL'),(123,'123'),(Decimal('1.2300'),'1.2300'),
    (b'\x00\xff',"X'00ff'"),("O'Brien", "CONVERT(X'4f27427269656e' USING utf8mb4)")])
def test_sql_values_preserve_types_without_quote_injection(value,expected):
    assert daily_sql.sql_value(value)==expected


def test_unknown_table_or_column_fails_closed():
    now=datetime(2026,11,25,tzinfo=timezone.utc)
    with pytest.raises(ValueError,match='sans politique'):
        daily_sql.build_policy([dict(table_name='new_unknown_table',column_name='id')],[],BATCH,now)
    with pytest.raises(ValueError,match='Colonne'):
        daily_sql.build_policy([dict(table_name='stock_bars_daily',column_name='id')],[],BATCH,now)


def test_parent_closure_preserves_all_references_of_retained_news():
    cols=[dict(table_name=t,column_name=c) for t,c in [('news_raw','published_at_utc'),('news_raw','article_id'),
        ('news_ticker_map','article_id'),('news_ticker_map','symbol'),('news_ticker_sentiment','article_id'),('news_ticker_sentiment','symbol')]]
    fk=[dict(table_name='news_ticker_map',column_name='article_id',parent='news_raw',parent_column='article_id',fk='raw'),
        dict(table_name='news_ticker_sentiment',column_name='article_id',parent='news_ticker_map',parent_column='article_id',fk='mapping'),
        dict(table_name='news_ticker_sentiment',column_name='symbol',parent='news_ticker_map',parent_column='symbol',fk='mapping')]
    p=daily_sql.build_policy(cols,fk,BATCH,datetime(2026,11,25,tzinfo=timezone.utc))
    assert 'EXISTS (SELECT 1 FROM `news_ticker_map`' in p['news_raw']
    assert '`news_ticker_sentiment`.`symbol`=`news_ticker_map`.`symbol`' in p['news_ticker_map']
    assert '`news_ticker_sentiment`.`article_id`=`news_ticker_map`.`article_id`' in p['news_ticker_map']


def test_worker_adapter_uses_authenticated_manifest_scope(daily_backup,monkeypatch):
    _,folder,_=daily_backup
    calls=[]
    monkeypatch.setattr(cli,'MySQL',lambda connections,**kwargs:calls.append((connections,kwargs)))
    request=dict(action='plan',folder=str(folder),password=PASSWORD,
        connections={n:dict(user='fixture',password='fixture') for n in DATABASES})
    cli.adapter(request)
    assert list(calls[0][0])==['alpha_trade']
    assert calls[0][1]['database_names']==('alpha_trade',)


def test_row_stream_has_one_read_only_snapshot_and_keeps_default_generated_columns(monkeypatch):
    conn=MagicMock();conn.__enter__.return_value=conn
    metadata=MagicMock();metadata.__enter__.return_value=metadata
    reader=MagicMock();reader.__enter__.return_value=reader
    conn.cursor.side_effect=[metadata,reader]
    metadata.fetchall.side_effect=[
        [dict(table_name='markets',column_name='id',extra=''),
         dict(table_name='markets',column_name='created_at',extra='DEFAULT_GENERATED'),
         dict(table_name='markets',column_name='computed',extra='VIRTUAL GENERATED')],
        [],[dict(name='markets')]]
    reader.fetchmany.side_effect=[[(1,datetime(2026,11,25,12,0))],[]]
    db=SimpleNamespace(connect=lambda n:conn,on_progress=None)
    ddl=[]
    def schema(db,name,stream,*,triggers,check):
        ddl.append(triggers);stream.write(b'-- TRIGGERS\n' if triggers else b'-- SCHEMA\n')
    monkeypatch.setattr(daily_sql,'dump_ddl',schema)
    out=io.BytesIO()
    result=daily_sql.dump_daily(db,'alpha_trade',out,batch=BATCH,cutoff=datetime.now(timezone.utc))
    commands=[c.args[0] for c in metadata.execute.call_args_list]
    assert 'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY' in commands
    assert commands.count('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')==1
    assert "SET SESSION time_zone='+00:00'" in commands
    query=reader.execute.call_args.args[0]
    assert '`created_at`' in query and '`computed`' not in query
    assert result['rows']==dict(markets=1) and ddl==[False,True]
    text=gzip.decompress(out.getvalue()).decode()
    assert "SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO'" in text
    assert text.index('-- SCHEMA')<text.index('INSERT INTO')<text.index('-- TRIGGERS')
    conn.rollback.assert_called_once()
    assert not any(c.startswith(('INSERT','DELETE','DROP','CREATE','UPDATE')) for c in commands)


def test_us_source_adapter_does_not_require_fr_or_cn_credentials(tmp_path,monkeypatch):
    (tmp_path/'config').mkdir()
    (tmp_path/'config/databases.yaml').write_text(yaml.safe_dump(dict(databases={
        'us_primary':dict(database='alpha_trade',user_env='FIX_US_USER',password_env='FIX_US_PASSWORD')})))
    monkeypatch.setenv('FIX_US_USER','fixture');monkeypatch.setenv('FIX_US_PASSWORD','fixture')
    monkeypatch.setattr(MySQL,'tool',staticmethod(lambda p,n:n))
    db=MySQL.source(tmp_path,database_names=('alpha_trade',))
    assert set(db.connections)=={'alpha_trade'}


def test_ui_submits_reduced_profile_and_model(tmp_path,monkeypatch):
    model_tree(tmp_path)
    monkeypatch.setattr(migration_runner,'PROJECT_ROOT',tmp_path)
    calls=[]
    monkeypatch.setattr(migration_runner,'start_job',lambda r,**kw:calls.append(r) or str(tmp_path/'job'))
    app=AppTest.from_string('from ihm.components.migration_panel import render_migration_panel\nrender_migration_panel()').run()
    app.selectbox(key='t56_backup_profile').select('us_daily').run()
    assert not app.exception
    assert app.selectbox(key='t56_selected_model').value==BATCH
    app.text_input(key='t56_password').set_value('fixture-long-password')
    app.text_input(key='t56_password_confirm').set_value('fixture-long-password')
    app.run();app.button(key='t56_export').click().run()
    assert not app.exception
    assert calls[0]['backup_profile']=='us_daily' and calls[0]['selected_model']==BATCH
