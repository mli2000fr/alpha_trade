"""TOP20 PERCENT versus full tradable universe; SELECT-only SQL, no fit/API/orders.

Read existing annual Oracle predictions and verify their causal lineage. Rank
membership is frozen before merging future path outcomes. Reuse the completed
full-universe TP10 experiments without changing their population or memberships.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_top10_symbol_reliability as gate
from scripts.research import us_tradable_symbol_reliability as base
from scripts.research import us_tradable_tp10_variants as variants
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

ARCHIVE = Path('artifacts/research/oracle_path_confirmation/20261013-v1')
CAMPAIGN = Path('artifacts/research/us_news_gpt_top20_history/20261015-v1')
FULL = Path('artifacts/research/us_tradable_tp10_variants/20261019-v2')
LOG = logging.getLogger(__name__)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def top_fraction(scores, fraction=.20):
    """Stable rank on all observable scores, never on future-qualified paths."""
    if not 0 < fraction <= 1:
        raise ValueError('Fraction must be in (0, 1]')
    if scores.empty or scores.duplicated(['date', 'symbol']).any():
        raise ValueError('Empty or duplicate score population')
    if not np.isfinite(scores.score).all() or not scores.score.between(0, 1).all():
        raise ValueError('Invalid Oracle probabilities')
    ordered = scores.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True]).copy()
    ordered['oracle_rank'] = ordered.groupby('date').cumcount() + 1
    ordered['scored_count'] = ordered.groupby('date').symbol.transform('size')
    ordered['selected_count'] = np.ceil(ordered.scored_count * fraction).astype(int)
    return ordered[ordered.oracle_rank.le(ordered.selected_count)].copy()


def restrict_paths(frame, selection):
    """Inner join; a missing path never promotes the next Oracle candidate."""
    keys = selection[['date', 'symbol', 'oracle_rank', 'scored_count', 'selected_count']]
    if keys.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate frozen membership')
    result = frame.merge(keys, on=['date', 'symbol'], how='inner', validate='many_to_one')
    if result.duplicated(['date', 'symbol', 'side']).any():
        raise ValueError('Duplicate path key')
    return result


def prepare(root):
    if (root/'protocol.json').exists():
        p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    root.mkdir(parents=True, exist_ok=False)
    from modelFactory.oracle_path.predict import load_contract, select_fold
    previous = read(FULL/'protocol.json')
    verify_hashes(Path('.'), previous['source_hashes'])
    sources = {str(FULL/'protocol.json'): digest(FULL/'protocol.json'),
               str(FULL/'paths-manifest.json'): digest(FULL/'paths-manifest.json'),
               str(CAMPAIGN/'protocol.json'): digest(CAMPAIGN/'protocol.json'),
               str(ARCHIVE/'scores.parquet'): digest(ARCHIVE/'scores.parquet')}
    for name in (Path(__file__), Path(base.__file__), Path(gate.__file__), Path(variants.__file__), base.UNIVERSE):
        sources[str(name)] = digest(name)
    annual = read(CAMPAIGN/'protocol.json')['annual_models']; contracts = {}
    profile = None
    for year, declaration in annual.items():
        folder, protocol, current, folds = load_contract('artifacts/models', declaration['batch_id'])
        fold = folds[declaration['fold']]
        if fold['backend'] != 'catboost' or fold['model_sha256'] != declaration['model_sha256']:
            raise ValueError('Unexpected annual model')
        if digest(folder/'feature_profile.json') != declaration['profile_sha256']:
            raise ValueError('Unexpected feature profile')
        available = max(pd.Timestamp(fold['metrics'][k]) for k in ('train_available_max', 'val_available_max'))
        if available >= pd.Timestamp(f'{year}-01-01') or str(available.date()) != declaration['available_date']:
            raise ValueError('Annual model not available strictly before test year')
        if select_fold(f'{year}-01-02', folds) != declaration['fold']:
            raise ValueError('Unexpected first annual causal fold')
        if set(protocol['universe']) != set(previous['symbols']):
            raise ValueError('Different model/tradable universe')
        if profile is not None and profile != current:
            raise ValueError('Annual feature profiles differ')
        profile = current
        contracts[year] = {k: v for k, v in declaration.items() if k != 'universe'}
        contracts[year]['model_file'] = fold['model_file']
        for path in (folder/'protocol.json', folder/'feature_profile.json', folder/'report.json',
                     Path(fold['model_file']), Path(fold['model_file']).parent/'done.json'):
            sources[str(path)] = digest(path)
    for folder in sorted((CAMPAIGN/'months').iterdir()):
        if (folder/'candidates.parquet').exists():
            prepared = read(folder/'prepared.json')
            verify_hashes(folder, {'candidates.parquet': prepared['files']['candidates.parquet']})
            sources[str(folder/'candidates.parquet')] = prepared['files']['candidates.parquet']
            sources[str(folder/'prepared.json')] = digest(folder/'prepared.json')
    for name in variants.PROFILES:
        report = read(FULL/name/'report.json'); verify_hashes(FULL/name, report['files'])
        for path in (FULL/name/'report.json', FULL/name/'evaluations.parquet', FULL/name/'primary.json'):
            sources[str(path)] = digest(path)
    from modelFactory.oracle.build_labels import nyse_sessions
    sessions = nyse_sessions('2024-01-01', '2026-09-30')
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
        annual_models=contracts, features_profile=profile, symbols=previous['symbols'], universe_count=len(previous['symbols']),
        sessions=[str(d.date()) for d in sessions], fraction=.20,
        ranking='ceil(0.20 * all valid scored tradable symbols at J); score DESC, symbol ASC; before future quality',
        missing_paths='Exclude unqualified outcome, never replace with next rank; report coverage',
        history_year=2024, evaluation_years=[2025, 2026], last_mature_decision='2026-09-01',
        primary_top20pct_gate='Same frozen rule, history restricted to Oracle TOP20%; monthly maturity strictly prior to rebalance',
        secondary_gate='Full-universe memberships reused unchanged, intersected with TOP20%',
        full_universe='Reuse verified completed TP10 v2 results, no Oracle filter',
        profiles=variants.PROFILES, holding_sessions=20, entry='J+1 open; entry session counts as 1',
        timeout='close session 20', trailing=False, fees_per_leg=gate.COST_PER_LEG, borrow_annual=gate.BORROW_ANNUAL,
        reserve='Current survivor universe; previously explored years; suspect adjusted prices/OST; hypothetical costs; not portfolio PnL',
        score_source='Existing SQL predictions plus causal lineage, not inference from a different feature snapshot',
        rejected_attempt='20261019-v1 cached-feature inference failed archived ranking parity; no outcome report used',
        sql='SELECT_ONLY_READ_ONLY_TRANSACTION', sql_writes=False, api_calls=0, training=False,
        model_changed=False, production_changed=False, orders=False)
    atomic_json(root/'protocol.json', p); return p


def score(root):
    p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
    from database.connection import get_sqlalchemy_engine
    from sqlalchemy import event, text
    from scripts.research.us_oracle_barrier_comparison import readonly_statement
    from scripts.research.us_oracle_h20_dataset_audit import readonly_begin
    from scripts.research.us_news_gpt_top20_history import validate_scores
    engine = get_sqlalchemy_engine()
    if engine.url.database != 'alpha_trade': raise ValueError('US database required')
    event.listen(engine, 'before_cursor_execute', readonly_statement)
    event.listen(engine, 'begin', readonly_begin)
    query = text('''SELECT p.prediction_date date,p.symbol,p.proba_extreme score,p.fold_start,
        p.future_return,p.oracle_extreme10,l.model_sha256,l.feature_profile_sha256,
        l.model_available_date,l.target_name,l.target_horizon,l.fold_start lineage_fold
        FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l
        ON p.prediction_date=l.prediction_date AND p.symbol=l.symbol AND p.batch_id=l.batch_id
        WHERE p.batch_id=:batch AND p.prediction_date BETWEEN :start AND :end''')
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            return export_scores(conn, query, root, p, validate_scores)
    finally:
        engine.dispose()


def export_scores(conn, query, root, p, validate_scores):
    for year, model_contract in p['annual_models'].items():
        marker = root/f'{year}-scores-ready.json'
        if marker.exists():
            verify_hashes(root, read(marker)['files']); continue
        LOG.info('Reading existing annual predictions %s, SELECT-only', year)
        atomic_json(root/'progress.json', dict(status='RUNNING', phase='READ_ONLY_SQL_SNAPSHOT', year=year))
        scores = pd.read_sql(query, conn, params=dict(batch=model_contract['batch_id'],
            start=f'{year}-01-01', end=min(f'{year}-12-31', '2026-09-30')))
        if scores.empty: raise ValueError('No stored predictions')
        scores['date'] = pd.to_datetime(scores.date)
        validate_scores(scores, {**model_contract, 'universe': p['symbols']})
        selected = top_fraction(scores, p['fraction'])
        old = pd.concat([pd.read_parquet(folder/'candidates.parquet', columns=['date', 'symbol', 'score', 'oracle_rank'])
                        for folder in sorted((CAMPAIGN/'months').glob(f'{year}-*'))], ignore_index=True)
        check = selected[selected.oracle_rank.le(20)][old.columns].sort_values(['date', 'oracle_rank']).reset_index(drop=True)
        old = old.sort_values(['date', 'oracle_rank']).reset_index(drop=True)
        pd.testing.assert_frame_equal(check[['date', 'symbol', 'oracle_rank']], old[['date', 'symbol', 'oracle_rank']])
        max_error = float(np.abs(check.score - old.score).max())
        if max_error > 1e-7: raise ValueError('Annual scores fail archived original TOP20-stocks canary')
        expected = {pd.Timestamp(d) for d in p['sessions'] if d.startswith(year)}
        if set(scores.date) != expected: raise ValueError('Incomplete scored session coverage')
        scores.to_parquet(root/f'{year}-all-scores.parquet', index=False)
        selected.to_parquet(root/f'{year}-top20pct.parquet', index=False)
        files = {n: digest(root/n) for n in (f'{year}-all-scores.parquet', f'{year}-top20pct.parquet')}
        atomic_json(marker, dict(rows=len(scores), selected=len(selected), sessions=len(expected), symbols=int(scores.symbol.nunique()),
            archived_original_top20_stocks_exact=True, score_max_error=max_error, files=files))
        LOG.info('%s scored: %d rows, %d TOP20%% rows; archived ranks exact', year, len(scores), len(selected))
    verify_hashes(Path('.'), p['sources'])


def run_case(root, name, selection, days):
    folder = root/name; folder.mkdir(exist_ok=True)
    if (folder/'report.json').exists():
        report = read(folder/'report.json'); verify_hashes(folder, report['files']); return report
    manifest = read(FULL/'paths-manifest.json')[name]; verify_hashes(FULL, manifest)
    # Archived paths, quality and TP/SL labels unchanged. Ranking already frozen.
    pieces = [restrict_paths(pd.read_parquet(FULL/n), selection) for n in manifest]
    f = gate.attach_costs(pd.concat(pieces, ignore_index=True)); del pieces
    f['symbol'] = f.symbol.astype('category'); f['side'] = f.side.astype('category')
    tests = f[f.date.dt.year.isin([2025, 2026])].copy()
    schedule = days[(days >= '2025-01-01') & (days <= '2026-09-01')].to_series().groupby(lambda d: d.to_period('M')).min()
    all_states, evaluations, audit = [], [], []
    for i, cutoff in enumerate(schedule, 1):
        membership, h = base.states_fast(f, cutoff, days)
        if not membership.max_known_maturity.lt(cutoff).all(): raise AssertionError('Future-label leakage')
        current = gate.apply_states(tests[tests.date.dt.to_period('M').eq(cutoff.to_period('M'))], membership)
        current['rebalance_date'] = cutoff; evaluations.append(current); all_states.append(membership)
        audit.append(dict(date=cutoff, history_rows=len(h), max_known_maturity=h.last_path_date.max(),
            passed_states=int(membership.passed.sum()), passed_symbols=int(membership.loc[membership.passed, 'symbol'].nunique())))
        LOG.info('%s TOP20%% %s: %d passed symbols', name, cutoff.date(), audit[-1]['passed_symbols'])
        atomic_json(root/'progress.json', dict(status='RUNNING', phase='TOP20PCT_MONTHLY_GATE', profile=name, completed=i, total=len(schedule)))
    evaluated = pd.concat(evaluations, ignore_index=True)
    pd.concat(all_states, ignore_index=True).to_parquet(folder/'monthly-memberships.parquet', index=False)
    evaluated.to_parquet(folder/'evaluations.parquet', index=False)
    primary = base.summary_bundle(evaluated, days)
    # Same previous full-history gate, different test scope: isolates scope effect.
    broad = pd.read_parquet(FULL/name/'evaluations.parquet')
    broad_top = restrict_paths(broad, selection)
    pd.testing.assert_frame_equal(evaluated[['date', 'symbol', 'side']].sort_values(['date', 'symbol', 'side']).reset_index(drop=True),
        broad_top[['date', 'symbol', 'side']].sort_values(['date', 'symbol', 'side']).reset_index(drop=True),
        check_dtype=False, check_categorical=False)
    secondary = base.summary_bundle(broad_top, days)
    full = read(FULL/name/'report.json')
    outputs = dict(top20pct=primary, top20pct_full_history_gate_control=secondary, full_universe=full['primary'])
    names = ['monthly-memberships.parquet', 'evaluations.parquet']
    for label, data in outputs.items():
        atomic_json(folder/f'{label}.json', data); names.append(f'{label}.json')
    coverage = selection.groupby(selection.date.dt.year).size().rename('ranked_pairs').to_frame()
    coverage['qualified_pairs'] = f[f.side.eq('LONG')].groupby(f.date.dt.year, observed=True).size()
    coverage['no_qualified_path'] = coverage.ranked_pairs - coverage.qualified_pairs
    coverage.to_csv(folder/'path-coverage.csv'); names.append('path-coverage.csv')
    report = dict(status='COMPLETED_EXPLORATORY_PRICE_RESERVE_NO_PROMOTION', profile=name,
        protocol_sha256=digest(root/'protocol.json'), evaluated_rows=len(evaluated), history_rows=int(f.date.dt.year.eq(2024).sum()),
        monthly_audit=audit, results=outputs, risk=variants.risk_summary(evaluated), coverage=coverage.reset_index().to_dict('records'),
        files={n: digest(folder/n) for n in names})
    atomic_json(folder/'report.json', report); return report


def run(root):
    p = read(root/'protocol.json'); verify_hashes(Path('.'), p['sources'])
    if (root/'report.json').exists(): raise ValueError('Completed immutable report exists')
    for year in p['annual_models']: verify_hashes(root, read(root/f'{year}-scores-ready.json')['files'])
    selection = pd.concat([pd.read_parquet(root/f'{year}-top20pct.parquet') for year in p['annual_models']], ignore_index=True)
    selection.groupby('date')[['scored_count', 'selected_count']].first().to_csv(root/'daily-ranking-coverage.csv')
    from modelFactory.oracle.build_labels import nyse_sessions
    days = nyse_sessions('2023-01-01', '2026-10-09')
    cases = {name: run_case(root, name, selection, days) for name in p['profiles']}
    rows = [dict(profile=name, scope=scope, **row) for name, case in cases.items()
            for scope, result in case['results'].items() for row in result['summary']]
    pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)} for r in rows]).to_csv(root/'comparison.csv', index=False)
    verify_hashes(Path('.'), p['sources'])
    atomic_json(root/'report.json', dict(status='COMPLETED_EXPLORATORY_PRICE_RESERVE_NO_PROMOTION',
        protocol_sha256=digest(root/'protocol.json'), comparison=rows,
        files={n: digest(root/n) for n in ['comparison.csv', 'daily-ranking-coverage.csv']},
        cases={n: dict(path=f'{n}/report.json', sha256=digest(root/n/'report.json')) for n in cases}))
    atomic_json(root/'progress.json', dict(status='COMPLETED_EXPLORATORY_PRICE_RESERVE_NO_PROMOTION', phase='DONE'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['prepare', 'score', 'run'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    {'prepare': prepare, 'score': score, 'run': run}[args.phase](args.output)


if __name__ == '__main__': main()
