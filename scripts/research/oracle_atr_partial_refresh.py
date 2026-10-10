"""Back up the US study, add its two metadata columns, refresh only aggregates."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
from sqlalchemy import inspect, text

from database.connection import get_sqlalchemy_engine
from service.market.oracle_atr_repair import save
from service.market.oracle_atr_study import MOVEMENT_FIELDS, TABLE, run


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--symbol-source', required=True)
    parser.add_argument('--start-date', required=True)
    parser.add_argument('--end-date', required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('Base US exigée')
        old = pd.read_sql(text(f'SELECT * FROM {TABLE}'), conn)
        ddl = conn.execute(text(f'SHOW CREATE TABLE {TABLE}')).fetchone()[1]
    old.to_parquet(args.output_dir/'study_before.parquet', index=False)
    save(args.output_dir/'schema_before.json', {'table': TABLE, 'ddl': ddl, 'backup_rows': len(old)})
    definitions = {'missing_returns_policy': "VARCHAR(16) NOT NULL DEFAULT 'strict'", 'movement_quality': 'JSON NULL'}
    existing = {c['name'] for c in inspect(engine).get_columns(TABLE)}
    with engine.begin() as conn:
        for column, definition in definitions.items():
            if column not in existing:
                conn.execute(text(f'ALTER TABLE {TABLE} ADD COLUMN {column} {definition}'))
    def progress(current, total, message):
        state = {'status': 'RUNNING', 'completed': current, 'total': total, 'message': message}
        save(args.output_dir/'progress.json', state)
        print(f'{current}/{total} {message}', flush=True)
    try:
        result = run(batch_id=args.batch_id, symbol_source=args.symbol_source, start_date=args.start_date,
            end_date=args.end_date, engine=engine, missing_returns_policy='partial', resume=False,
            date_batch_size=20, progress_callback=progress)
        rows = result.pop('rows')
        result['nonnull_lists'] = {field: sum(row[field] is not None for row in rows) for field in MOVEMENT_FIELDS}
        save(args.output_dir/'report.json', result)
        save(args.output_dir/'progress.json', {'status': 'COMPLETED', 'completed': len(rows), 'total': len(rows)})
        print(result, flush=True)
    except Exception as exc:
        save(args.output_dir/'failure.json', {'status':'FAILED','error':str(exc)})
        raise


if __name__ == '__main__':
    main()
