"""Daily US Oracle/ATR amplitude study; writes only its own aggregate table."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from common.market_calendar import _get_nyse_calendar
from common.oracle_atr import load_oracle_atr_by_date, filter_oracle_atr_percentiles
from common.universe_files import load_universe_file_symbols
from modelFactory.oracle.artifact_contract import resolve_oracle_artifact_horizon

TABLE = 'oracle_atr_market_regime_daily'
MACRO_FIELDS = ['vix', 'vix9d', 'ten_y', 'vxn', 'vix3m', 'move',
                'yield_10y_5d_pct', 'sentiment_score']


def summarize_day(scores, atr, labels, macro, *, as_of: date) -> dict:
    """Labels retain their original batch-wide deciles; unknown != zero."""
    if scores.symbol.duplicated().any() or labels.symbol.duplicated().any():
        raise ValueError('Doublons symbole dans les scores ou labels du jour')
    score_values = pd.to_numeric(scores.proba_extreme, errors='coerce')
    finite = np.isfinite(score_values)
    ranks = pd.Series(score_values[finite].to_numpy(), index=scores.loc[finite, 'symbol']).rank(pct=True).to_dict()
    before = sum(p >= .8 for p in ranks.values())
    valid_atr = {s: v for s, v in atr.items() if s in ranks and v is not None and np.isfinite(v) and v > 0}
    if ranks and valid_atr:
        kept, diag = filter_oracle_atr_percentiles(ranks, valid_atr)
        selected = set(kept)
    else:
        selected = set()
        diag = {'atr_valid': 0, 'atr_missing': len(ranks)}
    chosen = labels[labels.symbol.isin(selected)].copy()
    available = pd.to_datetime(chosen.oracle_available_date, errors='coerce')
    evaluable = (chosen.target_quality_valid.eq(1) & chosen.future_return.notna()
                 & chosen.oracle_decile.between(1, 10)
                 & available.notna() & available.dt.date.le(as_of))
    n = int(evaluable.sum())
    d1 = int((evaluable & chosen.oracle_decile.eq(1)).sum())
    d10 = int((evaluable & chosen.oracle_decile.eq(10)).sum())
    issues = []
    if macro is None or pd.isna(macro.get('mode')):
        issues.append('MISSING_REGIME')
    if macro is None or any(pd.isna(macro.get(k)) for k in MACRO_FIELDS):
        issues.append('MISSING_MACRO')
    if not ranks:
        issues.append('MISSING_ORACLE')
    elif diag['atr_missing']:
        issues.append('MISSING_ATR')
    if not selected:
        issues.append('EMPTY_INTERSECTION')
    elif n < len(selected):
        issues.append('INCOMPLETE_LABELS')
    result = {'regime_mode': macro.get('mode') if macro is not None else None,
              **{k: macro.get(k) if macro is not None else None for k in MACRO_FIELDS},
              'oracle_scored_count': len(ranks), 'oracle_top20_count': before,
              'atr_valid_count': diag['atr_valid'], 'atr_missing_count': diag['atr_missing'],
              'intersection_count': len(selected), 'evaluated_count': n,
              'unknown_count': len(selected)-n, 'd1_count': d1, 'd10_count': d10,
              'd1_pct': 100*d1/n if n else None, 'd10_pct': 100*d10/n if n else None,
              'd10_d1_ratio': d10/d1 if n and d1 else None,
              'd1_d10_total_pct': 100*(d1+d10)/n if n else None,
              'evaluation_coverage_pct': 100*n/len(selected) if selected else None,
              'status': 'COMPLETE' if not issues else 'INCOMPLETE',
              'quality_details': ','.join(issues) or None}
    return {k: None if pd.isna(v) else v for k, v in result.items()}


def run(*, batch_id: str, symbol_source: str, start_date: str, end_date: str,
        artifacts_dir='artifacts/models', engine=None, progress_callback=None,
        date_batch_size: int = 20, resume: bool = True) -> dict:
    if not isinstance(date_batch_size, int) or isinstance(date_batch_size, bool) or date_batch_size < 1:
        raise ValueError('date_batch_size doit être un entier strictement positif')
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if end < start:
        raise ValueError('La fin doit être postérieure ou égale au début')
    horizon = resolve_oracle_artifact_horizon(batch_id, artifacts_dir)
    if horizon is None:
        raise ValueError('Horizon Oracle absent : choisir un batch Oracle avec artefact identifiable')
    symbols = sorted(set(load_universe_file_symbols(symbol_source)))
    if not symbols:
        raise ValueError('Univers vide')
    universe_hash = hashlib.sha256(','.join(symbols).encode()).hexdigest()
    as_of = datetime.now(ZoneInfo('Europe/Paris')).date()
    if end > as_of:
        raise ValueError('Une étude ne peut pas demander des dates futures')
    if engine is None:
        from database.connection import get_sqlalchemy_engine
        engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('Cette étude US exige la base alpha_trade')
        # Check migration before doing costly price reads.
        conn.execute(text(f'SELECT trade_date FROM {TABLE} LIMIT 0'))
        completed = set()
        if resume:
            completed = {str(d)[:10] for d in conn.execute(text(
                f'SELECT trade_date FROM {TABLE} WHERE universe_hash=:hash AND oracle_batch_id=:batch '
                "AND oracle_horizon=:horizon AND status='COMPLETE' AND calculation_version='oracle_atr_v1' "
                'AND trade_date BETWEEN :start AND :end'),
                {'hash': universe_hash, 'batch': batch_id, 'horizon': horizon, 'start': start, 'end': end}).scalars().all()}
    calendar = _get_nyse_calendar()
    if calendar is None:
        raise RuntimeError('Calendrier NYSE fiable indisponible : aucun fallback lundi-vendredi pour cette étude')
    all_days = [d.date().isoformat() for d in calendar.schedule(start_date=start, end_date=end).index]
    days = [d for d in all_days if d not in completed]
    skipped = len(all_days)-len(days)
    records = []
    if progress_callback:
        progress_callback(skipped, len(all_days), f'Reprise : {skipped} séances complètes déjà enregistrées')
    for offset in range(0, len(days), date_batch_size):
        tranche = days[offset:offset+date_batch_size]
        if progress_callback:
            progress_callback(skipped+offset, len(all_days), f'Calcul tranche {tranche[0]} → {tranche[-1]}…')
        batch_records = _calculate_tranche(engine, symbols, tranche, batch_id, horizon, as_of)
        for row in batch_records:
            row.update(universe_source=symbol_source, universe_hash=universe_hash,
                       oracle_batch_id=batch_id, oracle_horizon=horizon, universe_count=len(symbols),
                       evaluated_as_of=as_of, calculation_version='oracle_atr_v1')
        _persist_tranche(engine, batch_records)
        records.extend(batch_records)
        if progress_callback:
            progress_callback(skipped+len(records), len(all_days),
                              f'Tranche persistée jusqu’au {tranche[-1]} : {len(records)} séances enregistrées')
    return {'persisted_rows': len(records), 'skipped_rows': skipped,
            'complete_rows': sum(r['status']=='COMPLETE' for r in records),
            'incomplete_rows': sum(r['status']!='COMPLETE' for r in records), 'horizon': horizon,
            'universe_hash': universe_hash, 'rows': records}


def _calculate_tranche(engine, symbols, days, batch_id, horizon, as_of):
    start, end = days[0], days[-1]
    with engine.connect() as conn:
        macro = pd.read_sql(text('SELECT * FROM stock_macro_indicators_daily WHERE trade_date BETWEEN :start AND :end'),
                            conn, params={'start': start, 'end': end})
        score_parts, label_parts = [], []
        for offset in range(0, len(symbols), 150):
            params = {'start': start, 'end': end, 'batch': batch_id,
                      'horizon': horizon, 'symbols': symbols[offset:offset+150]}
            score_parts.append(pd.read_sql(text('SELECT prediction_date,symbol,proba_extreme FROM oracle_extreme_predictions '
                'WHERE batch_id=:batch AND prediction_date BETWEEN :start AND :end AND symbol IN :symbols')
                .bindparams(bindparam('symbols', expanding=True)), conn, params=params))
            label_parts.append(pd.read_sql(text('SELECT prediction_date,symbol,future_return,oracle_decile,'
                'target_quality_valid,oracle_available_date FROM global_oracle_labels WHERE batch_id=:batch '
                'AND horizon=:horizon AND prediction_date BETWEEN :start AND :end AND symbol IN :symbols')
                .bindparams(bindparam('symbols', expanding=True)), conn, params=params))
    scores, labels = pd.concat(score_parts), pd.concat(label_parts)
    for frame, column in [(scores, 'prediction_date'), (labels, 'prediction_date'), (macro, 'trade_date')]:
        frame[column] = pd.to_datetime(frame[column]).dt.strftime('%Y-%m-%d')
    if macro.trade_date.duplicated().any():
        raise ValueError('Doublons macro par date')
    atr_map = load_oracle_atr_by_date(engine, symbols, days)
    score_groups = {d: g for d, g in scores.groupby('prediction_date')}
    label_groups = {d: g for d, g in labels.groupby('prediction_date')}
    macro_groups = {row['trade_date']: row for row in macro.to_dict('records')}
    records = []
    for day in days:
        row = summarize_day(score_groups.get(day, scores.iloc[:0]), atr_map.get(day, {}),
            label_groups.get(day, labels.iloc[:0]), macro_groups.get(day), as_of=as_of)
        row.update(trade_date=day)
        records.append(row)
    return records


def _persist_tranche(engine, records):
    if records:
        columns = list(records[0])
        keys = {'trade_date', 'universe_hash', 'oracle_batch_id', 'oracle_horizon'}
        sql = text(f'INSERT INTO {TABLE} ({",".join(columns)}) VALUES ({",".join(":"+k for k in columns)}) '
                   'ON DUPLICATE KEY UPDATE '+','.join(f'{k}=VALUES({k})' for k in columns if k not in keys))
        with engine.begin() as conn:
            conn.execute(sql, records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--symbol-source', required=True)
    parser.add_argument('--start-date', default='2020-01-01')
    parser.add_argument('--end-date', default='2026-09-30')
    parser.add_argument('--artifacts-dir', default='artifacts/models')
    parser.add_argument('--date-batch-size', type=int, default=20, help='Séances par transaction (défaut 20)')
    parser.add_argument('--no-resume', dest='resume', action='store_false', help='Recalculer aussi les séances complètes')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    summary = run(**vars(args), progress_callback=lambda i,n,message: logging.info('%d/%d %s', i,n,message))
    summary.pop('rows')
    print(json.dumps(summary, default=str))


if __name__ == '__main__':
    main()
