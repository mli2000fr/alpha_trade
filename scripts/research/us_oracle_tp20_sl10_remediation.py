"""Version price/feature repairs of the frozen baseline; no fitting or SQL writes."""
import argparse
import logging
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from modelFactory.oracle_barrier import SCORES
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import freeze_candidates, read
from scripts.research.us_oracle_barrier_grid_prepare import compute_avb, assert_feature_canary
from scripts.research.us_oracle_barrier_volume_prepare import volume_proofs, apply_volume_proofs
from scripts.research.us_oracle_h20_dataset_audit import restore_ranks
from scripts.research.us_oracle_merger_replay import RATIO
from scripts.research.us_oracle_tp20_sl10_campaign import MODEL, model_contract


def replace_base_features(frame, replacement, columns, *, effective_date=None):
    """Preserve scored membership/order and reject partial/duplicated repairs."""
    result = frame.copy()
    if replacement.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate repair keys')
    symbols = replacement.symbol.unique()
    target = result.loc[result.symbol.isin(symbols), ['date', 'symbol']]
    joined = target.merge(replacement, on=['date', 'symbol'], how='left',
                          validate='one_to_one', indicator=True)
    if len(joined) != len(replacement) or not joined['_merge'].eq('both').all():
        raise ValueError('Repair changes frozen eligibility')
    indexed = replacement.set_index(['date', 'symbol'])
    mask = result.symbol.isin(symbols)
    if effective_date is not None:
        mask &= result.date.ge(pd.Timestamp(effective_date))
    keys = pd.MultiIndex.from_frame(result.loc[mask, ['date', 'symbol']])
    for c in columns:
        result.loc[mask, c] = indexed.loc[keys, c].to_numpy().astype(result[c].dtype)
    return result


def prepare(source, output, repairs):
    source, output, repairs = map(Path, (source, output, repairs))
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError('Use a new empty version; preserve the failed baseline')
    source_ready, proof = read(source/'ready.json'), read(repairs/'prepared.json')
    verify_hashes(source, source_ready['files'])
    verify_hashes(repairs, proof['files'])
    _, profile, fold = model_contract(MODEL)
    old_profile = read(repairs/'input-protocol.json')
    if profile['generator_options'] != old_profile['options'] or profile['feature_columns'] != old_profile['columns']:
        raise ValueError('Qualified correction uses a different feature contract')
    inputs = {str(source/n): digest(source/n) for n in [*source_ready['files'], 'protocol.json', 'ready.json']}
    inputs.update({str(repairs/n): digest(repairs/n) for n in [*proof['files'], 'prepared.json', 'input-protocol.json']})
    for name in ('long_model.txt', 'short_model.txt', 'done.json'):
        inputs[str(fold/name)] = digest(fold/name)
    output.mkdir(parents=True)
    atomic_json(output/'remediation-inputs.json', dict(files=inputs, code_sha256=digest(__file__),
        scope='Qualified AVB share units and BAND/GPRE/ATEX volume; recompute affected features/ranks',
        models_unchanged=True, sql_writes=False, universe_unchanged=True))
    atomic_json(output/'progress.json', dict(status='RUNNING', phase='feature_remediation'))
    # Rebuild ranks from the original full-precision base cache. The serving
    # float32 matrix alone cannot reproduce ties in float64 daily ranks.
    chunks = sorted(source.glob('features-[0-9][0-9][0-9].parquet'))
    if len(chunks) != 72:
        raise ValueError('Incomplete full-precision feature cache')
    for path in chunks:
        verify_hashes(source, read(source/(path.name+'.json'))['files'])
        inputs[str(path)] = digest(path)
    features = pd.concat([pd.read_parquet(p) for p in chunks],ignore_index=True).sort_values(['date','symbol']).reset_index(drop=True)
    expected_keys = pd.read_parquet(source/'scores.parquet',columns=['date','symbol'])
    if not features[['date','symbol']].reset_index(drop=True).equals(expected_keys.reset_index(drop=True)):
        raise ValueError('Full-precision feature cache changes scored membership/order')
    columns = profile['feature_columns']
    base = [c for c in columns if not c.endswith('_xs_rank')]
    canaries = []
    warm = pd.read_parquet(repairs/'warmup-avb-spy.parquet')
    avb = warm.loc[warm.symbol.eq('AVB')].copy()
    spy = warm.loc[warm.symbol.eq('SPY')].copy()
    archived = features.loc[features.symbol.eq('AVB')]
    raw = compute_avb(avb, spy, profile['generator_options'], archived, base)
    before = proof['qualification']['avb_restored_first_date']
    raw_canary = assert_feature_canary(raw, archived, base, before=before)
    mask = avb.date.between(before, proof['qualification']['avb_restored_last_date'])
    if int(mask.sum()) != proof['qualification']['avb_successor_adjusted_rows']:
        raise ValueError('AVB correction coverage changed')
    for c in ('open', 'high', 'low', 'close', 'adj_close', 'vwap'):
        avb.loc[mask, c] *= RATIO
    avb['volume'] = avb.volume.astype(float)
    avb.loc[mask, 'volume'] /= RATIO
    rebuilt = compute_avb(avb, spy, profile['generator_options'], archived, base)
    corrected = assert_feature_canary(rebuilt, archived, base, before=before)
    # Match already independently qualified regenerated features on their keys.
    certified = pd.read_parquet(repairs/'repaired-avb-features.parquet')
    pair = certified.merge(rebuilt, on=['date', 'symbol'], suffixes=('_proof', '_new'), validate='one_to_one')
    if len(pair) != len(certified):
        raise ValueError('Qualified AVB archive no longer covered')
    for c in base:
        if not np.isclose(pair[c+'_proof'].to_numpy(np.float32), pair[c+'_new'].to_numpy(np.float32),
                          rtol=1e-6, atol=1e-6, equal_nan=True).all():
            raise ValueError(f'Qualified AVB feature mismatch {c}')
    # Pre-correction inputs stay bit-identical, not just close within a canary
    # tolerance: tiny recomputation roundoffs can change tied daily ranks.
    features = replace_base_features(features, rebuilt, base, effective_date=before)
    canaries.append(dict(symbol='AVB', raw=raw_canary, corrected=corrected))
    proofs, paths = volume_proofs()
    inputs.update({str(p):digest(p) for p in paths})
    vol = apply_volume_proofs(pd.read_parquet(repairs/'warmup-volume-spy.parquet'), proofs)
    spy = vol.loc[vol.symbol.eq('SPY')]
    # Same core feature builder; only its security segmentation argument is AVB.
    # Use each title's own registry below, not AVB's identity policy.
    from modelFactory.features import compute_features
    from modelFactory.oracle.security_continuity import load_security_discontinuities, split_frame_on_discontinuities
    kwargs = {k:v for k,v in profile['generator_options'].items() if k != 'enable_cross_sectional_ranks'}
    for p in proofs:
        symbol = p['symbol']
        archived = features.loc[features.symbol.eq(symbol)]
        parts = [compute_features(part, benchmark_df=spy.sort_values('date').reset_index(drop=True), **kwargs)
                 for part in split_frame_on_discontinuities(vol.loc[vol.symbol.eq(symbol)], symbol,
                                                           load_security_discontinuities())]
        rebuilt = pd.concat(parts, ignore_index=True).merge(archived[['date','symbol','selector_short_score']],
            on=['date','symbol'], how='inner', suffixes=('_discard',''), validate='one_to_one')
        rebuilt = rebuilt[['date','symbol',*base]]
        canaries.append(dict(symbol=symbol, corrected=assert_feature_canary(rebuilt, archived, base, before=p['date'])))
        features = replace_base_features(features, rebuilt, base, effective_date=p['date'])
    atomic_json(output/'progress.json', dict(status='RUNNING', phase='rank_and_frozen_inference'))
    features = restore_ranks(features, columns)
    features[columns] = features[columns].replace([np.inf,-np.inf],np.nan).astype(np.float32)
    import lightgbm as lgb
    scores = features[['date','symbol']].copy()
    changes = []
    prior_scores = pd.read_parquet(source/'scores.parquet')
    for side in ('long','short'):
        model = lgb.Booster(model_file=str(fold/f'{side}_model.txt'))
        if model.feature_name() != columns:
            raise ValueError('Frozen head feature order changed')
        c = SCORES[side]
        scores[c] = model.predict(features[columns], num_threads=3)
        for year in (2024,2025,2026):
            mask = scores.date.dt.year.eq(year)
            same = np.isclose(scores.loc[mask,c],prior_scores.loc[mask,c],rtol=1e-10,atol=1e-10)
            if year < 2026 and not same.all():
                raise ValueError('Unrelated pre-2026 inference drift')
            changes.append(dict(side=side,year=year,changed_rows=int((~same).sum())))
    selections = []
    for n in (10,20,50):
        for name, frame in [('before',prior_scores),('after',scores)]:
            selected = freeze_candidates(frame.loc[frame.date.dt.year.eq(2026)],n,'NEW_BARRIER_LONG')
            selections.append(dict(version=name,count=n,avb=int(selected.symbol.eq('AVB').sum()),
                                   toely=int(selected.symbol.eq('TOELY').sum())))
    features.to_parquet(output/'features.parquet', index=False)
    scores.to_parquet(output/'scores.parquet', index=False)
    for name in ('prices.parquet','macro.parquet','protocol.json'):
        shutil.copy2(source/name, output/name)
    audit = dict(status='QUALIFIED_LOCAL_FEATURE_REPAIRS', canaries=canaries, score_changes=changes,
        selections=selections, pre_2026_scores_unchanged=True, sql_writes=False, retraining=False,
        price_feature_corrections_aligned_for=['AVB','BAND','GPRE','ATEX'],
        full_input_pit_certified=False, unresolved=['AVB fractional cash if held', 'TOELY missing held prices'])
    atomic_json(output/'correction-audit.json', audit)
    verify_hashes(Path('.'),inputs)
    atomic_json(output/'remediation-inputs.json',dict(files=inputs,code_sha256=digest(__file__),
        models_unchanged=True,sql_writes=False,universe_unchanged=True))
    names = ['prices.parquet','scores.parquet','features.parquet','macro.parquet','correction-audit.json','remediation-inputs.json']
    atomic_json(output/'ready.json',dict(files={n:digest(output/n) for n in names},rows=len(scores),
        sessions=int(scores.date.nunique()),symbols=int(scores.symbol.nunique())))
    atomic_json(output/'progress.json',dict(status='READY_BASELINE',selections=selections))
    print(audit,flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repairs',type=Path,default=Path('artifacts/research/us_oracle_barrier_comparison/repaired-volume-grid-20261012-v1'))
    logging.basicConfig(level=logging.INFO)
    args = parser.parse_args()
    try:
        prepare(**vars(args))
    except Exception as exc:
        if args.output.exists() and not (args.output/'ready.json').exists():
            atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
