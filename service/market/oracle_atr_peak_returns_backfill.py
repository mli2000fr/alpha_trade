"""Fill dominant signed path returns, preserving archived prices, with a US backup.

Reads qualified exact HIGH/LOW paths; no training, selection change or terminal
return rewrite. Current peaks must match the archived peaks and J baseline. Dates still
immature or with no qualified path remain NULL; no missing value is imputed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import bindparam, inspect, text

from service.market.oracle_atr_peak_backfill import KEYS
from service.market.oracle_atr_repair import save
from service.market.oracle_atr_study import PEAK_FIELD, PEAK_PCT_FIELD, TABLE, attach_peak_returns
from service.market.oracle_path_maxima import load_price_peaks

UPDATED_FIELDS = [PEAK_PCT_FIELD, 'movement_quality', 'status', 'quality_details']


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest() if value is not None and not pd.isna(value) else None


def _json(value):
    return json.loads(value) if value is not None and not pd.isna(value) else None


def _nullable(value):
    return None if value is None or pd.isna(value) else value


def _load_current_paths(engine, originals, as_of):
    """Caller groups by exact batch, horizon and universe; no replacement symbols."""
    selections = {str(row['trade_date'])[:10]: json.loads(row['movement_quality'])['lists'].get(
        PEAK_FIELD, {}).get('value_symbols', []) for row in originals}
    symbols = sorted({symbol for selection in selections.values() for symbol in selection})
    if not symbols:
        return {day:{} for day in selections}
    query = text('SELECT prediction_date,symbol,future_return,target_quality_valid,oracle_available_date '
        'FROM global_oracle_labels WHERE batch_id=:batch AND horizon=:horizon '
        'AND prediction_date BETWEEN :start AND :end AND symbol IN :symbols').bindparams(
            bindparam('symbols', expanding=True))
    parts = []
    with engine.connect() as conn:
        for offset in range(0, len(symbols), 150):
            parts.append(pd.read_sql(query, conn, params={'batch':originals[0]['oracle_batch_id'],
                'horizon':int(originals[0]['oracle_horizon']), 'start':min(selections), 'end':max(selections),
                'symbols':symbols[offset:offset+150]}))
    return load_price_peaks(engine, selections, pd.concat(parts, ignore_index=True),
        horizon=int(originals[0]['oracle_horizon']), as_of=as_of)


def run(*, output_dir, apply=False, engine=None, tranche_size=100, date_batch_size=20,
        start_date='2020-01-01', end_date='2026-09-30'):
    if isinstance(tranche_size, bool) or not isinstance(tranche_size, int) or tranche_size < 1:
        raise ValueError('Tranche invalide')
    if isinstance(date_batch_size, bool) or not isinstance(date_batch_size, int) or date_batch_size < 1:
        raise ValueError('Tranche de dates invalide')
    start, end = pd.Timestamp(start_date).date(), pd.Timestamp(end_date).date()
    as_of = datetime.now(ZoneInfo('Europe/Paris')).date()
    if start > end or end > as_of:
        raise ValueError('Fenêtre invalide ou future')
    if engine is None:
        from database.connection import get_sqlalchemy_engine
        engine = get_sqlalchemy_engine(db_name='alpha_trade')
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('Base US alpha_trade exigée')
        schema = conn.execute(text(f'SHOW CREATE TABLE {TABLE}')).fetchone()[1]
        existing = {c['name'] for c in inspect(conn).get_columns(TABLE)}
        if PEAK_FIELD not in existing:
            raise ValueError('Prix maximaux absents : migration/calcul 0102 requis')
        frame = pd.read_sql(text(f'SELECT * FROM {TABLE} WHERE trade_date BETWEEN :start AND :end '
                                f'ORDER BY {",".join(KEYS)}'), conn, params={'start':start,'end':end})
    backup = output/'study_before.parquet'
    frame.to_parquet(backup, index=False)
    save(output/'protocol.json', {'apply': apply, 'rows': len(frame), 'schema_before': schema,
        'start':str(start), 'end':str(end), 'as_of':str(as_of), 'date_batch_size':date_batch_size,
        'backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'updated_fields': UPDATED_FIELDS, 'preserves_original_selection': True,
        'return_basis': 'argmax_abs(100*(max_high/close_J-1),100*(min_low/close_J-1)); retain sign',
        'tie_breaker': 'UP_ON_EXACT_UNROUNDED_TIE',
        'rounding_mode': 'ROUND_HALF_UP', 'training': False, 'source_sql_writes': False})
    completed, examined, all_rows = 0, 0, []
    days = sorted({str(day)[:10] for day in frame.trade_date})
    save(output/'progress.json', {'status':'RUNNING', 'apply':apply, 'completed_rows':0,
        'examined_rows':0, 'total_rows':len(frame)})
    try:
        # Add only the new nullable field after backup; never stamp unrelated migrations.
        if apply and PEAK_PCT_FIELD not in existing:
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE alpha_trade.{TABLE} ADD COLUMN {PEAK_PCT_FIELD} JSON NULL '
                    "COMMENT 'Oracle score order: dominant signed high/low excursion J+1..J+H, integer pct; research only'"))
        statement = text(f'UPDATE alpha_trade.{TABLE} SET '
            + ','.join(f'{field}=:{field}' for field in UPDATED_FIELDS)
            + ' WHERE ' + ' AND '.join(f'{key}=:{key}' for key in KEYS)
            + ' AND SHA2(CAST(movement_quality AS CHAR),256)=:old_quality_hash'
            + f' AND SHA2(CAST({PEAK_FIELD} AS CHAR),256) <=> :old_price_hash'
            + f' AND CAST({PEAK_PCT_FIELD} AS CHAR) <=> :old_return_value'
            + ' AND status <=> :old_status AND quality_details <=> :old_quality_details')
        for offset in range(0, len(days), date_batch_size):
            tranche_days = days[offset:offset+date_batch_size]
            part = frame[frame.trade_date.astype(str).str[:10].isin(tranche_days)]
            records = []
            for _, group in part.groupby(['oracle_batch_id','oracle_horizon','universe_hash'], sort=False):
                originals = group.to_dict('records')
                maxima = _load_current_paths(engine, originals, as_of)
                for original in originals:
                    row = attach_peak_returns(dict(original), maxima=maxima.get(str(original['trade_date'])[:10], {}))
                    all_rows.append(row)
                    if (_json(row[PEAK_PCT_FIELD]) == _json(original.get(PEAK_PCT_FIELD))
                        and _json(row['movement_quality']) == _json(original['movement_quality'])
                        and row['status'] == original['status']
                        and _nullable(row['quality_details']) == _nullable(original['quality_details'])):
                        continue
                    parameters = {key: row[key] for key in KEYS+UPDATED_FIELDS}
                    parameters.update(old_quality_hash=_hash(original['movement_quality']),
                        old_price_hash=_hash(original[PEAK_FIELD]), old_return_value=_nullable(original.get(PEAK_PCT_FIELD)),
                        old_status=original['status'], old_quality_details=_nullable(original['quality_details']))
                    records.append(parameters)
            for position in range(0, len(records), tranche_size):
                tranche = records[position:position+tranche_size]
                if apply:
                    with engine.begin() as conn:
                        for row in tranche:
                            if conn.execute(statement, row).rowcount != 1:
                                raise RuntimeError(f'Ligne modifiée simultanément : {row["trade_date"]} ; arrêt sans écrasement')
                completed += len(tranche)
            examined += len(part)
            save(output/'progress.json', {'status': 'RUNNING', 'apply': apply,
                'completed_rows': completed, 'examined_rows':examined, 'total_rows': len(frame),
                'last_date':tranche_days[-1]})
        infos = [json.loads(row['movement_quality'])['lists'][PEAK_PCT_FIELD] for row in all_rows]
        report = {'status': 'COMPLETED', 'apply': apply, 'examined_rows': len(frame),
            'changed_rows': completed, 'unchanged_rows': len(frame)-completed,
            'nonnull_rows': sum(row[PEAK_PCT_FIELD] is not None for row in all_rows),
            'qualified_values': sum(info['known_count'] for info in infos),
            'list_statuses': dict(Counter(info['status'] for info in infos)),
            'missing_reasons': dict(Counter(reason for info in infos for reason in info['missing_reasons'].values()))}
        save(output/'report.json', report)
        save(output/'progress.json', report)
        return report
    except Exception as exc:
        save(output/'progress.json', {'status': 'FAILED', 'apply': apply,
            'completed_rows': completed, 'examined_rows':examined, 'total_rows': len(frame), 'error': str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--start-date', default='2020-01-01')
    parser.add_argument('--end-date', default='2026-09-30')
    parser.add_argument('--date-batch-size', type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(run(**vars(args)), allow_nan=False))


if __name__ == '__main__':
    main()
