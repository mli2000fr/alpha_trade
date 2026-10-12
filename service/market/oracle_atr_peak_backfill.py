"""Backed-up, tranche-wise fill of the new peak list on existing US study rows.

Keeps all existing Oracle selections, returns and D1/D10 aggregates. Writes only
the new list and its quality/status metadata; never source prices or labels.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import bindparam, inspect, text

from service.market.oracle_atr_repair import save
from service.market.oracle_atr_study import PEAK_FIELD, PEAK_PCT_FIELD, TABLE, attach_price_peaks
from service.market.oracle_path_maxima import load_price_peaks

LOG = logging.getLogger(__name__)
KEYS = ['trade_date', 'universe_hash', 'oracle_batch_id', 'oracle_horizon']


def persist_peaks(engine, records):
    """An UPDATE cannot introduce new study identities or change old returns."""
    if records:
        assignments = [PEAK_FIELD, PEAK_PCT_FIELD, 'movement_quality', 'status', 'quality_details']
        statement = text(f'UPDATE {TABLE} SET '+','.join(f'{c}=:{c}' for c in assignments)
            +' WHERE '+' AND '.join(f'{c}=:{c}' for c in KEYS))
        with engine.begin() as conn:
            conn.execute(statement, [{c: row[c] for c in KEYS+assignments} for row in records])


def run(*, output_dir, start_date='2020-01-01', end_date='2026-09-30',
        date_batch_size=20, apply=False, engine=None):
    if isinstance(date_batch_size, bool) or not isinstance(date_batch_size, int) or date_batch_size < 1:
        raise ValueError('date_batch_size doit être un entier strictement positif')
    start, end = pd.Timestamp(start_date).date(), pd.Timestamp(end_date).date()
    as_of = datetime.now(ZoneInfo('Europe/Paris')).date()
    if start > end or end > as_of:
        raise ValueError('Fenêtre invalide ou future')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    if engine is None:
        from database.connection import get_sqlalchemy_engine
        engine = get_sqlalchemy_engine(db_name='alpha_trade')
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('Base US alpha_trade exigée')
        ddl = conn.execute(text(f'SHOW CREATE TABLE {TABLE}')).fetchone()[1]
        rows = pd.read_sql(text(f'SELECT * FROM {TABLE} WHERE trade_date BETWEEN :start AND :end '
            'ORDER BY trade_date,universe_hash,oracle_batch_id,oracle_horizon'), conn,
            params={'start': start, 'end': end})
    # Full scoped backup before DDL or any change to quality/status metadata.
    backup = output_dir/'study_before.parquet'
    rows.to_parquet(backup, index=False)
    save(output_dir/'protocol.json', {'apply': apply, 'start': str(start), 'end': str(end),
        'as_of': str(as_of), 'selected_rows': len(rows), 'schema_before': ddl,
        'backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'helpers_sha256': {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in [
            'service/market/oracle_atr_study.py', 'service/market/oracle_path_maxima.py']},
        'updated_fields': [PEAK_FIELD, PEAK_PCT_FIELD, 'movement_quality', 'status', 'quality_details'],
        'preserves_original_selection': True, 'training': False, 'source_sql_writes': False})
    if apply:
        existing = {c['name'] for c in inspect(engine).get_columns(TABLE)}
        with engine.begin() as conn:
            for column, description in [
                (PEAK_FIELD, 'Oracle score order: max high J+1..J+H in signal-day USD price scale; research only'),
                (PEAK_PCT_FIELD, 'Oracle score order: dominant signed high/low excursion J+1..J+H, integer pct; research only')]:
                if column not in existing:
                    conn.execute(text(f'ALTER TABLE alpha_trade.{TABLE} ADD COLUMN {column} JSON NULL '
                                      f"COMMENT '{description}'"))
    if 'missing_returns_policy' not in rows or 'movement_quality' not in rows:
        raise ValueError('Migration de qualité 0095 nécessaire avant le remplissage des pics')
    days = sorted({str(day)[:10] for day in rows.trade_date})
    records, completed = [], 0
    state = {'status': 'RUNNING', 'completed_rows': 0, 'total_rows': len(rows), 'apply': apply}
    save(output_dir/'progress.json', state)
    try:
        for offset in range(0, len(days), date_batch_size):
            tranche = days[offset:offset+date_batch_size]
            part = rows[rows.trade_date.astype(str).str[:10].isin(tranche)]
            updated = []
            for (batch, horizon, universe_hash), group in part.groupby(
                    ['oracle_batch_id', 'oracle_horizon', 'universe_hash'], sort=False):
                # Load labels for the original symbols in this precise study scope.
                originals = group.to_dict('records')
                selections = {str(row['trade_date'])[:10]: json.loads(row['movement_quality'])['lists'].get(
                    'predicted_oracle_score_order_returns_pct', {}).get('selection_symbols', []) for row in originals}
                symbols = sorted({s for values in selections.values() for s in values})
                query = text('SELECT prediction_date,symbol,future_return,target_quality_valid,oracle_available_date '
                    'FROM global_oracle_labels WHERE batch_id=:batch AND horizon=:horizon '
                    'AND prediction_date BETWEEN :start AND :end AND symbol IN :symbols').bindparams(
                        bindparam('symbols', expanding=True))
                pieces = []
                with engine.connect() as conn:
                    for position in range(0, len(symbols), 150):
                        pieces.append(pd.read_sql(query, conn, params={'batch': batch, 'horizon': int(horizon),
                            'start': min(selections), 'end': max(selections), 'symbols': symbols[position:position+150]}))
                labels = (pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=[
                    'prediction_date', 'symbol', 'future_return', 'target_quality_valid', 'oracle_available_date']))
                maxima = load_price_peaks(engine, selections, labels, horizon=int(horizon), as_of=as_of)
                for original in originals:
                    day = str(original['trade_date'])[:10]
                    row = attach_price_peaks(original, maxima.get(day, {}), horizon=int(horizon),
                        policy=original['missing_returns_policy'])
                    updated.append(row)
            if apply:
                persist_peaks(engine, updated)
            pd.DataFrame(updated).to_parquet(output_dir/f'tranche-{offset//date_batch_size:03d}.parquet', index=False)
            records.extend(updated)
            completed += len(updated)
            state.update(completed_rows=completed, last_date=tranche[-1])
            save(output_dir/'progress.json', state)
            LOG.info('%d/%d lignes : pics qualifiés jusqu’au %s', completed, len(rows), tranche[-1])
        infos = [json.loads(row['movement_quality'])['lists'][PEAK_FIELD] for row in records]
        counts = {status: sum(info['status'] == status for info in infos)
                  for status in ['COMPLETE', 'PARTIAL', 'UNAVAILABLE']}
        reasons = {}
        for info in infos:
            for reason in info['missing_reasons'].values():
                reasons[reason] = reasons.get(reason, 0)+1
        report = {'status': 'COMPLETED', 'apply': apply, 'rows': completed,
            'nonnull_rows': sum(row[PEAK_FIELD] is not None for row in records),
            'qualified_prices': sum(info['known_count'] for info in infos),
            'peak_list_statuses': counts, 'missing_reasons': reasons}
        save(output_dir/'report.json', report)
        save(output_dir/'progress.json', {**state, 'status': 'COMPLETED'})
        return report
    except Exception as exc:
        save(output_dir/'progress.json', {**state, 'status': 'FAILED', 'error': str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--start-date', default='2020-01-01')
    parser.add_argument('--end-date', default='2026-09-30')
    parser.add_argument('--date-batch-size', default=20, type=int)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(run(**vars(args)), allow_nan=False))


if __name__ == '__main__':
    main()
