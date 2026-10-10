"""Read-only, selection-preserving explanation of missing Oracle/ATR lists."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import text

from common.oracle_atr import load_oracle_atr_by_date
from common.universe_files import load_universe_file_symbols
from modelFactory.oracle.build_labels import label_calendar
from service.market.oracle_atr_repair import save
from service.market.oracle_atr_study import summarize_day, MOVEMENT_FIELDS


def explain_day(scores, atr, labels, *, as_of, available_date):
    """The required candidates are chosen before evaluating their outcomes."""
    summary = summarize_day(scores, atr, labels, None, as_of=as_of)
    finite_scores = scores[np.isfinite(pd.to_numeric(scores.proba_extreme, errors='coerce'))]
    score_map = dict(zip(finite_scores.symbol, finite_scores.proba_extreme))
    valid = (labels.target_quality_valid.eq(1)
             & np.isfinite(pd.to_numeric(labels.future_return, errors='coerce'))
             & labels.oracle_decile.between(1, 10)
             & pd.to_datetime(labels.oracle_available_date, errors='coerce').dt.normalize()
                 .le(pd.Timestamp(as_of)))
    known = set(labels.loc[valid, 'symbol'])
    n = summary['evaluated_count']
    oracle = sorted(score_map, key=lambda s: (-score_map[s], str(s)))[:n]
    valid_atr = {s: v for s, v in atr.items()
                 if s in score_map and v is not None and np.isfinite(v) and v > 0}
    atr_top = sorted(valid_atr, key=lambda s: (-valid_atr[s], str(s)))[:n]
    reasons = {}
    for row in labels.to_dict('records'):
        if row['symbol'] not in known:
            reason = row.get('target_quality_reason')
            reasons[row['symbol']] = str(reason) if pd.notna(reason) else 'UNAVAILABLE_OR_UNQUALIFIED_LABEL'
    if available_date > as_of:
        reason = 'H20_NOT_YET_AVAILABLE'
    elif not len(labels):
        reason = 'MATURE_LABELS_MISSING'
    else:
        reason = 'MISSING_OR_UNQUALIFIED_PRICES'
    missing = sorted(set(score_map) - known)
    return {
        'available_date': available_date.isoformat(), 'reason': reason,
        'evaluated_count': n, 'oracle_scored_count': len(score_map),
        'null_fields': [field for field in MOVEMENT_FIELDS if summary[field] is None],
        'real_benchmark_missing': [{'symbol': s, 'reason': reasons.get(s, reason)} for s in missing],
        'predicted_selection_missing': sorted(set(oracle) - known),
        'atr_selection_missing': sorted(set(atr_top) - known),
        'selection_policy': 'NO_REPLACEMENT_OF_UNKNOWN_CANDIDATES',
    }


def run(*, batch_id, start_date, end_date, symbol_source, output, horizon=20):
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    symbols = set(load_universe_file_symbols(symbol_source))
    params = {'batch': batch_id, 'start': start_date, 'end': end_date, 'h': horizon}
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('US audit requires alpha_trade')
        scores = pd.read_sql(text('SELECT prediction_date,symbol,proba_extreme '
            'FROM oracle_extreme_predictions WHERE batch_id=:batch '
            'AND prediction_date BETWEEN :start AND :end'), conn, params=params)
        labels = pd.read_sql(text('SELECT prediction_date,symbol,future_return,oracle_decile,'
            'target_quality_valid,target_quality_reason,oracle_available_date '
            'FROM global_oracle_labels FORCE INDEX(idx_gol_batch_date) WHERE batch_id=:batch '
            'AND horizon=:h AND prediction_date BETWEEN :start AND :end'), conn, params=params)
    scores = scores[scores.symbol.isin(symbols)].copy()
    labels = labels[labels.symbol.isin(symbols)].copy()
    for frame in (scores, labels):
        frame['prediction_date'] = pd.to_datetime(frame.prediction_date).dt.strftime('%Y-%m-%d')
    calendar = label_calendar(start_date, end_date, horizon)
    days = [d.isoformat() for d in calendar]
    atr = load_oracle_atr_by_date(engine, sorted(symbols), days)
    score_groups = dict(tuple(scores.groupby('prediction_date')))
    label_groups = dict(tuple(labels.groupby('prediction_date')))
    as_of = datetime.now(ZoneInfo('Europe/Paris')).date()
    rows = []
    for day, (exit_date, available) in calendar.items():
        iso = day.isoformat()
        row = explain_day(score_groups.get(iso, scores.iloc[:0]), atr.get(iso, {}),
            label_groups.get(iso, labels.iloc[:0]), as_of=as_of, available_date=available)
        row.update(trade_date=iso, exit_date=exit_date.isoformat())
        rows.append(row)
    save(output / 'dates.json', rows)
    missing_rows = [dict(trade_date=r['trade_date'], exit_date=r['exit_date'], **item)
                    for r in rows for item in r['real_benchmark_missing']]
    pd.DataFrame(missing_rows).to_csv(output / 'missing_prices.csv', index=False)
    report = {
        'batch_id': batch_id, 'horizon': horizon, 'evaluated_as_of': as_of,
        'start': start_date, 'end': end_date, 'dates': len(rows),
        'not_yet_available_dates': sum(r['reason'] == 'H20_NOT_YET_AVAILABLE' for r in rows),
        'null_dates': {field: sum(field in r['null_fields'] for r in rows) for field in MOVEMENT_FIELDS},
        'missing_symbols': sorted({r['symbol'] for r in missing_rows
                                  if r['reason'] != 'H20_NOT_YET_AVAILABLE'}),
        'status': 'READ_ONLY_DIAGNOSTIC',
    }
    save(output / 'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--start-date', required=True)
    parser.add_argument('--end-date', required=True)
    parser.add_argument('--symbol-source', default='universe-file:univers_filtred_tradable.txt')
    parser.add_argument('--horizon', default=20, type=int)
    parser.add_argument('--output', required=True)
    print(json.dumps(run(**vars(parser.parse_args())), default=str))


if __name__ == '__main__':
    main()
