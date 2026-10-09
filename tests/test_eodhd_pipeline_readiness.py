"""No production DB, network, real wait or import is used."""
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from dataIntegrityEngine.eodhd import readiness, cli


@pytest.mark.parametrize('instant,expected', [
    ('2026-10-08T22:45:00+02:00', '2026-10-07'),
    ('2026-10-09T00:00:00+02:00', '2026-10-08'),
    ('2026-10-09T08:00:00+02:00', '2026-10-08'),
    ('2026-10-12T08:00:00+02:00', '2026-10-09'),
    ('2026-10-28T23:00:00+01:00', '2026-10-28'),
    ('2026-11-05T00:00:00+01:00', '2026-11-04'),
    ('2026-07-06T08:00:00+02:00', '2026-07-02'),
    ('2026-11-27T21:00:00+01:00', '2026-11-27'),  # half-day close 18 UTC + 2h
])
def test_last_published_session_including_dst_holiday_and_half_day(instant, expected):
    assert readiness.latest_published_session({}, now=datetime.fromisoformat(instant)) == expected


def test_wait_is_pinned_across_midnight_with_no_real_sleep():
    clock = [datetime.fromisoformat('2026-10-08T22:45:00+02:00')]
    waits = []
    def sleep(seconds):
        waits.append(seconds)
        clock[0] += timedelta(seconds=seconds)
    ready = readiness.wait_for_publication(date(2026, 10, 8), {},
        now_fn=lambda: clock[0], sleep_fn=sleep)
    assert ready == datetime(2026, 10, 8, 22, tzinfo=UTC)
    assert sum(waits) == 75 * 60
    assert max(waits) <= 60


def test_publication_delay_is_configurable_and_invalid_values_fail():
    assert readiness.publication_at(date(2026, 10, 8), {'eodhd': {'bulk_publish_offset_hours': 1}}).hour == 21
    for value in (-1, 25, float('nan')):
        with pytest.raises(ValueError):
            readiness.publication_offset({'eodhd': {'bulk_publish_offset_hours': value}})
    with pytest.raises(ValueError, match='hors séance'):
        readiness.publication_at(date(2026, 10, 10), {})
    with pytest.raises(ValueError, match='future'):
        readiness.wait_for_publication(date(2026, 10, 9), {}, now_fn=lambda: datetime(2026, 10, 7, tzinfo=UTC))


def test_strict_calendar_has_no_weekday_fallback(monkeypatch):
    from common import market_calendar
    def unavailable(code, **kwargs):
        assert code == 'US_EQ' and kwargs == {'allow_us_weekday_fallback': False}
        raise RuntimeError('calendar unavailable')
    monkeypatch.setattr(market_calendar, 'get_market_calendar', unavailable)
    with pytest.raises(RuntimeError, match='unavailable'):
        readiness.latest_published_session({})


def test_coverage_requires_exact_date_valid_bar_and_benchmark():
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE stock_bars_daily (
            symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, is_filled INTEGER,
            PRIMARY KEY(symbol,date))'''))
        for symbol, day, filled, volume in [
            ('A', '2026-10-08', 0, 100), ('B', '2026-10-07', 0, 100),
            ('C', '2026-10-08', 1, 100), ('D', '2026-10-08', 0, 0),
            ('E', '2026-10-09', 0, 100), ('SPY', '2026-10-08', 0, 100),
        ]:
            conn.execute(text('INSERT INTO stock_bars_daily VALUES(:s,:d,10,11,9,10,:v,:f)'),
                         {'s':symbol,'d':day,'v':volume,'f':filled})
    gate = readiness.target_coverage(engine, ['A','B','C','D','E'], '2026-10-08')
    assert gate['covered'] == 1 and gate['status'] == 'FAILED'
    assert gate['missing_symbols'] == ['B','C','D','E']
    assert readiness.target_coverage(engine, ['A'], '2026-10-08')['status'] == 'PASSED'
    assert readiness.target_coverage(engine, ['A'], '2026-10-08', benchmark='QQQ')['status'] == 'FAILED'
    # Idempotent recheck: no writes and the existing target rows qualify.
    assert gate == readiness.target_coverage(engine, ['A','B','C','D','E'], '2026-10-08')
    with engine.begin() as conn:
        for i in range(19):
            conn.execute(text("INSERT INTO stock_bars_daily VALUES(:s,'2026-10-08',10,11,9,10,100,0)"), {'s':f'N{i}'})
    universe = [f'N{i}' for i in range(20)]
    assert readiness.target_coverage(engine, universe, '2026-10-08')['coverage_ratio'] == .95
    assert readiness.target_coverage(engine, universe, '2026-10-08')['status'] == 'PASSED'
    assert readiness.target_coverage(engine, universe, '2026-10-08', minimum=1)['status'] == 'FAILED'
    engine.dispose()


def cli_environment(monkeypatch):
    from dataIntegrityEngine import import_eodhd_bar as shim
    from common import universe_files
    from database import connection
    monkeypatch.setattr(shim, 'configure_root_logging', lambda **kwargs: None)
    monkeypatch.setattr(shim, '_load_config_safe', lambda: {'market_data': {'bars_provider': 'eodhd'}})
    monkeypatch.setattr(universe_files, 'load_universe_file_symbols', lambda source: ['A','B'])
    monkeypatch.setattr(connection, 'get_sqlalchemy_engine', lambda: 'isolated-engine')
    monkeypatch.setattr(readiness, 'publication_at', lambda *args, **kwargs: datetime(2026, 10, 8, 22, tzinfo=UTC))
    events = []
    monkeypatch.setattr(readiness, 'wait_for_publication', lambda *a, **kw: events.append('wait'))
    def ingest(**kwargs):
        events.append(('import', kwargs))
        return {'errors':0, 'target_date':kwargs['target_date'], 'rows_upserted_stock_bars_daily':2}
    monkeypatch.setattr(cli, 'run_eodhd_ingestion', ingest)
    summaries = []
    monkeypatch.setattr(cli, 'emit_run_summary', summaries.append)
    return events, summaries


def test_cli_waits_then_scopes_import_and_blocks_stale_data(monkeypatch):
    events, summaries = cli_environment(monkeypatch)
    monkeypatch.setattr(readiness, 'target_coverage', lambda *a, **kw: {
        'status':'FAILED', 'covered':0, 'requested':2, 'coverage_ratio':0,
        'minimum':.95, 'benchmark':'SPY', 'benchmark_available':False, 'missing_symbols':['A','B']})
    result = cli.main(['--write','--target-date','2026-10-08','--symbol-source','universe-file:test.txt',
                       '--wait-for-publication','--require-target-coverage'])
    assert events[0] == 'wait'
    assert events[1][1]['target_date'] == '2026-10-08'
    assert events[1][1]['symbols'] == ['A','B','SPY']
    assert result == 1 and summaries[-1]['status'] == 'FAILED'
    assert summaries[-1]['stopped_reason'] == 'target_date_coverage_insufficient'


def test_cli_qualified_existing_target_is_success(monkeypatch):
    events, summaries = cli_environment(monkeypatch)
    monkeypatch.setattr(readiness, 'target_coverage', lambda *a, **kw: {'status':'PASSED'})
    assert cli.main(['--write','--target-date','2026-10-08','--symbol-source','universe-file:test.txt',
                     '--require-target-coverage']) == 0
    assert summaries[-1]['status'] == 'COMPLETED'


def test_cli_coverage_read_failure_preserves_import_counters(monkeypatch):
    _, summaries = cli_environment(monkeypatch)
    def failed(*args, **kwargs):
        raise RuntimeError('DB unavailable')
    monkeypatch.setattr(readiness, 'target_coverage', failed)
    assert cli.main(['--write','--target-date','2026-10-08','--symbol-source','universe-file:test.txt',
                     '--require-target-coverage']) == 1
    assert summaries[-1]['rows_upserted_stock_bars_daily'] == 2
    assert summaries[-1]['stopped_reason'] == 'target_date_coverage_check_failed'


def test_empty_explicit_universe_never_falls_back(monkeypatch):
    events, _ = cli_environment(monkeypatch)
    from common import universe_files
    monkeypatch.setattr(universe_files, 'load_universe_file_symbols', lambda source: [])
    with pytest.raises(ValueError, match='vide'):
        cli.main(['--write','--symbol-source','universe-file:test.txt'])
    assert events == []


def test_cli_wrong_provider_and_invalid_threshold_never_import(monkeypatch):
    events, _ = cli_environment(monkeypatch)
    args = ['--write','--target-date','2026-10-08','--symbol-source','universe-file:test.txt', '--require-target-coverage']
    with pytest.raises(ValueError, match='coverage'):
        cli.main([*args, '--min-target-coverage','nan'])
    from dataIntegrityEngine import import_eodhd_bar as shim
    monkeypatch.setattr(shim, 'resolve_bars_provider', lambda cfg: 'alpaca')
    with pytest.raises(ValueError, match='fournisseur'):
        cli.main(args)
    assert events == []


def test_pipeline_import_summary_exposes_target_date_and_failure():
    from ihm.services.run_summary import get_run_summary_detail_lines
    lines = get_run_summary_detail_lines({'step_key':'import_alpaca_bar', 'run_summary': {
        'target_coverage': {'target_date':'2026-10-08','covered':0,'requested':2,
            'coverage_ratio':0,'status':'FAILED','benchmark':'SPY','benchmark_available':False},
        'error_message':'Cours J absents'}})
    assert any('2026-10-08' in line and '0/2' in line and 'FAILED' in line for line in lines)
    assert 'Cours J absents' in lines
