"""Isolated session import: no network, production SQL, sleep or orders."""
from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text

from dataIntegrityEngine import import_alpaca_session as module
from dataIntegrityEngine.eodhd.readiness import target_coverage


CFG = {'market_data': {'bars_provider': 'alpaca'}}
DAY = date(2026, 10, 19)
NOW = datetime(2026, 10, 20, 1, tzinfo=UTC)


def bar(day='2026-10-19'):
    return dict(t=day+'T04:00:00Z', o=10, h=12, l=9, c=11, v=100, n=10, vw=10.5)


def environment(monkeypatch):
    db = Mock()
    db.execute.return_value.scalar.return_value = 'alpha_trade'
    monkeypatch.setattr(module, '_get_latest_bar_dates', lambda *a: {'A':date(2026,10,16)})
    fetch = Mock(side_effect=lambda symbol, **kw: [bar()])
    monkeypatch.setattr(module, 'fetch_daily_history', fetch)
    daily, raw = [], []
    monkeypatch.setattr(module, '_upsert_stock_bars_daily', lambda db, rows: daily.extend(rows) or len(rows))
    monkeypatch.setattr(module, '_upsert_stock_bars', lambda db, rows: raw.extend(rows) or len(rows))
    gate = Mock(return_value={'status':'PASSED'})
    monkeypatch.setattr(module, 'target_coverage', gate)
    return dict(session=db, engine='test-engine', config=CFG, now_fn=lambda: NOW), fetch, daily, raw, gate


def test_explicit_session_refreshes_both_tables_and_repeats_same_keys(monkeypatch):
    kw, fetch, daily, raw, gate = environment(monkeypatch)
    for _ in range(2):
        result = module.run(target_date=DAY, symbols=['A'], **kw)
        assert result['status']=='COMPLETED' and result['rows_upserted_stock_bars_daily']==2
    assert [call.args[0] for call in fetch.call_args_list]==['A','SPY','A','SPY']
    assert all(c.kwargs['end']=='2026-10-19' and c.kwargs['feed']=='sip' for c in fetch.call_args_list)
    assert fetch.call_args_list[0].kwargs['start']=='2026-10-12'
    assert daily[0]['date']==DAY and raw[0]['timestamp']=='2026-10-19 09:30:00'
    assert daily[0]==daily[2] and raw[0]==raw[2]
    assert daily[0]['data_source']==raw[0]['data_source']=='alpaca_sip'
    assert kw['session'].commit.call_count==4
    assert gate.call_args.kwargs['require_raw'] is True
    assert gate.call_args.kwargs['required_source']=='alpaca_sip'


def test_missing_target_cannot_reuse_old_rows(monkeypatch):
    kw, fetch, _, _, gate = environment(monkeypatch)
    fetch.side_effect=lambda symbol, **kw: [bar('2026-10-16')] if symbol=='A' else [bar()]
    gate.return_value={'status':'FAILED','covered':0,'requested':1,'coverage_ratio':0,'benchmark_available':True}
    result=module.run(target_date=DAY,symbols=['A'],**kw)
    assert result['status']=='FAILED' and result['failed_symbols']==1
    assert gate.call_args.kwargs['excluded_symbols']=={'A'}
    assert result['rows_upserted_stock_bars_daily']==2


def test_commit_failure_keeps_only_committed_counters(monkeypatch):
    kw, _, _, _, gate = environment(monkeypatch)
    kw['session'].commit.side_effect=[RuntimeError('write failed'),None]
    result=module.run(target_date=DAY,symbols=['A'],**kw)
    assert result['rows_upserted_stock_bars_daily']==1
    assert kw['session'].rollback.call_count==1
    assert gate.call_args.kwargs['excluded_symbols']=={'A'}


def test_isolated_error_can_pass_only_when_explicit_coverage_gate_passes(monkeypatch):
    kw, fetch, _, _, gate=environment(monkeypatch)
    def download(symbol, **kwargs):
        if symbol=='A':
            raise RuntimeError('isolated timeout')
        return [bar()]
    fetch.side_effect=download
    result=module.run(target_date=DAY,symbols=['A','B'],**kw)
    assert result['status']=='COMPLETED' and result['warning_count']==1
    assert result['failed_symbol_list']==['A']
    assert gate.call_args.kwargs['excluded_symbols']=={'A'}


def test_old_last_date_is_caught_up_to_frozen_target(monkeypatch):
    kw, fetch, _, _, _=environment(monkeypatch)
    monkeypatch.setattr(module,'_get_latest_bar_dates',lambda *a:{'A':date(2026,8,3)})
    module.run(target_date=DAY,symbols=['A'],**kw)
    assert fetch.call_args_list[0].kwargs['start']=='2026-08-03'
    assert fetch.call_args_list[0].kwargs['end']=='2026-10-19'


def test_rights_quota_failure_stops_even_if_preexisting_coverage(monkeypatch):
    kw, fetch, _, _, _ = environment(monkeypatch)
    fetch.side_effect=module.DailyHistoryBlocked('403')
    result=module.run(target_date=DAY,symbols=['A','B'],**kw)
    assert fetch.call_count==1 and result['status']=='FAILED'
    assert result['stopped_reason']=='account_rights_or_quota'
    kw['session'].commit.assert_not_called()


def test_readback_failure_preserves_committed_counters(monkeypatch):
    kw, _, _, _, gate = environment(monkeypatch)
    gate.side_effect=RuntimeError('SQL')
    result=module.run(target_date=DAY,symbols=['A'],**kw)
    assert result['status']=='FAILED' and result['rows_upserted_stock_bars_daily']==2
    assert result['stopped_reason']=='target_date_coverage_check_failed'


@pytest.mark.parametrize('symbols,minimum,config', [([], .95, CFG),(['A'],float('nan'),CFG),
    (['A'],0,CFG),(['A'],.95,{'market_data':{'bars_provider':'eodhd'}})])
def test_invalid_inputs_never_download(monkeypatch,symbols,minimum,config):
    kw, fetch, _, _, _=environment(monkeypatch)
    kw['config']=config
    with pytest.raises(ValueError):
        module.run(target_date=DAY,symbols=symbols,minimum=minimum,**kw)
    fetch.assert_not_called()


def test_wrong_database_never_downloads(monkeypatch):
    kw, fetch, _, _, _=environment(monkeypatch)
    kw['session'].execute.return_value.scalar.return_value='alpha_trade_fr'
    with pytest.raises(ValueError,match='alpha_trade'):
        module.run(target_date=DAY,symbols=['A'],**kw)
    fetch.assert_not_called()


@pytest.mark.parametrize('day,close', [('2026-10-19',20), ('2026-11-04',21),('2026-11-27',18)])
def test_sip_close_delay_dst_and_halfday(day,close):
    ready=module.ready_at(date.fromisoformat(day))
    assert ready.hour==close and ready.minute==20


def test_wait_pins_session_across_midnight_and_requires_explicit_wait():
    clock=[datetime(2026,10,19,20,10,tzinfo=UTC)]
    waits=[]
    def sleep(seconds):
        waits.append(seconds);clock[0]+=timedelta(seconds=seconds)
    with pytest.raises(ValueError,match='Attendre'):
        module.await_session(DAY,now_fn=lambda:clock[0])
    module.await_session(DAY,wait=True,now_fn=lambda:clock[0],sleep_fn=sleep)
    assert sum(waits)==600 and max(waits)<=60
    module.await_session(DAY,now_fn=lambda:NOW)
    with pytest.raises(ValueError,match='hors séance'):
        module.ready_at(date(2026,10,18))
    with pytest.raises(ValueError,match='future'):
        module.await_session(DAY,wait=True,now_fn=lambda:datetime(2026,10,15,tzinfo=UTC))


def test_cli_emits_summary_and_preserves_failure_exit(monkeypatch,capsys):
    monkeypatch.setattr(module,'load_universe_file_symbols',lambda source:['A'])
    run=Mock(return_value={'errors':1,'status':'FAILED','inserted_bars':2})
    monkeypatch.setattr(module,'run',run)
    args=['--write','--require-target-coverage','--target-date',str(DAY),
          '--symbol-source','universe-file:test.txt','--wait-for-publication']
    assert module.main(args)==1
    assert run.call_args.kwargs['symbols']==['A'] and run.call_args.kwargs['wait']
    assert '::alpha_trade_run_summary::' in capsys.readouterr().out
    with pytest.raises(ValueError,match='obligatoires'):
        module.main([x for x in args if x!='--write'])


def test_sip_coverage_requires_provenance_both_tables_and_exact_values():
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE stock_bars_daily (symbol TEXT, date TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL, is_filled INTEGER,
            data_source TEXT, data_adjustment TEXT, PRIMARY KEY(symbol,date))'''))
        conn.execute(text('''CREATE TABLE stock_bars (symbol TEXT, timestamp TEXT, timeframe TEXT,
            open_price REAL, high_price REAL, low_price REAL, close_price REAL, volume REAL,
            data_source TEXT, data_adjustment TEXT, PRIMARY KEY(symbol,timestamp,timeframe))'''))
        for symbol,source in [('A','alpaca_sip'),('B','alpaca_iex'),('C','alpaca_sip'),('SPY','alpaca_sip')]:
            conn.execute(text("INSERT INTO stock_bars_daily VALUES(:s,'2026-10-19',10,12,9,11,100,0,:source,'split')"),dict(s=symbol,source=source))
            if symbol!='C':
                conn.execute(text("INSERT INTO stock_bars VALUES(:s,'2026-10-19 09:30:00','1D',10,12,9,11,100,:source,'split')"),dict(s=symbol,source=source))
    kwargs=dict(required_source='alpaca_sip',require_raw=True)
    assert target_coverage(engine,['A'],str(DAY),**kwargs)['status']=='PASSED'
    gate=target_coverage(engine,['A','B','C'],str(DAY),**kwargs)
    assert gate['missing_symbols']==['B','C'] and gate['status']=='FAILED'
    assert target_coverage(engine,['A'],str(DAY),excluded_symbols={'A'},**kwargs)['status']=='FAILED'
    with engine.begin() as conn:
        for index in range(19):
            params=dict(s=f'N{index}')
            conn.execute(text("INSERT INTO stock_bars_daily VALUES(:s,'2026-10-19',10,12,9,11,100,0,'alpaca_sip','split')"),params)
            conn.execute(text("INSERT INTO stock_bars VALUES(:s,'2026-10-19 09:30:00','1D',10,12,9,11,100,'alpaca_sip','split')"),params)
    universe=[f'N{index}' for index in range(20)]
    gate=target_coverage(engine,universe,str(DAY),**kwargs)
    assert gate['coverage_ratio']==.95 and gate['status']=='PASSED'
    assert target_coverage(engine,universe,str(DAY),minimum=1,**kwargs)['status']=='FAILED'
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_bars SET data_source='alpaca_iex' WHERE symbol='SPY'"))
    assert target_coverage(engine,universe,str(DAY),**kwargs)['status']=='FAILED'
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_bars SET volume=99 WHERE symbol='A'"))
    assert target_coverage(engine,['A'],str(DAY),**kwargs)['status']=='FAILED'
    engine.dispose()
