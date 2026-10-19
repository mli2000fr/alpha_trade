"""Bounded US information-axis readiness: SELECT-only inventory, no outcomes.

No supplier/LLM calls, backfills, SQL writes or model/batch changes. A fresh
snapshot is immutable. Qualification follows offline, never by future returns.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

from sqlalchemy import bindparam, text

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
TABLES = {
    'stock_analyst_consensus_eodhd_history': ('symbol', 'observed_at', 'available_at', 'snapshot_date'),
    'stock_earnings_calendar': ('symbol', 'last_updated', 'last_updated', 'earnings_date'),
    'sec_filing_raw': ('symbol', 'observed_at', 'available_at', 'filing_date'),
    'sec_corporate_events': ('symbol', 'available_at', 'available_at', 'filing_date'),
}


def query(conn, sql, symbols=None, **params):
    if not sql.lstrip().upper().startswith('SELECT'):
        raise ValueError('SELECT only')
    stmt = text(sql)
    if symbols is not None:
        stmt = stmt.bindparams(bindparam('symbols', expanding=True)); params['symbols'] = symbols
    return [dict(r) for r in conn.execute(stmt, params).mappings()]


def inventory(root):
    from database.connection import get_sqlalchemy_engine
    symbols = sorted({s.upper() for s in re.split(r'[,;\s]+', UNIVERSE.read_text(encoding='utf-8-sig').strip()) if s})
    root.mkdir(parents=True, exist_ok=False)
    cutoff = datetime.now(timezone.utc)
    atomic_json(root/'protocol.json', dict(created_at_utc=cutoff.isoformat(), universe=str(UNIVERSE),
        universe_sha256=digest(UNIVERSE), symbols=symbols, sql='READ ONLY / REPEATABLE READ / ROLLBACK',
        source_sha256=digest(Path(__file__)), decision='Inventory only, no future outcomes read or performance test.',
        primary_family='Actual same-period EPS/revenue changes between received EODHD snapshots; no calendar-date backdating or restored Yahoo.',
        secondary_readiness=['Guidance old/new same metric-period-unit-basis', 'Actual versus PRE-announcement archived consensus'],
        model_training=False, api_calls=0, sql_writes=False, production_changes=False, orders=False))
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade':
        raise ValueError('US database required')
    report = dict(started_at_utc=cutoff.isoformat(), universe_count=len(symbols), tables={})
    with engine.connect() as conn:
        conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
        schema = query(conn, 'SELECT TABLE_NAME,COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE()')
        names = {r['TABLE_NAME'] for r in schema}
        for table, (symbol, observed, available, event) in TABLES.items():
            if table not in names:
                report['tables'][table] = dict(status='MISSING_TABLE'); continue
            print('Inventory', table, flush=True)
            cols = {r['COLUMN_NAME'] for r in schema if r['TABLE_NAME'] == table}
            info = dict(columns=sorted(cols), global_counts=query(conn, f'''SELECT COUNT(*) n,
                COUNT(DISTINCT {symbol}) symbols,MIN({observed}) first_observed,MAX({observed}) last_observed,
                MIN({event}) first_event,MAX({event}) last_event FROM {table}''')[0],
                scoped=query(conn, f'''SELECT COUNT(*) n,COUNT(DISTINCT {symbol}) symbols,
                    COUNT(DISTINCT DATE({observed})) observation_dates,
                    MIN({available}) first_available,MAX({available}) last_available
                    FROM {table} WHERE {symbol} IN :symbols''', symbols)[0])
            report['tables'][table] = info
            if table == 'stock_analyst_consensus_eodhd_history':
                info['daily'] = query(conn, f'''SELECT snapshot_date,COUNT(*) n,COUNT(DISTINCT symbol) symbols,
                    MIN(observed_at) first_observed,MAX(observed_at) last_observed,
                    SUM(fiscal_identity_qualified) fiscal_qualified,SUM(units_qualified) units_qualified,
                    SUM(historical_pit_qualified) historical_pit_qualified,
                    SUM(revisions_down_7d IS NOT NULL) down7_present
                    FROM {table} WHERE symbol IN :symbols GROUP BY snapshot_date ORDER BY snapshot_date''', symbols)
                info['period_coverage'] = query(conn, f'''SELECT horizon_raw,COUNT(*) n,
                    MIN(fiscal_period_end) first_period,MAX(fiscal_period_end) last_period
                    FROM {table} WHERE symbol IN :symbols GROUP BY horizon_raw''', symbols)
            if table.startswith('sec_'):
                info['forms'] = query(conn, f'''SELECT form_type,COUNT(*) n,MIN(filing_date) first_filing,
                    MAX(filing_date) last_filing,MIN(available_at) first_available,
                    SUM(acceptance_datetime IS NOT NULL) acceptance_present
                    FROM {table} WHERE symbol IN :symbols GROUP BY form_type''', symbols)
        if 'sec_filing_documents' in names:
            report['documents'] = query(conn, '''SELECT d.document_type,COUNT(*) n,
                SUM(d.content_blob IS NOT NULL) with_blob,MIN(d.available_at) first_available,
                MAX(d.available_at) last_available FROM sec_filing_documents d
                JOIN sec_filing_raw f ON f.accession_number=d.accession_number
                WHERE f.symbol IN :symbols GROUP BY d.document_type''', symbols)
        if 'oracle_extreme_predictions' in names:
            report['oracle_batches'] = query(conn, '''SELECT batch_id,COUNT(*) n,
                COUNT(DISTINCT prediction_date) dates,MIN(prediction_date) first_prediction,
                MAX(prediction_date) last_prediction,MIN(created_at) first_created,MAX(created_at) last_created
                FROM oracle_extreme_predictions WHERE symbol IN :symbols AND prediction_date>='2026-10-01'
                GROUP BY batch_id''', symbols)
        if 'oracle_path_prediction_lineage' in names:
            report['oracle_path_lineage'] = query(conn, '''SELECT batch_id,target_name,target_horizon,
                COUNT(*) n,MIN(prediction_date) first_prediction,MAX(prediction_date) last_prediction,
                MAX(model_available_date) max_model_available,
                SUM(model_available_date>=prediction_date) bad_availability
                FROM oracle_path_prediction_lineage WHERE symbol IN :symbols AND prediction_date>='2026-10-01'
                GROUP BY batch_id,target_name,target_horizon''', symbols)
        report['raw_consensus_runs'] = query(conn, '''SELECT run_id,status,started_at,finished_at,
            requested_count,received_count,persisted_count,failed_count,empty_count
            FROM pit_collection_runs WHERE batch_name='eodhd_consensus_snapshot' ORDER BY started_at''')
        report['raw_consensus_receipts'] = query(conn, '''SELECT endpoint,provider,COUNT(*) n,
            MIN(observed_at) first_observed,MAX(observed_at) last_observed
            FROM pit_raw_payloads WHERE batch_name='eodhd_consensus_snapshot' GROUP BY endpoint,provider''')
        conn.rollback()
    engine.dispose()
    report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    report['status'] = 'INVENTORY_COMPLETED_NO_OUTCOMES_READ'
    atomic_json(root/'inventory.json', report)
    atomic_json(root/'inventory-seal.json', dict(files={n: digest(root/n) for n in ['protocol.json', 'inventory.json']}))
    print('Inventory complete', report['finished_at_utc'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    inventory(parser.parse_args().output)
