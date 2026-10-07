"""Annual portfolio replay of corrected predicted Oracle TOP10, SELECT-only.

Existing OOF models before July 2024; last frozen fold thereafter. No labels
enter selection, no training, no serving replacement and no SQL writes.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, event, text

from common.config_loader import load_config
from common.trading_costs import DEFAULT_COST_MODEL
from database.connection import get_sqlalchemy_engine
from service.market import parse_market_regimes
from scripts.research.us_concentrated_contract_audit import frozen_configs
from scripts.research.us_concentrated_exit_variants import VARIANTS
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_extreme50_capture import forbid_writes
from scripts.research.us_oracle_h20_dataset_audit import restore_ranks
from scripts.research.us_oracle_numeric_effect import read_json

LOG = logging.getLogger(__name__)
BASE = Path('artifacts/research/us_concentrated_replay')
TRAINING = BASE/'oracle-h20-numeric-effect-20261007-v1'
EXTERNAL = BASE/'oracle-h20-numeric-external-20261007-v1'
SECTORS = BASE/'live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet'


def select_scores(frame):
    """Only observable inputs are permitted across this selection boundary."""
    data = frame[['date', 'symbol', 'score', 'fold_start']].copy()
    data['date'] = pd.to_datetime(data.date)
    if data.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate prediction key')
    if (data[['date', 'symbol', 'fold_start']].isna().any().any()
            or not np.isfinite(data.score.to_numpy(dtype=float)).all()
            or (pd.to_datetime(data.fold_start) > data.date).any()):
        raise ValueError('Unqualified prediction chronology/score')
    counts = data.groupby('date').size()
    if (counts < 10).any():
        raise ValueError('Fewer than ten observable predictions')
    data = data.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True])
    data = data.groupby('date', sort=False).head(10).copy()
    data['oracle_rank'] = data.groupby('date').cumcount()+1
    data['ORACLE_TOP10'] = True
    return data.rename(columns={'score': 'proba_extreme'}).reset_index(drop=True)


def yearly_windows(start, end):
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if first > last:
        raise ValueError('Reversed date window')
    return [(year, max(first, pd.Timestamp(year, 1, 1)),
             min(last, pd.Timestamp(year, 12, 31)))
            for year in range(first.year, last.year+1)]


def check_coverage(scores, calendar, start, end):
    days = calendar[(calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end))]
    if days.empty:
        raise ValueError('Empty market calendar')
    counts = scores.groupby('date').size().reindex(days, fill_value=0)
    missing = counts[counts.ne(10)]
    if len(missing):
        raise ValueError('TOP10 coverage missing/incomplete: '+','.join(str(d.date()) for d in missing.index[:15]))
    return days


def gap_predictions(output, historical, threads):
    """Reuse already audited 2024 features and a model frozen before these dates."""
    import lightgbm as lgb
    destination = output/'gap-2024-predictions.parquet'
    if destination.exists():
        marker = read_json(output/'gap-2024.json')
        if digest(destination) != marker['sha256']:
            raise ValueError('Gap prediction hash changed')
        return pd.read_parquet(destination)
    root = Path(historical['after'])
    fold = historical['expected_fold_starts'][-1]
    directory = TRAINING/'corrected'/fold
    metrics = read_json(directory/'metrics.json')
    start = pd.Timestamp(metrics['fold_end'])+pd.Timedelta(days=1)
    end = pd.Timestamp('2024-12-31')
    if max(pd.Timestamp(metrics[k]) for k in ('train_max_available', 'val_max_available')) >= start:
        raise ValueError('Frozen model uses information unavailable at gap start')
    model_path = directory/'model.txt'
    if digest(model_path) != read_json(directory/'done.json')['model.txt']:
        raise ValueError('Frozen model hash mismatch')
    parts, sources = [], {}
    paths = sorted(root.glob('features-*.parquet'))
    audit = read_json(root/'protocol.json')
    if len(paths) != (audit['symbols']+audit['chunk_size']-1)//audit['chunk_size']:
        raise ValueError('Missing audited feature shards')
    for i, path in enumerate(paths):
        checksum = digest(path)
        if checksum != read_json(path.with_suffix('.json'))['sha256']:
            raise ValueError(f'Changed audited feature shard: {path}')
        sources[str(path)] = checksum
        part = pd.read_parquet(path, filters=[('date', '>=', start), ('date', '<=', end)])
        parts.append(part)
        atomic_json(output/'progress.json', dict(status='PREPARING', phase='2024_gap', completed=i+1, total=len(paths)))
    frame = restore_ranks(pd.concat(parts, ignore_index=True), historical['features'])
    model = lgb.Booster(model_file=str(model_path))
    if model.feature_name() != historical['features']:
        raise ValueError('Frozen feature contract mismatch')
    result = frame[['date', 'symbol']].copy()
    result['score'] = model.predict(frame[historical['features']], num_threads=threads)
    result['fold_start'] = fold
    result.to_parquet(destination, index=False)
    atomic_json(output/'gap-2024.json', dict(sha256=digest(destination), sources=sources,
        model_sha256=digest(model_path), start=str(start.date()), end=str(end.date()),
        training=False, labels_used=False, ranks_before_top10=True))
    return result


def prepare(output, start, end, threads):
    historical = read_json(TRAINING/'protocol.json')
    selected, sources = [], {}
    for fold in historical['expected_fold_starts']:
        root = TRAINING/'corrected'/fold
        path = root/'predictions.parquet'
        if digest(path) != read_json(root/'done.json')['predictions.parquet']:
            raise ValueError('Changed OOF predictions')
        sources[str(path)] = digest(path)
        selected.append(select_scores(pd.read_parquet(path)))
    selected.append(select_scores(gap_predictions(output, historical, threads)))
    path = EXTERNAL/'corrected-predictions.parquet'
    external_report = read_json(EXTERNAL/'report.json')
    if external_report['status'] != 'COMPLETED_FROZEN_EXTERNAL_CONFIRMATION':
        raise ValueError('External predictions incomplete')
    sources[str(path)] = digest(path)
    selected.append(select_scores(pd.read_parquet(path)))
    scores = pd.concat(selected, ignore_index=True)
    scores = scores.loc[scores.date.between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    if scores.duplicated(['date', 'symbol']).any():
        raise ValueError('Overlapping score periods')
    sectors = pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict()
    if set(scores.symbol)-set(sectors):
        raise ValueError('Current-sector evidence incomplete')
    symbols = sorted(set(scores.symbol)|{'SPY'})
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    event.listen(engine, 'before_cursor_execute', forbid_writes)
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
                raise ValueError('US database required')
            query = text('''SELECT date,symbol,open,high,low,close,adj_close,volume,is_filled,instrument_id
                FROM stock_bars_daily WHERE date BETWEEN :a AND :b AND symbol IN :symbols''').bindparams(bindparam('symbols', expanding=True))
            warmup = str((pd.Timestamp(start)-pd.Timedelta(days=400)).date())
            bars = pd.read_sql(query, conn, params=dict(a=warmup, b=end, symbols=symbols))
            macro = pd.read_sql(text('''SELECT * FROM stock_macro_indicators_daily
                WHERE trade_date BETWEEN :a AND :b'''), conn, params=dict(a=warmup, b=end))
    finally:
        engine.dispose()
    bars['date'] = pd.to_datetime(bars.date)
    if bars.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate price key')
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0), 'date']).sort_values()
    check_coverage(scores, calendar, start, end)
    # Missing macro rows are a blocking input, not invented neutral observations.
    expected = calendar[(calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end))]
    missing_macro = expected.difference(pd.DatetimeIndex(pd.to_datetime(macro.trade_date)))
    coverage = dict(sessions=len(expected), first=str(expected[0].date()), last=str(expected[-1].date()),
        missing_macro_dates=[str(d.date()) for d in missing_macro], candidates=len(scores), symbols=len(symbols)-1)
    atomic_json(output/'coverage.json', coverage)
    for name, frame in [('scores', scores), ('bars', bars), ('macro', macro)]:
        frame.to_parquet(output/f'{name}.parquet', index=False)
    manifest = dict(sources=sources, sector_sha256=digest(SECTORS),
        files={f'{name}.parquet':digest(output/f'{name}.parquet') for name in ('scores', 'bars', 'macro')})
    atomic_json(output/'inputs.json', manifest)


def run(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    risk, execution = frozen_configs()
    protocol = dict(experiment='CORRECTED_PREDICTED_ORACLE_TOP10_ANNUAL', start=args.start, end=args.end,
        years=list(range(pd.Timestamp(args.start).year, pd.Timestamp(args.end).year+1)),
        initial_equity_each_year=4000, annual_reset=True, terminal_liquidation=True,
        long_only=True, initial_stop_pct=.07, variants=args.variants, max_days=args.max_days,
        market=asdict(market), risk=asdict(risk), execution=asdict(execution),
        canonical_costs=asdict(DEFAULT_COST_MODEL), margin_interest_rate_annual=.075,
        code_sha256={name:digest(name) for name in [__file__,
            'scripts/research/us_concentrated_live_portfolio.py',
            'scripts/research/us_concentrated_contract_audit.py',
            'scripts/research/us_concentrated_fixed_stop.py',
            'backtesting/oracle_portfolio_ledger.py', 'backtesting/oracle_portfolio_session.py',
            'backtesting/simulator.py', 'common/trading_costs.py']},
        score_source='Corrected OOF through 2024-07-09; frozen 2024-01-08 fold thereafter',
        selection='10 descending predicted scores, symbol tie-break, no realized outcome filter',
        training=False, sql_writes=False, sectors='current NON-PIT explicitly accepted',
        limitations=['Current universe survivorship/reconstruction bias',
            'Daily macro archive is not certified publication vintage',
            'OHLC fills simulated; spread/slippage assumptions, no actual broker fills',
            'Exploratory historical replay; 2026 partial, not full-year return',
            'Fixed 7% initial stop is not a loss guarantee across gaps; native ATR sizing unchanged'])
    # Normalize dates/enums identically on first run and resume.
    import json
    protocol = json.loads(json.dumps(protocol, default=str))
    path = output/'protocol.json'
    if path.exists() and read_json(path) != protocol:
        raise ValueError('Annual replay resume protocol changed')
    atomic_json(path, protocol)
    if not (output/'inputs.json').exists():
        prepare(output, args.start, args.end, args.threads)
    manifest = read_json(output/'inputs.json')
    if digest(SECTORS) != manifest['sector_sha256']:
        raise ValueError('Sector evidence changed')
    for name, checksum in manifest['files'].items():
        if digest(output/name) != checksum:
            raise ValueError('Archived replay input changed')
    bars, scores, macro = [pd.read_parquet(output/f'{name}.parquet') for name in ('bars', 'scores', 'macro')]
    sectors = pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict()
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0), 'date']).sort_values()
    frames = {key:bars.pivot(index='date', columns='symbol', values=column).reindex(calendar)
        for key, column in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    reports, failures = [], []
    windows = yearly_windows(args.start, args.end)
    total = len(windows)*len(args.variants)
    for year, start, end in windows:
        for variant in args.variants:
            destination = output/str(year)/variant
            atomic_json(output/'progress.json', dict(status='RUNNING', year=year, variant=variant,
                completed_runs=len(reports), failed_runs=len(failures), total_runs=total))
            try:
                check_coverage(scores, calendar, start, end)
                report_path = destination/'report.json'
                if report_path.exists():
                    result = read_json(report_path)
                    if result['status'] != 'COMPLETED':
                        raise ValueError('Invalid completed run marker')
                else:
                    result = run_portfolio(frames=frames, scores=scores, sectors=sectors,
                        macro=ArchivedMacro(macro), market_config=market, policy='ORACLE_TOP10',
                        variant=variant, output=destination, quality=bars[['date','symbol','is_filled','instrument_id']],
                        initial_stop_pct=.07, reject_constrained_entries=True, max_days=args.max_days,
                        start_date=str(start.date()), end_date=str(end.date()))
                reports.append(dict(year=year, partial_year=year == pd.Timestamp(args.end).year
                    and pd.Timestamp(args.end).month != 12, smoke=args.max_days is not None, **result))
            except Exception as exc:
                LOG.exception('Annual replay failed year=%s variant=%s', year, variant)
                failures.append(dict(year=year, variant=variant, error=str(exc)))
            atomic_json(output/'report.json', dict(status='RUNNING', runs=reports, failures=failures))
    status = 'PARTIAL_FAILED' if failures else ('COMPLETED_SMOKE' if args.max_days else 'COMPLETED')
    atomic_json(output/'report.json', dict(status=status, runs=reports, failures=failures))
    atomic_json(output/'progress.json', dict(status=status, completed_runs=len(reports), failed_runs=len(failures), total_runs=total))
    LOG.info('Annual replay %s: %s', status, output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', default='2020-01-01')
    parser.add_argument('--end', default='2026-09-03')
    parser.add_argument('--variants', nargs='+', choices=list(VARIANTS), default=list(VARIANTS))
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--max-days', type=int, help='Smoke only, never an annual return')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run(args)
    except Exception as exc:
        atomic_json(args.output/'progress.json', dict(status='FAILED', error=str(exc)))
        raise
