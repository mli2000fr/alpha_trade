"""Version qualified archived volume repairs and re-infer frozen models, SELECT only."""
import argparse
import gc
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import event

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.features import compute_features
from modelFactory.oracle.security_continuity import load_security_discontinuities, split_frame_on_discontinuities
from modelFactory.oracle_barrier import SCORES
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_volume_refresh import qualify
from scripts.research.us_oracle_barrier_comparison import EXTERNAL, checkpoint_frame, read, readonly_statement
from scripts.research.us_oracle_barrier_grid_prepare import assert_feature_canary
from scripts.research.us_oracle_h20_dataset_audit import readonly_begin, restore_ranks


def volume_proofs():
    base = Path('artifacts/research/us_concentrated_replay')
    paths, proofs = [], []
    for symbol in ('BAND', 'GPRE', 'ATEX'):
        if symbol == 'BAND':
            root = base/'qualification-contract-20261006-v2'
            report_path, raw = root/'report.json', root/'BAND_eod.json'
            r = next(c for c in read(report_path)['cases'] if c['symbol'] == symbol)
            original, refreshed = r['archived'], r['refreshed']
            expected = r['raw_payload_sha256']
        else:
            root = base/f'{symbol.lower()}-volume-refresh-20261007-v1'
            report_path, raw = root/'report.json', root/'provider-response.json'
            r = read(report_path)
            original, refreshed, expected = r['original'], r['refreshed'], r['raw_sha256']
        if digest(raw) != expected or qualify(original, refreshed) != 'VENDOR_VOLUME_CORRECTION_NON_PIT':
            raise ValueError(f'Unqualified volume evidence {symbol}')
        day = refreshed['date']
        records = [x for x in read(raw) if x.get('date') == day]
        if len(records) != 1 or any(float(records[0][c]) != float(refreshed[c])
                                  for c in ('open','high','low','close','volume')):
            raise ValueError(f'Provider evidence mismatch {symbol}')
        proofs.append(dict(symbol=symbol, date=day, original_volume=float(original['volume']),
            replacement_volume=float(refreshed['volume']), original=original,
            raw_sha256=expected, historical_pit_evidence=False))
        paths.extend([report_path,raw])
    return proofs, paths


def apply_volume_proofs(bars, proofs):
    result = bars.copy()
    result['volume'] = result.volume.astype(float)
    for p in proofs:
        mask = result.symbol.eq(p['symbol']) & result.date.eq(pd.Timestamp(p['date']))
        if mask.sum() != 1 or result.loc[mask,'volume'].iloc[0] not in (p['original_volume'],p['replacement_volume']):
            raise ValueError('Volume repair target missing, duplicated or changed')
        for c in ('open','high','low','close'):
            if abs(float(result.loc[mask,c].iloc[0])-float(p['original'][c])) > .005:
                raise ValueError('Volume repair cannot hide an OHLC disagreement')
        result.loc[mask,'volume'] = p['replacement_volume']
    return result


def prepare(source, output):
    output.mkdir(parents=True,exist_ok=True)
    prior = read(source/'prepared.json')
    verify_hashes(source,prior['files'])
    protocol = read(source/'input-protocol.json')
    proofs, paths = volume_proofs()
    hashes = dict(protocol['source_hashes'])
    hashes.update({str(p):digest(p) for p in [source/'prepared.json',source/'input-protocol.json',
                  *[source/name for name in prior['files']],*paths]})
    config = dict(protocol,source_hashes=hashes,code_sha256=digest(__file__),
        correction_scope='AVB share units plus three qualified zero-volume corrections and affected daily ranks',
        volume_repairs=proofs)
    marker = output/'input-protocol.json'
    if marker.exists() and read(marker) != config:
        raise ValueError('Inputs changed; use new output')
    atomic_json(marker,config)
    if (output/'prepared.json').exists():
        ready = read(output/'prepared.json')
        verify_hashes(output,ready['files'])
        return ready
    atomic_json(output/'progress.json',dict(status='PREPARING',phase='qualified_volumes'))
    prices = apply_volume_proofs(pd.read_parquet(source/'prices.parquet'),proofs)
    prices.to_parquet(output/'prices.parquet',index=False)
    del prices
    columns = [c for c in protocol['columns'] if not c.endswith('_xs_rank')]
    features = pd.concat([pd.read_parquet(p) for p in sorted(EXTERNAL.glob('corrected-features-*.parquet'))],ignore_index=True)
    avb = pd.read_parquet(source/'repaired-avb-features.parquet')
    features = pd.concat([features.loc[features.symbol.ne('AVB')],avb.reindex(columns=features.columns)],ignore_index=True)
    symbols = [p['symbol'] for p in proofs]
    def load():
        engine = get_sqlalchemy_engine(db_name='alpha_trade')
        if engine.url.database != 'alpha_trade':
            raise ValueError('Wrong database')
        event.listen(engine,'begin',readonly_begin)
        event.listen(engine,'before_cursor_execute',readonly_statement)
        try:
            return load_universe_bars(engine,[*symbols,'SPY'],start_date='2012-12-27',end_date='2026-09-03')
        finally:
            engine.dispose()
    warm = checkpoint_frame(output,'warmup-volume-spy.parquet',load)
    warm = apply_volume_proofs(warm,proofs)
    benchmark = warm.loc[warm.symbol.eq('SPY')].sort_values('date').reset_index(drop=True)
    options = {k:v for k,v in protocol['options'].items() if k != 'enable_cross_sectional_ranks'}
    canaries = []
    for symbol in symbols:
        archived = features.loc[features.symbol.eq(symbol)].copy()
        bars = warm.loc[warm.symbol.eq(symbol)].copy()
        parts = [compute_features(part,benchmark_df=benchmark,**options)
            for part in split_frame_on_discontinuities(bars,symbol,load_security_discontinuities())]
        rebuilt = pd.concat(parts,ignore_index=True).merge(archived[['date','symbol','selector_short_score']],
            on=['date','symbol'],how='inner',suffixes=('_discard',''),validate='one_to_one')
        rebuilt = rebuilt[['date','symbol',*columns]]
        canary = assert_feature_canary(rebuilt,archived,columns,before='2026-06-18')
        canaries.append(dict(symbol=symbol,**canary))
        if len(rebuilt) != len(archived):
            raise ValueError('Feature eligibility changed')
        features = pd.concat([features.loc[features.symbol.ne(symbol)],rebuilt.reindex(columns=features.columns)],ignore_index=True)
    features = features.sort_values(['date','symbol']).reset_index(drop=True)
    before = pd.read_parquet(source/'scores.parquet')
    features = features.merge(before[['date','symbol']],on=['date','symbol'],validate='one_to_one')
    if len(features) != len(before):
        raise ValueError('Scored membership changed')
    for c in features.select_dtypes(include='float64'):
        features[c] = features[c].astype(np.float32)
    features = restore_ranks(features,protocol['columns'])
    features[protocol['columns']] = features[protocol['columns']].replace([np.inf,-np.inf],np.nan).astype(np.float32)
    import lightgbm as lgb
    scores = features[['date','symbol']].copy()
    for key,path in protocol['frozen_model_files'].items():
        model = lgb.Booster(model_file=path)
        if model.feature_name() != protocol['columns']:
            raise ValueError('Feature order changed')
        scores['old_score' if key=='old' else SCORES[key]] = model.predict(features[protocol['columns']],num_threads=3)
    scores['max_score'] = scores[list(SCORES.values())].max(axis=1)
    paired = scores.merge(before,on=['date','symbol'],suffixes=('_after','_before'),validate='one_to_one')
    changes = []
    for year,group in paired.groupby(paired.date.dt.year):
        for c in ('old_score',*SCORES.values()):
            same = np.isclose(group[c+'_after'],group[c+'_before'],rtol=1e-10,atol=1e-10)
            if year==2025 and not same.all():
                raise ValueError('Unrelated 2025 score drift')
            changes.append(dict(year=int(year),score=c,changed_rows=int((~same).sum())))
    scores.to_parquet(output/'scores.parquet',index=False)
    pd.read_parquet(source/'macro.parquet').to_parquet(output/'macro.parquet',index=False)
    for name in ('warmup-avb-spy.parquet','repaired-avb-features.parquet'):
        pd.read_parquet(source/name).to_parquet(output/name,index=False)
    report = dict(prior,status='PRICE_FEATURE_VOLUME_REPAIRS_READY',volume_repairs=proofs,
        volume_canaries=canaries,volume_score_changes=changes,
        non_avb_base_features_unchanged=False,unaffected_base_features_unchanged=True,
        files={name:digest(output/name) for name in ('prices.parquet','scores.parquet','macro.parquet',
            'warmup-avb-spy.parquet','repaired-avb-features.parquet','warmup-volume-spy.parquet')})
    verify_hashes(Path('.'),hashes)
    atomic_json(output/'prepared.json',report)
    atomic_json(output/'progress.json',dict(status='READY_GRID',rows=len(scores),volume_canaries=canaries,score_changes=changes))
    del features
    gc.collect()
    print(report['status'],changes,flush=True)
    return report


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    prepare(**vars(parser.parse_args()))
