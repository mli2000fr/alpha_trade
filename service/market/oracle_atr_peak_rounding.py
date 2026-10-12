"""Round existing study peak-price JSON lists, preserving full-precision metadata.

No price/label/selection recalculation. Backup before writing, scoped US table,
small transactions and optimistic checks against concurrent study updates.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from service.market.oracle_atr_peak_backfill import KEYS
from service.market.oracle_atr_repair import save
from service.market.oracle_atr_study import PEAK_FIELD, TABLE


def round_record(row):
    row = dict(row)
    values = json.loads(row[PEAK_FIELD])
    metadata = json.loads(row['movement_quality'])
    info = metadata['lists'][PEAK_FIELD]
    symbols = info['value_symbols']
    if len(values) != len(symbols) or info.get('unit') != 'USD_SIGNAL_DAY_PRICE_SCALE':
        raise ValueError('Liste de prix incohérente : formatage annulé')
    rounded = []
    for symbol in symbols:
        details = info.get('value_details', {}).get(symbol, {})
        if 'max_price' not in details:
            raise ValueError(f'Prix précis absent des métadonnées : {symbol}')
        value = details['max_price']
        if isinstance(value, bool) or not np.isfinite(float(value)) or float(value) <= 0:
            raise ValueError(f'Prix maximal non qualifié : {symbol}')
        rounded.append(int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)))
    info.update(rounding_decimals=0, rounding_mode='ROUND_HALF_UP',
                unrounded_value_location='value_details.<symbol>.max_price')
    row[PEAK_FIELD] = json.dumps(rounded, allow_nan=False)
    row['movement_quality'] = json.dumps(metadata, allow_nan=False)
    return row


def run(*, output_dir, apply=False, engine=None, tranche_size=100):
    if tranche_size < 1:
        raise ValueError('Tranche invalide')
    if engine is None:
        from database.connection import get_sqlalchemy_engine
        engine = get_sqlalchemy_engine(db_name='alpha_trade')
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('Base US alpha_trade exigée')
        frame = pd.read_sql(text(f'SELECT {",".join(KEYS)},{PEAK_FIELD},movement_quality FROM {TABLE} '
                                 f'WHERE {PEAK_FIELD} IS NOT NULL ORDER BY {",".join(KEYS)}'), conn)
    backup = output / 'before.parquet'
    frame.to_parquet(backup, index=False)
    save(output / 'protocol.json', {'apply': apply, 'fields': [PEAK_FIELD, 'movement_quality'],
        'backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(), 'rows': len(frame),
        'rounding_mode': 'ROUND_HALF_UP', 'unit_unchanged': 'USD_SIGNAL_DAY_PRICE_SCALE',
        'full_precision_details_preserved': True})
    records = []
    for original in frame.to_dict('records'):
        row = round_record(original)
        if (json.loads(row[PEAK_FIELD]) == json.loads(original[PEAK_FIELD])
            and json.loads(row['movement_quality']) == json.loads(original['movement_quality'])):
            continue
        row['old_value_hash'] = hashlib.sha256(original[PEAK_FIELD].encode()).hexdigest()
        row['old_quality_hash'] = hashlib.sha256(original['movement_quality'].encode()).hexdigest()
        records.append(row)
    statement = text(f'UPDATE {TABLE} SET {PEAK_FIELD}=:{PEAK_FIELD},movement_quality=:movement_quality '
        'WHERE ' + ' AND '.join(f'{key}=:{key}' for key in KEYS)
        + f' AND SHA2(CAST({PEAK_FIELD} AS CHAR),256)=:old_value_hash '
        + 'AND SHA2(CAST(movement_quality AS CHAR),256)=:old_quality_hash')
    completed = 0
    try:
        for offset in range(0, len(records), tranche_size):
            tranche = records[offset:offset + tranche_size]
            if apply:
                with engine.begin() as conn:
                    for row in tranche:
                        changed = conn.execute(statement, row).rowcount
                        if changed != 1:
                            raise RuntimeError(f'Ligne modifiée simultanément : {row["trade_date"]} ; arrêt sans écrasement')
            completed += len(tranche)
            save(output / 'progress.json', {'status': 'RUNNING', 'completed': completed, 'total': len(records)})
        report = {'status': 'COMPLETED', 'apply': apply, 'examined_rows': len(frame),
                  'changed_rows': completed, 'unchanged_rows': len(frame) - len(records)}
        save(output / 'report.json', report)
        save(output / 'progress.json', report)
        return report
    except Exception as exc:
        save(output / 'progress.json', {'status': 'FAILED', 'completed': completed,
                                       'total': len(records), 'error': str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(**vars(args)), allow_nan=False))


if __name__ == '__main__':
    main()
