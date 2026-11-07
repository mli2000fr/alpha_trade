"""Annual own-stock profitability models inside a path Oracle batch.

Two branches are trained. Serving always ranks LONG only, after a fixed Oracle
TOP-N, with no refill outside that pool. No broker calls or research imports.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import logging
import re

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from .named_prediction import predict_proba as named_predict_proba

LOG = logging.getLogger(__name__)
FEATURES = ['return_5d','return_10d','return_20d','momentum_60','rsi_14','adx_14',
    'atr20_pct','ema20_slope_10','ema50_slope_20','distance_ema20','distance_ema50',
    'range_position_20','range_position_50','vol_ratio_20_60','rolling_volatility_20',
    'relative_strength_20','relative_strength_60','benchmark_return_5','benchmark_return_20',
    'market_volatility_20','market_trend_strength_50']
DELTAS = ['return_5d','rsi_14','vol_ratio_20_60']
INPUTS = FEATURES + [c+'_delta5' for c in DELTAS]
SOURCE = 'oracle_path_long'


@dataclass(frozen=True)
class Settings:
    enabled: bool = False  # UI default only; each batch freezes an explicit opt-in
    oracle_top_n: int = 20
    selected_n: int = 5
    stop_loss_pct: float = .05
    horizon_sessions: int = 10
    fee_per_leg: float = .0008

    def __post_init__(self):
        if type(self.enabled) is not bool or any(type(v) is not int for v in
                (self.oracle_top_n,self.selected_n,self.horizon_sessions)):
            raise ValueError('Bundle parcours : booléen et nombres entiers requis')
        if not 1 <= self.selected_n <= self.oracle_top_n or self.oracle_top_n < 20 or self.horizon_sessions != 10:
            raise ValueError('Bundle parcours : pool >=20, TOP final <= pool, H10 requis')
        for name,lo,hi in [('stop_loss_pct',0,1),('fee_per_leg',0,.1)]:
            v=getattr(self,name)
            if isinstance(v,bool) or not np.isfinite(v) or not lo <= v < hi or (name=='stop_loss_pct' and v==0):
                raise ValueError('Bundle parcours : '+name+' invalide')


def settings():
    from common.config_loader import load_config
    return Settings(**((load_config().get('oracle_path') or {}).get('directional') or {}))


def enabled(protocol):
    return protocol.get('training_config',{}).get('oracle_path_directional_enabled',False) is True


def use_long_selection(protocol, requested=None):
    if requested is not None and type(requested) is not bool:
        raise ValueError('Sélection per-symbol LONG : booléen requis')
    if requested is True and not enabled(protocol):
        raise ValueError('Ce batch ne contient pas de modèles per-symbol LONG ; choisir un bundle parcours')
    return enabled(protocol) if requested is None else requested


def requested(artifacts_dir,batch):
    """Lightweight routing only. Consumers subsequently verify the full contract."""
    from .predict import model_root
    p=model_root(artifacts_dir,batch)/'protocol.json'
    return p.is_file() and enabled(json.loads(p.read_text(encoding='utf-8')))


def panels(bars,benchmark,calendar):
    from common.daily_bar_sources import select_daily_bars
    from modelFactory.features import compute_features
    bars=select_daily_bars(bars.copy()).sort_values('date')
    symbol=str(bars.symbol.iloc[0])
    grid=bars.set_index('date').reindex(calendar).rename_axis('date').reset_index()
    grid['symbol']=symbol
    for c in ['open','high','low','close','adj_close','volume','is_filled']:
        grid[c]=pd.to_numeric(grid[c],errors='coerce')
    if 'vwap' not in grid:grid['vwap']=grid.close
    good=(grid[['open','high','low','close']].notna().all(axis=1)
          &grid[['open','high','low','close']].gt(0).all(axis=1)&grid.is_filled.eq(0)
          &grid.volume.gt(0)&grid.instrument_id.notna())
    grid.loc[~good,['open','high','low','close','adj_close','volume','vwap']]=np.nan
    f=compute_features(grid,benchmark_df=benchmark,feature_set='expert',include_factors=False)
    f=f.set_index('date').reindex(calendar)
    for c in DELTAS:
        f[c+'_delta5']=(f[c]-f[c].shift(5)).where(f[c].notna().rolling(6).sum().eq(6))
    f=f.rename_axis('date').reset_index()[['date',*INPUTS]]
    f['symbol']=symbol
    recent=good.rolling(60,min_periods=60).sum().eq(60).to_numpy()
    return f.loc[recent & f[INPUTS].notna().mean(axis=1).ge(.8)].copy()


def labels(bars,calendar,contract,breaks=()):
    """Net outcome after SL or open11, fully mature and identity/source qualified.

    SHORT excludes borrow/dividend/locate costs and is archived, never traded.
    Even an early stop label is conservatively available only on open11.
    """
    a=bars.set_index('date').reindex(calendar)
    k=contract.horizon_sessions
    if len(a)<k+2:return pd.DataFrame(columns=['date','available','long','short'])
    raw=a[['open','high','low','close','adj_close','volume','is_filled']].apply(pd.to_numeric,errors='coerce')
    factor=raw.adj_close.fillna(raw.close)/raw.close
    p=raw[['open','high','low','close']].multiply(factor,axis=0)
    good=(np.isfinite(p).all(axis=1)&p.gt(0).all(axis=1)&factor.gt(0)
        &p.high.ge(p[['open','low','close']].max(axis=1))
        &p.low.le(p[['open','high','close']].min(axis=1))&raw.volume.gt(0)&raw.is_filled.eq(0))
    window=np.lib.stride_tricks.sliding_window_view
    valid=window(good.to_numpy(),k+2).all(axis=1)
    for c in ['instrument_id','data_source','data_adjustment']:
        codes=pd.factorize(a[c])[0]
        w=window(codes,k+2)
        valid &= (w==w[:,:1]).all(axis=1)&(w[:,0]>=0)
        if c!='instrument_id':
            valid &= ~window(a[c].astype(str).str.upper().isin(['UNKNOWN','']).to_numpy(),k+2).any(axis=1)
    o=window(p.open.to_numpy(float),k+2)
    hi=window(p.high.to_numpy(float),k+2)
    low=window(p.low.to_numpy(float),k+2)
    closes=window(p.close.to_numpy(float),k+2)
    ratios=closes[:,1:]/closes[:,:-1]
    valid &= ~((ratios>=20)|(ratios<=.05)).any(axis=1)
    n=len(valid);days=pd.DatetimeIndex(calendar[:n]);exits=pd.DatetimeIndex(calendar[k+1:])
    for e in breaks:valid &= ~((days<=e.last_predecessor_date)&(exits>=e.first_successor_date))
    out=pd.DataFrame(dict(date=days,available=exits))
    entry=o[:,1];fee=contract.fee_per_leg
    for side in ['long','short']:
        stop=entry*(1-contract.stop_loss_pct if side=='long' else 1+contract.stop_loss_pct)
        hit=(low[:,1:k+1]<=stop[:,None]) if side=='long' else (hi[:,1:k+1]>=stop[:,None])
        first=np.argmax(hit,axis=1)+1
        gap=o[np.arange(n),first]
        stopped=np.minimum(gap,stop) if side=='long' else np.maximum(gap,stop)
        exit_price=np.where(hit.any(axis=1),stopped,o[:,k+1])
        net=(exit_price*(1-fee)-entry*(1+fee)) if side=='long' else (entry*(1-fee)-exit_price*(1+fee))
        out[side]=np.where(valid,(net>0).astype(float),np.nan)
    return out


def split(panel,year,side):
    a,b=pd.Timestamp(f'{year-1}-01-01'),pd.Timestamp(f'{year}-01-01')
    good=panel[panel[side].notna()]
    return (good[good.date.lt(a)&good.available.lt(a)],
            good[good.date.ge(a)&good.date.lt(b)&good.available.lt(b)])


def train(cfg,engine,root,progress):
    import joblib
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.linear_model import LogisticRegression
    from lightgbm import LGBMClassifier
    from modelFactory.data_loader import load_benchmark_bars
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    from .train import atomic_json,digest
    root=Path(root)
    protocol=json.loads((root/'protocol.json').read_text())
    contract=Settings(**protocol['directional_contract'])
    folder=root/'directional';folder.mkdir(exist_ok=True)
    marker=folder/'manifest.json'
    if marker.exists():
        previous=json.loads(marker.read_text())
        if previous.get('status')=='COMPLETED':
            return load_manifest(root)[0]  # validates every immutable model before resume
    atomic_json(marker,dict(status='RUNNING',oracle_protocol_sha256=digest(root/'protocol.json')))
    start,end=pd.Timestamp(cfg.data.training_start_date),pd.Timestamp(cfg.data.training_end_date)
    calendar=nyse_sessions(start.date(),end.date())
    bench=load_benchmark_bars(engine,benchmark_symbol=cfg.data.benchmark_symbol,start_date=str(start.date()),end_date=str(end.date()))
    benchmark_file=folder/'benchmark.parquet'
    bench.to_parquet(benchmark_file,index=False)
    registry=load_security_discontinuities()
    records=[];sources={};skipped=[];oos_files=[]
    files=sorted((root/'chunks').glob('*/bars.parquet'))
    total=len(protocol['universe']);done=0
    for file in files:
        sources[str(file.relative_to(root))]=digest(file)
        bars=pd.read_parquet(file);chunk_predictions=[]
        for symbol,g in bars.groupby('symbol'):
            if not re.fullmatch(r'[A-Z0-9.^_-]+',symbol):raise ValueError('Symbole de modèle invalide')
            progress('directional',done,total,symbol);done+=1
            f=panels(g,bench,calendar)
            panel=f.merge(labels(g,calendar,contract,registry.get(symbol,())),on='date',validate='one_to_one')
            for year in range(start.year+2,end.year+2):
                for side in ['long','short']:
                    fit,cal=split(panel,year,side)
                    if (len(fit)<756 or len(cal)<126 or
                        fit[side].value_counts().reindex([0.,1.],fill_value=0).min()<40 or
                        cal[side].value_counts().reindex([0.,1.],fill_value=0).min()<15):
                        skipped.append(dict(symbol=symbol,year=year,side=side,reason='INSUFFICIENT_HISTORY_OR_CLASSES'))
                        continue
                    lo,hi=fit[INPUTS].quantile(.01),fit[INPUTS].quantile(.99)
                    x=fit[INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
                    z=cal[INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
                    model=make_pipeline(SimpleImputer(strategy='median').set_output(transform='pandas'),LGBMClassifier(
                        n_estimators=120,max_depth=3,num_leaves=7,learning_rate=.03,
                        min_child_samples=60,reg_alpha=1.,reg_lambda=10.,verbosity=-1,n_jobs=1,
                        random_state=cfg.reproducibility.seed))
                    model.fit(x,fit[side].astype(int))
                    cp=np.clip(named_predict_proba(model,z,INPUTS)[:,1],1e-6,1-1e-6)
                    if np.std(cp)<=1e-6:
                        skipped.append(dict(symbol=symbol,year=year,side=side,reason='CONSTANT_CALIBRATION'))
                        continue
                    calibrator=LogisticRegression(C=1.,random_state=cfg.reproducibility.seed)
                    calibrator.fit(np.log(cp/(1-cp)).reshape(-1,1),cal[side].astype(int))
                    path=folder/symbol/f'{side}-{year}.joblib';path.parent.mkdir(exist_ok=True)
                    weights=dict(model=model,calibrator=calibrator,lo=lo,hi=hi)
                    joblib.dump(weights,path,compress=3)
                    record=dict(symbol=symbol,year=year,side=side,file=str(path.relative_to(root)),
                        sha256=digest(path),fit_start=str(fit.date.min().date()),fit_end=str(fit.date.max().date()),
                        fit_available_max=str(fit.available.max().date()),calibration_start=str(cal.date.min().date()),
                        calibration_end=str(cal.date.max().date()),available=str(cal.available.max().date()),
                        fit_rows=len(fit),calibration_rows=len(cal))
                    from .directional_metrics import model_metrics
                    record['metrics'],predictions=model_metrics(panel,weights,record,calendar,end)
                    if len(predictions):chunk_predictions.append(predictions)
                    records.append(record)
                    LOG.info('Parcours per-symbol %s %s %d entraîné fit=%d cal=%d',symbol,side,year,len(fit),len(cal))
        if chunk_predictions:
            frame=pd.concat(chunk_predictions,ignore_index=True)
            path=folder/'oos'/f'{file.parent.name}.parquet';path.parent.mkdir(exist_ok=True)
            frame.to_parquet(path,index=False)
            oos_files.append(dict(path=str(path.relative_to(root)),sha256=digest(path),rows=len(frame)))
    if not any(r['side']=='long' for r in records):raise ValueError('Aucun modèle LONG annuel qualifié')
    result=dict(status='COMPLETED',schema_version=1,contract=asdict(contract),features=INPUTS,
        oracle_protocol_sha256=digest(root/'protocol.json'),source_hashes=sources,models=records,skipped=skipped,
        benchmark_file=str(benchmark_file.relative_to(root)),benchmark_sha256=digest(benchmark_file),
        oos_files=oos_files,
        selection_policy='ORACLE_TOP_N_THEN_LONG_TOP_N_NO_REFILL',serving_side='long',
        short_limitations='No borrow, locate or dividend costs; archived branch only')
    atomic_json(marker,result)
    return result


def load_manifest(root):
    from .train import digest
    root=Path(root);path=root/'directional/manifest.json'
    m=json.loads(path.read_text(encoding='utf-8'))
    p=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    if (not enabled(p) or p.get('horizon')!=10 or m.get('status')!='COMPLETED' or m.get('oracle_protocol_sha256')!=digest(root/'protocol.json')
        or m.get('features')!=INPUTS or m.get('contract')!=p.get('directional_contract')
        or m.get('serving_side')!='long'):
        raise ValueError('Bundle parcours directionnel absent/incomplet/incompatible')
    Settings(**m['contract'])
    if m.get('benchmark_file'):
        benchmark=(root/m['benchmark_file']).resolve()
        if not benchmark.is_relative_to(root.resolve()) or digest(benchmark)!=m.get('benchmark_sha256'):
            raise ValueError('Benchmark directionnel absent/corrompu')
    keys=set()
    for r in m['models']:
        key=(r['symbol'],r['year'],r['side'])
        path=(root/r['file']).resolve()
        if (key in keys or not path.is_relative_to(root.resolve()) or r['symbol'] not in p['universe']
            or r['side'] not in ['long','short'] or digest(path)!=r['sha256']
            or not pd.Timestamp(r['fit_available_max'])<pd.Timestamp(f"{r['year']-1}-01-01")
            or not pd.Timestamp(r['available'])<pd.Timestamp(f"{r['year']}-01-01")):
            raise ValueError('Modèle par titre corrompu ou non causal')
        keys.add(key)
    return m,digest(root/'directional/manifest.json')


def rank(scores,probabilities,contract):
    """Rank full observable amplitude universe, THEN consult own-stock LONG only."""
    a=scores.copy().rename(columns={'trade_date':'date'})
    a['date']=pd.to_datetime(a.date).dt.normalize()
    if a.duplicated(['date','symbol']).any() or not a.proba_extreme.between(0,1).all():
        raise ValueError('Oracle dupliqué ou score invalide')
    a=a.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True])
    a['oracle_rank']=a.groupby('date').cumcount()+1
    a=a.merge(probabilities,on=['date','symbol'],how='left',validate='one_to_one')
    eligible=a.oracle_rank.le(contract.oracle_top_n)&a.long_probability.notna()
    if not a.loc[eligible,'long_probability'].between(0,1).all():raise ValueError('Probabilité LONG invalide')
    ranked=a[eligible].sort_values(['date','long_probability','oracle_rank','symbol'],ascending=[True,False,True,True])
    # Join on decision keys, never depend on positional index alignment.
    ranks=ranked[['date','symbol']].assign(_rank=ranked.groupby('date').cumcount()+1)
    a=a.merge(ranks,on=['date','symbol'],how='left',validate='one_to_one').rename(columns={'_rank':'long_rank'})
    a['selected']=a.long_rank.le(contract.selected_n)
    a['reason']=np.where(a.oracle_rank.gt(contract.oracle_top_n),'OUTSIDE_ORACLE_POOL',
        np.where(a.long_probability.isna(),'MISSING_CAUSAL_LONG_MODEL_OR_FEATURES',
        np.where(a.selected,'SELECTED_LONG','BELOW_LONG_TOP_N')))
    return a


def infer(engine,root,scores):
    import joblib
    from .labels import load_bars
    from modelFactory.data_loader import load_benchmark_bars
    from modelFactory.oracle.build_labels import nyse_sessions
    m,checksum=load_manifest(root);c=Settings(**m['contract'])
    scores=scores.copy();scores['date']=pd.to_datetime(scores.date).dt.normalize()
    first,last=scores.date.min(),scores.date.max();start=first-pd.Timedelta(days=650)
    protocol=json.loads((Path(root)/'protocol.json').read_text())
    bench=load_benchmark_bars(engine,benchmark_symbol=protocol['training_config']['data']['benchmark_symbol'],
        start_date=str(start.date()),end_date=str(last.date()))
    calendar=nyse_sessions(start.date(),last.date())
    records={(r['symbol'],r['year'],r['side']):r for r in m['models']}
    names=sorted(set(scores.symbol));out=[];cache={}
    for offset in range(0,len(names),25):
        bars=load_bars(engine,names[offset:offset+25],str(start.date()),str(last.date()))
        for symbol,g in bars.groupby('symbol'):
            f=panels(g,bench,calendar);f=f[f.date.between(first,last)].set_index('date')
            for row in scores[scores.symbol.eq(symbol)].itertuples():
                item=dict(date=row.date,symbol=symbol,long_probability=None,short_probability=None,long_model_sha256=None,short_model_sha256=None)
                for side in ['long','short']:
                    record=records.get((symbol,row.date.year,side))
                    if record is None or row.date not in f.index:continue
                    if pd.Timestamp(record['available'])>=row.date:raise ValueError('Modèle directionnel futur')
                    # Models are local, hashed artifacts of the selected batch, never user uploads.
                    if record['file'] not in cache:cache[record['file']]=joblib.load(Path(root)/record['file'])
                    weights=cache[record['file']]
                    x=f.loc[[row.date],INPUTS].replace([np.inf,-np.inf],np.nan).clip(weights['lo'],weights['hi'],axis=1)
                    prob=np.clip(named_predict_proba(weights['model'],x,INPUTS)[:,1],1e-6,1-1e-6)
                    item[side+'_probability']=float(weights['calibrator'].predict_proba(np.log(prob/(1-prob)).reshape(-1,1))[0,1])
                    item[side+'_model_sha256']=record['sha256']
                out.append(item)
    cols=['date','symbol','long_probability','short_probability','long_model_sha256','short_model_sha256']
    result=rank(scores,pd.DataFrame(out,columns=cols),c)
    result['manifest_sha256']=checksum
    return result


DDL='''CREATE TABLE IF NOT EXISTS alpha_trade.oracle_path_directional_predictions (
 prediction_date DATE NOT NULL, symbol VARCHAR(20) NOT NULL, batch_id VARCHAR(255) NOT NULL,
 long_probability DOUBLE NULL, short_probability DOUBLE NULL,
 long_model_sha256 CHAR(64) NULL, short_model_sha256 CHAR(64) NULL,
 manifest_sha256 CHAR(64) NOT NULL, oracle_rank INT NOT NULL, long_rank INT NULL,
 selected BOOLEAN NOT NULL, reason VARCHAR(80) NOT NULL,
 updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
 PRIMARY KEY (prediction_date,symbol,batch_id)
)'''


def write_predictions(engine,frame,batch_id):
    cols=['long_probability','short_probability','long_model_sha256','short_model_sha256',
          'manifest_sha256','oracle_rank','long_rank','selected','reason']
    rows=[]
    for r in frame.to_dict('records'):
        row={k:(None if pd.isna(r[k]) else r[k]) for k in cols}
        row.update(prediction_date=str(pd.Timestamp(r['date']).date()),symbol=r['symbol'],batch_id=batch_id)
        rows.append(row)
    insert=text('INSERT INTO alpha_trade.oracle_path_directional_predictions ('+
        ','.join(['prediction_date','symbol','batch_id',*cols])+') VALUES ('+
        ','.join(':'+k for k in ['prediction_date','symbol','batch_id',*cols])+') ON DUPLICATE KEY UPDATE '+
        ','.join(k+'=VALUES('+k+')' for k in cols))
    with engine.begin() as conn:
        conn.execute(text(DDL))
        if rows:conn.execute(insert,rows)
    LOG.info('Bundle parcours batch=%s : %d lignes, %d sélectionnées LONG, aucune sélection SHORT',
             batch_id,len(rows),int(frame.selected.sum()))


def validate_saved(root,oracle,saved):
    """Read-only consumers recompute the complete TOP20/TOP5 and verify lineage."""
    m,checksum=load_manifest(root);c=Settings(**m['contract'])
    a=oracle.copy().rename(columns={'trade_date':'date','prediction_date':'date'})
    a['date']=pd.to_datetime(a.date).dt.normalize()
    b=saved.copy().rename(columns={'prediction_date':'date'})
    b['date']=pd.to_datetime(b.date).dt.normalize()
    if (b.duplicated(['date','symbol']).any() or len(a)!=len(b)
        or set(zip(a.date,a.symbol))!=set(zip(b.date,b.symbol)) or not b.manifest_sha256.eq(checksum).all()):
        raise ValueError('Prédictions directionnelles incomplètes/dupliquées/autre contrat')
    records={(r['symbol'],r['year'],r['side']):r for r in m['models']}
    for r in b.itertuples():
        for side in ['long','short']:
            prob=getattr(r,side+'_probability');checksum_model=getattr(r,side+'_model_sha256')
            if pd.isna(prob):
                if pd.notna(checksum_model):raise ValueError('Score absent avec modèle annoncé')
                continue
            record=records.get((r.symbol,r.date.year,side))
            if (record is None or checksum_model!=record['sha256'] or not 0<=float(prob)<=1
                or pd.Timestamp(record['available'])>=r.date):
                raise ValueError('Score directionnel non causal ou autre modèle')
    columns=['date','symbol','long_probability','short_probability','long_model_sha256','short_model_sha256']
    computed=rank(a,b[columns],c).sort_values(['date','symbol']).reset_index(drop=True)
    archived=b.sort_values(['date','symbol']).reset_index(drop=True)
    for col in ['oracle_rank','long_rank','selected','reason']:
        if not computed[col].fillna(-1).eq(archived[col].fillna(-1)).all():
            raise ValueError('Classement directionnel archivé incompatible : '+col)
    return computed


def read_predictions(engine,root,oracle,batch_id,*,cutoff=None):
    from datetime import datetime,timezone
    a=oracle.copy().rename(columns={'trade_date':'date','prediction_date':'date'})
    days=pd.to_datetime(a.date)
    now=cutoff or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Cutoff directionnel UTC requis')
    mysql=engine.dialect.name=='mysql'
    predicate='UNIX_TIMESTAMP(updated_at)<=:epoch' if mysql else 'updated_at<=:cutoff'
    query=text('SELECT * FROM oracle_path_directional_predictions WHERE batch_id=:batch '
        'AND prediction_date BETWEEN :start AND :end AND symbol IN :symbols AND '+predicate
        ).bindparams(bindparam('symbols',expanding=True))
    with engine.connect() as conn:
        saved=pd.read_sql(query,conn,params=dict(batch=batch_id,start=days.min().date(),end=days.max().date(),
            symbols=sorted(set(a.symbol)),epoch=now.timestamp(),cutoff=now.astimezone(timezone.utc).replace(tzinfo=None)))
    return validate_saved(root,a,saved)


def selected_predictions(engine,root,oracle,batch_id):
    a=read_predictions(engine,root,oracle,batch_id)
    return a[a.selected].sort_values(['date','long_rank']).copy()
