"""Fast read-only metadata inventory; archives are kept but never parsed as code."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from service.migration import inventory,environment,cli
from service.migration.tracking import Progress
from ihm.services import migration_runner


def fixture_tree(tmp_path):
    root=tmp_path/'project'
    files={
        'service/client.py':"import os\nENV='CUSTOM_API_TOKEN'\na=os.getenv(ENV)\nb=os.environ.get('DIRECT_KEY')\nc=os.environ['INDEX_KEY']\n",
        'config/routes.yaml':'password_env: ROUTE_PASSWORD\n',
        '.env':'ENV_FILE_KEY=private-value\n',
        'scripts/watcher.env':'WATCHER_LOCAL_KEY=another-private-value\n',
        'artifacts/models/run/weights.bin':'model fixture',
        'artifacts/ihm_backtesting_runs/run/report.json':'{"message":"${ARCHIVE_ONLY_KEY}"}',
        'analyst_research/result.json':'{"message":"${RESEARCH_ONLY_KEY}"}',
        'tests/example.py':"import os\nx=os.getenv('TEST_ONLY_KEY')",
        '.venv/skip.py':'must not archive this',
        'backups/migrations/skip.json':'must not recurse backups',
    }
    for name,value in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding='utf-8')
    return root


def test_scan_counts_preserves_models_and_results_and_emits_ticks(tmp_path):
    root=fixture_tree(tmp_path);events=[]
    entries=inventory.scan(root,on_progress=lambda phase,**fields:events.append(fields))
    paths=[r['path'] for group in entries.values() for r in group]
    assert 'artifacts/models/run/weights.bin' in paths
    assert 'artifacts/ihm_backtesting_runs/run/report.json' in paths
    assert 'tests/example.py' in paths
    assert '.venv/skip.py' not in paths and 'backups/migrations/skip.json' not in paths
    assert events[-1]['files_done']==len(paths)
    assert events[-1]['processed_bytes']==sum(r['size'] for group in entries.values() for r in group)


def test_discovery_does_not_open_archive_json_but_keeps_real_sources(tmp_path,monkeypatch):
    root=fixture_tree(tmp_path)
    files=[r['path'] for group in inventory.scan(root).values() for r in group]
    original=Path.read_text
    def read(path,*args,**kwargs):
        assert not path.is_relative_to(root/'artifacts')
        assert not path.is_relative_to(root/'analyst_research')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    names=environment.discover_names(root,files)
    assert {'CUSTOM_API_TOKEN','DIRECT_KEY','INDEX_KEY','ROUTE_PASSWORD','ENV_FILE_KEY','WATCHER_LOCAL_KEY'}<=names
    assert not names & {'ARCHIVE_ONLY_KEY','RESEARCH_ONLY_KEY','TEST_ONLY_KEY'}


def test_scan_and_environment_discovery_can_be_canceled(tmp_path):
    root=fixture_tree(tmp_path)
    with pytest.raises(InterruptedError):inventory.scan(root,cancel=lambda:True)
    with pytest.raises(InterruptedError):environment.discover_names(root,['service/client.py'],cancel=lambda:True)


def test_inventory_worker_needs_no_password_or_database_and_persists_no_values(tmp_path,monkeypatch):
    root=fixture_tree(tmp_path);job=tmp_path/'job';job.mkdir()
    def forbidden(*args,**kwargs):raise AssertionError('Inventory must not connect to SQL')
    monkeypatch.setattr(cli,'adapter',forbidden)
    monkeypatch.setattr(environment,'registry_values',lambda scope:{})
    monkeypatch.setenv('CUSTOM_API_TOKEN','synthetic-secret-not-for-output')
    result=cli.run_request(dict(action='inventory',root=str(root)),job)
    assert result['status']=='INVENTORIED' and len(result['packages'])==4
    public=json.dumps(result)
    assert 'synthetic-secret-not-for-output' not in public and 'private-value' not in public
    assert any(v['name']=='CUSTOM_API_TOKEN' and v['present'] for v in result['variables'])
    for path in job.glob('*.json*'):
        assert 'synthetic-secret-not-for-output' not in path.read_text(encoding='utf-8')
    assert json.loads((job/'tracking.json').read_text())['percent']==100


def test_inventory_fragment_displays_progress_immediately(monkeypatch):
    state=dict(progress={'status':'STARTED'},tracking={'phase':'INVENTORY_SCAN','label':'Inventaire des fichiers du projet',
        'percent':0,'files_done':1234,'processed_bytes':1048576,'item':'artifacts/research','elapsed_seconds':12},result={})
    monkeypatch.setattr(migration_runner,'job_state',lambda path:state)
    app=AppTest.from_string("from ihm.components.migration_inventory import render_inventory_result\nrender_inventory_result('fixture-job')").run()
    assert not app.exception and app.get('progress')
    assert any(metric.value=='1,234' for metric in app.metric)
    assert app.button(key='t56_inventory_cancel')


def test_inventory_button_launches_worker_instead_of_scanning_in_ui(tmp_path,monkeypatch):
    root=fixture_tree(tmp_path);job=tmp_path/'job';job.mkdir();(job/'progress.json').write_text('{"status":"STARTING"}')
    monkeypatch.setattr(migration_runner,'PROJECT_ROOT',root)
    calls=[]
    monkeypatch.setattr(migration_runner,'start_job',lambda request,**kw:calls.append(request) or str(job))
    def forbidden(*args,**kwargs):raise AssertionError('No synchronous scan in Streamlit')
    monkeypatch.setattr(inventory,'scan',forbidden)
    app=AppTest.from_string('from ihm.components.migration_panel import render_migration_panel\nrender_migration_panel()').run()
    app.text_input(key='t56_password').set_value('synthetic-password-1212').run()
    app.button(key='t56_inventory').click().run()
    assert not app.exception
    assert calls==[dict(action='inventory',root=str(root))]
    assert app.text_input(key='t56_password').value=='synthetic-password-1212'
    assert app.button(key='t56_inventory_cancel')


def test_read_only_inventory_launch_does_not_claim_migration_guard(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Read-only inventory must remain usable during a backup')
    monkeypatch.setattr(migration_runner,'os_guard',forbidden)
    calls=[]
    monkeypatch.setattr(migration_runner,'_start_job',lambda request,**kw:calls.append(request) or 'inventory-job')
    assert migration_runner.start_job({'action':'inventory','root':'synthetic-project'})=='inventory-job'
    assert calls[0]['action']=='inventory'
