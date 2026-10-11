"""Research only: cached daily provider comparison and frozen Oracle sensitivity."""
from pathlib import Path
import argparse
import hashlib
import json
import logging
from unittest.mock import patch
import numpy as np
import pandas as pd
from sqlalchemy import event
from common.universe_files import load_universe_file_symbols
from common.verified_http import verified_session
from database.connection import get_sqlalchemy_engine
from service.alpaca.clientAlpaca import _build_headers
from service.eodhd.clientEodhd import fetch_eod, fetch_splits
from service._http_retry import request_with_retry, RetryPolicy
from service.market.intraday_backfill import atomic_json
from scripts.research.us_prospective_directional_collection_audit import query

START='2023-01-01'
END='2026-09-30'
EVAL='2025-01-01'
BATCH='model-factory-20261003082853-e98332'


def summary(values):
    values=np.asarray(values,dtype=float)
    values=values[np.isfinite(values)]
    return dict(n=len(values),median=float(np.median(values)) if len(values) else None,
                p95=float(np.quantile(values,.95)) if len(values) else None,
                maximum=float(values.max()) if len(values) else None)


def alpaca(session,symbol,feed):
    params=dict(symbols=symbol,timeframe='1Day',adjustment='raw',feed=feed,
                asof='-',start=START+'T00:00:00Z',end=END+'T23:59:59Z',limit=10000,sort='asc')
    rows=[];seen=set()
    while True:
        response=request_with_retry(session,'GET','https://data.alpaca.markets/v2/stocks/bars',
            headers=_build_headers('default'),params=params,policy=RetryPolicy(max_attempts=3,timeout_seconds=45))
        data=response.json()
        if set(data.get('bars',{}))- {symbol}:raise ValueError('Unexpected symbol in provider response')
        rows.extend(data.get('bars',{}).get(symbol,[]))
        token=data.get('next_page_token')
        if not token:break
        if token in seen:raise ValueError('Repeated pagination token')
        seen.add(token);params['page_token']=token
    return rows


def frame(rows,symbol,provider,splits):
    df=pd.DataFrame(rows)
    if df.empty:return df
    if provider!='eodhd':
        df=df.rename(columns=dict(t='date',o='open',h='high',l='low',c='close',v='volume',vw='vwap'))
        df['date']=pd.to_datetime(df.date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    else:
        df['date']=pd.to_datetime(df.date)
        df['vwap']=(df.high+df.low+df.close)/3
    for col in ('open','high','low','close','volume','vwap'):df[col]=pd.to_numeric(df[col],errors='coerce')
    df['symbol']=symbol
    df=df.sort_values('date')
    if df.date.duplicated().any():raise ValueError('Duplicate daily provider bars')
    df['factor']=1.
    for split in splits:
        numerator,denominator=split['split'].split('/')
        df.loc[df.date.lt(pd.Timestamp(split['date'])),'factor']*=float(numerator)/float(denominator)
    # EODHD documents its native volume as split-adjusted; do not adjust it twice.
    df['adjusted_volume']=df.volume if provider=='eodhd' else df.volume*df.factor
    return df


def price_comparison(eod,other):
    merged=eod.merge(other,on=['symbol','date'],suffixes=('_e','_a'))
    merged=merged[merged.date.ge(EVAL)].copy()
    metrics={}
    for col in ('open','high','low','close'):
        delta=(merged[col+'_a']/merged[col+'_e']-1)*10000
        metrics[col+'_absolute_bps']=summary(delta.abs())
        metrics[col+'_above_10bps_pct']=float(delta.abs().gt(10).mean()*100)
        metrics[col+'_above_100bps_pct']=float(delta.abs().gt(100).mean()*100)
        merged[col+'_difference_bps']=delta
    metrics['volume_share']=summary(merged.adjusted_volume_a/merged.adjusted_volume_e)
    metrics['matched_days']=len(merged)
    metrics['eod_days']=int(eod.date.ge(EVAL).sum())
    metrics['provider_days']=int(other.date.ge(EVAL).sum())
    return metrics,merged


def model_frame(df):
    out=df[['symbol','date','open','high','low','close','vwap']].copy()
    out[['open','high','low','close','vwap']]=out[['open','high','low','close','vwap']].div(df.factor,axis=0)
    out['volume']=df.adjusted_volume.to_numpy()
    out['adj_close']=out.close
    out['daily_return']=out.groupby('symbol').close.pct_change(fill_method=None)
    out['is_filled']=0
    return out


def score_comparison(base,other):
    joined=base.merge(other,on=['date','symbol'],suffixes=('_base','_other'))
    daily=[]
    for day,part in joined.groupby('date'):
        n=max(1,int(np.ceil(len(part)*.2)))
        a=set(part.sort_values(['score_base','symbol'],ascending=[False,True]).head(n).symbol)
        b=set(part.sort_values(['score_other','symbol'],ascending=[False,True]).head(n).symbol)
        top_n=min(10,len(part))
        top_a=set(part.sort_values(['score_base','symbol'],ascending=[False,True]).head(top_n).symbol)
        top_b=set(part.sort_values(['score_other','symbol'],ascending=[False,True]).head(top_n).symbol)
        daily.append(dict(date=str(day.date()),count=len(part),top20_overlap=len(a&b)/n,
            top10_overlap=len(top_a&top_b)/top_n,
            rank_correlation=part.score_base.corr(part.score_other,method='spearman')))
    delta=(joined.score_other-joined.score_base).abs()
    return dict(absolute_probability_change=summary(delta),
        mean_probability_change=float(delta.mean()),
        daily_top20_overlap=summary([x['top20_overlap'] for x in daily]),
        mean_top20_overlap=float(np.mean([x['top20_overlap'] for x in daily])),
        mean_sample_top10_overlap=float(np.mean([x['top10_overlap'] for x in daily])),
        mean_rank_correlation=float(np.nanmean([x['rank_correlation'] for x in daily])),
        daily=daily)


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    engine=get_sqlalchemy_engine()
    event.listen(engine,'begin',lambda conn:conn.exec_driver_sql('SET TRANSACTION READ ONLY'))
    protocol_path=output/'protocol.json'
    if protocol_path.exists():protocol=json.loads(protocol_path.read_text())
    else:
        universe=load_universe_file_symbols('universe-file:univers_filtred_tradable.txt')
        with engine.connect() as conn:
            pool=pd.DataFrame(query(conn,'SELECT symbol, AVG(close*volume) liquidity,COUNT(*) n FROM stock_bars_daily '
                'WHERE symbol IN :symbols AND date BETWEEN :start AND :end AND is_filled=0 GROUP BY symbol',
                symbols=universe,start='2024-10-01',end='2024-12-31'))
        pool=pool[pool.n.ge(40)].sort_values(['liquidity','symbol']).reset_index(drop=True)
        pool['stratum']=np.minimum(3,np.arange(len(pool))*4//len(pool))
        pool['hash']=pool.symbol.map(lambda s:hashlib.sha256(('daily-audit-v1:'+s).encode()).hexdigest())
        selected=pool.sort_values('hash').groupby('stratum').head(6)
        protocol=dict(batch=BATCH,start=START,end=END,evaluation_start=EVAL,
            sample=selected[['symbol','liquidity','stratum']].to_dict('records'),
            sampling='4 pre-period dollar-volume strata, 6 hash-selected current tradable symbols each',
            rules='Raw OHLC comparison; common split factors; matched history only; no imputation; sample ranks; fixed SPY/selector context; no training or SQL writes',
            limitations=['Current universe survivor bias','Sample ranks not full production ranks',
                'Sensitivity not predictive performance or non-inferiority','EODHD is not independent ground truth'])
        atomic_json(protocol_path,protocol)
    session=verified_session();frames={p:[] for p in ('eodhd','iex','sip')};errors=[]
    for index,item in enumerate(protocol['sample']):
        symbol=item['symbol'];folder=output/'cache'/symbol;folder.mkdir(parents=True,exist_ok=True)
        split_path=folder/'splits.json'
        if not split_path.exists():atomic_json(split_path,fetch_splits(symbol,start=START,end=END,session=session))
        splits=json.loads(split_path.read_text())
        for provider in frames:
            cache=folder/(provider+'.json')
            try:
                if not cache.exists():
                    payload=fetch_eod(symbol,start=START,end=END,session=session) if provider=='eodhd' else alpaca(session,symbol,provider)
                    atomic_json(cache,payload)
                part=frame(json.loads(cache.read_text()),symbol,provider,splits)
                if part.empty:raise ValueError('Empty history')
                frames[provider].append(part)
            except Exception as exc:
                # Provider exception URLs can contain secrets; archive only type and HTTP status.
                response=getattr(exc,'response',None)
                errors.append(dict(symbol=symbol,provider=provider,error_type=type(exc).__name__,http_status=getattr(response,'status_code',None)))
        atomic_json(output/'progress.json',dict(status='FETCHING',completed=index+1,total=len(protocol['sample']),errors=errors))
        logging.info('Provider histories %d/%d %s',index+1,len(protocol['sample']),symbol)
    data={p:pd.concat(parts,ignore_index=True) if parts else pd.DataFrame() for p,parts in frames.items()}
    report=dict(protocol=protocol,errors=errors,prices={},sensitivity={})
    for provider in ('iex','sip'):
        if data[provider].empty:continue
        stats,detail=price_comparison(data['eodhd'],data[provider]);report['prices'][provider]=stats
        detail.to_csv(output/(provider+'-paired-prices.csv'),index=False)
        report['prices'][provider]['by_year']={str(y):price_comparison(data['eodhd'][data['eodhd'].date.dt.year.eq(y)],data[provider][data[provider].date.dt.year.eq(y)])[0] for y in (2025,2026)}
    from modelFactory.oracle.dataset import build_feature_matrix
    from modelFactory.data_loader import load_benchmark_bars
    import lightgbm as lgb
    root=Path('artifacts/models/oracle/champions')/BATCH
    meta=json.loads((root/'oracle_champions.json').read_text())[-1]
    path=Path(meta['model_file']);path=path if path.exists() else root/path.name
    booster=lgb.Booster(model_file=str(path))
    options=json.loads((root/'feature_profile.json').read_text())['generator_options']
    benchmark=load_benchmark_bars(engine,'SPY',start_date=START,end_date=END)
    importance=pd.DataFrame(dict(feature=booster.feature_name(),gain=booster.feature_importance('gain'),splits=booster.feature_importance('split')))
    importance.to_csv(output/'model-feature-importance.csv',index=False)
    family=importance.feature.str.contains('volume|cmf|vwap|obv|amihud',case=False,regex=True)
    report['volume_family_gain_fraction']=float(importance.loc[family,'gain'].sum()/importance.gain.sum())
    report['model_file_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    for provider in ('iex','sip'):
        if data[provider].empty:continue
        keys=data['eodhd'][['symbol','date']].merge(data[provider][['symbol','date']],on=['symbol','date'])
        e=model_frame(data['eodhd'].merge(keys,on=['symbol','date']))
        a=model_frame(data[provider].merge(keys,on=['symbol','date']))
        e=e.sort_values(['symbol','date']).reset_index(drop=True);a=a.sort_values(['symbol','date']).reset_index(drop=True)
        price_only=e.copy()
        for col in ('open','high','low','close','adj_close','daily_return'):
            price_only[col]=a[col].to_numpy()
        variants={'baseline':e,'constant_volume_scale':e.assign(volume=e.volume*.03),
            'volume_only':e.assign(volume=a.volume.to_numpy()),
            'prices_only':price_only,'vwap_only':e.assign(vwap=a.vwap.to_numpy()),'full_provider':a}
        scored={}
        for name,bars in variants.items():
            with patch('modelFactory.oracle.dataset.load_universe_bars',return_value=bars),patch('modelFactory.oracle.dataset.load_benchmark_bars',return_value=benchmark):
                features=build_feature_matrix(engine,sorted(bars.symbol.unique()),start_date=EVAL,end_date=END,generator_options=options)
            features=features[features.date.ge(EVAL)&features.date.le(END)].copy()
            missing=set(booster.feature_name())-set(features)
            if missing:raise ValueError('Missing model features: '+str(sorted(missing)))
            matrix=features[booster.feature_name()].replace([np.inf,-np.inf],np.nan).astype(float)
            scored[name]=features[['date','symbol']].assign(score=booster.predict(matrix,num_threads=2))
            scored[name].to_csv(output/(provider+'-'+name+'-scores.csv'),index=False)
            logging.info('Oracle %s %s rows=%d',provider,name,len(features))
        report['sensitivity'][provider]={name:score_comparison(scored['baseline'],scores) for name,scores in scored.items() if name!='baseline'}
        report.setdefault('sensitivity_by_year',{})[provider]={str(year):{
            name:score_comparison(scored['baseline'][scored['baseline'].date.dt.year.eq(year)],scores[scores.date.dt.year.eq(year)])
            for name,scores in scored.items() if name!='baseline'} for year in (2025,2026)}
        atomic_json(output/'report.partial.json',report)
    atomic_json(output/'report.json',report)
    atomic_json(output/'progress.json',dict(status='COMPLETED',errors=errors))
    engine.dispose()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO)
    run(args.output_dir)
