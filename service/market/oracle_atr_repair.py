"""Bounded, backed-up repair of US Oracle labels and their ATR study.

No training, no invented prices, no replacement of a selected symbol by a winner.
Price rereads are archived evidence only: terminal gaps and identity changes need
separate qualification before writing market prices.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text

from modelFactory.oracle.build_labels import (
    build_labels, label_calendar, load_stored_membership, load_universe_from_bars,
)
from modelFactory.oracle.artifact_contract import resolve_oracle_artifact_horizon
from service.market.oracle_atr_study import MOVEMENT_FIELDS, run as study_run

LOG = logging.getLogger(__name__)


def save(path, payload):
    # Avoid partially read checkpoints and transient Windows reader/AV locks.
    descriptor, name = tempfile.mkstemp(prefix=f'.{path.stem}-', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(payload, indent=2, default=str, allow_nan=False))
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(12):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 11:
                    raise
                time.sleep(min(.05 * 2**attempt, .5))
    finally:
        temporary.unlink(missing_ok=True)


def calendar_changes(groups, calendar):
    """Never change availability alone when an existing exit used the wrong session."""
    updates, rebuild = [], []
    for row in groups.to_dict('records'):
        day = pd.Timestamp(row['prediction_date']).date()
        if day not in calendar:
            raise ValueError(f'Label sur une date hors séance NYSE : {day}')
        exit_day, available = calendar[day]
        if (pd.Timestamp(row['exit_min']).date() != exit_day
                or pd.Timestamp(row['exit_max']).date() != exit_day):
            rebuild.append(day.isoformat())
        elif (row['missing_available'] or pd.isna(row['available_min'])
              or pd.isna(row['available_max'])
              or pd.Timestamp(row['available_min']).date() != available
              or pd.Timestamp(row['available_max']).date() != available):
            updates.append({'day': day, 'available': available})
    return updates, rebuild


def rebuild_dates(wrong_exits, synthetic_days, invalid, *, include_invalid=False):
    """Return dates, never a reduced set of selected symbols."""
    days = set(wrong_exits) | {str(d)[:10] for d in synthetic_days}
    if include_invalid:
        days.update(pd.to_datetime(invalid.prediction_date).dt.strftime('%Y-%m-%d'))
    return sorted(days)


def fetch_price_evidence(symbol, start, end, *, session):
    """Use the same verified session for prices and adjustment evidence."""
    from service.eodhd.clientEodhd import fetch_eod, fetch_splits
    return {
        'bars': fetch_eod(symbol, start=start, end=end,
                          feature='oracle_atr_repair', session=session),
        'splits': fetch_splits(symbol, start=start,
                              feature='oracle_atr_repair', session=session),
    }


def coverage(engine, batch_id, horizon, start, end):
    fields = ','.join(f'SUM({name} IS NULL) AS {name}' for name in MOVEMENT_FIELDS)
    with engine.connect() as conn:
        return dict(conn.execute(text(f'SELECT COUNT(*) AS dates,{fields} '
            'FROM oracle_atr_market_regime_daily WHERE oracle_batch_id=:batch '
            'AND oracle_horizon=:h AND trade_date BETWEEN :start AND :end'),
            {'batch': batch_id, 'h': horizon, 'start': start, 'end': end}).mappings().one())


def qualify_static_extension(engine, batch_id, horizon, reference_day):
    """Reconstruct a static seed only if its original daily membership is reproduced.

    No today's universe or TOP20 is used. Dynamic universes need their own PIT
    membership contract and are deliberately not extended through this path.
    """
    profile_path = Path('artifacts/models') / batch_id / 'oracle/feature_profile.json'
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    if profile.get('oracle_universe_mode') != 'static_bars':
        return [], 'NOT_A_QUALIFIED_STATIC_BARS_CONTRACT'
    with engine.connect() as conn:
        seed = sorted(conn.execute(text('SELECT DISTINCT symbol FROM global_oracle_labels '
            'WHERE batch_id=:batch AND horizon=:h'), {'batch': batch_id, 'h': horizon}).scalars().all())
    old = load_stored_membership(engine, batch_id, horizon, reference_day, reference_day)
    reproduced = load_universe_from_bars(engine, seed, start_date=reference_day, end_date=reference_day)
    if not old or old != reproduced:
        return [], 'ORIGINAL_STATIC_MEMBERSHIP_NOT_REPRODUCED'
    return seed, 'STATIC_BARS_SEED_FROM_ORIGINAL_LABELS_REFERENCE_DAY_MATCHES'


def run(*, batch_id, horizon, start_date, end_date, symbol_source, output,
        apply=False, fetch_prices=False, rebuild_invalid_labels=False, engine=None):
    from database.connection import get_sqlalchemy_engine
    engine = engine or get_sqlalchemy_engine(db_name='alpha_trade')
    if resolve_oracle_artifact_horizon(batch_id) != horizon:
        raise ValueError('Horizon du correctif différent du contrat Oracle')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    file_log = logging.FileHandler(output / 'run.log', encoding='utf-8')
    file_log.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    LOG.addHandler(file_log)
    LOG.info('Audit start batch=%s horizon=%d apply=%s', batch_id, horizon, apply)
    params = {'batch': batch_id, 'h': horizon, 'start': start_date, 'end': end_date}
    predicate = 'batch_id=:batch AND horizon=:h AND prediction_date BETWEEN :start AND :end'
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('US repair requires alpha_trade')
        groups = pd.read_sql(text('SELECT prediction_date,COUNT(*) AS n,'
            'MIN(oracle_exit_date) exit_min,MAX(oracle_exit_date) exit_max,'
            'MIN(oracle_available_date) available_min,MAX(oracle_available_date) available_max,'
            'SUM(oracle_available_date IS NULL) missing_available '
            f'FROM global_oracle_labels FORCE INDEX (idx_gol_batch_date) '
            f'WHERE {predicate} GROUP BY prediction_date'), conn, params=params)
        invalid = pd.read_sql(text('SELECT prediction_date,symbol,oracle_exit_date,target_quality_reason '
            f'FROM global_oracle_labels FORCE INDEX (idx_gol_quality_batch) '
            f'WHERE {predicate} AND target_quality_valid=0'), conn, params=params)
        bounds = pd.read_sql(text('SELECT symbol,MIN(date) first_bar,MAX(date) last_bar '
            'FROM stock_bars_daily WHERE symbol IN (SELECT DISTINCT symbol FROM global_oracle_labels '
            f'WHERE {predicate} AND target_quality_valid=0) AND COALESCE(is_filled,0)=0 '
            'GROUP BY symbol'), conn, params=params)
        synthetic_days = set()
        for endpoint in ('prediction_date', 'oracle_exit_date'):
            # Separate exact-key joins: an OR join scans every historical bar of
            # every symbol for each label, making this bounded audit unbounded.
            synthetic_days.update(conn.execute(text('SELECT DISTINCT l.prediction_date '
                'FROM global_oracle_labels l FORCE INDEX (idx_gol_quality_batch) '
                'STRAIGHT_JOIN stock_bars_daily b '
                f'ON b.symbol=l.symbol AND b.date=l.{endpoint} '
                'WHERE l.batch_id=:batch AND l.horizon=:h AND l.prediction_date BETWEEN :start AND :end '
                'AND b.is_filled=1 AND l.target_quality_valid=1'), params).scalars().all())
        last_price_day = conn.execute(text('SELECT MAX(date) FROM stock_bars_daily '
                                          'WHERE COALESCE(is_filled,0)=0')).scalar()
    calendar = label_calendar(start_date, end_date, horizon)
    updates, wrong_exits = calendar_changes(groups, calendar)
    # Only re-rank when the target actually changes. Existing missing-price
    # exclusions remain exclusions; rereading a provider does not certify identity.
    # Prices may have been supplied since these labels were calculated. Rebuild
    # the whole original daily membership (not just the repaired symbols), so
    # deciles and all comparative selections stay on the same population.
    rebuild_days = rebuild_dates(wrong_exits, synthetic_days, invalid,
                                 include_invalid=rebuild_invalid_labels)
    before = coverage(engine, batch_id, horizon, start_date, end_date)
    missing = invalid.merge(bounds, on='symbol', how='left')
    missing['gap_kind'] = [
        'MISSING_OR_SUSPECT_PRICE' if r.target_quality_reason != 'missing_exit_bar'
        else ('INTERIOR_GAP' if pd.notna(r.last_bar) and pd.Timestamp(r.oracle_exit_date) <= pd.Timestamp(r.last_bar)
              else 'TERMINAL_GAP_NOT_A_ZERO_RETURN')
        for r in missing.itertuples()]
    missing.to_parquet(output / 'unqualified_prices.parquet', index=False)
    known_days = set(pd.to_datetime(groups.prediction_date).dt.date)
    today = datetime.now(ZoneInfo('Europe/Paris')).date()
    unlabeled_mature = [day.isoformat() for day, (_, available) in calendar.items()
                        if available <= today and day not in known_days]
    extend_days = [day for day in unlabeled_mature if last_price_day is not None
                   and calendar[pd.Timestamp(day).date()][0] <= last_price_day]
    seed, extension_reason = (qualify_static_extension(engine, batch_id, horizon,
        max(known_days).isoformat()) if extend_days and known_days else ([], 'NO_MATURE_PRICE_WINDOW'))
    save(output / 'static_extension_membership.json', {'symbols': seed, 'dates': extend_days,
        'qualification': extension_reason,
        'symbols_sha256': hashlib.sha256(','.join(seed).encode()).hexdigest()})
    plan = {'batch_id': batch_id, 'horizon': horizon, 'start': start_date, 'end': end_date,
            'availability_dates': len(updates), 'wrong_exit_dates': wrong_exits,
            'rebuild_dates': rebuild_days, 'before': before,
            'unqualified_price_rows': len(invalid), 'unqualified_symbols': int(invalid.symbol.nunique()),
            'mature_dates_without_original_membership': unlabeled_mature,
            'static_extension_dates': extend_days if seed else [],
            'static_extension_qualification': extension_reason,
            'price_policy': 'Archive provider evidence; do not invent delisting prices or overwrite suspect identities',
            'apply': apply, 'rebuild_invalid_labels': rebuild_invalid_labels}
    save(output / 'plan.json', plan)
    LOG.info('Repair plan: availability=%d, rebuild=%d, unqualified symbols=%d',
             len(updates), len(rebuild_days), invalid.symbol.nunique())

    if fetch_prices:
        from common.verified_http import verified_session
        # Keep TLS verification, including the Windows certificate store. A
        # plain requests session can fail behind the local TLS proxy and open
        # the provider circuit before any price evidence has been received.
        provider_session = verified_session()
        evidence = output / 'provider_evidence'
        evidence.mkdir()
        results = []
        for symbol, rows in missing.groupby('symbol', sort=True):
            LOG.info('Price evidence %s (%d/%d)', symbol, len(results)+1, invalid.symbol.nunique())
            first = pd.to_datetime(rows.prediction_date).min().date().isoformat()
            last = min(pd.to_datetime(rows.oracle_exit_date).max().date(), today).isoformat()
            result = {'symbol': symbol, 'start': first, 'end': last}
            try:
                evidence_payload = fetch_price_evidence(symbol, first, last, session=provider_session)
                bars = evidence_payload['bars']
                payload = json.dumps(evidence_payload, allow_nan=False).encode()
                digest = hashlib.sha256(payload).hexdigest()
                (evidence / f'{symbol.replace("/", "_")}-{digest}.json').write_bytes(payload)
                actual_dates = {str(row.get('date'))[:10] for row in bars}
                needed = {pd.Timestamp(d).date().isoformat() for d in rows.oracle_exit_date}
                result.update(received_bars=len(bars), exit_dates_received=sorted(actual_dates & needed),
                              exit_dates_missing=sorted(needed - actual_dates), sha256=digest,
                              status='EVIDENCE_ONLY_NOT_IDENTITY_CERTIFIED')
            except Exception as exc:
                # Provider exceptions can contain credential-bearing URLs.
                result.update(status='FETCH_FAILED', error_type=type(exc).__name__)
            results.append(result)
            save(output / 'price_evidence_progress.json', results)
        save(output / 'price_evidence_report.json', results)
        provider_session.close()

    if apply:
        # Back up every row on each affected date BEFORE its first SQL mutation.
        affected = sorted({str(row['day']) for row in updates} | set(rebuild_days))
        backup = output / 'labels_before'
        backup.mkdir()
        for day in affected:
            with engine.connect() as conn:
                old = pd.read_sql(text('SELECT * FROM global_oracle_labels '
                    'WHERE batch_id=:batch AND horizon=:h AND prediction_date=:day'),
                    conn, params={**params, 'day': day})
            old.to_parquet(backup / f'{day}.parquet', index=False)
        with engine.connect() as conn:
            old_study = pd.read_sql(text('SELECT * FROM oracle_atr_market_regime_daily '
                'WHERE oracle_batch_id=:batch AND oracle_horizon=:h AND trade_date BETWEEN :start AND :end'),
                conn, params=params)
        old_study.to_parquet(output / 'study_before.parquet', index=False)
        for row in updates:
            with engine.begin() as conn:
                conn.execute(text('UPDATE global_oracle_labels SET oracle_available_date=:available '
                    'WHERE batch_id=:batch AND horizon=:h AND prediction_date=:day'), {**params, **row})
        # Load the common matrix once. A date remains the minimum ranking unit;
        # only affected dates are rewritten, with all their original symbols.
        if rebuild_days:
            result = build_labels(batch_id, horizon=horizon,
                                  start_date=rebuild_days[0], end_date=rebuild_days[-1],
                                  prediction_dates=rebuild_days, engine=engine,
                                  universe_mode='stored_membership',
                                  progress_callback=lambda i,n,msg: LOG.info('Labels %d/%d %s', i,n,msg))
            if result['status'] != 'completed':
                raise RuntimeError(f'Labels non reconstruits: {result}')
            save(output / 'label_rebuild_report.json', result)
        if seed and extend_days:
            # Save an explicit absent-row snapshot; abort if a concurrent writer
            # has populated a date since the audit rather than overwrite it.
            for day in extend_days:
                if load_stored_membership(engine, batch_id, horizon, day, day):
                    raise RuntimeError(f'Concurrent label writer for {day}: stop and re-audit')
            result = build_labels(batch_id, horizon=horizon,
                start_date=extend_days[0], end_date=extend_days[-1], symbols=seed,
                engine=engine, universe_mode='static_bars',
                progress_callback=lambda i,n,msg: LOG.info('Extension %d/%d %s', i,n,msg))
            if result['status'] != 'completed':
                raise RuntimeError(f'Extension de labels non terminée : {result}')
            save(output / 'label_extension_report.json', result)
        # Do not repeatedly recalculate years whose sole issue is missing macro.
        # Refresh every missing movement list plus dates whose labels changed.
        incomplete = old_study[list(MOVEMENT_FIELDS)].isna().any(axis=1)
        study_days = sorted(set(pd.to_datetime(old_study.loc[incomplete, 'trade_date']).dt.strftime('%Y-%m-%d'))
                            | set(affected) | (set(extend_days) if seed else set()))
        LOG.info('Recomputing %d study dates in tranches of 20 sessions', len(study_days))
        study = study_run(batch_id=batch_id, symbol_source=symbol_source,
                          start_date=start_date, end_date=end_date, engine=engine,
                          date_batch_size=20, resume=False, trade_dates=study_days,
                          progress_callback=lambda i, n, msg: LOG.info('%d/%d %s', i, n, msg))
        study.pop('rows', None)
        plan['study'] = study
    plan['after'] = coverage(engine, batch_id, horizon, start_date, end_date)
    plan['status'] = 'COMPLETED_WITH_QUALIFICATION_RESERVES' if apply else 'AUDIT_ONLY'
    save(output / 'report.json', plan)
    LOG.info('Completed: before=%s after=%s', before, plan['after'])
    LOG.removeHandler(file_log)
    file_log.close()
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--horizon', type=int, default=20)
    parser.add_argument('--start-date', default='2020-01-01')
    parser.add_argument('--end-date', default='2026-09-30')
    parser.add_argument('--symbol-source', default='universe-file:univers_filtred_tradable.txt')
    parser.add_argument('--output', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--fetch-prices', action='store_true')
    parser.add_argument('--rebuild-invalid-labels', action='store_true',
                        help='Recalculer les dates incomplètes avec leurs membres originaux et les prix actuels')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    print(json.dumps(run(**vars(args)), default=str))


if __name__ == '__main__':
    main()
