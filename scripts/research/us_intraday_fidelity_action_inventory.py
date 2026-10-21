"""Supplementary READ ONLY inventory of staging CA, not a coverage certificate."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_intraday_fidelity_readiness import READ


def run(root):
    if (root/'source-actions.json').exists():
        raise ValueError('Immutable supplemental inventory')
    verify_hashes(root, READ(root/'prepared.json')['files'])
    from sqlalchemy import text, bindparam, inspect
    from database.connection import get_sqlalchemy_engine
    cases = pd.read_parquet(root/'candidates.parquet')
    symbols = sorted(cases.symbol.unique())
    start = cases.oracle_date.min().to_pydatetime()
    end = (cases.expiry.max().tz_convert('America/New_York').tz_localize(None).normalize()
        +pd.Timedelta(days=1)).to_pydatetime()
    engine = get_sqlalchemy_engine()
    started = datetime.now(timezone.utc).isoformat()
    frame = pd.DataFrame()
    table = 'corporate_action_source_events'
    with engine.connect() as conn:
        conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
        if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade':
            raise ValueError('US alpha_trade required')
        inspector = inspect(conn)
        present = table in inspector.get_table_names()
        if present:
            frame = pd.read_sql_query(text('''SELECT id,provider,provider_event_id,symbol,action_type,
                effective_date,value_num,related_symbol,notes,observed_at,available_at,payload_hash,
                run_id,conflict_group_key FROM corporate_action_source_events
                WHERE symbol IN :symbols AND effective_date>=:start AND effective_date<:end''')
                .bindparams(bindparam('symbols', expanding=True)), conn,
                params=dict(symbols=symbols, start=start, end=end))
        conn.rollback()
    engine.dispose()
    frame.to_parquet(root/'source-actions.parquet', index=False)
    conflicts = 0
    if len(frame):
        conflicts = int(frame.groupby(['symbol', 'action_type', 'effective_date']).value_num.nunique().gt(1).sum())
    atomic_json(root/'source-actions.json', dict(status='SOURCE_EVENT_INVENTORY_NOT_QUALIFICATION',
        started_at_utc=started, finished_at_utc=datetime.now(timezone.utc).isoformat(),
        source_sha256=digest(Path(__file__)), prepared_sha256=digest(root/'prepared.json'),
        files={'source-actions.parquet': digest(root/'source-actions.parquet')},
        table=table, present=present, rows=len(frame),
        symbols=int(frame.symbol.nunique()) if len(frame) else 0,
        action_types={str(k): int(v) for k, v in frame.action_type.value_counts().items()} if len(frame) else {},
        providers={str(k): int(v) for k, v in frame.provider.value_counts().items()} if len(frame) else {},
        conflicting_value_groups=conflicts,
        transaction='REPEATABLE READ / READ ONLY / ROLLBACK', sql_writes=False, provider_calls=False,
        note='This is the OTHER staging source, distinct from corporate_actions_events. No automatic ingestion or application. value_num alone does not qualify currency, payable date, complete coverage, deduplication, identity or original payload. Empty is NOT proof of no CA.'))
    print(READ(root/'source-actions.json'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    run(p.parse_args().output)
