"""Archive-only TOP50 research inputs; fill 2023 with a frozen causal model.

No fit, provider call, SQL, label-based membership or production mutation.
The missing 2023 half is a fixed-model extension, never claimed as old OOF.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle_path.train import restore_ranks,digest
from scripts.research.us_concentrated_historical_tapes import atomic_json
from scripts.research.us_oracle_path_economic_replay import qualify_entries

LOG=logging.getLogger(__name__)
OUTPUT=Path('artifacts/research/us_weak_topn_2020_2024/20261029-v1/dataset')
SOURCE=Path('artifacts/research/us_oracle_path_entry_separability/20261014-v2')
HISTORY=Path('artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path')
EXTERNAL=Path('artifacts/research/oracle_path_confirmation/20261013-v1')
PRICE_TAPE=Path('artifacts/research/us_oracle_tp20_sl10_new/20261012-v6')
PROFILE=Path('config/features/shared_direction/shared.json')
CONFIG=Path('config/research/us_weak_topn_2020_2024_20261029.json')
START='2018-07-05'
END='2024-12-31'
PRICE_END='2025-02-14'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def verify(path,expected):
    actual=digest(path)
    if actual!=expected:
        raise ValueError(f'Changed immutable source: {path}')
    return actual


def validate_keys(frame):
    result=frame.copy()
    result['date']=pd.to_datetime(result.date).dt.normalize()
    if result[['date','symbol']].isna().any().any() or result.duplicated(['date','symbol']).any():
        raise ValueError('Missing or duplicate observable identity')
    return result


def freeze_top(scores,count=50):
    """Membership uses only finite scores available at J, never a target."""
    if type(count) is not int or count<1:
        raise ValueError('Positive integer TOP required')
    result=validate_keys(scores[['date','symbol','score_lightgbm']])
    if not (np.isfinite(result.score_lightgbm)&result.score_lightgbm.between(0,1)).all():
        raise ValueError('Invalid amplitude score')
    result=result.sort_values(['date','score_lightgbm','symbol'],ascending=[True,False,True],kind='stable')
    result['oracle_rank']=result.groupby('date').cumcount()+1
    result['scored_count']=result.groupby('date').symbol.transform('size')
    if result.groupby('date').size().lt(count).any():
        raise ValueError('Insufficient daily scoring universe')
    return result.loc[result.oracle_rank.le(count)].copy()


def validate_top(frame,count=50):
    result=validate_keys(frame)
    if result.duplicated(['date','oracle_rank']).any():
        raise ValueError('Duplicate daily Oracle rank')
    grouped=result.groupby('date').oracle_rank.agg(['min','max','size','nunique'])
    if grouped.empty or not (grouped['min'].eq(1)&grouped['max'].eq(count)&
        grouped['size'].eq(count)&grouped['nunique'].eq(count)).all():
        raise ValueError('Original complete TOP ranks required')
    return result


def missing_sessions(frame,calendar,year):
    expected=pd.DatetimeIndex(calendar)
    expected=expected[expected.year==year]
    observed=pd.DatetimeIndex(pd.to_datetime(frame.date).unique())
    return expected.difference(observed)


def causal_spec(name,done,first_decision):
    metrics=done['metrics']
    start=pd.Timestamp(metrics['test_start'])
    first=pd.Timestamp(first_decision)
    if start>first:
        raise ValueError('Model test interval begins after the scored decision')
    for key in ('train_available_max','val_available_max'):
        value=pd.Timestamp(metrics[key])
        if pd.isna(value) or value>=first or value>=start:
            raise ValueError('Training or validation not strictly before decisions')
    return dict(fold_start=name,original_test_start=str(start.date()),
        original_test_end=str(pd.Timestamp(metrics['test_end']).date()),
        train_available_max=metrics['train_available_max'],val_available_max=metrics['val_available_max'])


def normalize_prices(frame):
    """Normalize current archive adjustments once; preserve lineage and volume."""
    result=validate_keys(frame)
    factor=pd.to_numeric(result.adj_close,errors='coerce').where(result.adj_close.notna(),result.close)/result.close
    for column in ('open','high','low','close'):
        result[column]=pd.to_numeric(result[column],errors='coerce')*factor
    # Downstream standard labelers may apply adj_close/close again; it is now 1.
    result['adj_close']=result.close
    result['adjustment_factor_applied']=factor
    if 'instrument_id' in result:
        # Raw archive integer/float/string encodings must not manufacture a
        # lineage break at the boundary; nonnumeric namespaces remain explicit.
        original=result.instrument_id.astype('string')
        numeric=pd.to_numeric(result.instrument_id,errors='coerce')
        integer=numeric.notna() & np.isfinite(numeric) & numeric.mod(1).eq(0)
        original.loc[integer]=numeric.loc[integer].astype('int64').astype('string')
        result['instrument_id']=original
    return result


def _check_artifact(path,expected,sources):
    sources[str(path)]=verify(path,expected)


def _chunk_sources(root,protocol,sources):
    folders=sorted((root/'chunks').iterdir())
    for folder in folders:
        done=read(folder/'done.json')
        sources[str(folder/'done.json')]=digest(folder/'done.json')
        for name in ('features.parquet','bars.parquet'):
            path=folder/name
            expected=protocol['source_hashes'].get(str(path))
            if expected is None:
                expected=done['files'][name]
            _check_artifact(path,expected,sources)
    return folders


def run(output=OUTPUT):
    output=Path(output)
    if (output/'report.json').exists():
        report=read(output/'report.json')
        for name,sha in report['files'].items():verify(output/name,sha)
        for path,sha in report['source_hashes'].items():verify(path,sha)
        print(json.dumps(dict(status='REUSED_VERIFIED_DATASET',output=str(output))))
        return report
    output.mkdir(parents=True,exist_ok=False)
    atomic_json(output/'progress.json',dict(status='RUNNING',phase='qualifying_archives'))
    source_report,protocol=read(SOURCE/'report.json'),read(SOURCE/'protocol.json')
    if source_report['status']!='COMPLETED_EXPLORATORY' or not source_report['source_hashes_verified_after_calculation']:
        raise ValueError('Completed verified TOP50 source required')
    sources={str(p):digest(p) for p in (Path(__file__),PROFILE,CONFIG,SOURCE/'report.json',SOURCE/'protocol.json')}
    _check_artifact(SOURCE/'candidate-population.parquet',source_report['files']['candidate-population.parquet'],sources)
    _check_artifact(PRICE_TAPE/'prices.parquet',read(PRICE_TAPE/'ready.json')['files']['prices.parquet'],sources)
    sources[str(PRICE_TAPE/'ready.json')]=digest(PRICE_TAPE/'ready.json')
    hist_folders=_chunk_sources(HISTORY,protocol,sources)
    ext_folders=_chunk_sources(EXTERNAL,protocol,sources)
    shared=read(PROFILE)['feature_columns']
    keep_features=list(dict.fromkeys([*shared,'rolling_volatility_60','atr_14_norm','atr20_pct']))
    cols=['date','symbol','score_lightgbm','oracle_rank','selected','entry_quality_reason',*keep_features]
    old=pd.read_parquet(SOURCE/'candidate-population.parquet',columns=cols)
    old=validate_top(old.loc[old.date.between(START,END)]).reset_index(drop=True)
    calendar=nyse_sessions(pd.Timestamp('2016-01-01').date(),pd.Timestamp(PRICE_END).date())
    expected=calendar[(calendar>=START)&(calendar<=END)]
    absent=expected.difference(pd.DatetimeIndex(old.date.unique()))
    missing=missing_sessions(old,calendar,2023)
    if not absent.equals(missing):
        raise ValueError('Unexpected gaps outside the authorized 2023 completion')
    if missing.empty:
        raise ValueError('No 2023 gap to complete; inspect source provenance')
    final=HISTORY/'folds'/'2023-01-05'
    done=read(final/'done.json')
    spec=causal_spec(final.name,done,missing.min())
    model=final/'path_model.txt'
    _check_artifact(model,done['files']['path_model.txt'],sources)
    sources[str(final/'done.json')]=digest(final/'done.json')
    feature_cols=protocol['columns']
    raw=list(dict.fromkeys(c.removesuffix('_xs_rank') for c in feature_cols))
    # Read all available symbols before cross-sectional rank restoration.
    extension=[];eligibility=[];prices=[]
    for i,folder in enumerate(hist_folders):
        atomic_json(output/'progress.json',dict(status='RUNNING',phase='historical_archives',completed=i,total=len(hist_folders)))
        part=pd.read_parquet(folder/'features.parquet',columns=['date','symbol',*raw])
        keys=part.loc[part.date.between(START,END),['date','symbol']].copy()
        keys['feature_archive']='historical'
        eligibility.append(keys)
        extension.append(part.loc[part.date.isin(missing)])
        bars=pd.read_parquet(folder/'bars.parquet')
        bars=bars.loc[bars.date.between('2016-01-01','2023-12-31')].copy()
        bars['input_archive']='historical_raw_bars'
        prices.append(bars)
        LOG.info('Historical archive %d/%d',i+1,len(hist_folders))
    all_features=restore_ranks(pd.concat(extension,ignore_index=True),protocol['options'])
    all_features=validate_keys(all_features)
    if set(shared)-set(all_features):
        raise ValueError('Original shared feature profile incomplete')
    booster=lgb.Booster(model_file=str(model))
    if booster.feature_name()!=feature_cols:
        raise ValueError('Frozen Oracle feature order changed')
    atomic_json(output/'progress.json',dict(status='RUNNING',phase='frozen_2023_extension',rows=len(all_features)))
    scores=all_features[['date','symbol']].copy()
    scores['score_lightgbm']=booster.predict(all_features[feature_cols].replace([np.inf,-np.inf],np.nan).astype(np.float32),num_threads=2)
    top=freeze_top(scores,50).merge(all_features[['date','symbol',*keep_features]],on=['date','symbol'],validate='one_to_one')
    scores.to_parquet(output/'2023-extension-full-scores.parquet',index=False)
    del all_features,extension
    for i,folder in enumerate(ext_folders):
        part=pd.read_parquet(folder/'features.parquet',columns=['date','symbol'])
        part=part.loc[part.date.between('2024-01-01',END)].copy()
        part['feature_archive']='external'
        eligibility.append(part)
    eligible=validate_keys(pd.concat(eligibility,ignore_index=True))
    eligible['feature_eligible']=True
    eligible=eligible.sort_values(['date','symbol']).reset_index(drop=True)
    tape=pd.read_parquet(PRICE_TAPE/'prices.parquet')
    tape=tape.loc[tape.date.between('2024-01-01',PRICE_END)].copy()
    tape['input_archive']='external_campaign_adjusted_tape'
    prices.append(tape)
    price_frame=normalize_prices(pd.concat(prices,ignore_index=True))
    # Use only retrospective J history for entry qualification; future prices do
    # not decide TOP membership. Existing source flags are retained unchanged.
    qualified=qualify_entries(top,price_frame,calendar)
    old['score_regime']=np.where(old.date.ge('2024-01-01'),'ARCHIVED_FIXED_CAUSAL_MODEL','ARCHIVED_WALK_FORWARD_TEST')
    qualified['score_regime']='FROZEN_CAUSAL_EXTENSION_2023'
    # Existing scored-count is reconstructed from observable J keys, never labels.
    counts=eligible.groupby('date').size()
    old['scored_count']=old.date.map(counts)
    population=validate_top(pd.concat([old,qualified],ignore_index=True)).sort_values(['date','oracle_rank']).reset_index(drop=True)
    if not pd.DatetimeIndex(population.date.unique()).equals(expected):
        raise ValueError('Incomplete official session coverage after extension')
    for name in ('fold_start','train_available_max','val_available_max','model_sha256'):
        population[name]=None
    lineage=[]
    for fold in protocol['folds']:
        folder=HISTORY/'folds'/fold['name'];meta=read(folder/'done.json')
        info=causal_spec(fold['name'],meta,fold['start'])
        weight=folder/'path_model.txt'
        _check_artifact(weight,meta['files']['path_model.txt'],sources)
        sources[str(folder/'done.json')]=digest(folder/'done.json')
        info['model_sha256']=sources[str(weight)]
        mask=population.date.between(fold['start'],fold['end'])
        for name in ('fold_start','train_available_max','val_available_max','model_sha256'):population.loc[mask,name]=info[name]
        lineage.append(info)
    fixed=population.date.gt(pd.Timestamp(spec['original_test_end']))
    for name in ('fold_start','train_available_max','val_available_max'):
        population.loc[fixed,name]=spec[name]
    population.loc[fixed,'model_sha256']=sources[str(model)]
    if population[['fold_start','train_available_max','val_available_max','model_sha256']].isna().any().any():
        raise ValueError('Missing causal model lineage')
    if not (pd.to_datetime(population.train_available_max).lt(population.date)&
            pd.to_datetime(population.val_available_max).lt(population.date)).all():
        raise ValueError('Future model availability')
    membership=pd.MultiIndex.from_frame(eligible[['date','symbol']])
    if not pd.MultiIndex.from_frame(population[['date','symbol']]).isin(membership).all():
        raise ValueError('Selected name not in observable feature universe')
    coverage=[]
    for count in (20,50):
        sub=population.loc[population.oracle_rank.le(count)]
        for year,group in sub.groupby(sub.date.dt.year):
            coverage.append(dict(year=int(year),top=count,dates=int(group.date.nunique()),rows=len(group),
                symbols=int(group.symbol.nunique()),entry_qualified=int(group.selected.sum()),
                extension_rows=int(group.score_regime.eq('FROZEN_CAUSAL_EXTENSION_2023').sum()),
                expected_dates=int(sum(expected.year==year))))
    population.to_parquet(output/'top50-features.parquet',index=False)
    eligible.to_parquet(output/'feature-eligibility.parquet',index=False)
    price_frame.sort_values(['symbol','date']).to_parquet(output/'adjusted-prices.parquet',index=False)
    pd.DataFrame(coverage).to_csv(output/'coverage.csv',index=False)
    atomic_json(output/'model-lineage.json',dict(folds=lineage,extension=spec,
        extension_dates=[str(d.date()) for d in missing],fixed_external_model='2023-01-05'))
    files={p.name:digest(p) for p in output.iterdir() if p.suffix in ('.parquet','.csv') or p.name=='model-lineage.json'}
    report=dict(status='COMPLETED_DATASET',start=START,end=END,price_end=PRICE_END,
        missing_2023_reason='Archived ten-fold walk-forward ends 2023-07-07; raw 2023 prices/features exist',
        original_2023_dates=int(old.loc[old.date.dt.year.eq(2023),'date'].nunique()),
        completed_2023_dates=int(population.loc[population.date.dt.year.eq(2023),'date'].nunique()),
        added_2023_sessions=len(missing),coverage=coverage,shared_feature_columns=shared,
        shared_profile_sha256=sources[str(PROFILE)],price_rows=len(price_frame),feature_eligibility_rows=len(eligible),
        source_hashes=sources,files=files,no_training=True,no_provider_calls=True,no_sql=True,no_orders=True,
        limitations=['Extension uses frozen January2023 model; not newly recreated OOF folds',
            'Existing adjusted archive values and survivor universe are not point-in-time data revisions',
            'Research period already observed; not an independent holdout',
            'First causal scores July2018: fewer than504 prior selection dates for early2020'])
    # Recheck immutable data sources after construction.
    for path,sha in sources.items():verify(path,sha)
    atomic_json(output/'report.json',report)
    atomic_json(output/'manifest.json',report)
    atomic_json(output/'progress.json',dict(status='COMPLETED',phase='dataset_ready',added_2023_sessions=len(missing)))
    print(json.dumps(dict(status=report['status'],added_2023_sessions=len(missing),coverage=coverage),indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    run(args.output)
