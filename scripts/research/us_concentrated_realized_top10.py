"""HINDSIGHT ONLY: ten largest absolute realized H20 moves, LONG both signs.

No training, SQL writes, Oracle prediction gate or ATR candidate gate.
Never deploy this deliberately future-informed selection.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from common.config_loader import load_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, apply_overlay
from scripts.research.us_concentrated_live_portfolio import (
    ArchivedMacro, apply_verified_volume_overlay, run_portfolio,
)
from scripts.research.us_concentrated_exit_variants import VARIANTS
from service.market import parse_market_regimes


def realized_membership(labels):
    """Rank full finite-label universe first, then flag invalid endpoints; no refill."""
    data = labels.copy()
    data['date'] = pd.to_datetime(data.date)
    if data.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate realized label')
    data['future_return'] = pd.to_numeric(data.future_return, errors='coerce')
    data = data.loc[np.isfinite(data.future_return)].copy()
    data['absolute_future_return'] = data.future_return.abs()
    data = data.sort_values(['date', 'absolute_future_return', 'symbol'], ascending=[True, False, True])
    data['realized_rank'] = data.groupby('date').cumcount()+1
    data = data.loc[data.realized_rank.le(10)].copy()
    data['REALIZED_TOP10'] = (data.target_quality_valid.eq(1) & data.local_endpoint_ok.eq(True)
        & pd.to_datetime(data.oracle_exit_date).gt(data.date))
    return data


def replay_scores(membership, *, positive_only=False):
    """Synthetic ranking carrier, NOT calibrated probability or model output."""
    scores = membership[['date', 'symbol', 'REALIZED_TOP10']].copy()
    scores['proba_extreme'] = 1-membership.realized_rank.to_numpy()/1000
    scores['fold_start'] = pd.NaT
    if positive_only:
        scores['REALIZED_POSITIVE_TOP10'] = membership.REALIZED_TOP10 & membership.future_return.gt(0)
    return scores


def run(args):
    start, end = pd.Timestamp(args.start_date), pd.Timestamp(args.end_date)
    if pd.isna(start) or pd.isna(end) or start > end:
        raise ValueError('Invalid replay date range')
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output/'progress.json', {'status': 'PREPARING', 'completed_runs': 0, 'total_runs': 4})
    root = Path('artifacts/research/us_extreme50_capture/audit-20261006-v1')
    reference = Path('artifacts/research/us_concentrated_replay/fixed-sl7-oracle_top10-20261007-v1')
    contract = json.loads((reference/'contract.json').read_text())
    source_files = [root/str(year)/'labels_endpoint_checks.parquet' for year in (2025, 2026)]
    labels = pd.concat([pd.read_parquet(p) for p in source_files], ignore_index=True)
    labels['date'] = pd.to_datetime(labels.date)
    labels = labels.loc[labels.date.between(start, end)]
    if labels.empty:
        raise ValueError('No archived labels in requested date range')
    membership = realized_membership(labels)
    membership.to_parquet(output/'realized_membership.parquet', index=False)
    excluded = membership.loc[~membership.REALIZED_TOP10]
    symbols = sorted(set(membership.loc[membership.REALIZED_TOP10, 'symbol']) | {'SPY'})
    if args.market_archive:
        archived_protocol = json.loads((args.market_archive/'protocol.json').read_text())
        if digest(args.market_archive/'bars-raw.parquet') != archived_protocol['raw_bars_sha256']:
            raise ValueError('Archived raw bars changed')
        if archived_protocol['source_hashes'] != {str(p):digest(p) for p in source_files}:
            raise ValueError('Archived label source changed')
        bars = pd.read_parquet(args.market_archive/'bars-raw.parquet')
        if not set(symbols).issubset(set(bars.symbol)):
            raise ValueError('Archive missing selected symbols')
    else:
        # Archive paths including names outside predicted TOP20; SELECT only.
        from sqlalchemy import bindparam, event, text
        from database.connection import get_sqlalchemy_engine
        from scripts.research.us_extreme50_capture import forbid_writes
        engine = get_sqlalchemy_engine()
        event.listen(engine, 'before_cursor_execute', forbid_writes)
        try:
            with engine.connect() as conn:
                if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
                    raise ValueError('US database required')
                query = text('SELECT date,symbol,open,high,low,close,adj_close,volume,is_filled,instrument_id,data_source,data_adjustment FROM stock_bars_daily WHERE date BETWEEN :a AND :b AND symbol IN :symbols').bindparams(bindparam('symbols', expanding=True))
                bars = pd.read_sql(query, conn, params={'a': (start-pd.Timedelta(days=366)).date(), 'b': end.date(), 'symbols': symbols})
        finally:
            engine.dispose()
    bars['date'] = pd.to_datetime(bars.date)
    if bars.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate price keys')
    bars.to_parquet(output/'bars-raw.parquet', index=False)
    band = Path('artifacts/research/us_concentrated_replay/contract-validation-20261006-v3/band_volume_overlay.parquet')
    if 'BAND' in symbols:
        bars = apply_overlay(bars, pd.read_parquet(band))
    for overlay in contract['volume_overlays']:
        if digest(overlay['path']) != overlay['sha256']:
            raise ValueError('Changed overlay evidence')
        if pd.read_parquet(overlay['path']).symbol.isin(symbols).any():
            bars = apply_verified_volume_overlay(bars, overlay['path'])
    bars.to_parquet(output/'bars-effective.parquet', index=False)
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0), 'date'].unique()).sort_values()
    frames = {key: bars.pivot(index='date', columns='symbol', values=col).reindex(calendar)
        for key,col in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    sector_path = Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet')
    if digest(sector_path) != contract['sector_sha256']:
        raise ValueError('Changed sectors')
    sectors = pd.read_parquet(sector_path).set_index('symbol').sector.to_dict()
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    if json.loads(json.dumps(asdict(market), default=str)) != contract['market']:
        raise ValueError('Changed market configuration')
    from scripts.research.us_concentrated_contract_audit import frozen_configs
    risk, _ = frozen_configs()
    if json.loads(json.dumps(asdict(risk), default=str)) != contract['risk']:
        raise ValueError('Changed risk configuration')
    macro_frame = pd.read_parquet(reference/'macro-evidence.parquet')
    macro_frame.to_parquet(output/'macro-evidence.parquet', index=False)
    scores = replay_scores(membership, positive_only=args.positive_only)
    policy = 'REALIZED_POSITIVE_TOP10' if args.positive_only else 'REALIZED_TOP10'
    scores.to_parquet(output/'replay-scores.parquet', index=False)
    coverage = {'universe_symbols_with_labels': int(labels.symbol.nunique()),
        'ranked_dates': int(membership.date.nunique()), 'raw_top10_occurrences': len(membership),
        'qualified_occurrences': int(membership.REALIZED_TOP10.sum()),
        'positive_occurrences': int((membership.REALIZED_TOP10 & membership.future_return.gt(0)).sum()),
        'negative_occurrences': int((membership.REALIZED_TOP10 & membership.future_return.lt(0)).sum()),
        'positive_only': args.positive_only, 'selected_occurrences': int(scores[policy].sum()),
        'last_rankable_signal_date': str(membership.date.max().date()),
        'excluded_without_replacement': excluded[['date','symbol','future_return']].to_dict('records')}
    atomic_json(output/'protocol.json', {'hindsight_only': True, 'tradable_strategy': False,
        'requested_start_date': str(start.date()), 'requested_end_date': str(end.date()),
        'terminal_policy': 'Liquidate remaining positions on last replay session, even before expiry',
        'coverage': coverage, 'future_target': 'Absolute adjusted H20 return close J to close J+20',
        'selection': 'Ten names ranked by realized absolute return, not ten percent, both signs LONG',
        'positive_only': args.positive_only, 'policy': policy, 'no_replenishment': True,
        'direction_filter': 'Qualified realized H20 return > 0 AFTER original top10 rank' if args.positive_only else None,
        'market_archive': str(args.market_archive) if args.market_archive else None,
        'score_carrier': '1-rank/1000: future-informed synthetic priority, NOT model probability',
        'atr_selection_gate': False, 'initial_stop_pct': .07, 'sizing_unchanged': True,
        'opening_budget_policy': 'reject_whole_order_no_resize',
        'risk': asdict(risk), 'market': asdict(market), 'variants': VARIANTS,
        'source_hashes': {str(p):digest(p) for p in source_files},
        'raw_bars_sha256': digest(output/'bars-raw.parquet'),
        'effective_bars_sha256': digest(output/'bars-effective.parquet'),
        'code_sha256': digest(Path(__file__)), 'database_writes': False, 'training': False,
        'limitations': ['Current universe and sectors non-PIT', 'Daily synthetic OHLC fills',
            'Only finite archived labels rankable; not all unknown true movements',
            'Price quality failures excluded AFTER rank without replacement',
            'No candidate after label maturity boundary; holdings monitored to requested end date',
            'Native score_source oracle_amplitude is a carrier label, not a real prediction here']})
    results = []
    for variant in VARIANTS:
        atomic_json(output/'progress.json', {'status': 'RUNNING', 'completed_runs':len(results),
            'total_runs': 4, 'active_variant': variant})
        try:
            result = run_portfolio(frames=frames, scores=scores, sectors=sectors,
                macro=ArchivedMacro(macro_frame), market_config=market, policy=policy,
                variant=variant, output=output/variant, max_days=args.max_days,
                quality=bars[['date','symbol','is_filled','instrument_id']], initial_stop_pct=.07,
                reject_constrained_entries=True, start_date=start, end_date=end)
        except Exception as exc:
            if not args.continue_after_variant_error:
                raise
            result = {'status':'FAILED', 'policy':policy, 'variant':variant, 'error':str(exc)}
            logging.exception('Independent variant failed; other variants will start from scratch')
        result.update(hindsight_only=True, tradable_strategy=False, synthetic_future_rank_score=True)
        atomic_json(output/variant/'report.json', result)
        results.append(result)
    completed = sum(r['status'] == 'COMPLETED' for r in results)
    status = 'COMPLETED' if completed == 4 else 'PARTIAL_FAILED'
    atomic_json(output/'report.json', {'status':status,'hindsight_only':True,
        'coverage':coverage,'runs':results})
    atomic_json(output/'progress.json', {'status':status,'completed_runs':completed,
        'attempted_runs':4,'failed_runs':4-completed,'total_runs':4})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-days', type=int)
    parser.add_argument('--start-date', default='2025-01-01')
    parser.add_argument('--end-date', default='2026-09-30')
    parser.add_argument('--positive-only', action='store_true',
        help='Keep only positive actual returns inside original realized top10; no replenishment')
    parser.add_argument('--market-archive', type=Path,
        help='Reuse verified raw price archive; no SQL read')
    parser.add_argument('--continue-after-variant-error', action='store_true',
        help='Attempt independent variants even if a previous one is blocked; never fabricate PnL')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run(args)
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output/'failure.json', {'status':'FAILED', 'error':str(exc)})
            progress_path = args.output/'progress.json'
            state = json.loads(progress_path.read_text()) if progress_path.exists() else {}
            atomic_json(progress_path, dict(state, status='FAILED', error=str(exc)))
        raise


if __name__ == '__main__':
    main()
