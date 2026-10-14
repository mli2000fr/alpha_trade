"""Read-only causal lineage and annual portfolio audit; writes research report only."""
import argparse
from pathlib import Path

import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_annual_models import MODELS, COUNTS, causal_fold
from scripts.research.us_oracle_barrier_comparison import read, freeze_candidates
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from scripts.research.us_oracle_tp20_sl10_campaign import annual_metrics


def audit(root):
    root = Path(root)
    report, manifest = read(root/'report.json'), read(root/'manifest.json')
    if report['status'] != 'COMPLETED_EXPLORATORY' or report['completed'] != 9 or report['failed']:
        raise ValueError('Nine completed cases required')
    if report['manifest_sha256'] != digest(root/'manifest.json'):
        raise ValueError('Changed manifest')
    verify_hashes(Path('.'), manifest['source_hashes'])
    verify_hashes(Path('.'), manifest['code_hashes'])
    expected = {(y, n) for y in MODELS for n in COUNTS}
    if len(report['portfolios']) != 9 or {(r['year'], r['count']) for r in report['portfolios']} != expected:
        raise ValueError('Duplicate or missing annual case')
    common_hashes = None
    scores_by_year, contexts, paths = {}, {}, [root/'manifest.json', root/'report.json']
    for year, batch in MODELS.items():
        armroot = root/str(year)
        ready = read(armroot/'ready.json')['files']
        verify_hashes(armroot, ready)
        current = {n: ready[n] for n in ('prices.parquet', 'macro.parquet', 'lifecycle.json')}
        if common_hashes is not None and current != common_hashes:
            raise ValueError('Execution inputs differ')
        common_hashes = current
        context = read(armroot/'protocol.json')
        contexts[year] = context
        if context['batch_id'] != batch:
            raise ValueError('Wrong model attribution')
        model = Path(context['model'])
        folds = {p.name: read(p/'done.json') for p in (model/'folds').iterdir() if (p/'done.json').exists()}
        scores = pd.read_parquet(armroot/'scores.parquet')
        if scores.duplicated(['date', 'symbol']).any() or not scores.date.dt.year.eq(year).all():
            raise ValueError('Invalid annual score membership')
        schedule = {str(day.date()): causal_fold(day, folds) for day in sorted(scores.date.unique())}
        if schedule != context['fold_schedule'] or not scores.fold_start.eq(scores.date.dt.strftime('%Y-%m-%d').map(schedule)).all():
            raise ValueError('Causal lineage differs from saved scores')
        scores_by_year[year] = scores
        paths.extend(armroot/n for n in ('ready.json', 'protocol.json', 'scores.parquet'))
    calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(), pd.Timestamp('2026-10-09').date())
    checks, comparisons = [], []
    for result in report['portfolios']:
        year, count = result['year'], result['count']
        case = root/str(year)/'BASELINE'/f'{year}-TOP{count}'
        verify_hashes(case, result['files'])
        if read(case/'case-report.json') != result or result['baseline_model'] != MODELS[year]:
            raise ValueError('Changed or misattributed case report')
        trades, daily = [pd.read_parquet(case/n) for n in ('trades.parquet', 'daily.parquet')]
        if not trades.side.eq('buy').all() or not trades['rank'].between(1, count).all():
            raise ValueError('Unexpected side or rank')
        if daily.positions.iloc[-1] or abs(result['cash_reconciliation_error']) > 1e-6:
            raise ValueError('Incomplete portfolio/cash')
        if not result['account_wealth_complete'] or result['unvalued_fractional_claims']:
            raise ValueError('Unvalued corporate action')
        cutoff = pd.Timestamp('2026-09-03' if year == 2026 else f'{year}-12-31')
        if not pd.to_datetime(trades.signal_date).between(pd.Timestamp(f'{year}-01-01'), cutoff).all():
            raise ValueError('Signal outside decision cohort')
        # Check executed entries against pre-outcome frozen LONG ranks, including
        # original symbol for a corporate-action successor.
        candidates = freeze_candidates(scores_by_year[year], count, 'NEW_BARRIER_LONG')
        entries = trades[['signal_date', 'symbol', 'rank']].copy()
        if 'entry_symbol' in trades:
            entries['symbol'] = trades.entry_symbol.where(trades.entry_symbol.notna(), trades.symbol)
        entries['date'] = pd.to_datetime(entries.signal_date)
        frozen = candidates[['date', 'symbol', 'selection_rank']].rename(columns={'selection_rank': 'rank'})
        joined = entries.merge(frozen, on=['date', 'symbol'],
            how='left', suffixes=('_executed', '_frozen'), validate='many_to_one')
        # The ledger's trade rank is the builder's accepted-entry rank, not
        # necessarily the original model rank (held/rejected candidates remain
        # in the frozen pool). Audit membership, never equate the two ranks.
        if joined.rank_frozen.isna().any() or not joined.rank_frozen.between(1, count).all():
            raise ValueError('Trade outside observable frozen TOP pool')
        if annual_metrics(result, trades, daily, year) != result['annual_metrics']:
            raise ValueError('Metrics do not reproduce tapes')
        checks.append(dict(year=year, count=count, **verify_trade_contract(trades, .2, .1, calendar),
            cash_error=result['cash_reconciliation_error'], final_positions=0))
        paths.extend(case/n for n in ('case-report.json', 'trades.parquet', 'daily.parquet'))
        old = Path(manifest['source'])/'BASELINE'/f'{year}-TOP{count}'/'case-report.json'
        prior = read(old)['annual_metrics']
        comparisons.append(dict(year=year, count=count, prior_model='model-factory-20261012183840-6d6569',
            current_model=MODELS[year], old_return_pct=prior['return_pct'],
            new_return_pct=result['annual_metrics']['return_pct'],
            delta_return_points=result['annual_metrics']['return_pct']-prior['return_pct']))
        paths.append(old)
    result = dict(status='NINE_CAUSAL_ANNUAL_CASES_VERIFIED', checks=checks, comparisons=comparisons,
        source_hashes={str(p): digest(p) for p in paths}, code_sha256=digest(__file__),
        causal_fit_and_selection_before_each_decision=True, common_prices_macro_lifecycle=True,
        no_sql_writes=True, no_training=True, no_broker_orders=True, exploratory_not_live_certification=True,
        comparison_reserve='Different start dates/folds and refreshed training data; improvement is not attributable solely to model age')
    atomic_json(root/'completion-audit.json', result)
    print(result['status'], flush=True)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    audit(**vars(p.parse_args()))
