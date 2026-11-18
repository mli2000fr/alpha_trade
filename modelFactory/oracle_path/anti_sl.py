"""Optional B29/H10 first-session LONG SL veto, bound to the Oracle bundle.

Training uses only this bundle's causal OOF TOP10% pool. Serving scores every
Oracle row, but the veto is applied only AFTER a consumer's fixed LONG TOP-N.
Missing causal heads abstain explicitly; corrupt/missing declared artifacts fail.
"""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

PATH_SOURCES=['return_5d','rsi_14','vol_ratio_20_60','range_position_20','rolling_volatility_20_zscore']
FIELDS=['anti_sl_probability','anti_sl_threshold','anti_sl_model_sha256','anti_sl_manifest_sha256',
        'anti_sl_available','anti_sl_status','anti_sl_features_sha256']


@dataclass(frozen=True)
class Contract:
    version:int=1
    oracle_pool_fraction:float=.10
    calibration_quantile:float=.90
    feature_mode:str='B29_PATH10_44'
    target:str='LONG_FIRST_SESSION_SL'
    stop_loss_pct:float=.05
    missing_policy:str='KEEP_WITH_EXPLICIT_ABSTENTION'


def enabled(protocol):return protocol.get('training_config',{}).get('oracle_path_anti_sl_enabled',False) is True


def require_bundle_route(protocol):
    if enabled(protocol):
        raise ValueError('Ce batch contient un filtre anti-SL automatique après le classement LONG per-symbol. '
            'Utiliser le parcours bundle LONG ; les filtres options/GPT seuls ne rejouent pas ce classement.')


def columns():
    from .directional_features import compact_columns
    return compact_columns('compact_volatility')+[c+'_path10_'+s for c in PATH_SOURCES for s in ['delta','slope','std']]


def path_features(frame,calendar):
    if frame.duplicated('date').any():raise ValueError('Anti-SL: duplicate feature dates')
    a=frame.set_index('date').reindex(calendar);x=np.arange(10,dtype=float)-4.5
    for c in PATH_SOURCES:
        s=pd.to_numeric(a[c],errors='coerce');valid=s.notna().rolling(10).sum().eq(10)
        a[c+'_path10_delta']=(s-s.shift(9)).where(valid)
        a[c+'_path10_slope']=s.rolling(10).apply(lambda v:float(v@x/(x@x)),raw=True).where(valid)
        a[c+'_path10_std']=s.rolling(10).std().where(valid)
    return a.loc[pd.DatetimeIndex(frame.date)].rename_axis('date').reset_index()


def labels(bars,calendar,stop_loss_pct,breaks=()):
    from common.daily_bar_sources import select_daily_bars
    a=select_daily_bars(bars.copy()).set_index('date').reindex(calendar)
    p=a[['open','high','low','close','volume','is_filled']].apply(pd.to_numeric,errors='coerce')
    good=np.isfinite(p).all(axis=1)&p[['open','high','low','close','volume']].gt(0).all(axis=1)&p.is_filled.eq(0)
    good &= p.high.ge(p[['open','close','low']].max(axis=1))&p.low.le(p[['open','close','high']].min(axis=1))
    valid=(good&good.shift(-1,fill_value=False)).to_numpy()[:-2]
    for c in ['instrument_id','data_source','data_adjustment']:
        s=a[c];valid &= (s.notna()&s.eq(s.shift(-1))).to_numpy()[:-2]
        if c!='instrument_id':valid &= ~s.astype(str).str.upper().isin(['UNKNOWN','']).to_numpy()[:-2]
    days=pd.DatetimeIndex(calendar);entry=p.open.shift(-1).to_numpy()[:-2]
    stop=np.array([round(float(v)*(1-stop_loss_pct),2) if np.isfinite(v) else np.nan for v in entry])
    for e in breaks:valid &= ~((days[:-2]<=e.last_predecessor_date)&(days[1:-1]>=e.first_successor_date))
    return pd.DataFrame(dict(date=days[:-2],available=days[2:],first_session_sl=np.where(valid,
        (p.low.shift(-1).to_numpy()[:-2]<=stop).astype(float),np.nan)))


def oof_pool(root,protocol):
    from .train import digest
    from . import SCORE
    parts=[]
    for folder in sorted((Path(root)/'folds').iterdir()):
        if not (folder/'done.json').is_file():continue
        done=json.loads((folder/'done.json').read_text());file=folder/'oof.parquet'
        if done['files'].get('oof.parquet')!=digest(file):raise ValueError('Anti-SL: corrupt OOF fold')
        champion=done['champion'];weight=folder/champion['model_file']
        if done['files'].get(champion['model_file'])!=digest(weight):raise ValueError('Anti-SL: corrupt OOF champion')
        f=pd.read_parquet(file);f['date']=pd.to_datetime(f.date)
        m=done['metrics'];available=max(pd.Timestamp(m[k]) for k in ['train_available_max','val_available_max'])
        if not f.date.gt(available).all():raise ValueError('Anti-SL: future/in-sample Oracle gate')
        parts.append(f[['date','symbol',SCORE]])
    if not parts:raise ValueError('Anti-SL: causal Oracle OOF history required')
    a=pd.concat(parts,ignore_index=True)
    if a.duplicated(['date','symbol']).any() or not a[SCORE].between(0,1).all():raise ValueError('Anti-SL: invalid OOF keys/scores')
    count=max(1,int(np.ceil(len(protocol['universe'])*Contract().oracle_pool_fraction)))
    return a.sort_values(['date',SCORE,'symbol'],ascending=[True,False,True]).groupby('date').head(count)[['date','symbol']]


def fit_head(fit,cal,seed):
    from lightgbm import LGBMClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.linear_model import LogisticRegression
    from .named_prediction import predict_proba
    cols=columns();lo,hi=fit[cols].quantile(.01),fit[cols].quantile(.99)
    x=fit[cols].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
    z=cal[cols].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
    model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True).set_output(transform='pandas'),
        LGBMClassifier(n_estimators=120,max_depth=3,num_leaves=7,learning_rate=.03,min_child_samples=60,
            reg_alpha=1.,reg_lambda=10.,verbosity=-1,n_jobs=1,random_state=seed))
    model.fit(x,fit.first_session_sl.astype(int))
    p=np.clip(predict_proba(model,z,cols)[:,1],1e-6,1-1e-6)
    if np.std(p)<=1e-6:return None
    calibrator=LogisticRegression(C=1.,random_state=seed).fit(np.log(p/(1-p)).reshape(-1,1),cal.first_session_sl.astype(int))
    return dict(model=model,calibrator=calibrator,lo=lo,hi=hi,features=cols)


def train(cfg,root,progress):
    import joblib
    from . import directional as d
    from .train import atomic_json,digest
    from .directional_metrics import predict,classification_metrics
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    root=Path(root);protocol=json.loads((root/'protocol.json').read_text())
    folder=root/'anti_sl';folder.mkdir(exist_ok=True);manifest=folder/'manifest.json'
    if manifest.exists():return load_manifest(root)[0]
    pool=oof_pool(root,protocol);pool.to_parquet(folder/'oof-pool.parquet',index=False)
    bench=pd.read_parquet(root/'directional/benchmark.parquet');parts=[];sources={}
    start,end=pd.Timestamp(cfg.data.training_start_date),pd.Timestamp(cfg.data.training_end_date)
    calendar=nyse_sessions(start.date(),end.date());registry=load_security_discontinuities()
    chunks=sorted((root/'chunks').glob('*/bars.parquet'))
    for n,file in enumerate(chunks):
        bars=pd.read_parquet(file);sources[str(file.relative_to(root))]=digest(file)
        for symbol,g in bars.groupby('symbol'):
            f=path_features(d.panels(g,bench,calendar,feature_mode='compact_volatility'),calendar)
            f=f.merge(labels(g,calendar,protocol['directional_contract']['stop_loss_pct'],registry.get(symbol,())),on='date',validate='one_to_one')
            parts.append(pool[pool.symbol.eq(symbol)].merge(f,on=['date','symbol'],validate='one_to_one'))
        progress('anti_sl_features',n+1,len(chunks),file.parent.name)
    panel=pd.concat(parts,ignore_index=True)
    if panel.duplicated(['date','symbol']).any():raise ValueError('Anti-SL: duplicate training rows')
    panel.to_parquet(folder/'training-panel.parquet',index=False);records=[];skipped=[]
    good=panel[panel.first_session_sl.notna()]
    for year in range(start.year+2,end.year+2):
        boundary=pd.Timestamp(year-1,1,1);limit=pd.Timestamp(year,1,1)
        fit=good[good.date.lt(boundary)&good.available.lt(boundary)]
        cal=good[good.date.ge(boundary)&good.date.lt(limit)&good.available.lt(limit)]
        enough=(len(fit)>=2000 and len(cal)>=500 and fit.first_session_sl.value_counts().reindex([0.,1.],fill_value=0).min()>=30
            and cal.first_session_sl.value_counts().reindex([0.,1.],fill_value=0).min()>=10)
        weights=fit_head(fit,cal,cfg.reproducibility.seed) if enough else None
        if weights is None:
            skipped.append(dict(year=year,reason='INSUFFICIENT_PAST_OOF_OR_CONSTANT_CALIBRATION'));continue
        file=folder/f'head-{year}.joblib';joblib.dump(weights,file,compress=3)
        probabilities=predict(weights,cal)
        records.append(dict(year=year,file=str(file.relative_to(root)),sha256=digest(file),
            threshold=float(np.quantile(probabilities,.90)),available=str(cal.available.max().date()),
            fit_available_max=str(fit.available.max().date()),fit_start=str(fit.date.min().date()),fit_end=str(fit.date.max().date()),
            calibration_start=str(cal.date.min().date()),calibration_end=str(cal.date.max().date()),
            fit_rows=len(fit),calibration_rows=len(cal),calibration=classification_metrics(cal.first_session_sl,probabilities)))
        progress('anti_sl_models',year-start.year-1,end.year-start.year,year)
    if not records:raise ValueError('Aucun modèle anti-SL causal entraîné : historique Oracle OOF insuffisant ; allonger la période.')
    result=dict(status='COMPLETED',schema_version=1,contract=protocol['anti_sl_contract'],features=columns(),
        oracle_protocol_sha256=digest(root/'protocol.json'),directional_manifest_sha256=digest(root/'directional/manifest.json'),
        pool_sha256=digest(folder/'oof-pool.parquet'),training_panel_sha256=digest(folder/'training-panel.parquet'),
        sources=sources,models=records,skipped=skipped,selection_policy='AFTER_FIXED_LONG_TOP_N_NO_REFILL')
    atomic_json(manifest,result);return load_manifest(root)[0]


def load_manifest(root):
    from .train import digest
    root=Path(root);p=json.loads((root/'protocol.json').read_text());path=root/'anti_sl/manifest.json'
    if not enabled(p):raise ValueError('Batch sans tête anti-SL déclarée')
    m=json.loads(path.read_text())
    if (p.get('horizon')!=10 or p.get('directional_contract',{}).get('feature_mode')!='compact_volatility'
        or p.get('directional_contract',{}).get('stop_loss_pct')!=Contract().stop_loss_pct
        or p.get('anti_sl_contract')!=asdict(Contract()) or m.get('contract')!=p['anti_sl_contract']
        or m.get('status')!='COMPLETED' or m.get('features')!=columns()
        or m.get('oracle_protocol_sha256')!=digest(root/'protocol.json')
        or m.get('directional_manifest_sha256')!=digest(root/'directional/manifest.json') or not m.get('models')):
        raise ValueError('Contrat/manifeste anti-SL incompatible ou incomplet')
    years=set()
    for record in m['models']:
        file=(root/record['file']).resolve()
        if not file.is_relative_to(root.resolve()) or record['year'] in years or digest(file)!=record['sha256']:
            raise ValueError('Poids anti-SL absents, dupliqués ou corrompus')
        years.add(record['year']);year=int(record['year'])
        if (not 0<=record['threshold']<=1 or pd.Timestamp(record['fit_available_max'])>=pd.Timestamp(year-1,1,1)
            or pd.Timestamp(record['available'])>=pd.Timestamp(year,1,1)):
            raise ValueError('Calibration anti-SL future ou seuil invalide')
    return m,digest(path)


def score_features(root,scores,features):
    import joblib
    from .directional_metrics import predict
    manifest,checksum=load_manifest(root);heads={r['year']:r for r in manifest['models']};rows=[]
    f=features.set_index(['date','symbol'])
    if f.index.has_duplicates:raise ValueError('Anti-SL: duplicate inference features')
    # Predict once per annual head, rather than once per symbol and session.
    probabilities={};feature_hashes={}
    keys=pd.MultiIndex.from_frame(scores[['date','symbol']])
    present=f.index.intersection(keys)
    for year,record in heads.items():
        subset=present[pd.DatetimeIndex(present.get_level_values('date')).year==year]
        if not len(subset):continue
        weights=joblib.load(Path(root)/record['file'])
        if weights.get('features')!=columns():raise ValueError('Ordre des variables anti-SL incompatible')
        x=f.loc[subset,columns()].reset_index(drop=True)
        for i,(key,prob) in enumerate(zip(subset,predict(weights,x))):
            probabilities[key]=float(prob)
            feature_hashes[key]=hashlib.sha256(x.iloc[[i]].reset_index(drop=True).to_json(orient='split',double_precision=15).encode()).hexdigest()
    for row in scores.itertuples():
        day=pd.Timestamp(row.date);key=(day,row.symbol);record=heads.get(day.year)
        item=dict(date=day,symbol=row.symbol,anti_sl_probability=None,anti_sl_threshold=None,anti_sl_model_sha256=None,
            anti_sl_manifest_sha256=checksum,anti_sl_available=None,anti_sl_status='NO_CAUSAL_MODEL',anti_sl_features_sha256=None)
        if record:
            if pd.Timestamp(record['available'])>=day:raise ValueError('Modèle anti-SL futur')
            item.update(anti_sl_threshold=record['threshold'],anti_sl_model_sha256=record['sha256'],
                anti_sl_available=record['available'],anti_sl_status='INSUFFICIENT_FEATURES')
            if key in probabilities:
                item.update(anti_sl_probability=probabilities[key],anti_sl_status='SCORED',
                    anti_sl_features_sha256=feature_hashes[key])
        rows.append(item)
    return pd.DataFrame(rows)


def apply_filter(frame):
    if not any(c in frame for c in FIELDS):return frame
    if not set(FIELDS)<=set(frame):raise ValueError('Prédictions anti-SL incomplètes ; relancer ML Predict')
    a=frame.copy();p=pd.to_numeric(a.anti_sl_probability,errors='coerce');threshold=pd.to_numeric(a.anti_sl_threshold,errors='coerce')
    known=p.notna()
    if ((a.anti_sl_probability.notna()&~known).any()
        or (a.anti_sl_threshold.notna()&threshold.isna()).any()
        or (known&(~p.between(0,1)|~threshold.between(0,1)|~a.anti_sl_status.eq('SCORED'))).any()
        or (~known&~a.anti_sl_status.isin(['NO_CAUSAL_MODEL','INSUFFICIENT_FEATURES'])).any()):
        raise ValueError('Score/statut anti-SL invalide')
    a['selected_before_anti_sl']=a.selected.copy()
    long=a.selected&(a.side.eq('long') if 'side' in a else True)
    a['anti_sl_rejected']=long&known&p.gt(threshold)
    a.loc[a.anti_sl_rejected,'selected']=False
    if 'retain_long' in a:a.loc[a.anti_sl_rejected,'retain_long']=False
    if 'side' in a:a.loc[a.anti_sl_rejected,'side']='flat'
    if 'rank' in a:a.loc[a.anti_sl_rejected,'rank']=np.nan
    a.loc[a.anti_sl_rejected,'reason']='ANTI_SL_FIRST_SESSION_RISK'
    return a
