"""Frozen terminal vs TP-before-SL Oracle: count TOP10/20/50, SELECT only.

No fit, production replacement, broker connection or SQL persistence. Ranking
never sees future quality/labels. Native risk/cash/lifecycle own portfolio fills.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import gc
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import event, text

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from common.config_loader import load_config
from database.connection import get_sqlalchemy_engine
from execution_engine.models import IntentRole
from modelFactory.config import OracleBarrierConfig
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle.security_continuity import load_security_discontinuities
from modelFactory.oracle_barrier import SCORES, TARGETS
from modelFactory.oracle_barrier.labels import load_bars, symbol_barriers
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_fixed_stop import fixed_stop_protections
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_h20_dataset_audit import restore_ranks
from service.market import parse_market_regimes

LOG = logging.getLogger(__name__)
BASE = Path('artifacts/research/us_concentrated_replay')
OLD = BASE/'oracle-h20-numeric-effect-20261007-v1'
EXTERNAL = BASE/'oracle-h20-numeric-external-20261007-v1'
NEW = Path('artifacts/models/model-factory-20261011221400-867a1e/oracle_barrier')
SECTORS = BASE/'live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet'
COUNTS = (10, 20, 50)
ARMS = {'OLD_TERMINAL_LONG': 'old_score', 'NEW_BARRIER_LONG': SCORES['long']}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def readonly_statement(conn, cursor, statement, parameters, context, executemany):
    # Engine setup transaction is allowed, arbitrary SET/DML/DDL is not.
    normalized = ' '.join(statement.strip().upper().split())
    if normalized != 'SET TRANSACTION READ ONLY' and normalized.split()[0] != 'SELECT':
        raise RuntimeError('Comparison is SELECT-only')


def fixed_barrier_protections(protection):
    result = fixed_stop_protections(protection, .07)
    signals, frame, orders = (result.signals_df.copy(), result.protection_frame.copy(),
                              result.order_lifecycle_frame.copy())
    if not signals.empty:
        prices = signals.set_index('symbol').fill_price.astype(float)*1.20
        if not prices.index.is_unique or not np.isfinite(prices).all() or prices.le(0).any():
            raise ValueError('Invalid fixed-TP anchors')
        for target in (signals, frame):
            if not target.empty:
                target['replay_take_profit_price'] = target.symbol.map(prices)
        if not orders.empty:
            mask = orders.intent_role.eq(IntentRole.TAKE_PROFIT)
            orders.loc[mask, 'limit_price'] = orders.loc[mask, 'symbol'].map(prices)
    return replace(result, signals_df=signals, protection_frame=frame,
        order_lifecycle_frame=orders, diagnostics=dict(result.diagnostics,
            research_take_profit_pct=.20, take_profit_unchanged=False,
            research_trailing_enabled=False))


class FixedBarrierLedger(OraclePortfolioLedger):
    def _build_entry_protections(self, phase3, *, execution_config):
        return fixed_barrier_protections(super()._build_entry_protections(
            phase3, execution_config=execution_config))


def freeze_candidates(scores, count, arm):
    """Only observable keys/scores enter ranking; never replace unknown outcomes.

    Native sizing receives identical rank percentiles, not uncalibrated scores
    with very different base rates. Raw model scores remain in research archive.
    """
    if count not in COUNTS or arm not in ARMS:
        raise ValueError('Unknown frozen count/arm')
    column = ARMS[arm]
    frame = scores[['date', 'symbol', column]].copy()
    if frame.duplicated(['date', 'symbol']).any() or not np.isfinite(frame[column]).all():
        raise ValueError('Duplicate keys or invalid score')
    frame = frame.sort_values(['date', column, 'symbol'], ascending=[True, False, True])
    frame['selection_rank'] = frame.groupby('date').cumcount()+1
    population = frame.groupby('date').symbol.transform('size')
    frame['proba_extreme'] = 1-(frame.selection_rank-1)/population
    frame = frame.loc[frame.selection_rank.le(count)].copy()
    frame['selected'] = True
    frame['arm'], frame['count'] = arm, count
    return frame.rename(columns={column: 'raw_model_score'})


def outcome_metrics(frame, side='long'):
    outcome = frame[f'{side}_outcome'].fillna('UNQUALIFIED')
    target = frame[TARGETS[side]]
    qualified = target.notna()
    denominator = int(qualified.sum())
    return {'selected': len(frame), 'evaluated': denominator,
        'unknown': int((~qualified).sum()),
        'tp_rate': float(target[qualified].mean()) if denominator else None,
        'sl_rate': float(outcome[qualified].eq('SL').mean()) if denominator else None,
        'expiry_rate': float(outcome[qualified].eq('EXPIRED').mean()) if denominator else None,
        'outcomes': outcome.value_counts().to_dict()}


def audit_selection(scores, labels):
    selected, annual, directional = [], [], []
    for count in COUNTS:
        for arm in ARMS:
            candidates = freeze_candidates(scores, count, arm)
            observations = candidates.merge(labels, on=['date', 'symbol'], how='left', validate='one_to_one')
            selected.append(observations)
            for year, group in observations.groupby(observations.date.dt.year):
                annual.append(dict(count=count, arm=arm, year=int(year), **outcome_metrics(group)))
        # Independent diagnostic, unchanged .55 threshold. No short-PnL claim.
        ranked = scores.sort_values(['date', 'max_score', 'symbol'], ascending=[True, False, True]).copy()
        ranked['rank'] = ranked.groupby('date').cumcount()+1
        ranked = ranked.loc[ranked['rank'].le(count)].merge(labels, on=['date', 'symbol'], how='left', validate='one_to_one')
        for year, group in ranked.groupby(ranked.date.dt.year):
            long = group[SCORES['long']].gt(group[SCORES['short']])
            different = (group[SCORES['long']]-group[SCORES['short']]).abs().gt(1e-12)
            chosen = group.max_score.ge(.55) & different
            target = group[TARGETS['long']].where(long, group[TARGETS['short']])
            paired = chosen & group[list(TARGETS.values())].notna().all(axis=1)
            directional.append(dict(count=count, year=int(year), candidates=len(group),
                abstentions=int((~chosen).sum()), long_selected=int((chosen & long).sum()),
                short_selected=int((chosen & ~long).sum()), evaluated=int((chosen & target.notna()).sum()),
                chosen_tp_rate=float(target[chosen & target.notna()].mean()) if (chosen & target.notna()).any() else None,
                paired_evaluated=int(paired.sum()),
                paired_chosen_tp_rate=float(target[paired].mean()) if paired.any() else None,
                paired_always_long_tp_rate=float(group.loc[paired, TARGETS['long']].mean()) if paired.any() else None))
    return pd.concat(selected, ignore_index=True), annual, directional


def checkpoint_frame(output, name, builder):
    path, marker = output/name, output/f'{name}.json'
    if marker.exists():
        if digest(path) != read(marker)['sha256']:
            raise ValueError(f'Changed research checkpoint: {name}')
        return pd.read_parquet(path)
    result = builder()
    result.to_parquet(path, index=False)
    atomic_json(marker, {'sha256': digest(path), 'rows': len(result)})
    return result


def validate_sources():
    old, new, profile, external = read(OLD/'protocol.json'), read(NEW/'protocol.json'), read(NEW/'feature_profile.json'), read(EXTERNAL/'protocol.json')
    if old['features'] != profile['feature_columns'] or sorted(new['universe']) != sorted(external['symbols']):
        raise ValueError('Feature/universe contracts differ')
    history = read(Path(old['after'])/'protocol.json')
    if history['generator_options'] != profile['generator_options']:
        raise ValueError('Generator options differ')
    models = {'old': OLD/'corrected/2024-01-08/model.txt',
              'long': NEW/'folds/2024-01-08/long_model.txt',
              'short': NEW/'folds/2024-01-08/short_model.txt'}
    verify_hashes(models['old'].parent, read(models['old'].parent/'done.json'))
    verify_hashes(models['long'].parent, read(models['long'].parent/'done.json')['files'])
    markers = sorted(EXTERNAL.glob('features-*.json'))
    if len(markers) != 72:
        raise ValueError('Incomplete external feature archive')
    for marker in markers:
        verify_hashes(EXTERNAL, read(marker))
    dates = [read(models['old'].parent/'metrics.json')['val_max_available']]
    dates += [h['val_available_max'] for h in read(models['long'].parent/'done.json')['metrics']['heads'].values()]
    if any(pd.Timestamp(d) >= pd.Timestamp('2025-01-01') for d in dates):
        raise ValueError('Training/validation overlaps test')
    return old, new, profile, external, models


def prepare(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    old, new, profile, external, models = validate_sources()
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    if market.earnings_shield.enabled or market.buyback_blackout.enabled:
        raise ValueError('Historical event shield evidence missing')
    cfg = frozen_backtest_config('2025-01-01', args.as_of)
    source_paths = [Path(__file__), Path('scripts/research/us_concentrated_live_portfolio.py'),
        Path('backtesting/oracle_portfolio_ledger.py'), Path('backtesting/oracle_portfolio_session.py'),
        Path('risk_management/portfolio_builder.py'), Path('config.yaml'),
        OLD/'protocol.json', NEW/'protocol.json', NEW/'feature_profile.json', EXTERNAL/'protocol.json', SECTORS,
        *models.values(), *EXTERNAL.glob('features-*.json')]
    protocol = {'experiment': 'terminal_vs_barrier_count_top10_20_50', 'counts': COUNTS,
        'start': '2025-01-01', 'decision_end': '2026-09-03', 'as_of': args.as_of,
        'old_reference': old['reference_batch'], 'old_artifact': str(models['old']),
        'new_reference': new['batch_id'], 'new_fold': '2024-01-08',
        'generator_options': profile['generator_options'], 'features': profile['feature_columns'],
        'universe': sorted(new['universe']), 'common_score_for_sizing': 'descending_rank_percentile',
        'SL': .07, 'TP': .20, 'holding_sessions': 20, 'expiry': 'entry_index+20 at OPEN',
        'entry': 'next session open, native gap gate <=3%', 'trailing': False,
        'portfolio': {'annual_reset_equity': 4000, 'currency': 'USD', 'max_positions': 8,
            'margin_interest_rate_annual': .075, 'risk': asdict(cfg.risk_config),
            'execution': asdict(cfg.exec_config), 'market': asdict(market)},
        'price_basis': 'current adjusted OHLC; dividends implicit, not cash-event certification',
        'fill_rules': 'native conservative limit TP gaps and SL-first daily collisions; no invented intrabar order',
        'source_hashes': {str(p): digest(p) for p in source_paths},
        'limitations': ['already inspected 2025/2026, not virgin holdout',
            'static 1790-symbol universe; current non-PIT sectors explicitly accepted',
            'different training targets AND fit settings: not causal target-only ablation',
            'macro archives are not certified publication vintages',
            'selector features are the immutable Oct7 archive, not the subsequently revised SQL screener scores',
            'same ATR-based native sizing despite fixed executed SL7; not calibrated score sizing',
            'annual decision cohorts include expiry tail in following year, not calendar-only returns',
            'short head .55 diagnostic only: no historical borrow/executable SHORT PnL'],
        'sql_writes': False, 'training': False, 'broker_calls': False, 'serving_modified': False}
    if (output/'protocol.json').exists() and read(output/'protocol.json') != json.loads(json.dumps(protocol, default=str)):
        raise ValueError('Resume protocol differs; use another output directory')
    atomic_json(output/'protocol.json', protocol)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade':
        raise ValueError('US database required')
    from scripts.research.us_oracle_h20_dataset_audit import readonly_begin
    event.listen(engine, 'before_cursor_execute', readonly_statement)
    event.listen(engine, 'begin', readonly_begin)
    symbols = sorted(set(new['universe']) | {'SPY'})
    try:
        chunks = []
        for i, offset in enumerate(range(0, len(symbols), 100)):
            atomic_json(output/'progress.json', dict(status='RUNNING', phase='prices', completed=i, total=18))
            chunk = symbols[offset:offset+100]
            chunks.append(checkpoint_frame(output, f'bars-{i:02d}.parquet',
                lambda chunk=chunk: load_bars(engine, chunk, '2024-01-01', args.as_of)))
        bars = pd.concat(chunks, ignore_index=True)
        if bars.duplicated(['date', 'symbol']).any():
            raise ValueError('Duplicate price keys')
        macro = checkpoint_frame(output, 'macro.parquet', lambda: pd.read_sql(
            text('SELECT * FROM stock_macro_indicators_daily WHERE trade_date BETWEEN :start AND :end'),
            engine, params=dict(start='2024-01-01', end=args.as_of), parse_dates=['trade_date']))
        # Values, not filename equality: sources evolved since the old archive.
        # A frozen training overlap plus a current external canary detects drift.
        def canary():
            old_train = pd.read_parquet(Path(old['after'])/'features-000.parquet')
            new_train = pd.read_parquet(NEW/'chunks/0000/features.parquet')
            sample = new_train.loc[new_train.date.ge(pd.Timestamp('2024-01-01'))]
            columns = [c for c in profile['feature_columns'] if not c.endswith('_xs_rank')]
            pairs = old_train.merge(sample, on=['date', 'symbol'], suffixes=('_old', '_new'), validate='one_to_one')
            if len(pairs) < 6000:
                raise ValueError('Insufficient training feature canary')
            for c in columns:
                if not np.array_equal(pairs[c+'_old'].to_numpy(np.float32), pairs[c+'_new'].to_numpy(np.float32), equal_nan=True):
                    raise ValueError(f'Training feature drift: {c}')
            requested = read(NEW/'chunks/0000/done.json')['symbols']
            current = build_feature_matrix(engine, requested, start_date='2016-01-01', end_date='2026-09-03',
                generator_options={**profile['generator_options'], 'enable_cross_sectional_ranks': False})
            current = current.loc[current.date.between('2025-01-01', '2026-09-03'), ['date', 'symbol', *columns]]
            archived = pd.read_parquet(EXTERNAL/'corrected-features-000.parquet')
            pair = current.merge(archived, on=['date', 'symbol'], suffixes=('_current', '_archive'), validate='one_to_one')
            if len(pair) != len(current) or len(pair) != len(archived):
                raise ValueError('External feature canary keys changed')
            drift = []
            for c in columns:
                same = np.isclose(pair[c+'_current'], pair[c+'_archive'], rtol=1e-6, atol=1e-6, equal_nan=True)
                if not same.all():
                    drift.append(dict(feature=c, revised_rows=int((~same).sum())))
            # Mutable historical screener metadata must not silently replace a
            # frozen input archive. This is a shared archived-input experiment,
            # NOT proof that these metadata were originally available at J.
            atomic_json(output/'feature-version-audit.json', dict(training_overlap_rows=len(pairs),
                external_rows=len(pair), columns=len(columns), current_sql_differences=drift,
                policy='KEEP_IMMUTABLE_SHARED_EXTERNAL_ARCHIVE', selector_publication_pit_certified=False))
            non_selector = [d for d in drift if not d['feature'].startswith('selector_')]
            if non_selector:
                raise ValueError(f'Non-selector feature drift: {non_selector}; qualify before reusing archives')
            return pd.DataFrame([{'training_overlap_rows': len(pairs), 'external_rows': len(pair),
                'features': len(columns), 'revised_selector_columns': len(drift)}])
        checkpoint_frame(output, 'feature-canary.parquet', canary)
    finally:
        engine.dispose()
    registry, barriers = load_security_discontinuities(), OracleBarrierConfig(take_profit_pct=.20, stop_loss_pct=.07, max_sessions=20)
    sessions = nyse_sessions(pd.Timestamp('2024-01-01').date(), (pd.Timestamp(args.as_of)+pd.Timedelta(days=180)).date())
    def labels_and_membership():
        parts = []
        for symbol, group in bars.groupby('symbol'):
            if symbol not in new['universe']:
                continue
            part, _ = symbol_barriers(group, sessions, start='2025-01-01', end=args.as_of, registry=registry, config=barriers)
            parts.append(part.loc[part.date.le(pd.Timestamp('2026-09-03'))])
        return pd.concat(parts, ignore_index=True)
    labels = checkpoint_frame(output, 'labels.parquet', labels_and_membership)
    # Labels include all eligible J keys, even unknown future paths. Target and
    # quality columns never enter feature construction, scoring or ranking.
    membership = labels[['date', 'symbol']]
    def predict():
        import lightgbm as lgb
        atomic_json(output/'progress.json', dict(status='RUNNING', phase='frozen_inference'))
        features = pd.concat([pd.read_parquet(p) for p in sorted(EXTERNAL.glob('corrected-features-*.parquet'))], ignore_index=True)
        features = features.merge(membership, on=['date', 'symbol'], validate='one_to_one')
        for c in features.select_dtypes(include='float64'):
            features[c] = features[c].astype(np.float32)
        features = restore_ranks(features, profile['feature_columns'])
        columns = profile['feature_columns']
        features[columns] = features[columns].replace([np.inf, -np.inf], np.nan).astype(np.float32)
        result = features[['date', 'symbol']].copy()
        for key, path in models.items():
            model = lgb.Booster(model_file=str(path))
            if model.feature_name() != columns:
                raise ValueError('Frozen model column/order mismatch')
            column = 'old_score' if key == 'old' else SCORES[key]
            result[column] = model.predict(features[columns], num_threads=args.threads)
        result['max_score'] = result[list(SCORES.values())].max(axis=1)
        return result
    scores = checkpoint_frame(output, 'scores.parquet', predict)
    selected, annual, directional = audit_selection(scores, labels)
    selected.to_parquet(output/'selected-outcomes.parquet', index=False)
    atomic_json(output/'candidate-report.json', dict(status='COMPLETED', annual=annual, direction=directional,
        feature_canary=read(output/'feature-canary.parquet.json'), ranked_before_future_qualification=True))
    atomic_json(output/'progress.json', dict(status='READY_PORTFOLIOS', score_rows=len(scores),
        sessions=int(scores.date.nunique()), total_runs=12))
    del selected
    gc.collect()
    return bars, scores, macro, market


def run(args):
    output = args.output
    bars, scores, macro, market = prepare(args)
    if args.prepare_only:
        return
    sectors = pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict()
    calendar = nyse_sessions(pd.Timestamp('2024-01-01').date(), pd.Timestamp(args.as_of).date())
    factor = bars.adj_close.where(bars.adj_close.notna(), bars.close)/bars.close
    adjusted = bars.copy()
    adjusted[['open', 'high', 'low', 'close']] = adjusted[['open', 'high', 'low', 'close']].mul(factor, axis=0)
    reports, failures = [], []
    for year in (2025, 2026):
        cutoff = pd.Timestamp(f'{year}-12-31' if year == 2025 else '2026-09-03')
        final_decision = calendar[calendar <= cutoff][-1]
        expiry_index = calendar.get_loc(final_decision)+21
        if expiry_index >= len(calendar):
            raise ValueError('Missing complete 21-session expiry tail')
        end = calendar[expiry_index]
        year_scores = scores.loc[scores.date.dt.year.eq(year)]
        for count in COUNTS:
            for arm in ARMS:
                destination = output/f'{year}-TOP{count}-{arm}'
                key = dict(year=year, count=count, arm=arm)
                report_path = destination/'report.json'
                atomic_json(output/'progress.json', dict(status='RUNNING', phase='portfolio', **key,
                    completed_runs=len(reports), failed_runs=len(failures), total_runs=12))
                if report_path.exists():
                    result = read(report_path)
                else:
                    candidates = freeze_candidates(year_scores, count, arm)
                    # Do not silently reselect for future missing held bars.
                    required = sorted(set(candidates.symbol) | {'SPY'})
                    missing_sector = set(required)-{'SPY'}-set(sectors)
                    if missing_sector:
                        raise ValueError(f'Missing sector metadata: {sorted(missing_sector)}')
                    subset = adjusted.loc[adjusted.symbol.isin(required)]
                    frames = {key: subset.pivot(index='date', columns='symbol', values=column).reindex(calendar)
                        for key, column in [('opens', 'open'), ('close', 'close'), ('high', 'high'), ('low', 'low'), ('volume', 'volume')]}
                    try:
                        result = run_portfolio(frames=frames, scores=candidates, sectors=sectors,
                            macro=ArchivedMacro(macro), market_config=market, policy='selected',
                            variant='CURRENT_NO_EXPIRY', output=destination,
                            start_date=f'{year}-01-01', end_date=str(end.date()), decision_end_date=str(final_decision.date()),
                            quality=bars.loc[bars.symbol.isin(required), ['date', 'symbol', 'is_filled', 'instrument_id']],
                            ledger_factory=FixedBarrierLedger, expiry_open_sessions=20,
                            protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
                    except Exception as exc:
                        failures.append(dict(**key, error_type=type(exc).__name__, error=str(exc)))
                        atomic_json(output/'failures.json', failures)
                        LOG.exception('Frozen portfolio failed %s', key)
                        continue
                trades = pd.read_parquet(destination/'trades.parquet')
                result.update(key)
                result.update(exit_reasons=trades.exit_reason.value_counts().to_dict() if len(trades) else {})
                atomic_json(report_path, result)
                reports.append(result)
                atomic_json(output/'portfolio-results.partial.json', reports)
    protocol = read(output/'protocol.json')
    for name, checksum in protocol['source_hashes'].items():
        if digest(name) != checksum:
            raise ValueError(f'Frozen comparison source changed during execution: {name}')
    status = 'COMPLETED' if not failures else 'PARTIAL_FAILED'
    atomic_json(output/'report.json', dict(status=status, portfolios=reports, failures=failures,
        candidates=read(output/'candidate-report.json'), protocol_sha256=digest(output/'protocol.json'),
        limitations=protocol['limitations']))
    atomic_json(output/'progress.json', dict(status=status, completed_runs=len(reports), failed_runs=len(failures), total_runs=12))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--as-of', default='2026-10-12')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    try:
        run(args)
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__':
    main()
