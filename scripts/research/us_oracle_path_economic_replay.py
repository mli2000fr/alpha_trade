"""Frozen path-amplitude LightGBM economic replay; no fit, SQL write or orders.

Scores precede future label exclusions. TOP-K membership is fixed before entry
quality/risk filters. LONG is an explicit policy, not an inferred direction.
"""
from dataclasses import asdict
from functools import partial
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import event, text

from common.config_loader import load_config
from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_barrier_comparison import SECTORS, read, readonly_statement
from scripts.research.us_oracle_barrier_exit_grid import GridLedger
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from scripts.research.us_oracle_h20_dataset_audit import readonly_begin
from scripts.research.us_oracle_tp20_sl10_campaign import annual_metrics, code_hashes
from scripts.research.us_oracle_tp20_sl10_lifecycle import load_events
from service.market import parse_market_regimes

LOG = logging.getLogger(__name__)
CONFIRMATION = Path('artifacts/research/oracle_path_confirmation/20261013-v1')
TAPES = Path('artifacts/research/us_oracle_tp20_sl10_new/20261012-v6')
YEARS, COUNTS = (2024, 2025, 2026), (10, 20, 50)
AS_OF = '2026-10-09'
DECISION_END = '2026-09-10'


def freeze_top(scores, count):
    """Only J's scores determine membership; no realised outcomes are read."""
    if type(count) is not int or count < 1:
        raise ValueError('Positive integer TOP count required')
    frame = scores[['date', 'symbol', 'score_lightgbm']].copy()
    frame['date'] = pd.to_datetime(frame.date).dt.normalize()
    if frame.duplicated(['date', 'symbol']).any() or frame.symbol.isna().any():
        raise ValueError('Duplicate/missing score identity')
    values = frame.score_lightgbm
    if not np.isfinite(values).all() or not values.between(0, 1).all():
        raise ValueError('Invalid LightGBM amplitude scores')
    # Allocation strength, NOT probability of a positive return. Computed on
    # the full observable population, before TOP-K or entry-quality filtering.
    frame['proba_extreme'] = frame.groupby('date').score_lightgbm.rank(method='average', pct=True)
    frame = frame.sort_values(['date', 'score_lightgbm', 'symbol'], ascending=[True, False, True])
    frame['oracle_rank'] = frame.groupby('date').cumcount()+1
    frame = frame.loc[frame.oracle_rank.le(count)].copy()
    frame['selected'] = True
    return frame


def cohort_window(year, calendar, decision_end=DECISION_END):
    cutoff = pd.Timestamp(decision_end if year == 2026 else f'{year}-12-31')
    final = calendar[calendar <= cutoff][-1]
    index = calendar.get_loc(final)+21  # decision J, entry J+1, exit J+21 open
    if index >= len(calendar):
        raise ValueError('Insufficient terminal tail for twenty held sessions')
    return final, calendar[index]


def covered_windows(calendar, macro_dates):
    """Global calendar truncation for missing macro, never price/outcome filters."""
    expected = calendar[calendar >= '2024-01-01']
    missing = expected.difference(pd.DatetimeIndex(macro_dates))
    ceiling = calendar[-1] if missing.empty else calendar[calendar < missing.min()][-1]
    latest = calendar[calendar.get_loc(ceiling)-21]
    if latest < pd.Timestamp('2026-01-01'):
        raise ValueError('Insufficient continuous macro coverage for all three annual cohorts')
    decision_end = min(pd.Timestamp(DECISION_END), latest)
    return {str(year): dict(decision_end=str(final.date()), terminal_date=str(end.date()),
        decision_sessions=len(calendar[(calendar >= f'{year}-01-01') & (calendar <= final)]))
        for year in YEARS for final, end in [cohort_window(year, calendar, decision_end)]}


def qualify_entries(candidates, prices, calendar):
    """J-only strict history check AFTER ranking; never backfill the TOP pool."""
    selected = candidates.copy()
    columns = sorted(set(selected.symbol))
    p = prices.loc[prices.symbol.isin(columns)].copy()
    if p.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate price identity')
    wide = {c: p.pivot(index='date', columns='symbol', values=c).reindex(index=calendar, columns=columns)
            for c in ('open', 'high', 'low', 'close', 'volume', 'is_filled', 'instrument_id')}
    valid = pd.DataFrame(True, index=calendar, columns=columns)
    for c in ('open', 'high', 'low', 'close', 'volume'):
        valid &= np.isfinite(wide[c]) & wide[c].gt(0)
    valid &= wide['is_filled'].eq(0)
    valid &= wide['high'].ge(wide['open']) & wide['high'].ge(wide['close'])
    valid &= wide['low'].le(wide['open']) & wide['low'].le(wide['close'])
    valid &= wide['high'].ge(wide['low'])
    history = valid.rolling(21, min_periods=21).sum().eq(21)
    # ATR20 requires 20 true ranges and the preceding close, never future bars.
    previous = wide['close'].shift()
    tr = np.maximum(wide['high']-wide['low'],
                    np.maximum((wide['high']-previous).abs(), (wide['low']-previous).abs()))
    history &= tr.rolling(20, min_periods=20).mean().gt(0)
    for symbol in columns:
        identity = wide['instrument_id'][symbol]
        codes, _ = pd.factorize(identity)
        code = pd.Series(codes, index=calendar, dtype=float).mask(codes < 0)
        stable = code.rolling(21, min_periods=21).max().eq(code.rolling(21, min_periods=21).min())
        history[symbol] &= stable
    index = pd.MultiIndex.from_frame(selected[['date', 'symbol']])
    qualified = history.stack(future_stack=True).reindex(index).fillna(False).to_numpy(dtype=bool)
    selected['selected'] = qualified
    selected['entry_quality_reason'] = np.where(qualified, '', 'J_HISTORY_OHLCV_FILLED_IDENTITY_ATR_UNQUALIFIED')
    return selected


def cohort_metrics(result, trades, daily, year, cutoff):
    metrics = annual_metrics(result, trades, daily, year)
    # The old campaign helper's 2026 cutoff is September 3; never inherit it.
    marked = daily.loc[pd.to_datetime(daily.date).le(cutoff)]
    metrics['calendar_mark_to_market_capital'] = float(marked.equity.iloc[-1]) if len(marked) else None
    metrics['mean_capital_deployed_usd'] = float(daily.gross_notional.mean())
    metrics['max_capital_deployed_usd'] = float(daily.gross_notional.max())
    return metrics


def prepare(output, confirmation=CONFIRMATION, tapes=TAPES):
    """Snapshot input provenance and, only if needed, SELECT the macro tail."""
    if (output/'manifest.json').exists():
        manifest = read(output/'manifest.json')
        verify_hashes(Path('.'), manifest['source_hashes'])
        verify_hashes(Path('.'), manifest['code_hashes'])
        verify_hashes(output, manifest['files'])
        return manifest
    plan, report = read(confirmation/'plan.json'), read(confirmation/'report.json')
    if read(confirmation/'progress.json')['status'] != 'COMPLETED' or report['status'] not in ('completed', 'completed_with_reservations'):
        raise ValueError('Completed causal score confirmation required')
    if report['fixed_fold'] != plan['fixed_fold'] or report['model_hashes'] != plan['model_hashes']:
        raise ValueError('Score/model provenance mismatch')
    for name in ('train_available_max', 'val_available_max'):
        if pd.isna(pd.Timestamp(plan[name])) or pd.Timestamp(plan[name]) >= pd.Timestamp('2024-01-01'):
            raise ValueError('Fit/validation must precede the entire economic window')
    model = Path(plan['source'])/'models/oracle-path-comparison/oracle_path'
    model_file = model/'folds'/plan['fixed_fold']/'path_model.txt'
    if digest(model_file) != plan['model_hashes']['lightgbm']:
        raise ValueError('Original LightGBM model changed')
    if digest(model/'protocol.json') != plan['source_protocol_sha256'] or digest(model/'feature_profile.json') != plan['feature_profile_sha256']:
        raise ValueError('Original model contract changed')
    verify_hashes(Path('.'), plan['original_source_hashes'])
    ready = read(tapes/'ready.json')
    verify_hashes(tapes, {n: ready['files'][n] for n in ('prices.parquet', 'macro.parquet', 'lifecycle.json', 'protocol.json')})
    if read(tapes/'completion-audit.json')['status'] != 'ALL_NINE_BASELINE_CASES_VERIFIED':
        raise ValueError('Qualified common price/lifecycle tape required')
    if set(read(tapes/'protocol.json')['universe']) != set(plan['universe']):
        raise ValueError('Price and score universes differ')
    events = load_events(tapes)
    scores = pd.read_parquet(confirmation/'scores.parquet')
    if len(scores) != report['scored_rows'] or set(scores.symbol) != set(plan['universe']) or not scores.fold_start.eq(plan['fixed_fold']).all():
        raise ValueError('Score population/fold differs from confirmation')
    scores = scores[['date', 'symbol', 'score_lightgbm']].copy()
    scores.to_parquet(output/'scores.parquet', index=False)
    calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(), pd.Timestamp(AS_OF).date())
    macro = pd.read_parquet(tapes/'macro.parquet')
    missing = calendar[calendar >= '2024-01-01'].difference(pd.DatetimeIndex(macro.trade_date))
    supplementary = False
    if len(missing):
        LOG.info('Reading missing archived macro dates: %s', [str(d.date()) for d in missing])
        engine = get_sqlalchemy_engine(db_name='alpha_trade')
        if engine.url.database != 'alpha_trade':
            raise ValueError('US database required')
        event.listen(engine, 'begin', readonly_begin)
        event.listen(engine, 'before_cursor_execute', readonly_statement)
        try:
            extra = pd.read_sql(text('SELECT * FROM stock_macro_indicators_daily WHERE trade_date BETWEEN :start AND :end'),
                engine, params=dict(start=str(missing.min().date()), end=AS_OF), parse_dates=['trade_date'])
        finally:
            engine.dispose()
        extra = extra.loc[extra.trade_date.isin(missing)]
        if not extra.empty:
            macro = pd.concat([macro, extra], ignore_index=True).sort_values('trade_date')
        supplementary = True
    if macro.trade_date.duplicated().any():
        raise ValueError('Duplicate archived macro dates; no forward-fill')
    windows = covered_windows(calendar, macro.trade_date)
    if windows['2026']['decision_end'] != DECISION_END:
        LOG.warning('Macro coverage limits 2026 decisions to %s, exits to %s',
            windows['2026']['decision_end'], windows['2026']['terminal_date'])
    macro.to_parquet(output/'macro.parquet', index=False)
    prices = pd.read_parquet(tapes/'prices.parquet')
    if prices.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate common prices')
    cfg = frozen_backtest_config('2024-01-02', AS_OF)
    market = parse_market_regimes(load_config().get('market_regimes'))
    if market.earnings_shield.enabled or market.buyback_blackout.enabled:
        raise ValueError('Historical earnings/buyback evidence required by active guards')
    for year in YEARS:
        final = pd.Timestamp(windows[str(year)]['decision_end'])
        expected = calendar[(calendar >= f'{year}-01-01') & (calendar <= final)]
        observed = pd.DatetimeIndex(scores.loc[scores.date.isin(expected), 'date'].unique())
        if len(expected.difference(observed)):
            raise ValueError(f'Missing scoring sessions for {year}')
    files = ('scores.parquet', 'macro.parquet')
    paths = [confirmation/'plan.json', confirmation/'report.json', confirmation/'scores.parquet',
        model/'protocol.json', model/'feature_profile.json', model_file,
        model/'folds'/plan['fixed_fold']/'done.json', tapes/'ready.json', tapes/'prices.parquet',
        tapes/'macro.parquet', tapes/'lifecycle.json', tapes/'completion-audit.json', SECTORS]
    hashes = code_hashes()
    hashes[str(Path(__file__))] = digest(__file__)
    hashes['scripts/research/oracle_path_confirmation.py'] = digest('scripts/research/oracle_path_confirmation.py')
    manifest = dict(schema_version=1, source_hashes={str(p): digest(p) for p in paths},
        code_hashes=hashes, files={n: digest(output/n) for n in files}, confirmation=str(confirmation), tapes=str(tapes),
        backend='lightgbm', validation_champion=plan['validation_champion'],
        backend_choice='user operational choice, not a newly selected validation champion',
        fixed_fold=plan['fixed_fold'], model_sha256=plan['model_hashes']['lightgbm'],
        train_available_max=plan['train_available_max'], val_available_max=plan['val_available_max'],
        years=list(YEARS), counts=list(COUNTS), windows=windows, as_of=AS_OF,
        requested_2026_decision_end=DECISION_END,
        macro_missing_dates=[str(d.date()) for d in calendar[calendar >= '2024-01-01'].difference(pd.DatetimeIndex(macro.trade_date))],
        target='absolute maximum HIGH/LOW excursion J+1..J20 from close J; cross-sectional TOP20 label',
        selection='raw score descending; symbol ascending tie-break; TOP titles, not TOP percent',
        allocation='full-J-population percentile, NOT P(up); native ATR sizing retained',
        direction_policy='LONG_ONLY_EXPLICIT_NOT_LEARNED', atr_membership_gate=False,
        take_profit_pct=.20, stop_loss_pct=.10, trailing=False, expiry_open_sessions=20,
        annual_initial_equity=4000., risk=asdict(cfg.risk_config), execution=asdict(cfg.exec_config),
        market=asdict(market), events=events, macro_tail_select_only=supplementary,
        no_training=True, no_sql_writes=True, no_broker_calls=True, no_promotion=True,
        limitations=['static survivor universe; current sectors accepted but not PIT',
            'current adjusted daily OHLC, not bid/ask or observed broker fills',
            'macro publication vintages not independently certified',
            'risk/cost/lifecycle shared engine with frozen research configuration, not exact current live settings',
            'ATR-native sizing retained despite fixed SL10; not equal monetary risk per trade',
            '2024-2026 already explored; not virgin holdouts; annual reset, January tails not calendar returns'])
    atomic_json(output/'manifest.json', manifest)
    verify_hashes(Path('.'), manifest['source_hashes'])
    return manifest


def run_case(output, manifest, year, count, scores, prices, macro, sectors, calendar):
    root = output/f'{year}-TOP{count}'
    root.mkdir(parents=True, exist_ok=True)
    marker = root/'case-report.json'
    if marker.exists() and read(marker)['status'] == 'COMPLETED_EXPLORATORY':
        saved = read(marker)
        verify_hashes(root, saved['files'])
        return saved
    window = manifest['windows'][str(year)]
    population = scores.loc[scores.date.dt.year.eq(year) & scores.date.le(window['decision_end'])]
    candidates = qualify_entries(freeze_top(population, count), prices, calendar)
    candidates.to_parquet(root/'candidates.parquet', index=False)
    required = set(candidates.symbol) | {'SPY', 'VMRK'}
    sector_map = dict(sectors)
    sector_map['VMRK'] = sector_map['EQR']
    for e in manifest['events']:
        if e['source'] in required:
            required.add(e['target'])
            if e.get('event_type') == 'NAME_CHANGE':
                sector_map[e['target']] = sector_map[e['source']]
    if required-{'SPY'}-set(sector_map):
        raise ValueError(f'Missing sectors: {required-set(sector_map)}')
    subset = prices.loc[prices.symbol.isin(required)]
    frames = {key: subset.pivot(index='date', columns='symbol', values=col).reindex(calendar)
        for key, col in [('opens', 'open'), ('close', 'close'), ('high', 'high'), ('low', 'low'), ('volume', 'volume')]}
    result = run_portfolio(frames=frames, scores=candidates, sectors=sector_map,
        macro=ArchivedMacro(macro), market_config=parse_market_regimes(manifest['market']),
        policy='selected', variant='CURRENT_NO_EXPIRY', output=root,
        start_date=f'{year}-01-01', end_date=window['terminal_date'], decision_end_date=window['decision_end'],
        quality=subset[['date', 'symbol', 'is_filled', 'instrument_id']],
        ledger_factory=partial(GridLedger, tp_pct=.2, sl_pct=.1, cash_policy='STRICT', events=manifest['events']),
        expiry_open_sessions=20, protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    trades = pd.read_parquet(root/'trades.parquet')
    audit = verify_trade_contract(trades, .2, .1, calendar)
    if not trades.empty and not trades.get('direction', pd.Series('long', index=trades.index)).str.lower().isin(['long', 'buy']).all():
        raise ValueError('Unexpected short trade')
    if not result.get('account_wealth_complete', False) or abs(result['cash_reconciliation_error']) > 1e-6:
        raise ValueError('Incomplete account wealth or cash reconciliation')
    result.update(status='COMPLETED_EXPLORATORY', year=year, count=count,
        backend='lightgbm', side='LONG', tp_pct=.2, sl_pct=.1, trailing=False,
        selected_candidate_rows=len(candidates), j_quality_rejections=int((~candidates.selected).sum()),
        annual_metrics=cohort_metrics(result, trades, pd.read_parquet(root/'daily.parquet'), year, window['decision_end']),
        protection_audit=audit, files={p.name: digest(p) for p in root.glob('*.parquet')})
    atomic_json(marker, result)
    return result


def run(output, confirmation=CONFIRMATION, tapes=TAPES, prepare_only=False):
    output = Path(output)
    with exclusive_run(output):
        results = []
        try:
            atomic_json(output/'progress.json', dict(status='RUNNING', phase='preflight', completed_runs=0, total_runs=9))
            manifest = prepare(output, confirmation, tapes)
            if prepare_only:
                atomic_json(output/'progress.json', dict(status='READY', completed_runs=0, total_runs=9))
                return
            scores = pd.read_parquet(output/'scores.parquet')
            prices = pd.read_parquet(Path(manifest['tapes'])/'prices.parquet')
            macro = pd.read_parquet(output/'macro.parquet')
            sectors = pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict()
            calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(), pd.Timestamp(AS_OF).date())
            for year in YEARS:
                for count in COUNTS:
                    atomic_json(output/'progress.json', dict(status='RUNNING', phase='portfolio', year=year, count=count,
                        completed_runs=len(results), total_runs=9, current_case=f'{year}-TOP{count}'))
                    LOG.info('Starting %s TOP%s', year, count)
                    result = run_case(output, manifest, year, count, scores, prices, macro, sectors, calendar)
                    results.append(result)
                    atomic_json(output/'report.json', dict(status='RUNNING', portfolios=results, completed_runs=len(results), total_runs=9))
                    LOG.info('Completed %s TOP%s: %s', year, count, result['annual_metrics'])
            verify_hashes(Path('.'), manifest['source_hashes'])
            verify_hashes(Path('.'), manifest['code_hashes'])
            verify_hashes(output, manifest['files'])
            atomic_json(output/'report.json', dict(status='COMPLETED_EXPLORATORY', portfolios=results,
                completed_runs=9, total_runs=9, source_hashes_verified=True, no_training=True,
                no_sql_writes=True, no_broker_calls=True, no_promotion=True))
            pd.DataFrame([dict(year=r['year'], count=r['count'], **r['annual_metrics']) for r in results]).to_csv(output/'annual-summary.csv', index=False)
            atomic_json(output/'progress.json', dict(status='COMPLETED', completed_runs=9, total_runs=9))
        except Exception as exc:
            atomic_json(output/'progress.json', dict(status='FAILED', completed_runs=len(results), total_runs=9,
                error_type=type(exc).__name__, error=str(exc)))
            atomic_json(output/'report.json', dict(status='PARTIAL_FAILED', portfolios=results, completed_runs=len(results),
                total_runs=9, error_type=type(exc).__name__, error=str(exc)))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--confirmation', type=Path, default=CONFIRMATION)
    parser.add_argument('--tapes', type=Path, default=TAPES)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    run(**vars(args))
