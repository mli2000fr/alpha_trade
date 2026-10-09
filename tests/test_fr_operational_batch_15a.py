from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from service.fr import operational_batch_15a as runner
from ihm.services import batch_management


def config(tmp_path, name='fr_calendar_snapshot', **changes):
    payload = yaml.safe_load((runner.ROOT/'batch_fr.yaml').read_text(encoding='utf-8'))
    payload[name].update(changes)
    path = tmp_path/'batch_fr.yaml'
    path.write_text(yaml.safe_dump(payload), encoding='utf-8')
    return path


def test_fr_catalog_has_only_fr_and_defaults(tmp_path):
    specs = batch_management.load_batch_specs(str(config(tmp_path)))
    assert len(specs) == 13
    assert 'fr_pit_quality_daily' not in {s.name for s in specs}
    assert 'fr_consensus_borrow_options' not in {s.name for s in specs}
    assert all(s.name.startswith('fr_') and s.timezone == 'Europe/Paris' for s in specs)
    assert all(s.raw_config['database_alias'] == 'fr_primary' for s in specs)
    assert {s.name for s in specs if s.runnable} == {'fr_calendar_snapshot', 'fr_daily_bars_sync',
        'fr_corporate_actions_sync','fr_amf_short_sync','fr_dila_disclosures_sync', 'fr_db_backup','fr_security_master_sync','fr_artifacts_backup','fr_options_mifir_trade_sync'}
    assert all('univers_batch' not in s.symbols_file for s in specs)


@pytest.mark.parametrize('name,status', [('fr_consensus_snapshot', 'BLOCKED_YAHOO_AUTOMATED_ACCESS'),
                                       ('fr_fundamentals_sync', 'BLOCKED_INPI_RETENTION')])
def test_legal_blocks_remain_non_runnable_even_if_enabled_is_toggled(tmp_path, monkeypatch, name, status):
    monkeypatch.setattr(runner, 'OPS', tmp_path/'ops')
    spec = next(s for s in batch_management.load_batch_specs(str(config(tmp_path))) if s.name == name)
    assert not spec.enabled and not spec.runnable
    assert spec.status == status and spec.unlock_steps and spec.research_notice
    path = config(tmp_path, name, enabled=True)
    spec = next(s for s in batch_management.load_batch_specs(str(path)) if s.name == name)
    assert not spec.runnable
    monkeypatch.setattr(runner, '_handle', lambda *a, **kw: pytest.fail('Blocked collector must not execute'))
    assert runner.run(name, config_path=path)['status'] == 'SKIPPED_DISABLED_OR_UNQUALIFIED'


@pytest.mark.parametrize('field,value', [('market_code','US_EQ'), ('database_alias','cn_primary'),
                                      ('canonical_writes_enabled', True), ('serving_enabled', True)])
def test_rejects_cross_market_or_serving_config(tmp_path, field, value):
    path = config(tmp_path, **{field:value})
    result = runner.run('fr_calendar_snapshot', config_path=path, dry_run=True)
    assert result['status'] == 'FAILED'
    assert result['failed_count'] == 1
    assert result['persisted_count'] == 0


def test_calendar_snapshot_is_idempotent_and_records_runs(tmp_path, monkeypatch):
    from common import market_calendar
    monkeypatch.setattr(runner, 'OPS', tmp_path/'ops')
    path = config(tmp_path)
    first = runner.run('fr_calendar_snapshot', config_path=path, today=date(2026,10,5))
    second = runner.run('fr_calendar_snapshot', config_path=path, today=date(2026,10,5))
    assert first['status'] == second['status'] == 'SUCCESS'
    assert first['persisted_count'] == second['persisted_count'] > 200
    assert len(list((tmp_path/'ops/calendar').glob('*.json'))) == 1
    assert len(list((tmp_path/'ops/runs/fr_calendar_snapshot').glob('*.json'))) == 2
    assert runner.latest_run('fr_calendar_snapshot')['status'] == 'SUCCESS'


def test_disabled_cannot_collect_and_unimplemented_cannot_be_activated(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'OPS', tmp_path/'ops')
    path = config(tmp_path, 'fr_security_master_sync',enabled=False)
    assert runner.run('fr_security_master_sync', config_path=path)['status'] == 'SKIPPED_DISABLED_OR_UNQUALIFIED'
    path = config(tmp_path, 'fr_borrow_snapshot', enabled=True, status='ACTIVE')
    result = runner.run('fr_borrow_snapshot', config_path=path)
    assert result['status'] == 'FAILED'
    assert 'non implémenté' in result['error_message']
    assert runner.latest_run('fr_borrow_snapshot')['failed_count'] == 1


def test_dry_run_no_disk_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'OPS', tmp_path/'ops')
    path = config(tmp_path)
    result = runner.run('fr_calendar_snapshot', config_path=path, dry_run=True)
    assert result['status'] == 'DRY_RUN'
    assert result['persisted_count'] == 0
    assert not (tmp_path/'ops').exists()


def test_partial_daily_collection_publishes_but_does_not_mask_failure(monkeypatch):
    from service.fr import eodhd_daily_15b, publish_daily_bars_staging
    cfg=runner.load_section('fr_daily_bars_sync',runner.ROOT/'batch_fr.yaml')
    def partial(config,result,**kwargs):
        result.update(window=['2026-10-01','2026-10-08'],state_path='checkpoint',failed_count=2)
        raise RuntimeError('two source failures')
    seen=[]
    monkeypatch.setattr(eodhd_daily_15b,'collect',partial)
    monkeypatch.setattr(publish_daily_bars_staging,'run',lambda **kw:(seen.append(kw),
        {'status':'COMPLETED','new_staging_rows':10})[1])
    result={}
    with pytest.raises(RuntimeError,match='two source failures'):
        runner._handle('fr_daily_bars_sync',cfg,result,dry_run=False,today=None)
    assert len(seen)==1 and seen[0]['write'] is True
    assert result['sql_persisted_count']==10 and result['failed_count']==2
    assert result['sql_writes'] is True


def test_daily_dryrun_never_publishes(monkeypatch):
    from service.fr import eodhd_daily_15b, publish_daily_bars_staging
    cfg=runner.load_section('fr_daily_bars_sync',runner.ROOT/'batch_fr.yaml')
    monkeypatch.setattr(eodhd_daily_15b,'collect',lambda cfg,result,**kw:result.update(state_path='checkpoint',window=['2026-10-01','2026-10-08']))
    monkeypatch.setattr(publish_daily_bars_staging,'run',lambda **kw:pytest.fail('Dry-run SQL'))
    runner._handle('fr_daily_bars_sync',cfg,{},dry_run=True,today=None)


def test_daily_smoke_sql_scope_matches_collection_scope(monkeypatch):
    from service.fr import eodhd_daily_15b, publish_daily_bars_staging
    cfg=runner.load_section('fr_daily_bars_sync',runner.ROOT/'batch_fr.yaml')
    monkeypatch.setattr(eodhd_daily_15b,'collect',lambda cfg,result,**kw:result.update(state_path='checkpoint',window=['2026-10-01','2026-10-08']))
    monkeypatch.setattr(eodhd_daily_15b,'symbols_from_identities',lambda path:['AB.PA','AC.PA','AD.PA'])
    seen=[]
    monkeypatch.setattr(publish_daily_bars_staging,'run',lambda **kw:(seen.append(kw),
        {'status':'COMPLETED','new_staging_rows':0})[1])
    runner._handle('fr_daily_bars_sync',cfg,{},dry_run=False,today=None,max_symbols=2)
    assert seen[0]['selected_symbols']==['AB.PA','AC.PA']


def test_db_backup_uses_fr_route_and_required_identity(tmp_path, monkeypatch):
    from database import router
    from scripts import backup_db
    called = []
    monkeypatch.setattr(router, 'resolve_database_route', lambda alias, market:
        SimpleNamespace(host='frhost', database='alpha_trade_fr'))
    monkeypatch.setattr(backup_db, 'backup_db', lambda **kwargs:
        (called.append(kwargs), SimpleNamespace(errors=[], dump_path='test.sql.gz'))[1])
    path = config(tmp_path, 'fr_db_backup')
    assert runner.run('fr_db_backup', config_path=path, dry_run=True)['status'] == 'DRY_RUN'
    assert called[0]['db'] == 'alpha_trade_fr'
    assert called[0]['host'] == 'frhost'
    assert called[0]['archive_prefix'] == 'alpha_trade_fr'
    path = config(tmp_path, 'fr_db_backup', db='alpha_trade')
    assert runner.run('fr_db_backup', config_path=path, dry_run=True)['status'] == 'FAILED'
    assert len(called) == 1


def test_commands_use_fr_wrapper_and_config_and_no_disabled_install(tmp_path):
    specs = batch_management.load_batch_specs(str(config(tmp_path)))
    for spec in specs:
        for command in (batch_management.build_install_command(spec), batch_management.build_run_command(spec)):
            assert 'fr_operational_launcher_15a.ps1' in ' '.join(command)
            assert command[command.index('-BatchConfigPath')+1] == spec.catalog_path
    blocked = next(s for s in specs if s.name == 'fr_borrow_snapshot')
    assert batch_management.install_batch(blocked).ok is False


def test_duplicate_across_catalogues_blocks_loading(tmp_path):
    path = config(tmp_path)
    (tmp_path/'batch.yaml').write_text(yaml.safe_dump({'fr_calendar_snapshot': {'enabled':True}}))
    with pytest.raises(ValueError, match='Doublons'):
        batch_management.load_batch_specs(str(path))


def test_wrapper_uses_common_notifier_and_no_us_runner():
    source = (runner.ROOT/'scripts/windows/fr_operational_launcher_15a.ps1').read_text()
    assert "RunnerModule = 'service.fr.operational_batch_15a'" in source
    assert "'batch_fr.yaml'" in source
    assert "'forward_pit_launcher.ps1'" in source
