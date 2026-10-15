"""Univariate conditional TP20-before-SL10 audit. Inference only, no fitting/PnL.

Historical OOF files were future-quality-conditioned. Re-score the observable
population with existing causal fold weights, freeze TOPs, THEN attach labels.
"""
import argparse
import gc
import json
import logging
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sqlalchemy import event, text

from database.connection import get_sqlalchemy_engine
from modelFactory.config import OracleBarrierConfig
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import load_security_discontinuities, DEFAULT_REGISTRY_PATH
from modelFactory.oracle_barrier.labels import symbol_barriers
from modelFactory.oracle_path.train import restore_ranks
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import readonly_statement
from scripts.research.us_oracle_h20_dataset_audit import readonly_begin
from scripts.research.us_oracle_path_economic_replay import freeze_top, qualify_entries

LOG = logging.getLogger(__name__)
HISTORY = Path('artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path')
CONFIRMATION = Path('artifacts/research/oracle_path_confirmation/20261013-v1')
PORTFOLIOS = Path('artifacts/research/us_oracle_path_economic/20261013-v1')
MACRO = ['vix','vix9d','ten_y','vxn','vix3m','move','rvx','yield_10y_5d_pct','sentiment_score']
PERIODS = ['DISCOVERY_2018_2021','VALIDATION_2022','CONFIRM_2023','CHECK_2024','CHECK_2025','CHECK_2026']
TARGET = 'long_tp_before_sl'
RULES = dict(primary_top=10, robustness_tops=[20,50], min_coverage=.9,
    discovery_daily_auc=.55, validation_daily_auc=.53, external_daily_auc=.52,
    min_discovery_dates=100, min_validation_dates=30, min_external_dates=30,
    maxT_alpha=.05, block_sessions=63, min_block_dates=20, min_blocks=8,
    permutations=999, seed=20261014, min_positive_and_negative_per_day=2)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def causal_fold_contract(done, start):
    metrics = done['metrics']
    for key in ('train_available_max','val_available_max'):
        value = pd.Timestamp(metrics[key])
        if pd.isna(value) or value >= pd.Timestamp(start):
            raise ValueError('Fit and validation must precede every scored decision')


def label_input(group):
    """Nullable string IDs in replay tape -> float/NaN, never a fabricated ID.

    Shared historical label helper expects a NumPy boolean comparison. Keep
    the original replay tape unchanged; nonnumeric successor namespaces remain
    unqualified rather than being coerced into another instrument identity.
    """
    result=group.copy()
    result['instrument_id']=pd.to_numeric(result.instrument_id,errors='coerce').astype(float)
    return result


def period_dates(dates):
    dates = pd.to_datetime(dates)
    year = dates.dt.year
    return pd.Series(np.select([year.le(2021),year.eq(2022),year.eq(2023),year.eq(2024),year.eq(2025),year.eq(2026)],
        PERIODS,default='OUTSIDE'),index=dates.index)


def evaluable(frame):
    """Purge discovery/validation at their boundary; no future-label reselection."""
    known = frame.selected & frame.path_qualified.fillna(False) & frame[TARGET].notna()
    availability = pd.to_datetime(frame.oracle_available_date)
    known &= availability.notna() & availability.le(pd.Timestamp('2026-10-09'))
    known &= ~frame.period.eq(PERIODS[0]) | availability.lt(pd.Timestamp('2022-01-01'))
    known &= ~frame.period.eq(PERIODS[1]) | availability.lt(pd.Timestamp('2023-01-01'))
    return known


def auc(y,x):
    x,y = np.asarray(x,dtype=float),np.asarray(y,dtype=bool)
    good=np.isfinite(x)
    x,y=x[good],y[good]
    n1,n0=int(y.sum()),int((~y).sum())
    if not n1 or not n0:
        return None
    ranks=rankdata(x,method='average')
    return float((ranks[y].sum()-n1*(n1+1)/2)/(n1*n0))


def daily_aucs(frame,columns):
    """Equal-date conditional discrimination; date-constant macro cannot help it."""
    values=frame[columns].replace([np.inf,-np.inf],np.nan)
    valid=values.notna()
    positive=frame[TARGET].eq(1)
    ranks=values.groupby(frame.date).rank(method='average')
    n1=valid.mul(positive,axis=0).groupby(frame.date).sum()
    n0=valid.mul(~positive,axis=0).groupby(frame.date).sum()
    sums=ranks.mul(positive,axis=0).groupby(frame.date).sum()
    result=(sums-n1*(n1+1)/2)/(n1*n0)
    return result.where(n1.ge(2)&n0.ge(2))


def maxT_block_pvalues(daily,columns,calendar):
    """Joint block sign-flip max-|t|, conditional diagnostic, not alpha proof."""
    if not columns:
        return {}
    order=pd.Series(np.arange(len(calendar)),index=calendar)
    blocks=(order.reindex(daily.index)//RULES['block_sessions']).astype(int)
    centered=daily[columns]-.5
    means=centered.groupby(blocks.to_numpy()).mean()
    counts=centered.groupby(blocks.to_numpy()).count()
    means=means.where(counts.ge(RULES['min_block_dates']))
    matrix=means.to_numpy(float)
    n=np.isfinite(matrix).sum(axis=0)
    def statistic(a):
        with np.errstate(invalid='ignore',divide='ignore'):
            return np.abs(np.nanmean(a,axis=0)/(np.maximum(np.nanstd(a,axis=0,ddof=1),1e-12)/np.sqrt(n)))
    observed=statistic(matrix)
    eligible=n>=RULES['min_blocks']
    rng=np.random.default_rng(RULES['seed'])
    maxima=[]
    for _ in range(RULES['permutations']):
        permuted=statistic(matrix*rng.choice([-1.,1.],size=(len(matrix),1)))
        finite=permuted[eligible & np.isfinite(permuted)]
        maxima.append(float(finite.max()) if len(finite) else 0.)
    null=np.asarray(maxima)
    return {c:dict(blocks=int(n[i]),p_maxT=float((1+(null>=observed[i]).sum())/(1+len(null)))
        if eligible[i] and np.isfinite(observed[i]) else None) for i,c in enumerate(columns)}


def tier(feature):
    if feature.startswith('macro_'):
        return 'MACRO_PUBLICATION_LINEAGE_RESERVED'
    if any(word in feature for word in ('selector_','sector_','sentiment','company_idio')):
        return 'DERIVED_SOURCE_LINEAGE_RESERVED'
    if feature=='score_lightgbm':
        return 'AMPLITUDE_REFERENCE_NOT_NEW_FEATURE'
    return 'CAUSAL_PRICE_CALCULATION_CURRENT_HISTORY'


def frozen_probe(discovery,validation,quality,pvalue):
    """No external/test argument accepted by candidate selection."""
    d,v=discovery.get('daily_auc_oriented'),validation.get('daily_auc_oriented')
    return bool(quality=='CAUSAL_PRICE_CALCULATION_CURRENT_HISTORY' and pvalue is not None and pvalue<=RULES['maxT_alpha']
        and d is not None and v is not None and d>=RULES['discovery_daily_auc'] and v>=RULES['validation_daily_auc']
        and discovery['coverage']>=RULES['min_coverage'] and validation['coverage']>=RULES['min_coverage']
        and discovery['daily_auc_dates']>=RULES['min_discovery_dates'] and validation['daily_auc_dates']>=RULES['min_validation_dates'])


def feature_statistics(pool,columns,count,calendar):
    pool=pool.loc[pool.oracle_rank.le(count)].copy()
    known=pool.loc[evaluable(pool)].copy()
    daily=daily_aucs(known,columns)
    mapping=known[['date','period']].drop_duplicates().set_index('date').period
    discovery_days=daily.loc[mapping.reindex(daily.index).eq(PERIODS[0])]
    # Feature family classification also freezes on discovery alone: even
    # unlabelled external feature variability must not alter selection/maxT.
    discovery_pool=pool.loc[pool.period.eq(PERIODS[0])]
    common=(discovery_pool.groupby('date')[columns].nunique().le(1).mean()).to_dict()
    family=[c for c in columns if common[c]<.98 and tier(c)=='CAUSAL_PRICE_CALCULATION_CURRENT_HISTORY']
    pvalues=maxT_block_pvalues(discovery_days,family,calendar)
    results=[]
    for feature in columns:
        discovery_auc=discovery_days[feature].mean()
        orientation=1 if pd.isna(discovery_auc) or discovery_auc>=.5 else -1
        periods={}
        for name in PERIODS:
            sub=known.loc[known.period.eq(name)]
            x=pd.to_numeric(sub[feature],errors='coerce').replace([np.inf,-np.inf],np.nan)
            good=x.notna()
            y=sub[TARGET].eq(1)
            pos,neg=x[good&y],x[good&~y]
            a=auc(y[good],x[good])
            dates=daily.index[mapping.reindex(daily.index).eq(name)]
            day_values=daily.loc[dates,feature].dropna()
            oriented=day_values if orientation==1 else 1-day_values
            pooled=np.sqrt((pos.var(ddof=0)+neg.var(ddof=0))/2) if len(pos) and len(neg) else np.nan
            periods[name]=dict(rows=len(sub),valid=int(good.sum()),coverage=float(good.mean()) if len(sub) else 0.,
                unique=int(x.nunique()),auc_raw=a,auc_raw_oriented=a if orientation==1 or a is None else 1-a,
                mean_tp=float(pos.mean()) if len(pos) else None,mean_other=float(neg.mean()) if len(neg) else None,
                median_tp=float(pos.median()) if len(pos) else None,median_other=float(neg.median()) if len(neg) else None,
                standardized_mean_difference=float((pos.mean()-neg.mean())/pooled) if np.isfinite(pooled) and pooled>0 else None,
                daily_auc_oriented=float(oriented.mean()) if len(oriented) else None,daily_auc_dates=len(oriented),
                daily_auc_fraction_above_half=float(oriented.gt(.5).mean()) if len(oriented) else None)
        p=pvalues.get(feature,dict(blocks=0,p_maxT=None))
        qualifies=frozen_probe(periods[PERIODS[0]],periods[PERIODS[1]],tier(feature),p['p_maxT']) and common[feature]<.98
        confirmations=[periods[k] for k in PERIODS[2:]]
        stable=qualifies and all(r['daily_auc_oriented'] is not None and r['daily_auc_oriented']>=RULES['external_daily_auc']
            and r['daily_auc_dates']>=RULES['min_external_dates'] and r['coverage']>=RULES['min_coverage'] for r in confirmations)
        results.append(dict(feature=feature,top=count,tier=tier(feature),orientation_frozen_discovery=orientation,
            constant_within_date_fraction=float(common[feature]),**p,periods=periods,
            probe_selected_before_external=bool(qualifies),external_stability_pass=bool(stable)))
    return results,known


def cache_frame(output,name,builder):
    path,marker=output/name,output/(name+'.json')
    if marker.exists():
        verify_hashes(output,read(marker)['files'])
        return pd.read_parquet(path)
    frame=builder()
    frame.to_parquet(path,index=False)
    atomic_json(marker,dict(files={name:digest(path)},rows=len(frame)))
    return frame


def macro_snapshot():
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':
        raise ValueError('US database required')
    event.listen(engine,'begin',readonly_begin)
    event.listen(engine,'before_cursor_execute',readonly_statement)
    try:
        return pd.read_sql(text('SELECT trade_date,'+','.join(MACRO)+',created_at,updated_at FROM stock_macro_indicators_daily '
            'WHERE trade_date BETWEEN :start AND :end ORDER BY trade_date'),engine,
            params=dict(start='2018-07-05',end='2026-09-02'),parse_dates=['trade_date','created_at','updated_at'])
    finally:
        engine.dispose()


def source_protocol(output):
    profile=read(HISTORY/'feature_profile.json')
    protocol=read(HISTORY/'protocol.json')
    confirmation=read(CONFIRMATION/'plan.json')
    source_report=read(PORTFOLIOS/'report.json')
    if source_report['status']!='COMPLETED_EXPLORATORY':
        raise ValueError('Completed portfolio baseline required')
    verify_hashes(Path('.'),confirmation['original_source_hashes'])
    paths={Path(__file__),HISTORY/'feature_profile.json',HISTORY/'protocol.json',CONFIRMATION/'plan.json',
        CONFIRMATION/'scores.parquet',PORTFOLIOS/'manifest.json',PORTFOLIOS/'report.json',DEFAULT_REGISTRY_PATH,
        Path('modelFactory/oracle_barrier/labels.py'),Path('modelFactory/oracle_path/train.py'),
        Path('scripts/research/us_oracle_path_economic_replay.py')}
    fold_specs=[]
    for folder in sorted((HISTORY/'folds').iterdir()):
        done=read(folder/'done.json')
        verify_hashes(folder,done['files'])
        start,end=done['metrics']['test_start'],done['metrics']['test_end']
        causal_fold_contract(done,start)
        fold_specs.append(dict(name=folder.name,start=start,end=end,metrics=done['metrics']))
        paths.update(folder/name for name in ('done.json','path_model.txt','oof.parquet'))
    for root in (HISTORY,CONFIRMATION):
        for folder in sorted((root/'chunks').iterdir()):
            done=read(folder/'done.json')
            verify_hashes(folder,{name:done['files'][name] for name in ('features.parquet','bars.parquet')})
            paths.update(folder/name for name in ('done.json','features.parquet','bars.parquet'))
    portfolio_manifest=read(PORTFOLIOS/'manifest.json')
    verify_hashes(Path('.'),portfolio_manifest['source_hashes'])
    price_path=Path(portfolio_manifest['tapes'])/'prices.parquet'
    paths.add(price_path)
    frozen=dict(rules=RULES,folds=fold_specs,columns=profile['feature_columns'],options=profile['generator_options'],
        universe=protocol['universe'],historical_population='all observable features; score BEFORE future qualification',
        external_decision_end='2026-09-02',as_of='2026-10-09',price_path=str(price_path),
        target=dict(tp_pct=.2,sl_pct=.1,max_sessions=20,entry='J+1 open',available='J+22 for every outcome',
            other_class='SL or EXPIRED; EXPIRED can have positive PnL',ambiguous='exclude with explicit coverage'),
        source_hashes={str(p):digest(p) for p in sorted(paths)},no_training=True,no_backtest=True,no_sql_writes=True,no_orders=True)
    marker=output/'protocol.json'
    if marker.exists():
        if read(marker)!=frozen:
            raise ValueError('Protocol changed; new output directory required')
    else:
        atomic_json(marker,frozen)
    if len(fold_specs)!=10:
        raise ValueError('Ten causal historical folds required')
    return frozen


def prepare_population(output,protocol):
    profile_cols=protocol['columns']
    raw=list(dict.fromkeys(c.removesuffix('_xs_rank') for c in profile_cols))
    registry=load_security_discontinuities()
    cfg=OracleBarrierConfig(take_profit_pct=.2,stop_loss_pct=.1,max_sessions=20)
    populations=[]
    for phase,root,as_of in [('historical',HISTORY,'2023-12-29'),('external',CONFIRMATION,'2026-10-09')]:
        def build():
            parts,labels,bars_parts=[],[],[]
            calendar=nyse_sessions(pd.Timestamp('2016-01-01' if phase=='historical' else '2023-01-01').date(),
                (pd.Timestamp(as_of)+pd.Timedelta(days=90)).date())
            folders=sorted((root/'chunks').iterdir())
            for i,folder in enumerate(folders):
                atomic_json(output/'progress.json',dict(status='RUNNING',phase=phase+'_cache',completed=i,total=len(folders)))
                part=pd.read_parquet(folder/'features.parquet',columns=['date','symbol',*raw])
                part=part.loc[part.date.ge('2018-07-05' if phase=='historical' else '2024-01-01')]
                if phase=='external':
                    part=part.loc[part.date.le('2026-09-02')]
                parts.append(part)
                if phase=='historical':
                    bars=pd.read_parquet(folder/'bars.parquet')
                    bars_parts.append(bars)
                    for symbol,group in bars.groupby('symbol'):
                        label,_=symbol_barriers(label_input(group),calendar,start='2018-07-05',end=as_of,registry=registry,config=cfg)
                        labels.append(label)
                LOG.info('%s cache %d/%d',phase,i+1,len(folders))
            features=restore_ranks(pd.concat(parts,ignore_index=True),protocol['options'])
            del parts
            if features.duplicated(['date','symbol']).any():
                raise ValueError('Duplicate observable features')
            atomic_json(output/'progress.json',dict(status='RUNNING',phase=phase+'_scoring'))
            if phase=='historical':
                scored=[]
                for fold in protocol['folds']:
                    folder=HISTORY/'folds'/fold['name']
                    sub=features.loc[features.date.between(fold['start'],fold['end'])]
                    booster=lgb.Booster(model_file=str(folder/'path_model.txt'))
                    if booster.feature_name()!=profile_cols:
                        raise ValueError('Original feature ordering differs')
                    score=sub[['date','symbol']].copy()
                    score['score_lightgbm']=booster.predict(sub[profile_cols].replace([np.inf,-np.inf],np.nan).astype(np.float32),num_threads=3)
                    score['fold_start']=fold['name']
                    # Reproduction of old qualified OOF is an integrity check,
                    # NOT the definition of the new candidate population.
                    old=pd.read_parquet(folder/'oof.parquet',columns=['date','symbol','score_lightgbm'])
                    compared=old.merge(score,on=['date','symbol'],suffixes=('_old','_new'),validate='one_to_one')
                    error=float((compared.score_lightgbm_old-compared.score_lightgbm_new).abs().max())
                    if len(compared)!=len(old) or error>1e-7:
                        raise ValueError(f'Original OOF reproduction differs: {fold["name"]} {error}')
                    atomic_json(output/f'oof-check-{fold["name"]}.json',dict(rows=len(compared),max_score_difference=error,
                        all_observable_scored_rows=len(score),original_qualified_oof_rows=len(old)))
                    scored.append(score)
                    LOG.info('Scored existing fold %s: %d observable rows, old OOF reproduced',fold['name'],len(score))
                scores=pd.concat(scored,ignore_index=True)
                price_frame=pd.concat(bars_parts,ignore_index=True)
                factor=price_frame.adj_close.where(price_frame.adj_close.notna(),price_frame.close)/price_frame.close
                for col in ('open','high','low','close'):
                    price_frame[col]*=factor
                target=pd.concat(labels,ignore_index=True)
            else:
                scores=pd.read_parquet(CONFIRMATION/'scores.parquet')
                scores=scores.loc[scores.date.le('2026-09-02')]
                price_frame=pd.read_parquet(protocol['price_path'])
                for symbol,group in price_frame.loc[price_frame.symbol.isin(protocol['universe'])].groupby('symbol'):
                    label,_=symbol_barriers(label_input(group),calendar,start='2024-01-01',end=as_of,registry=registry,config=cfg)
                    labels.append(label)
                target=pd.concat(labels,ignore_index=True)
            selected=qualify_entries(freeze_top(scores,50),price_frame,calendar)
            selected=selected.merge(features[['date','symbol',*profile_cols]],on=['date','symbol'],how='left',validate='one_to_one')
            if selected[profile_cols].isna().all(axis=1).any():
                raise ValueError('Selected features absent')
            selected=selected.merge(target[['date','symbol',TARGET,'long_outcome','path_qualified','path_quality_reason',
                'oracle_available_date','entry_date','entry_price']],on=['date','symbol'],how='left',validate='one_to_one')
            selected['phase']=phase
            return selected
        populations.append(cache_frame(output,phase+'-population.parquet',build))
        gc.collect()
    pool=pd.concat(populations,ignore_index=True)
    if pool.duplicated(['date','symbol']).any():
        raise ValueError('Overlapping score periods')
    pool['period']=period_dates(pool.date)
    macro=cache_frame(output,'macro-snapshot.parquet',macro_snapshot)
    if macro.trade_date.duplicated().any():
        raise ValueError('Duplicate macro date')
    macro=macro.rename(columns={'trade_date':'date',**{c:'macro_'+c for c in MACRO}})
    return pool.merge(macro,on='date',how='left',validate='many_to_one')


def temporal_context(pool,columns,count):
    sub=pool.loc[pool.oracle_rank.le(count)]
    known=sub.loc[evaluable(sub)]
    daily_target=known.groupby('date')[TARGET].mean()
    result=[]
    for feature in columns:
        if not feature.startswith('macro_') and sub.groupby('date')[feature].nunique().gt(1).mean()>.02:
            continue
        values=sub.groupby('date')[feature].median()
        rows=[]
        for period in PERIODS:
            dates=sub.loc[sub.period.eq(period),'date'].unique()
            paired=pd.DataFrame(dict(value=values,target=daily_target)).reindex(dates).dropna()
            correlation=float(spearmanr(paired.value,paired.target).statistic) if len(paired)>2 and paired.value.nunique()>1 and paired.target.nunique()>1 else None
            rows.append(dict(period=period,dates=len(dates),paired_dates=len(paired),
                paired_coverage=len(paired)/len(dates) if len(dates) else 0.,spearman_with_daily_tp_rate=correlation))
        result.append(dict(feature=feature,top=count,periods=rows,
            status='RETROSPECTIVE_TEMPORAL_CONTEXT_NOT_CROSS_SECTIONAL_FILTER',tier=tier(feature)))
    return result


def run(output):
    output=Path(output)
    with exclusive_run(output):
        try:
            atomic_json(output/'progress.json',dict(status='RUNNING',phase='source_qualification'))
            protocol=source_protocol(output)
            pool=prepare_population(output,protocol)
            pool.to_parquet(output/'candidate-population.parquet',index=False)
            columns=[*protocol['columns'],'score_lightgbm',*['macro_'+c for c in MACRO]]
            calendar=nyse_sessions(pd.Timestamp('2018-07-05').date(),pd.Timestamp('2026-09-02').date())
            all_results,contexts,coverage=[] ,[],[]
            for count in (10,20,50):
                atomic_json(output/'progress.json',dict(status='RUNNING',phase='univariate_statistics',top=count))
                results,known=feature_statistics(pool,columns,count,calendar)
                all_results.extend(results)
                contexts.extend(temporal_context(pool,columns,count))
                for period in PERIODS:
                    selected=pool.loc[pool.oracle_rank.le(count)&pool.period.eq(period)]
                    observed=known.loc[known.period.eq(period)]
                    coverage.append(dict(top=count,period=period,selected=len(selected),dates=int(selected.date.nunique()),
                        j_qualified=int(selected.selected.sum()),known_labels=len(observed),
                        evaluated_label_coverage=len(observed)/len(selected) if len(selected) else 0.,
                        tp_count=int(observed[TARGET].eq(1).sum()),tp_pct=float(100*observed[TARGET].mean()) if len(observed) else None,
                        outcomes=selected.long_outcome.fillna('ABSENT_LABEL').value_counts().to_dict(),
                        unknown_reasons=selected.path_quality_reason.fillna('ABSENT_LABEL').value_counts().to_dict()))
                LOG.info('Finished TOP%d: %d features, %d pre-external probes',count,len(results),sum(r['probe_selected_before_external'] for r in results))
            selected=[r for r in all_results if r['top']==10 and r['probe_selected_before_external']]
            stable=[r for r in selected if r['external_stability_pass']]
            verdict='MONOTONE_ASSOCIATION_TO_CONFIRM_NOT_ALPHA' if stable else 'NO_STABLE_UNIVARIATE_ENTRY_SEPARATION'
            result=dict(status='COMPLETED_EXPLORATORY',verdict=verdict,rules=RULES,coverage=coverage,
                features=all_results,temporal_context=contexts,primary_pre_external_probes=[r['feature'] for r in selected],
                primary_external_stable=[r['feature'] for r in stable],
                source_protocol_sha256=digest(output/'protocol.json'),
                limitations=['no fitting, calibrating, threshold optimization, portfolio replay or PnL change',
                    'other class includes positive expirations; this is TP-before-SL separability, not exact net-win prediction',
                    'current adjusted price archives; date-causal feature calculations are not certified historical provider vintages',
                    'macro created_at/updated_at are storage times, not publication/availability; no strict historical PIT certification',
                    'selector-derived fields lineage reserved; no consensus/news tested outside the frozen archived profile',
                    'daily conditional AUC omits single-class/sparse dates; their coverage is reported',
                    '63-session sign-flip blocks approximate dependence, not independent observations or proof of tradeable alpha',
                    'overlapping twenty-session outcomes, repeated symbols and nested TOPs',
                    '2023 only existing OOF through July 7; 2026 through September 2, not full years',
                    '2024-2026 already examined; exploratory confirmation, not virgin holdouts'],
                no_training=True,no_backtest=True,no_sql_writes=True,no_broker_calls=True,no_promotion=True)
            records=[]
            for r in all_results:
                for name,period in r['periods'].items():
                    records.append(dict(feature=r['feature'],top=r['top'],period=name,tier=r['tier'],
                        orientation=r['orientation_frozen_discovery'],p_maxT=r['p_maxT'],
                        pre_external_probe=r['probe_selected_before_external'],external_stable=r['external_stability_pass'],**period))
            pd.DataFrame(records).to_csv(output/'feature-statistics.csv',index=False)
            pd.DataFrame(coverage).to_csv(output/'coverage.csv',index=False)
            lines=['# Oracle parcours — séparabilité conditionnelle TP20 avant SL10','',
                f'Verdict : **{verdict}**.',
                f'{len(protocol["columns"])} features archivées + score de référence + neuf indicateurs macro.',
                f'TOP10 : {len(selected)} pistes sélectionnées sur 2018–2021/2022 ; {len(stable)} passent la confirmation figée.',
                'Pas d’entraînement, de backtest, d’optimisation de seuil ou d’écriture SQL.','',
                '| TOP | Période | Sélectionnés | Labels évaluables | TP20 % |','| ---: | --- | ---: | ---: | ---: |']
            for c in coverage:
                lines.append(f'| {c["top"]} | {c["period"]} | {c["selected"]} | {c["known_labels"]} | {c["tp_pct"]:.2f} |')
            lines+=['','## Features retenues AVANT confirmation','']
            for r in selected:
                lines.append(f'- {r["feature"]} : orientation {r["orientation_frozen_discovery"]:+d}, '
                    f'p maxT={r["p_maxT"]:.3f}, stabilité externe={r["external_stability_pass"]}.')
            if not selected:lines.append('Aucune feature ne passe simultanément les gates figés de découverte et validation.')
            lines+=['','## Limites','',*['- '+s for s in result['limitations']], '',
                'Les meilleurs chiffres des tests ne servent jamais à reselectionner les features.',
                'Macro/variables communes à une date : associations temporelles séparées dans report.json, pas shortlist cross-sectionnelle.',
                'Voir feature-statistics.csv pour toutes les features, couverture, moyennes, médianes et AUC par période.']
            (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
            verify_hashes(Path('.'),protocol['source_hashes'])
            result['source_hashes_verified_after_calculation']=True
            result['files']={p.name:digest(p) for p in output.glob('*') if p.suffix in ('.parquet','.csv','.md')}
            atomic_json(output/'report.json',result)
            atomic_json(output/'progress.json',dict(status='COMPLETED',verdict=verdict))
            LOG.info('Finished: %s',verdict)
            return result
        except Exception as exc:
            atomic_json(output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    run(**vars(args))
