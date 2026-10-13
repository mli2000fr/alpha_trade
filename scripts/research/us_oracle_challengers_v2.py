"""Versioned technical remediation: align benchmark indices in offline tail.

No change to fit, thresholds, profiles, test dates, Oracle weights or live.
The original v1 implementation and failed outputs remain available unchanged.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from modelFactory.features import compute_features
from scripts.research import us_oracle_challengers as shared


def causal_features(bars, benchmark):
    """Both dates and adjusted benchmark values must have aligned row indices."""
    bars = bars.sort_values('date').reset_index(drop=True).copy()
    benchmark = benchmark.sort_values('date').reset_index(drop=True).copy()
    bars['adj_close'], benchmark['adj_close'] = bars.close, benchmark.close
    # The thirteen frozen features do not use VWAP. The canonical builder
    # already treats its absent optional close-to-VWAP feature as zero.
    bars['vwap'] = np.nan
    return compute_features(bars, benchmark_df=benchmark, feature_set='expert')


def daily_feature_tail(root):
    target = root/'daily-tail'; target.mkdir(exist_ok=True)
    if (target/'ready.json').exists():
        shared.verify_hashes(target, shared.read(target/'ready.json')['files'])
        saved = shared.read(target/'ready.json')
        if not saved.get('nonempty_tail_verified'): raise ValueError('Unqualified empty daily tail')
        return pd.read_parquet(target/'features.parquet')
    prices = pd.read_parquet(root/'prices.parquet')
    candidates = shared.freeze_candidates(pd.read_parquet(root/'scores.parquet'), 50, 'NEW_BARRIER_LONG')
    required = set(candidates.loc[candidates.date.dt.year.eq(2026)].symbol)
    events = shared.load_events(root)
    for e in events:
        if e['source'] in required: required.add(e['target'])
    benchmark = prices.loc[prices.symbol.eq('SPY')].copy()
    reference = pd.read_parquet(root/'features.parquet', columns=['date','symbol',*shared.FEATURES])
    reference = reference.loc[reference.date.between('2026-08-03','2026-09-03')].set_index(['date','symbol'])
    parts, canaries = [], []
    for i, symbol in enumerate(sorted(required)):
        bars = prices.loc[prices.symbol.eq(symbol)].copy()
        for e in events:
            if e['target'] == symbol and e.get('event_type') == 'NAME_CHANGE':
                prefix = prices.loc[prices.symbol.eq(e['source']) & prices.date.lt(e['day'])].copy()
                ratio = float(e['ratio'])
                prefix[['open','high','low','close']] /= ratio
                prefix['volume'] *= ratio; prefix['symbol'] = symbol
                bars = pd.concat([prefix, bars.loc[bars.date.ge(e['day'])]], ignore_index=True)
        f = causal_features(bars, benchmark)
        tail = f.loc[f.date.gt('2026-09-03'), ['date','symbol',*shared.FEATURES]]
        if len(bars.loc[bars.date.gt('2026-09-03')]) and tail.empty:
            raise ValueError(f'Empty feature tail despite qualified bars: {symbol}')
        parts.append(tail)
        # Fixed public canaries, independent of future PnL or fitted decisions.
        if symbol in ('AAPL','NVDA','BAND','GPRE','ATEX','TOELY'):
            observed = f.set_index(['date','symbol'])[shared.FEATURES]
            keys = reference.index.intersection(observed.index)
            keys = keys[keys.get_level_values('symbol') == symbol]
            if len(keys):
                actual, expected = observed.loc[keys], reference.loc[keys]
                discrepancies = [c for c in shared.FEATURES if not np.isclose(
                    actual[c], expected[c], rtol=1e-5, atol=1e-6, equal_nan=True).all()]
                if discrepancies: raise ValueError(f'Feature tail/pre-tail parity mismatch {symbol}: {discrepancies}')
                canaries.append(dict(symbol=symbol,rows=len(keys),features=len(shared.FEATURES),verified=True))
        shared.atomic_json(target/'progress.json', dict(status='RUNNING',completed=i+1,total=len(required)))
    result = pd.concat(parts,ignore_index=True)
    if result.empty or result.duplicated(['date','symbol']).any(): raise ValueError('Empty or duplicate daily tail')
    if not canaries: raise ValueError('No independent pre-tail feature canary available')
    result.to_parquet(target/'features.parquet',index=False)
    shared.atomic_json(target/'ready.json',dict(files={'features.parquet':shared.digest(target/'features.parquet')},
        rows=len(result),symbols=int(result.symbol.nunique()),nonempty_tail_verified=True,
        pre_tail_canaries=canaries,benchmark_indices_aligned=True,
        source='qualified local adjusted price archive; causal predecessor/successor lineage; no SQL',
        price_basis_reserve='current vendor adjusted prices, not independent historical publication vintages'))
    shared.atomic_json(target/'progress.json',dict(status='COMPLETED',rows=len(result)))
    return result


def source_manifest():
    return {**shared.code_hashes(), str(Path(shared.__file__).relative_to(Path.cwd())):shared.digest(shared.__file__),
            str(Path(__file__).relative_to(Path.cwd())):shared.digest(__file__)}


def run(output,baseline,model,workers=3,fit_cache=None):
    # Only research-function bindings are versioned here. No core file/runtime
    # is altered, and the exact replacement implementation is hash-frozen.
    shared.source_manifest = source_manifest
    shared.daily_feature_tail = daily_feature_tail
    shared.initialize(output,baseline,model)
    shared.atomic_json(output/'progress.json',dict(status='RUNNING',phase='OOF_training_dataset'))
    if fit_cache is not None and not (output/'fit-data').exists():
        saved=shared.read(fit_cache/'training-source-manifest.json')
        shared.verify_hashes(Path('.'),saved['files'])
        shared.verify_hashes(fit_cache,saved['dataset_hashes'])
        shutil.copytree(fit_cache,output/'fit-data')
        shared.atomic_json(output/'training-cache-lineage.json',dict(source=str(fit_cache),
            manifest_sha256=shared.digest(fit_cache/'training-source-manifest.json'),
            change='benchmark row-index alignment in external tail only; training untouched'))
    shared.run(output,baseline,model,workers)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,default=shared.BASELINE)
    parser.add_argument('--model',type=Path,default=shared.MODEL)
    parser.add_argument('--workers',type=int,choices=(1,2,3),default=3)
    parser.add_argument('--fit-cache',type=Path)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:run(**vars(args))
    except Exception as exc:
        args.output.mkdir(parents=True,exist_ok=True)
        shared.atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
