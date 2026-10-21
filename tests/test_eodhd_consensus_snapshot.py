from datetime import UTC, datetime
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine, text, Column, Table, MetaData, String, UniqueConstraint

from service.eodhd import consensus_snapshot as mod
from database.repositories.eodhd_consensus import persist_rows, TABLE


def item(**kw):
    return dict(code='ABC.US', date='2026-09-30', period='0q',
        earningsEstimateAvg='1.5', earningsEstimateNumberOfAnalysts='12',
        epsTrend7daysAgo='1.3', epsRevisionsUpLast30days='4') | kw


def payload(*rows):
    return {'trends':[list(rows)]}


def parsed(*rows):
    return mod.parse(payload(*rows),['ABC'],datetime(2026,10,11,1,tzinfo=UTC),'test')['ABC']


def test_fiscal_history_retained_without_false_historical_pit():
    rows=parsed(item(),item(date='2023-09-30'))
    assert len(rows)==2
    assert rows[0]['snapshot_date'].isoformat()=='2026-10-10'
    assert rows[1]['fiscal_period_end'].isoformat()=='2023-09-30'
    assert rows[0]['eps_avg']==1.5 and rows[0]['eps_analyst_count']==12
    assert rows[0]['revisions_down_7d'] is None
    assert rows[0]['revisions_down_30d'] is None
    assert rows[0]['currency'] is None and not rows[0]['units_qualified']
    assert not rows[1]['historical_pit_qualified']
    assert rows[1]['available_at']==datetime(2026,10,11,1)


def test_duplicate_identity_deduplicated_but_conflicts_rejected():
    assert len(parsed(item(),item()))==1
    changed=item();changed['earningsEstimateAvg']='2'
    with pytest.raises(ValueError,match='Conflicting'):
        parsed(item(),changed)


@pytest.mark.parametrize('value',[-1,1.5,True,'inf'])
def test_invalid_counts_rejected(value):
    bad=item();bad['earningsEstimateNumberOfAnalysts']=value
    with pytest.raises(ValueError):parsed(bad)


def test_foreign_symbol_and_unknown_schema_rejected():
    bad=item();bad['code']='MSFT.US'
    with pytest.raises(ValueError):parsed(bad)
    with pytest.raises(ValueError):mod.parse([],['ABC'],datetime.now(UTC),'test')


def sqlite_engine(rows):
    metadata=MetaData()
    Table(TABLE,metadata,*[Column(key,String) for key in rows[0]],
        UniqueConstraint('provider','symbol','snapshot_date','fiscal_period_end','horizon_raw'))
    engine=create_engine('sqlite:///:memory:')
    metadata.create_all(engine)
    # SQLite accepts datetime/date bind values and returns text in these tests.
    return engine


def test_append_only_daily_period_key():
    rows=parsed(item(),item(date='2023-09-30'))
    engine=sqlite_engine(rows)
    with engine.begin() as conn:
        assert persist_rows(conn,rows)==2
        changed=dict(rows[0],eps_avg=99)
        assert persist_rows(conn,[changed])==0
        assert conn.execute(text(f'SELECT eps_avg FROM {TABLE} WHERE fiscal_period_end=:date'),
                            {'date':'2026-09-30'}).scalar()=='1.5'
        following=dict(rows[0],snapshot_date='2026-10-11',run_id='next')
        assert persist_rows(conn,[following])==1


def setup_collect(monkeypatch):
    from service.forward_pit import batch
    monkeypatch.setattr(batch,'_collection_symbols',lambda cfg:['ABC','DEF'])
    monkeypatch.setattr(mod,'verified_session',MagicMock)
    monkeypatch.setattr(mod.time,'sleep',lambda _:None)


def test_dry_run_counts_without_sql(monkeypatch):
    setup_collect(monkeypatch)
    monkeypatch.setattr(mod,'fetch',lambda group,session:payload(item()))
    outcome=mod.collect(None,{'min_coverage':.5},'test',True)
    assert outcome.requested==2 and outcome.received==1 and outcome.empty==1
    assert outcome.persisted==0 and outcome.details['api_calls']==1


def test_permission_fail_keeps_detailed_counters(monkeypatch):
    from service.forward_pit.batch import BatchRunError
    setup_collect(monkeypatch)
    fetch=MagicMock(side_effect=mod.EodhdPermissionError('HTTP 403'))
    monkeypatch.setattr(mod,'fetch',fetch)
    with pytest.raises(BatchRunError) as error:
        mod.collect(None,{},'test',True)
    assert error.value.outcome.requested==2 and error.value.outcome.failed==2
    assert fetch.call_count==1


def test_missing_schema_keeps_counters_and_never_calls_api(monkeypatch):
    from service.forward_pit.batch import BatchRunError
    setup_collect(monkeypatch)
    engine = MagicMock()
    engine.url.database = 'alpha_trade'
    engine.connect.side_effect = RuntimeError('Missing dedicated table')
    fetch = MagicMock()
    monkeypatch.setattr(mod, 'fetch', fetch)
    with pytest.raises(BatchRunError) as error:
        mod.collect(engine, {}, 'test', False)
    assert error.value.outcome.requested == 2
    assert error.value.outcome.failed == 1
    assert 'SQL 0099' in str(error.value)
    fetch.assert_not_called()


def test_catalog_has_universe_notifications_recovery_and_no_yahoo():
    from ihm.services.batch_management import load_batch_specs, build_install_command, build_run_command
    spec=next(s for s in load_batch_specs() if s.name==mod.BATCH)
    assert spec.enabled
    assert spec.raw_config['status'] == 'RESEARCH_ONLY'
    assert spec.symbols_file == 'config/univers_batch/stock_bars_daily.txt'
    assert spec.universe_scope == spec.symbols_file
    assert spec.raw_config['symbol_source'] == 'universe-file'
    assert spec.raw_config['coverage_symbols_file'] == 'config/univers_batch/univers_filtred_tradable.txt'
    assert spec.raw_config['recovery_run_hours']=='4'
    assert not any('stock_analyst_estimate_history'==t for t in spec.tables)
    assert 'install_forward_pit_task.ps1' in ' '.join(build_install_command(spec))
    assert 'forward_pit_launcher.ps1' in ' '.join(build_run_command(spec))


def test_database_universe_normalized_and_limited():
    engine = MagicMock()
    engine.url.database = 'alpha_trade'
    engine.connect.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = [' z ', 'ABC', 'abc', '']
    assert mod.load_symbols(engine, {'symbol_source':'stock_bars_daily'}) == ['ABC', 'Z']
    assert mod.load_symbols(engine, {'symbol_source':'stock_bars_daily','max_symbols':1}) == ['ABC']


def test_file_universe_is_read_without_querying_the_database(tmp_path):
    path = tmp_path / 'symbols.txt'
    path.write_text(' z,ABC,abc;DEF\n', encoding='utf-8')
    engine = MagicMock()
    cfg = {'symbol_source':'universe-file', 'symbols_file':str(path)}
    assert mod.load_symbols(engine, cfg) == ['ABC','DEF','Z']
    engine.connect.assert_not_called()


def test_database_universe_rejects_other_market():
    engine = MagicMock()
    engine.url.database = 'alpha_trade_fr'
    with pytest.raises(ValueError, match='alpha_trade'):
        mod.load_symbols(engine, {'symbol_source':'stock_bars_daily'})
    engine.connect.assert_not_called()


def test_invalid_first_symbol_does_not_abort_valid_sibling(monkeypatch):
    setup_collect(monkeypatch)
    calls=[]
    def fetch(group, session):
        calls.append(list(group))
        if 'ABC' in group:
            raise mod.EodhdSymbolNotFound('HTTP 404 missing ABC')
        return payload(item(code='DEF.US'))
    monkeypatch.setattr(mod,'fetch',fetch)
    result=mod.collect(None,{'min_coverage':.5},'test',True)
    assert result.received==1 and result.empty==1 and result.failed==0
    assert calls==[['ABC','DEF'],['ABC'],['DEF']]
    assert result.details['invalid_symbol_count']==1
    assert result.details['no_consensus_count']==0


def test_coverage_only_on_reference_and_empty_outside_is_normal(monkeypatch):
    from service.forward_pit import batch
    setup_collect(monkeypatch)
    monkeypatch.setattr(batch,'_collection_symbols',lambda cfg:
        ['ABC'] if cfg.get('symbols_file')=='reference' else ['ABC','DEF'])
    monkeypatch.setattr(mod,'fetch',lambda group,session:payload(item()))
    result=mod.collect(None,{'coverage_symbols_file':'reference','min_coverage':.95},'test',True)
    assert result.details['coverage']==1
    assert result.details['overall_coverage']==.5
    assert result.details['reference_requested']==1
    assert result.details['no_consensus_symbols']==['DEF']
    assert not result.failed and not result.warnings


def test_missing_reference_title_not_removed_from_denominator(monkeypatch):
    from service.forward_pit import batch
    from service.forward_pit.outcomes import BatchRunError
    setup_collect(monkeypatch)
    monkeypatch.setattr(batch,'_collection_symbols',lambda cfg:
        ['ABC','MISSING'] if cfg.get('symbols_file')=='reference' else ['ABC','DEF'])
    monkeypatch.setattr(mod,'fetch',lambda group,session:payload(item(),item(code='DEF.US')))
    with pytest.raises(BatchRunError) as error:
        mod.collect(None,{'coverage_symbols_file':'reference'},'test',True)
    assert error.value.outcome.details['coverage']==.5
    assert error.value.outcome.details['reference_missing_from_collection']==['MISSING']


def test_technical_error_is_not_an_empty_consensus(monkeypatch):
    from service.forward_pit.outcomes import BatchRunError
    setup_collect(monkeypatch)
    monkeypatch.setattr(mod,'fetch',MagicMock(side_effect=RuntimeError('network error')))
    with pytest.raises(BatchRunError) as error:
        mod.collect(None,{},'test',True)
    result=error.value.outcome
    assert result.failed==2 and result.empty==0
    assert result.details['errors'][0]['error_type']=='RuntimeError'


def test_duplicate_runner_module_keeps_error_outcome(monkeypatch):
    import runpy
    from service.forward_pit import batch
    from service.forward_pit.outcomes import BatchRunError,Outcome
    with pytest.warns(RuntimeWarning,match='found in sys.modules'):
        namespace=runpy.run_module('service.forward_pit.batch',run_name='_counter_regression_runner')
    assert namespace['BatchRunError'] is batch.BatchRunError is BatchRunError
    globals_=namespace['execute'].__globals__
    engine=MagicMock();engine.url.database='alpha_trade'
    outcome=Outcome(requested=20,received=12,persisted=120,empty=7,failed=1)
    handler=MagicMock(side_effect=BatchRunError('technical failure',outcome))
    monkeypatch.setitem(globals_,'get_sqlalchemy_engine',lambda:engine)
    monkeypatch.setitem(globals_,'load_batch_config',lambda path:{mod.BATCH:{'enabled':True,'provider':'eodhd'}})
    monkeypatch.setitem(globals_['HANDLERS'],mod.BATCH,handler)
    with pytest.raises(BatchRunError):
        namespace['execute'](mod.BATCH)
    calls=engine.begin.return_value.__enter__.return_value.execute.call_args_list
    update=calls[-1].args[1]
    assert update['requested']==20 and update['received']==12
    assert update['persisted']==120 and update['empty']==7 and update['failed']==1
