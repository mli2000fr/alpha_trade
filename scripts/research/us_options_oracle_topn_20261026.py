"""US options equal mix conditional on original Oracle TOP10/20/50, no fitting."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
from sqlalchemy import text,bindparam
from scripts.research import us_options_equal_mix_20261026 as b

PARENT=Path('artifacts/research/us_options_equal_mix/20261026-v2')
OUTPUT=Path('artifacts/research/us_options_oracle_topn/20261026-v1')
DOC=Path('doc/ml/options_oracle_topn_protocole_20261026.md')
TEST=Path('tests/test_us_options_oracle_topn_20261026.py')
BATCHES={'2026-09':'model-factory-20261014113232-bc35a7',
         '2026-10':'model-factory-20261016180250-3b0515'}


def verify_parent():
    seal=b.read(PARENT/'seal.json')
    for name,sha in seal['files'].items():
        if b.digest(PARENT/name)!=sha:raise ValueError('Parent output changed: '+name)
    for name,sha in seal['sources'].items():
        if b.digest(name)!=sha:raise ValueError('Parent source changed: '+name)
    return {str(PARENT/'seal.json'):b.digest(PARENT/'seal.json')}


def snapshot(output):
    sources=verify_parent()
    output.mkdir(parents=True,exist_ok=False)
    parent=b.read(PARENT/'protocol.json');cutoff=pd.Timestamp(parent['cutoff'])
    from modelFactory.oracle_path.predict import load_contract
    models={}
    for batch in BATCHES.values():
        root,p,profile,folds=load_contract('artifacts/models',batch)
        if p['target']!='oracle_path_extreme20' or p['horizon']!=20:raise ValueError('Not path H20')
        models[batch]=dict(folds=folds,profile_sha256=b.digest(root/'feature_profile.json'))
        for file in [root/'protocol.json',root/'feature_profile.json',root/'report.json']:
            sources[str(file)]=b.digest(file)
        for fold in folds.values():sources[fold['model_file']]=b.digest(fold['model_file'])
    sources.update({str(p):b.digest(p) for p in [Path(__file__),DOC,TEST,b.UNIVERSE,
        Path('modelFactory/oracle_path/predict.py')]})
    protocol=dict(created_at_utc=pd.Timestamp.now(tz='UTC'),data_cutoff=cutoff,
        parent=str(PARENT),sources=sources,models=models,batch_policy=BATCHES,
        ranks=[10,20,50],ranking='Oracle score desc, symbol asc BEFORE options/labels',
        minimum_daily_coverage=.95,weights=dict(volume=.5,oi=.5),training=False,
        new_inference=False,SQL_writes=False,provider_calls=0,LLM_calls=0,
        oracle_horizon=20,outcome_horizons=[5,10,20],independent_holdout=False)
    b.write(output/'protocol.json',protocol)
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine()
    if engine.url.database!='alpha_trade':raise ValueError('US database only')
    sql='''SELECT p.prediction_date signal_day,p.symbol,p.proba_extreme,p.fold_start,
        p.batch_id,p.created_at prediction_created_at,l.fold_start lineage_fold_start,
        l.model_available_date,l.target_name,l.target_horizon,l.model_sha256,
        l.feature_profile_sha256,l.created_at lineage_created_at
        FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l
        ON l.prediction_date=p.prediction_date AND l.symbol=p.symbol AND l.batch_id=p.batch_id
        WHERE p.batch_id IN :batches AND p.prediction_date BETWEEN '2026-09-10' AND '2026-10-23'
        AND p.created_at<=:cutoff'''
    try:
        with engine.connect() as conn:
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':raise ValueError('Wrong schema')
            rows=[dict(r) for r in conn.execute(text(sql).bindparams(bindparam('batches',expanding=True)),
                dict(batches=list(BATCHES.values()),cutoff=cutoff.tz_localize(None).to_pydatetime())).mappings()]
            conn.rollback()
    finally:engine.dispose()
    pd.DataFrame(rows).to_parquet(output/'oracle-scores.parquet',index=False)
    b.write(output/'snapshot-seal.json',dict(files={n:b.digest(output/n) for n in ['protocol.json','oracle-scores.parquet']}))
    print('Oracle rows='+str(len(rows)),flush=True)


def rank_oracle(scores,symbols,models,cal):
    scores=scores.copy()
    scores['signal_day']=pd.to_datetime(scores.signal_day)
    scores=scores[scores.symbol.isin(symbols)].copy()
    scores=scores[scores.signal_day.dt.strftime('%Y-%m').map(BATCHES).eq(scores.batch_id)]
    if scores.duplicated(['signal_day','symbol']).any():raise ValueError('Duplicate Oracle scores')
    scores['proba_extreme']=pd.to_numeric(scores.proba_extreme,errors='coerce')
    if not (np.isfinite(scores.proba_extreme)&scores.proba_extreme.between(0,1)).all():raise ValueError('Bad Oracle score')
    for r in scores.to_dict('records'):
        if pd.isna(r['fold_start']) or pd.isna(r['lineage_fold_start']):raise ValueError('Missing Oracle lineage')
        name=str(pd.Timestamp(r['fold_start']).date());model=models[r['batch_id']];fold=model['folds'][name]
        metrics=fold['metrics'];day=pd.Timestamp(r['signal_day'])
        available=max(pd.Timestamp(metrics[k]) for k in ['train_available_max','val_available_max'])
        if (not available<day or pd.Timestamp(name)>day or pd.Timestamp(r['lineage_fold_start'])!=pd.Timestamp(name)
            or pd.Timestamp(r['model_available_date'])!=available.normalize()
            or r['target_name']!='oracle_path_extreme20' or r['target_horizon']!=20
            or r['model_sha256']!=fold['model_sha256'] or r['feature_profile_sha256']!=model['profile_sha256']):
            raise ValueError('Incompatible/future Oracle model')
    ordered=scores.sort_values(['signal_day','proba_extreme','symbol'],ascending=[True,False,True],kind='stable')
    coverage=ordered.groupby('signal_day').size().rename('scored_count').reset_index()
    coverage['qualified']=coverage.scored_count.ge(.95*len(symbols))
    ordered=ordered.merge(coverage,on='signal_day',validate='many_to_one')
    ordered['oracle_rank']=ordered.groupby('signal_day').cumcount()+1
    ordered=ordered[ordered.qualified].copy()
    dates=list(cal.day);nextday={d:dates[i+1] for i,d in enumerate(dates[:-1])}
    ordered['entry_day']=ordered.signal_day.map(nextday)
    if ordered.entry_day.isna().any():raise ValueError('Missing official next session')
    opened=cal.set_index('day').opened
    ordered['decision_at']=ordered.entry_day.map(opened)-pd.Timedelta(minutes=5)
    ordered['physically_observed_before_decision']=(
        pd.to_datetime(ordered.prediction_created_at,utc=True).lt(ordered.decision_at)
        &pd.to_datetime(ordered.lineage_created_at,utc=True).lt(ordered.decision_at))
    ordered['entry_day']=ordered.entry_day.dt.strftime('%Y-%m-%d')
    return ordered,coverage


def cohort(topn,features,labels):
    selected=features.merge(topn[b.KEY+['oracle_rank','physically_observed_before_decision']],
        on=b.KEY,how='inner',validate='one_to_one')
    scored=b.score_candidates(selected)
    scored=scored.merge(selected[b.KEY+['oracle_rank','physically_observed_before_decision']],on=b.KEY,validate='one_to_one')
    # Original scores are replaced by ranks of the observable TOPN cohort only.
    outcomes=labels.drop(columns=b.SCORES,errors='ignore')
    result=outcomes.merge(scored[b.KEY+b.SCORES+['oracle_rank','physically_observed_before_decision']],
        on=b.KEY,validate='many_to_one')
    return scored,result


def summarize(frame,decision_days,cal):
    result={}
    for h in [5,10,20]:
        f=frame[frame.horizon.eq(h)]
        first=frame.sort_values(b.KEY).drop_duplicates('symbol')[b.KEY]
        spaced=b.spaced_dates(decision_days,h,cal)
        strict=f[f.physically_observed_before_decision]
        result[str(h)]=dict(all=b.metrics(f),strict_created_before_decision=b.metrics(strict),
            nonoverlap_dates=spaced,nonoverlap=b.metrics(f[f.entry_day.isin(spaced)]),
            first_per_symbol=b.metrics(f.merge(first,on=b.KEY,validate='many_to_one')))
    return result


def analyze(output):
    if (output/'report.json').exists():raise FileExistsError('Immutable report')
    verify_parent();protocol=b.read(output/'protocol.json');seal=b.read(output/'snapshot-seal.json')
    for n,sha in seal['files'].items():
        if b.digest(output/n)!=sha:raise ValueError('Snapshot changed')
    for n,sha in protocol['sources'].items():
        if b.digest(n)!=sha:raise ValueError('Frozen source changed '+n)
    parent=b.read(PARENT/'protocol.json');symbols=parent['symbols']
    cal=pd.read_parquet(PARENT/'calendar.parquet')
    raw=pd.read_parquet(output/'oracle-scores.parquet')
    ranked,coverage=rank_oracle(raw,symbols,protocol['models'],cal)
    ranked.to_parquet(output/'oracle-ranked.parquet',index=False)
    coverage.to_parquet(output/'oracle-date-coverage.parquet',index=False)
    all_days=[str(d.date()) for d in cal.loc[cal.day.between(pd.Timestamp('2026-09-14'),pd.Timestamp('2026-10-23')),'day']]
    report=dict(status='COMPLETED_EXPLORATORY_CONDITIONAL_NO_PROMOTION',model_policy=BATCHES,
        oracle_horizon=20,missing_oracle_signal_days=sorted(set(all_days)-set(ranked.signal_day.dt.strftime('%Y-%m-%d'))),
        retrospective_reconstruction_not_strict_PIT=True,source_results={})
    for source in ['eodhd_eod','alpaca_sip']:
        features=pd.read_parquet(PARENT/source/'features.parquet')
        labels=pd.read_parquet(PARENT/source/'protected-paths.parquet')
        report['source_results'][source]={}
        for n in [10,20,50]:
            selected=ranked[ranked.oracle_rank.le(n)].copy()
            selected.to_parquet(output/f'oracle-top{n}.parquet',index=False)
            scored,panel=cohort(selected,features,labels)
            scored.to_parquet(output/f'{source}-top{n}-asof-scores.parquet',index=False)
            panel.to_parquet(output/f'{source}-top{n}-paths.parquet',index=False)
            joined=selected.merge(scored[b.KEY],on=b.KEY,how='left',indicator=True,validate='one_to_one')
            daily=joined.assign(has_features=joined['_merge'].eq('both')).groupby('entry_day').agg(
                requested=('symbol','size'),options_covered=('has_features','sum')).reset_index()
            item=dict(oracle_candidates=len(selected),oracle_dates=int(selected.entry_day.nunique()),
                covered_asof=len(scored),covered_symbols=int(scored.symbol.nunique()),
                feature_coverage_pct=100*len(scored)/len(selected) if len(selected) else None,
                coverage_daily=daily.to_dict('records'),horizons=summarize(panel,selected.entry_day,cal))
            report['source_results'][source][str(n)]=item
    b.write(output/'report.json',report)
    b.write(output/'seal.json',dict(files={p.name:b.digest(p) for p in output.iterdir()
        if p.is_file() and p.name!='seal.json'},sources=protocol['sources']))
    print(report['status'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True,choices=['snapshot','analyze'])
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args();(snapshot if args.phase=='snapshot' else analyze)(args.output)
