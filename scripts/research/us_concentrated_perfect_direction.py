"""EX-POST COUNTERFACTUAL. Never import its filtered universe into serving.

Keep only actual positive Oracle H20 labels inside the ORIGINAL daily ten.
No replenishment, direction training, label writes, or live setting changes.
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
from scripts.research.us_concentrated_historical_tapes import (
    atomic_json, verify_hashes, digest, decision_rows, apply_overlay,
)
from scripts.research.us_concentrated_live_portfolio import (
    run_portfolio, ArchivedMacro, apply_verified_volume_overlay,
)
from scripts.research.us_concentrated_exit_variants import VARIANTS
from service.market import parse_market_regimes


def hindsight_membership(candidates):
    """Explicit future-label use confined to this research-only boundary.

    Do NOT select the ten best after filtering the positive labels: daily
    membership must be frozen BEFORE reading the realized direction.
    Unknown/invalid labels are neither negatives nor assumed winners.
    """
    frame = decision_rows(candidates)
    labels = candidates[['date', 'symbol', 'future_return', 'target_quality_valid',
        'local_endpoint_ok', 'oracle_exit_date', 'oracle_decile']].copy()
    labels['date'] = pd.to_datetime(labels.date)
    frame = frame.merge(labels, on=['date', 'symbol'], how='left', validate='one_to_one')
    observable = (frame.future_return.map(lambda v: pd.notna(v) and np.isfinite(float(v)))
        & frame.target_quality_valid.eq(1) & frame.local_endpoint_ok.eq(True)
        & pd.to_datetime(frame.oracle_exit_date).gt(frame.date))
    frame['OBSERVED_TOP10'] = frame.ORACLE_TOP10 & observable
    frame['PERFECT_POSITIVE_TOP10'] = frame.OBSERVED_TOP10 & frame.future_return.gt(0)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('artifacts/research/us_concentrated_replay/prepare-20261006-v1'))
    parser.add_argument('--reference', type=Path, default=Path('artifacts/research/us_concentrated_replay/live-portfolio-oracle_top10-20261007-v2'))
    parser.add_argument('--evidence', type=Path, default=Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1'))
    parser.add_argument('--max-days', type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.source/'report.json').read_text(encoding='utf-8'))
    verify_hashes(args.source, manifest['files_sha256'])
    candidates = pd.read_parquet(args.source/'candidates.parquet')
    membership = hindsight_membership(candidates)
    original = membership.loc[membership.ORACLE_TOP10]
    audit = original[['date', 'symbol', 'future_return', 'oracle_exit_date', 'oracle_decile',
        'OBSERVED_TOP10', 'PERFECT_POSITIVE_TOP10']].copy()
    audit.to_parquet(args.output/'ex_post_membership.parquet', index=False)
    coverage = {'original_top10_candidate_days': len(original),
        'observable_candidate_days': int(original.OBSERVED_TOP10.sum()),
        'positive_candidate_days': int(original.PERFECT_POSITIVE_TOP10.sum()),
        'unknown_candidate_days': int((~original.OBSERVED_TOP10).sum()),
        'nonpositive_observed_candidate_days': int((original.OBSERVED_TOP10 & original.future_return.le(0)).sum()),
        'hindsight_only': True, 'tradable_strategy': False, 'no_replenishment': True,
        'positive_definition': 'Qualified Oracle H20 future_return > 0, close J to close J+20; NOT realized trade PnL and NOT decile D10 only',
        'positive_deciles': original.loc[original.PERFECT_POSITIVE_TOP10, 'oracle_decile'].value_counts().sort_index().to_dict()}
    atomic_json(args.output/'coverage.json', coverage)
    baseline_contract = json.loads((args.reference/'contract.json').read_text(encoding='utf-8'))
    bars = pd.concat([pd.read_parquet(args.source/f'bars-{y}.parquet') for y in (2024, 2025, 2026)])
    bars['date'] = pd.to_datetime(bars.date)
    band = Path('artifacts/research/us_concentrated_replay/contract-validation-20261006-v3/band_volume_overlay.parquet')
    bars = apply_overlay(bars, pd.read_parquet(band))
    for overlay in baseline_contract['volume_overlays']:
        if digest(overlay['path']) != overlay['sha256']:
            raise ValueError('Baseline overlay changed')
        bars = apply_verified_volume_overlay(bars, overlay['path'])
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0), 'date'].unique()).sort_values()
    frames = {key: bars.pivot(index='date', columns='symbol', values=column).reindex(calendar)
        for key, column in [('opens', 'open'), ('close', 'close'), ('high', 'high'), ('low', 'low'), ('volume', 'volume')]}
    # Same pre-period benchmark history as reference, read-only and archived.
    from database.connection import get_sqlalchemy_engine
    from sqlalchemy import event, text
    from scripts.research.us_extreme50_capture import forbid_writes
    engine = get_sqlalchemy_engine()
    event.listen(engine, 'before_cursor_execute', forbid_writes)
    with engine.connect() as conn:
        warmup = pd.read_sql(text("SELECT date, close FROM stock_bars_daily WHERE symbol='SPY' AND date BETWEEN '2024-01-01' AND '2024-09-30'"), conn)
    engine.dispose()
    warmup['date'] = pd.to_datetime(warmup.date)
    warmup.to_parquet(args.output/'spy-warmup.parquet', index=False)
    extra = pd.DatetimeIndex(warmup.date)
    for key in frames:
        frames[key] = frames[key].reindex(extra.union(frames[key].index)).sort_index()
        if key == 'close':
            frames[key].loc[extra, 'SPY'] = warmup.set_index('date')['close']
    sector_path = args.evidence/'current-sector-mapping.parquet'
    if digest(sector_path) != baseline_contract['sector_sha256']:
        raise ValueError('Baseline sectors changed')
    sectors = pd.read_parquet(sector_path).set_index('symbol').sector.to_dict()
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    if json.loads(json.dumps(asdict(market), default=str)) != baseline_contract['market']:
        raise ValueError('Regime configuration changed since baseline')
    macro = ArchivedMacro(pd.read_parquet(args.reference/'macro-evidence.parquet'))
    # Future labels leave this module ONLY via the two explicit boolean masks.
    scores = decision_rows(candidates)
    for policy in ('OBSERVED_TOP10', 'PERFECT_POSITIVE_TOP10'):
        scores[policy] = membership.set_index(['date','symbol'])[policy].reindex(
            pd.MultiIndex.from_frame(scores[['date','symbol']])).to_numpy()
    atomic_json(args.output/'protocol.json', dict(**coverage, reference=str(args.reference),
        source_sha256=manifest['files_sha256'], variants=VARIANTS,
        code_sha256=digest(Path(__file__)), database_writes=False, training=False,
        limitation='Perfect endpoint direction need not produce a winning stop/trailing path; not a formal maximum PnL bound'))
    results = []
    for policy in ('OBSERVED_TOP10', 'PERFECT_POSITIVE_TOP10'):
        for variant in VARIANTS:
            result = run_portfolio(frames=frames, scores=scores, sectors=sectors, macro=macro,
                market_config=market, policy=policy, variant=variant, output=args.output/policy/variant,
                max_days=args.max_days, quality=bars[['date','symbol','is_filled','instrument_id']])
            result.update(hindsight_only=True, tradable_strategy=False)
            atomic_json(args.output/policy/variant/'report.json', result)
            results.append(result)
            atomic_json(args.output/'progress.json', {'status': 'RUNNING', 'completed_runs': len(results),
                'total_runs': 8, 'last_policy': policy, 'last_variant': variant})
    atomic_json(args.output/'report.json', {'status': 'COMPLETED', 'hindsight_only': True,
        'coverage': coverage, 'runs': results})
    atomic_json(args.output/'progress.json', {'status': 'COMPLETED', 'completed_runs': 8, 'total_runs': 8})


if __name__ == '__main__':
    main()
