"""Frozen H20 >=50% capture audit. SELECT only, no fitting or trading changes."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, event, text

from common.oracle_atr import atr20_percent_panel
from common.universe_files import load_universe_file_symbols
from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.artifact_contract import resolve_oracle_artifact_horizon

LOGGER = logging.getLogger(__name__)
POLICIES = ('ALL', 'ORACLE_TOP20', 'ATR_TOP20', 'INTERSECTION',
            'ORACLE_TOP10', 'ORACLE_TOP20_COUNT', 'ORACLE_TOP50',
            'ATR_TOP10', 'ATR_TOP20_COUNT', 'ATR_TOP50',
            'INTERSECTION_ORACLE_TOP10', 'INTERSECTION_ORACLE_TOP20',
            'INTERSECTION_ORACLE_TOP50')


def forbid_writes(conn, cursor, statement, parameters, context, executemany):
    if statement.lstrip().split()[0].upper() not in {'SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN'}:
        raise RuntimeError('Read-only audit rejected SQL')


def freeze_selection(scores, atr):
    """All masks are fixed without looking at future labels or price quality."""
    if scores.duplicated(['date', 'symbol']).any() or atr.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate score/ATR keys')
    data = scores.copy()
    data['proba_extreme'] = pd.to_numeric(data.proba_extreme, errors='coerce')
    data = data[np.isfinite(data.proba_extreme)].merge(atr, on=['date', 'symbol'], how='left', validate='one_to_one')
    data = data.sort_values(['date', 'symbol']).reset_index(drop=True)
    data['atr20_pct'] = pd.to_numeric(data.atr20_pct, errors='coerce')
    data.loc[~np.isfinite(data.atr20_pct) | data.atr20_pct.le(0), 'atr20_pct'] = np.nan
    data['oracle_percentile'] = data.groupby('date').proba_extreme.rank(pct=True)
    data['atr_percentile'] = data.groupby('date').atr20_pct.rank(pct=True)
    data['ALL'] = True
    data['ORACLE_TOP20'] = data.oracle_percentile.ge(.8)
    data['ATR_TOP20'] = data.atr_percentile.ge(.8)
    data['INTERSECTION'] = data.ORACLE_TOP20 & data.ATR_TOP20
    oracle_rank = data.groupby('date').proba_extreme.rank(ascending=False, method='first')
    atr_rank = data.groupby('date').atr20_pct.rank(ascending=False, method='first')
    intersection_rank = data.proba_extreme.where(data.INTERSECTION).groupby(data.date).rank(ascending=False, method='first')
    for k in (10, 20, 50):
        data[f'ORACLE_TOP{k}' if k != 20 else 'ORACLE_TOP20_COUNT'] = oracle_rank.le(k)
        data[f'ATR_TOP{k}' if k != 20 else 'ATR_TOP20_COUNT'] = atr_rank.le(k)
        data[f'INTERSECTION_ORACLE_TOP{k}'] = intersection_rank.le(k)
    return data


def qualify_endpoints(labels, bars):
    """Local price checks, not independent proof or a trading eligibility certificate."""
    data = labels.copy()
    for col in ('future_return', 'future_return_raw'):
        data[col] = pd.to_numeric(data[col], errors='coerce')
    prices = bars[['date', 'symbol', 'close', 'adj_close', 'volume', 'is_filled', 'instrument_id']].copy()
    for prefix, key in (('entry', 'date'), ('exit', 'oracle_exit_date')):
        renamed = prices.rename(columns={c: f'{prefix}_{c}' for c in prices if c not in ('date', 'symbol')})
        renamed = renamed.rename(columns={'date': key})
        data = data.merge(renamed, on=[key, 'symbol'], how='left', validate='many_to_one')
    for col in [c for c in data if c.startswith(('entry_', 'exit_')) and c not in ('entry_is_filled', 'exit_is_filled')]:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    data['recomputed_return'] = data.exit_adj_close / data.entry_adj_close - 1
    data['raw_endpoint_return'] = data.exit_close / data.entry_close - 1
    data['endpoint_mismatch'] = (data.recomputed_return - data.future_return).abs().gt(1e-6)
    data['missing_adjusted_endpoint'] = (~np.isfinite(data.recomputed_return)
        | data.entry_adj_close.le(0) | data.exit_adj_close.le(0))
    data['filled_endpoint'] = data.entry_is_filled.fillna(True).astype(bool) | data.exit_is_filled.fillna(True).astype(bool)
    data['zero_endpoint_volume'] = data.entry_volume.fillna(0).le(0) | data.exit_volume.fillna(0).le(0)
    data['identity_change'] = (data.entry_instrument_id.notna() & data.exit_instrument_id.notna()
                              & data.entry_instrument_id.ne(data.exit_instrument_id))
    data['impossible_long_return'] = data.future_return.le(-1)
    data['adjustment_effect_gt5pp'] = (data.raw_endpoint_return - data.recomputed_return).abs().gt(.05)
    guards = ['endpoint_mismatch', 'missing_adjusted_endpoint', 'filled_endpoint',
              'zero_endpoint_volume', 'identity_change', 'impossible_long_return']
    data['local_endpoint_ok'] = ~data[guards].any(axis=1)
    # A correct adjusted split may legitimately change the raw/adjusted return.
    # This flag is informational, never a reason to silently delete the target.
    return data


def metrics(frame, *, as_of):
    valid = (frame.target_quality_valid.eq(1) & np.isfinite(frame.future_return)
             & pd.to_datetime(frame.oracle_available_date).le(pd.Timestamp(as_of)))
    rows = []
    for scope, qualified in [('LABEL_VALID', valid), ('LOCAL_ENDPOINT_OK', valid & frame.local_endpoint_ok.fillna(False))]:
        for threshold in (.5, 1.):
            for side in ('ABS', 'UP', 'DOWN'):
                target = (frame.future_return.abs().ge(threshold) if side == 'ABS' else
                          frame.future_return.ge(threshold) if side == 'UP' else frame.future_return.le(-threshold))
                base_events = int((qualified & target).sum())
                base_valid = int(qualified.sum())
                base_precision = base_events/base_valid if base_valid else None
                for policy in POLICIES:
                    selection = frame[policy]
                    known = selection & qualified
                    found = known & target
                    n = int(known.sum())
                    hits = int(found.sum())
                    selected = int(selection.sum())
                    precision = hits/n if n else None
                    rows.append(dict(scope=scope, threshold_pct=int(threshold*100), side=side,
                        policy=policy, selected=selected, evaluated=n, unknown=selected-n,
                        target_hits=hits, reference_targets=base_events,
                        precision_pct=100*precision if precision is not None else None,
                        capture_pct=100*hits/base_events if base_events else None,
                        lift_vs_all=precision/base_precision if precision is not None and base_precision else None,
                        days=int(frame.loc[known, 'date'].nunique()),
                        days_with_hit=int(frame.loc[found, 'date'].nunique())))
    return rows


def cluster_events(tails):
    """Descriptive same-symbol/sign nonoverlapping H20 windows; no independence claim."""
    data = tails.sort_values(['symbol', 'date']).copy()
    rows = []
    for (symbol, side), group in data.groupby(['symbol', 'side']):
        end = None
        current = None
        for row in group.to_dict('records'):
            if end is None or row['date'] > end:
                current = dict(symbol=symbol, side=side, start=row['date'], end=row['oracle_exit_date'],
                               windows=0, max_abs_return_pct=0.,
                               **{p: False for p in POLICIES})
                rows.append(current)
                end = row['oracle_exit_date']
            current['windows'] += 1
            current['max_abs_return_pct'] = max(current['max_abs_return_pct'], abs(row['future_return'])*100)
            for policy in POLICIES:
                current[policy] = bool(current[policy] or row[policy])
    return rows


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding='utf-8')


def run(*, batch_id, symbol_source, start_date, end_date, output, artifacts_dir='artifacts/models'):
    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    as_of = datetime.now(ZoneInfo('Europe/Paris')).date()
    if end < start or end.date() > as_of:
        raise ValueError('Invalid date range')
    if resolve_oracle_artifact_horizon(batch_id, artifacts_dir) != 20:
        raise ValueError('This frozen experiment requires Oracle H20')
    symbols = sorted(set(load_universe_file_symbols(symbol_source)))
    if not symbols:
        raise ValueError('Empty universe')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    engine = get_sqlalchemy_engine()
    event.listen(engine, 'before_cursor_execute', forbid_writes)
    def progress(phase, **details):
        LOGGER.info('%s %s', phase, details)
        dump(output/'progress.json', dict(phase=phase, **details))
    all_metrics, tails_parts, coverage = [], [], []
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
                raise ValueError('US database required')
            batch = conn.execute(text('SELECT training_start_date,training_end_date,command_line FROM model_training_batch WHERE batch_id=:batch'),
                                 {'batch': batch_id}).mappings().first()
        dump(output/'protocol.json', dict(batch_id=batch_id, symbol_source=symbol_source,
            universe_hash=hashlib.sha256(','.join(symbols).encode()).hexdigest(), universe_count=len(symbols),
            start_date=start_date, end_date=end_date, evaluated_as_of=as_of,
            training_metadata=dict(batch) if batch else None, thresholds_pct=[50,100],
            policies=POLICIES, sql_writes=False, training=False,
            notes=['Static current universe, survivorship risk', 'Recall conditional on finite Oracle scores',
                   'No proof of historical tradability or independently verified price adjustment',
                   'fold_start recorded, not full train/validation lineage certification',
                   'No parameter selection from results, no economic replay']))
        for year in range(start.year, end.year+1):
            a, b = max(start, pd.Timestamp(year,1,1)), min(end, pd.Timestamp(year,12,31))
            progress('LOAD_YEAR', year=year)
            dest = output/str(year)
            dest.mkdir()
            with engine.connect() as conn:
                params = {'a': a.date(), 'b': b.date(), 'batch': batch_id, 'symbols': symbols}
                query = text('SELECT prediction_date AS date,symbol,proba_extreme,fold_start FROM oracle_extreme_predictions WHERE batch_id=:batch AND prediction_date BETWEEN :a AND :b AND symbol IN :symbols').bindparams(bindparam('symbols', expanding=True))
                scores = pd.read_sql(query, conn, params=params)
                query = text('SELECT prediction_date AS date,symbol,future_return,future_return_raw,oracle_decile,target_quality_valid,target_quality_reason,oracle_exit_date,oracle_available_date FROM global_oracle_labels WHERE batch_id=:batch AND horizon=20 AND prediction_date BETWEEN :a AND :b AND symbol IN :symbols').bindparams(bindparam('symbols', expanding=True))
                labels = pd.read_sql(query, conn, params=params)
                query = text('SELECT date,symbol,high,low,close,adj_close,volume,is_filled,instrument_id,data_source,data_adjustment FROM stock_bars_daily WHERE date BETWEEN :a AND :b AND symbol IN :symbols').bindparams(bindparam('symbols', expanding=True))
                bars = pd.read_sql(query, conn, params={**params, 'a': (a-pd.Timedelta(days=90)).date(), 'b': (b+pd.Timedelta(days=45)).date()})
            for frame in (scores, labels, bars):
                frame['date'] = pd.to_datetime(frame.date)
            for key in ('oracle_exit_date','oracle_available_date'):
                labels[key] = pd.to_datetime(labels[key])
            if labels.duplicated(['date','symbol']).any() or bars.duplicated(['date','symbol']).any():
                raise ValueError('Duplicate labels/bars')
            scores.to_parquet(dest/'scores.parquet', index=False)
            labels.to_parquet(dest/'labels.parquet', index=False)
            # Archived endpoints enable reproducible checks without a second SQL read.
            progress('CALCULATE_YEAR', year=year, scores=len(scores), labels=len(labels), bars=len(bars))
            atr = atr20_percent_panel(bars)
            selected = freeze_selection(scores, atr)
            qualified = qualify_endpoints(labels, bars)
            qualified.to_parquet(dest/'labels_endpoint_checks.parquet', index=False)
            data = selected.merge(qualified, on=['date','symbol'], how='left', validate='one_to_one')
            for col in ('local_endpoint_ok','endpoint_mismatch','missing_adjusted_endpoint','filled_endpoint',
                        'zero_endpoint_volume','identity_change','impossible_long_return','adjustment_effect_gt5pp'):
                data[col] = data[col].fillna(False).astype(bool)
            data.to_parquet(dest/'panel.parquet', index=False)
            rows = metrics(data, as_of=as_of)
            all_metrics.extend([dict(year=year, **r) for r in rows])
            dump(dest/'metrics.json', rows)
            valid = data.target_quality_valid.eq(1) & np.isfinite(data.future_return) & data.oracle_available_date.le(pd.Timestamp(as_of))
            tails = data[valid & data.future_return.abs().ge(.5)].copy()
            tails['side'] = np.where(tails.future_return.gt(0), 'UP', 'DOWN')
            tails_parts.append(tails)
            coverage.append(dict(year=year, scores=len(scores), finite_scores=len(data),
                valid_labels=int(valid.sum()), missing_or_invalid_labels=int((~valid).sum()),
                valid_atr=int(data.atr20_pct.notna().sum()), days=int(data.date.nunique()),
                fold_starts=[str(v) for v in sorted(data.fold_start.dropna().unique())],
                post_training_rows=int(data.date.gt(pd.Timestamp(batch['training_end_date'])).sum()) if batch and batch['training_end_date'] else None,
                quality_reasons=data.target_quality_reason.fillna('NONE_OR_NO_LABEL').value_counts().to_dict(),
                tail_windows=len(tails), local_endpoint_tail_windows=int(tails.local_endpoint_ok.sum())))
            dump(output/'coverage.json', coverage)
            progress('YEAR_COMPLETE', year=year, tail_windows=len(tails))
        tails = pd.concat(tails_parts, ignore_index=True)
        tails.to_parquet(output/'extreme_windows.parquet', index=False)
        clusters = cluster_events(tails)
        dump(output/'clusters.json', clusters)
        pd.DataFrame(all_metrics).to_parquet(output/'year_policy_metrics.parquet', index=False)
        aggregate = []
        for keys, group in pd.DataFrame(all_metrics).groupby(['scope','threshold_pct','side','policy']):
            scope, threshold, side, policy = keys
            n, hits, reference = (int(group[c].sum()) for c in ('evaluated','target_hits','reference_targets'))
            aggregate.append(dict(scope=scope, threshold_pct=int(threshold), side=side, policy=policy,
                selected=int(group.selected.sum()), evaluated=n, unknown=int(group.unknown.sum()),
                target_hits=hits, reference_targets=reference,
                precision_pct=100*hits/n if n else None, capture_pct=100*hits/reference if reference else None))
        top = tails.assign(abs_return=tails.future_return.abs()).sort_values(['abs_return','date'], ascending=[False,True]).head(100)
        # Full paths for the largest cases; flag discontinuities rather than certify them.
        paths = []
        with engine.connect() as conn:
            for row in top.drop_duplicates(['symbol','date']).to_dict('records'):
                path = pd.read_sql(text('SELECT date,symbol,close,adj_close,volume,is_filled,data_source,data_adjustment,instrument_id FROM stock_bars_daily WHERE symbol=:symbol AND date BETWEEN :a AND :b ORDER BY date'),conn,
                    params={'symbol':row['symbol'],'a':row['date'].date(),'b':row['oracle_exit_date'].date()})
                adj = pd.to_numeric(path.adj_close, errors='coerce')
                step = adj.pct_change(fill_method=None).abs()
                paths.append(dict(date=row['date'],symbol=row['symbol'],future_return_pct=float(row['future_return']*100),
                    local_endpoint_ok=bool(row['local_endpoint_ok']), path_bars=len(path),
                    zero_volume_bars=int(path.volume.fillna(0).le(0).sum()),
                    max_abs_daily_return_pct=float(step.max()*100) if step.notna().any() else None,
                    bars=path.to_dict('records')))
        dump(output/'largest_paths.json', paths)
        flags = {key: int(tails[key].sum()) for key in ('endpoint_mismatch','missing_adjusted_endpoint',
                 'filled_endpoint','zero_endpoint_volume','identity_change','impossible_long_return','adjustment_effect_gt5pp')}
        report = dict(status='COMPLETED_DESCRIPTIVE_AUDIT_NOT_DEPLOYABLE', sql_writes=False, training=False,
            coverage=coverage, aggregate_metrics=aggregate, tail_quality_flags=flags,
            clusters=dict(total=len(clusters), windows=len(tails),
                policy_any_capture_pct={p:100*sum(c[p] for c in clusters)/len(clusters) if clusters else None for p in POLICIES}),
            largest_paths_audited=len(paths),
            verdict='PRICE_QUALITY_AND_DIRECTION_UNRESOLVED_NO_DEPLOYMENT',
            caveats=['Extreme-window counts are overlapping, not independent trades',
                     'Endpoint checks exclude no suspicious rows from LABEL_VALID results',
                     'LOCAL_ENDPOINT_OK is sensitivity only, not proof of independently corrected prices',
                     '>=100% downside from a long price return is economically impossible',
                     'Precision/recall do not show direction prediction or realizable portfolio PnL'])
        dump(output/'report.json', report)
        progress('COMPLETED', report=str(output/'report.json'))
        return report
    except Exception as exc:
        progress('FAILED', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        event.remove(engine, 'before_cursor_execute', forbid_writes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id', default='model-factory-20261003082853-e98332')
    parser.add_argument('--symbol-source', default='universe-file:univers_filtred_tradable.txt')
    parser.add_argument('--start-date', default='2020-01-01')
    parser.add_argument('--end-date', default='2026-09-30')
    parser.add_argument('--artifacts-dir', default='artifacts/models')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(**vars(args))
    print(f'Extreme50 capture terminé: {args.output}')


if __name__ == '__main__':
    main()
