"""Read-only SQL, chronological research of Oracle/ATR tail composition."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text


FEATURES = ['vix_lag1', 'term_lag1', 'vix_change5_lag1', 'sentiment_lag1']


def prepare(raw, maturity):
    frame = raw.sort_values('trade_date').copy()
    if frame.trade_date.duplicated().any():
        raise ValueError('One universe/batch/horizon required')
    frame['trade_date'] = pd.to_datetime(frame.trade_date)
    frame['term'] = frame.vix/frame.vix3m.replace(0, np.nan)
    frame['vix_change5'] = frame.vix/frame.vix.shift(5)-1
    for source, target in [('vix','vix_lag1'),('term','term_lag1'),
                           ('vix_change5','vix_change5_lag1'),('sentiment_score','sentiment_lag1'),
                           ('regime_mode','regime_lag1')]:
        frame[target] = frame[source].shift(1)
    frame['feature_session'] = frame.trade_date.shift(1)
    frame['tail_count'] = frame.d1_count+frame.d10_count
    frame['tail_share'] = frame.d10_count/frame.tail_count.replace(0, np.nan)
    frame['d10_fraction'] = frame.d10_count/frame.evaluated_count.replace(0,np.nan)
    frame['d1_fraction'] = frame.d1_count/frame.evaluated_count.replace(0,np.nan)
    frame['tail_fraction'] = frame.tail_count/frame.evaluated_count.replace(0,np.nan)
    maturity = maturity.copy()
    maturity['trade_date'] = pd.to_datetime(maturity.trade_date)
    maturity['label_mature_at'] = pd.to_datetime(maturity.label_mature_at)
    frame = frame.merge(maturity, on='trade_date', how='left', validate='one_to_one')
    frame['eligible'] = (frame.unknown_count.eq(0)&frame.evaluated_count.gt(0)&frame.tail_count.ge(20)
        &frame[FEATURES].notna().all(axis=1)&frame.label_mature_at.notna()
        &frame.label_mature_at.gt(frame.trade_date)&frame.feature_session.lt(frame.trade_date))
    return frame


def training_mask(frame, test_start):
    return frame.eligible & frame.trade_date.lt(test_start) & frame.label_mature_at.lt(test_start)


def metrics(y,pred):
    y,pred = np.asarray(y,float),np.asarray(pred,float)
    return {'days':len(y),'mae_pp':float(np.mean(np.abs(y-pred))*100),
        'mse':float(np.mean((y-pred)**2)), 'pred_std':float(np.std(pred)),
        'correlation':float(np.corrcoef(y,pred)[0,1]) if np.std(y)>0 and np.std(pred)>1e-10 else None}


def block_ci(delta, block=20, draws=1000):
    """Circular moving block bootstrap; descriptive, not independent folds."""
    a=np.asarray(delta,float)
    rng=np.random.default_rng(13002026)
    means=[]
    for _ in range(draws):
        starts=rng.integers(0,len(a),size=int(np.ceil(len(a)/block)))
        indices=np.concatenate([(s+np.arange(block))%len(a) for s in starts])[:len(a)]
        means.append(a[indices].mean())
    return [float(v) for v in np.quantile(means,[.025,.975])]


def evaluate(frame):
    records=[]; folds=[]
    specs={'vix_only':['vix_lag1'], 'vix_term_change':FEATURES[:3], 'vix_term_change_sentiment':FEATURES}
    for year in range(2023,2027):
        start=pd.Timestamp(year,1,1)
        train=frame[training_mask(frame,start)]
        test=frame[frame.eligible & frame.trade_date.dt.year.eq(year)]
        if len(train)<252 or len(test)<30:
            folds.append({'year':year,'status':'INSUFFICIENT_SUPPORT','train':len(train),'test':len(test)})
            continue
        mean=float(train.tail_share.mean())
        regime=train.groupby('regime_lag1').tail_share.mean().to_dict()
        predictions={'historical_mean':np.full(len(test),mean),
            'existing_regime':test.regime_lag1.map(regime).fillna(mean).to_numpy()}
        for name,columns in specs.items():
            model=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),Ridge(alpha=10))
            model.fit(train[columns],train.tail_share)
            predictions[name]=np.clip(model.predict(test[columns]),0,1)
        fold={'year':year,'status':'COMPLETE','train_days':len(train),'test_days':len(test),
            'train_max_label_maturity':str(train.label_mature_at.max()), 'models':{}}
        y=test.tail_share.to_numpy()
        for name,pred in predictions.items():
            score=metrics(y,pred)
            if name not in ('historical_mean','existing_regime'):
                score['paired_mse_delta_vs_mean_ci95']=block_ci((y-pred)**2-(y-predictions['historical_mean'])**2)
                score['paired_mse_delta_vs_regime_ci95']=block_ci((y-pred)**2-(y-predictions['existing_regime'])**2)
            fold['models'][name]=score
        folds.append(fold)
        for i,(_,row) in enumerate(test.iterrows()):
            records.append({'trade_date':str(row.trade_date.date()),'year':year,
                'tail_share':row.tail_share,'d10_fraction':row.d10_fraction,'d1_fraction':row.d1_fraction,
                'tail_fraction':row.tail_fraction,'tail_count':row.tail_count,
                **{name:float(pred[i]) for name,pred in predictions.items()}})
    return folds,pd.DataFrame(records)


def run(output):
    from database.connection import get_sqlalchemy_engine
    output.mkdir(parents=True,exist_ok=False)
    protocol={'primary_target':'d10_count/(d1_count+d10_count) on decision date J, realized at label maturity',
        'feature_timing':'Previous observed NYSE session; historical publication times unverified',
        'eligibility':'unknown_count=0, evaluated>0, tail_count>=20, all four features and maturity available',
        'test_years':[2023,2024,2025,2026], 'train':'Expanding past with max batch label maturity strictly before January 1',
        'models':['historical_mean','existing_regime','vix_only','vix_term_change','vix_term_change_sentiment'],
        'ridge_alpha':10,'no_tuning':True,'bootstrap_block':20,'bootstrap_draws':1000,
        'canonical_writes':False,'serving_changes':False,'not_virgin_confirmation':True,
        'limits':['Batch OOS lineage must be checked before promotion','Macro publication/vintage PIT not certified',
                  'No economic backtest: tail composition is not tradable return','2026 already explored; all results research only'],
        'implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    engine=get_sqlalchemy_engine()
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('US database required')
        raw=pd.read_sql(text('SELECT * FROM oracle_atr_market_regime_daily ORDER BY trade_date'),conn)
        groups=raw[['oracle_batch_id','oracle_horizon','universe_hash']].drop_duplicates()
        if len(groups)!=1:
            raise ValueError('Explicit group selection needed; never mix batches/universes')
        batch=groups.iloc[0]
        maturity=pd.read_sql(text('SELECT prediction_date AS trade_date, MAX(oracle_available_date) AS label_mature_at '
            'FROM global_oracle_labels WHERE batch_id=:batch AND horizon=:horizon GROUP BY prediction_date'),
            conn,params={'batch':batch.oracle_batch_id,'horizon':int(batch.oracle_horizon)})
    raw.to_parquet(output/'raw_snapshot.parquet',index=False)
    maturity.to_parquet(output/'maturity_snapshot.parquet',index=False)
    frame=prepare(raw,maturity)
    frame.to_parquet(output/'daily_features.parquet',index=False)
    correlations={}
    for key in ['vix','vix3m','vix9d','vxn','sentiment_score','ten_y','move','yield_10y_5d_pct']:
        sample=frame[[key,'d10_d1_ratio']].replace([np.inf,-np.inf],np.nan).dropna()
        correlations[key]={'days':len(sample),'pearson':sample[key].corr(sample.d10_d1_ratio),
            'spearman':sample[key].corr(sample.d10_d1_ratio,method='spearman')}
    folds,preds=evaluate(frame)
    preds.to_parquet(output/'oos_predictions.parquet',index=False)
    bands=[]
    for year,part in preds.groupby('year'):
        for lo,hi in [(0,.4),(.4,.5),(.5,.6),(.6,.7),(.7,1.00001)]:
            group=part[part.vix_term_change_sentiment.ge(lo)&part.vix_term_change_sentiment.lt(hi)]
            if len(group):
                bands.append({'year':int(year),'predicted_band':[lo,hi],'days':len(group),
                    'predicted_share':group.vix_term_change_sentiment.mean(),'realized_share':group.tail_share.mean(),
                    'd10_fraction':group.d10_fraction.mean(),'d1_fraction':group.d1_fraction.mean()})
    development=[f for f in folds if f['year']<2026 and f['status']=='COMPLETE']
    stable=bool(development) and all(f['models']['vix_term_change_sentiment']['paired_mse_delta_vs_regime_ci95'][1]<0
        and f['models']['vix_term_change_sentiment']['paired_mse_delta_vs_mean_ci95'][1]<0 for f in development)
    report={'status':'COMPLETE_RESEARCH_ONLY','rows':len(frame),'eligible_days':int(frame.eligible.sum()),
        'd1_zero_days':int(frame.d1_count.eq(0).sum()),'correlations':correlations,'folds':folds,'calibration_bands':bands,
        'stable_incremental_2023_2025':stable,'verdict':'INCREMENTAL_RESEARCH_CANDIDATE' if stable else 'NO_STABLE_INCREMENTAL_REGIME_SIGNAL',
        'canonical_writes':False,'economic_benefit_proven':False,'production_go':False,
        'snapshot_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.parquet')}}
    (output/'report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps(report,default=str))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
