"""Daily US Oracle/ATR amplitude study; writes only its own aggregate table."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from common.market_calendar import _get_nyse_calendar
from common.oracle_atr import load_oracle_atr_by_date, filter_oracle_atr_percentiles
from common.universe_files import load_universe_file_symbols
from modelFactory.oracle.artifact_contract import resolve_oracle_artifact_horizon

TABLE = 'oracle_atr_market_regime_daily'
CALCULATION_VERSION = 'oracle_atr_v5_partial_returns'
MOVEMENT_FIELDS = ('real_oracle_top_returns_pct', 'intersection_returns_pct',
                   'predicted_oracle_top_returns_pct', 'atr_top_returns_pct',
                   'predicted_oracle_score_order_returns_pct')
MACRO_FIELDS = ['vix', 'vix9d', 'ten_y', 'vxn', 'vix3m', 'move',
                'yield_10y_5d_pct', 'sentiment_score']


def resolve_returns_policy(value=None) -> str:
    if value is None:
        from common.config_loader import load_config
        value = (load_config().get('oracle_atr_study') or {}).get('missing_returns_policy', 'partial')
    if value not in {'strict', 'partial'}:
        raise ValueError('missing_returns_policy doit être strict ou partial')
    return value


def summarize_day(scores, atr, labels, macro, *, as_of: date,
                  missing_returns_policy='strict', expected_available_date=None) -> dict:
    """Labels retain their original batch-wide deciles; unknown != zero."""
    policy = resolve_returns_policy(missing_returns_policy)
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
    labels = labels.reset_index(drop=True).copy()
    labels['future_return'] = pd.to_numeric(labels.future_return, errors='coerce')
    available = pd.to_datetime(labels.oracle_available_date, errors='coerce')
    valid = (labels.target_quality_valid.eq(1) & np.isfinite(labels.future_return)
                 & labels.oracle_decile.between(1, 10)
                 # Keep pandas datetime types even for empty/all-NaT series.
                 # Availability is a calendar date, inclusive of the whole day.
                 & available.notna() & available.dt.normalize().le(pd.Timestamp(as_of)))
    immature = expected_available_date is not None and expected_available_date > as_of
    if immature:
        valid[:] = False
    chosen = labels[labels.symbol.isin(selected)]
    evaluable = valid.loc[chosen.index]
    n = int(evaluable.sum())
    d1 = int((evaluable & chosen.oracle_decile.eq(1)).sum())
    d10 = int((evaluable & chosen.oracle_decile.eq(10)).sum())
    issues = []
    if immature:
        issues.append('HORIZON_NOT_YET_AVAILABLE')
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
    movements = dict.fromkeys(MOVEMENT_FIELDS)
    returns = labels.loc[valid].set_index('symbol').future_return.to_dict()
    label_map = labels.set_index('symbol').to_dict('index')
    quality = {}

    def missing_reason(symbol):
        row = label_map.get(symbol)
        if immature:
            return 'NOT_YET_AVAILABLE'
        if row is None:
            return 'LABEL_MISSING'
        reason = row.get('target_quality_reason')
        if pd.notna(reason):
            return str(reason)
        availability_date = pd.to_datetime(row.get('oracle_available_date'), errors='coerce')
        if pd.notna(availability_date) and availability_date.date() > as_of:
            return 'NOT_YET_AVAILABLE'
        return 'LABEL_UNQUALIFIED'

    def serialize(field, symbols, *, keep_order=False, population=None, basis='INITIAL_SELECTION'):
        # Choose first, evaluate second. Partial mode never recruits a replacement.
        known = [s for s in symbols if s in returns]
        missing = [s for s in symbols if s not in returns]
        ordered = known if keep_order else sorted(known, key=lambda s: (-abs(returns[s]), str(s)))
        quality[field] = {
            'requested_count': len(symbols), 'known_count': len(known),
            'missing_count': len(missing),
            'coverage_pct': 100*len(known)/len(symbols) if symbols else None,
            'selection_symbols': symbols, 'value_symbols': ordered,
            'original_selection_positions': [symbols.index(s)+1 for s in ordered],
            'missing_symbols': missing,
            'missing_reasons': {s: missing_reason(s) for s in missing},
            'selection_basis': basis,
        }
        if population is not None:
            unknown_population = sorted(s for s in population if s not in returns)
            quality[field].update(
                reference_population_count=len(population),
                reference_known_count=len(population)-len(unknown_population),
                reference_coverage_pct=100*(len(population)-len(unknown_population))/len(population) if population else None,
                reference_missing_symbols=unknown_population,
                reference_missing_reasons={s: missing_reason(s) for s in unknown_population},
            )
        else:
            unknown_population = []
        complete = not missing and not unknown_population and bool(symbols)
        quality[field]['status'] = ('COMPLETE' if complete else 'PARTIAL' if known else 'UNAVAILABLE')
        if not known or (policy == 'strict' and (missing or unknown_population)):
            return None
        values = [int((Decimal(str(returns[s]))*100).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP)) for s in ordered]
        return json.dumps(values, allow_nan=False)

    if n:
        # Existing intersection was already partial; expose its full initial scope.
        movements['intersection_returns_pct'] = serialize('intersection_returns_pct', sorted(selected))
        if policy == 'strict':
            # Preserve the legacy intersection's known-only serialization.
            known_intersection = sorted(selected & set(returns), key=lambda s: (-abs(returns[s]), str(s)))
            movements['intersection_returns_pct'] = json.dumps([int((Decimal(str(returns[s]))*100).quantize(
                Decimal('1'), rounding=ROUND_HALF_UP)) for s in known_intersection])
        score_map = dict(zip(scores.loc[finite, 'symbol'], score_values[finite]))
        oracle_top = sorted(score_map, key=lambda s: (-score_map[s], str(s)))[:n]
        movements['predicted_oracle_score_order_returns_pct'] = serialize(
            'predicted_oracle_score_order_returns_pct', oracle_top, keep_order=True)
        atr_top = sorted(valid_atr, key=lambda s: (-valid_atr[s], str(s)))[:n]
        for field, population, issue in (
            ('predicted_oracle_top_returns_pct', oracle_top, 'INCOMPLETE_PREDICTED_TOP_RETURNS'),
            ('atr_top_returns_pct', atr_top, 'INCOMPLETE_ATR_TOP_RETURNS'),
        ):
            movements[field] = serialize(field, population)
            if quality[field]['status'] != 'COMPLETE':
                issues.append(issue)
        # With incomplete coverage this is explicitly a benchmark among known
        # titles, NOT the true full-universe future TOP20.
        amplitudes = pd.Series({s: abs(returns[s]) for s in ranks if s in returns}, dtype=float)
        real_pool = amplitudes[amplitudes.rank(pct=True) >= .8].index.tolist()
        real_top = sorted(real_pool, key=lambda s: (-abs(returns[s]), str(s)))[:n]
        movements['real_oracle_top_returns_pct'] = serialize('real_oracle_top_returns_pct',
            real_top, population=list(ranks), basis='REALIZED_TOP20_AMONG_EVALUABLE_SYMBOLS')
        if len(real_top) < n:
            info = quality['real_oracle_top_returns_pct']
            info.update(requested_count=n, selection_shortfall_count=n-len(real_top),
                        coverage_pct=100*len(real_top)/n,
                        status='PARTIAL' if real_top else 'UNAVAILABLE')
            if policy == 'strict':
                movements['real_oracle_top_returns_pct'] = None
        if quality['real_oracle_top_returns_pct']['status'] != 'COMPLETE':
            issues.append('INCOMPLETE_REAL_TOP_RETURNS')
    else:
        # Never turn an immature/empty date into an apparently successful [] list.
        for field in MOVEMENT_FIELDS:
            serialize(field, sorted(selected) if field == 'intersection_returns_pct' else [],
                      population=list(ranks) if field == 'real_oracle_top_returns_pct' else None)
    quality_payload = {'policy': policy,
                       'expected_available_date': str(expected_available_date) if expected_available_date else None,
                       'target_evaluated_count': n, 'lists': quality}
    result = {'regime_mode': macro.get('mode') if macro is not None else None,
              **movements,
              'missing_returns_policy': policy,
              'movement_quality': json.dumps(quality_payload, allow_nan=False),
              **{k: macro.get(k) if macro is not None else None for k in MACRO_FIELDS},
              'oracle_scored_count': len(ranks), 'oracle_top20_count': before,
              'atr_valid_count': diag['atr_valid'], 'atr_missing_count': diag['atr_missing'],
              'intersection_count': len(selected), 'evaluated_count': n,
              'unknown_count': len(selected)-n, 'd1_count': d1, 'd10_count': d10,
              'd1_pct': 100*d1/n if n else None, 'd10_pct': 100*d10/n if n else None,
              'd10_d1_ratio': d10/d1 if n and d1 else None,
              'd1_d10_total_pct': 100*(d1+d10)/n if n else None,
              'evaluation_coverage_pct': 100*n/len(selected) if selected else None,
              'status': ('COMPLETE' if not issues else 'PARTIAL' if policy == 'partial' and n else 'INCOMPLETE'),
              'quality_details': ','.join(issues) or None}
    return {k: None if pd.isna(v) else v for k, v in result.items()}


def run(*, batch_id: str, symbol_source: str, start_date: str, end_date: str,
        artifacts_dir='artifacts/models', engine=None, progress_callback=None,
        date_batch_size: int = 20, resume: bool = True,
        trade_dates: list[str] | None = None, missing_returns_policy=None) -> dict:
    policy = resolve_returns_policy(missing_returns_policy)
    version = CALCULATION_VERSION if policy == 'partial' else 'oracle_atr_v5_strict_returns'
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
        conn.execute(text(f'SELECT trade_date,{",".join(MOVEMENT_FIELDS)},movement_quality,missing_returns_policy FROM {TABLE} LIMIT 0'))
        completed = set()
        if resume:
            completed = {str(d)[:10] for d in conn.execute(text(
                f'SELECT trade_date FROM {TABLE} WHERE universe_hash=:hash AND oracle_batch_id=:batch '
                "AND oracle_horizon=:horizon AND status='COMPLETE' AND calculation_version=:version "
                'AND trade_date BETWEEN :start AND :end'),
                {'hash': universe_hash, 'batch': batch_id, 'horizon': horizon, 'start': start, 'end': end,
                 'version': version}).scalars().all()}
    calendar = _get_nyse_calendar()
    if calendar is None:
        raise RuntimeError('Calendrier NYSE fiable indisponible : aucun fallback lundi-vendredi pour cette étude')
    all_days = [d.date().isoformat() for d in calendar.schedule(start_date=start, end_date=end).index]
    if trade_dates is not None:
        requested = {date.fromisoformat(d).isoformat() for d in trade_dates}
        if requested.difference(all_days):
            raise ValueError('trade_dates contient une date hors fenêtre ou hors séance NYSE')
        all_days = [d for d in all_days if d in requested]
    days = [d for d in all_days if d not in completed]
    skipped = len(all_days)-len(days)
    records = []
    if progress_callback:
        progress_callback(skipped, len(all_days), f'Reprise : {skipped} séances complètes déjà enregistrées')
    for offset in range(0, len(days), date_batch_size):
        tranche = days[offset:offset+date_batch_size]
        if progress_callback:
            progress_callback(skipped+offset, len(all_days), f'Calcul tranche {tranche[0]} → {tranche[-1]}…')
        batch_records = _calculate_tranche(engine, symbols, tranche, batch_id, horizon, as_of, policy)
        for row in batch_records:
            row.update(universe_source=symbol_source, universe_hash=universe_hash,
                       oracle_batch_id=batch_id, oracle_horizon=horizon, universe_count=len(symbols),
                       evaluated_as_of=as_of, calculation_version=version)
        _persist_tranche(engine, batch_records)
        records.extend(batch_records)
        if progress_callback:
            progress_callback(skipped+len(records), len(all_days),
                              f'Tranche persistée jusqu’au {tranche[-1]} : {len(records)} séances enregistrées')
    return {'persisted_rows': len(records), 'skipped_rows': skipped,
            'complete_rows': sum(r['status']=='COMPLETE' for r in records),
            'partial_rows': sum(r['status']=='PARTIAL' for r in records),
            'incomplete_rows': sum(r['status']=='INCOMPLETE' for r in records),
            'missing_returns_policy': policy, 'horizon': horizon,
            'universe_hash': universe_hash, 'rows': records}


def _calculate_tranche(engine, symbols, days, batch_id, horizon, as_of, policy='strict'):
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
                'target_quality_valid,target_quality_reason,oracle_available_date FROM global_oracle_labels WHERE batch_id=:batch '
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
    from modelFactory.oracle.build_labels import label_calendar
    availability = label_calendar(start, end, horizon)
    for day in days:
        row = summarize_day(score_groups.get(day, scores.iloc[:0]), atr_map.get(day, {}),
            label_groups.get(day, labels.iloc[:0]), macro_groups.get(day), as_of=as_of,
            missing_returns_policy=policy, expected_available_date=availability[date.fromisoformat(day)][1])
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
    parser.add_argument('--missing-returns-policy', choices=['strict', 'partial'], default=None,
                        help='Politique des listes ; défaut config.yaml, sinon partial')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    summary = run(**vars(args), progress_callback=lambda i,n,message: logging.info('%d/%d %s', i,n,message))
    summary.pop('rows')
    print(json.dumps(summary, default=str))


if __name__ == '__main__':
    main()
