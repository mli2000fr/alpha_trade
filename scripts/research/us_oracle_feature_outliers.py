"""Read-only US bars audit: reproduce basic Oracle price features by segment."""
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text,bindparam

from database.connection import get_sqlalchemy_engine
from modelFactory.features import _build_adjusted_price_frame
from modelFactory.oracle.security_continuity import load_security_discontinuities,split_frame_on_discontinuities
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

FEATURES=['daily_return_recomputed','overnight_gap_recomputed','rolling_volatility_20_recomputed']


def diagnose_segment(frame):
    data=frame.sort_values('date').reset_index(drop=True).copy()
    adjusted=_build_adjusted_price_frame(data)
    close=adjusted.close
    data['adjusted_close_used']=close
    data['adjusted_open_used']=adjusted.open
    data['previous_date']=data.date.shift(1)
    for col in ['close','adj_close','open','volume','instrument_id','is_filled']:
        if col in data:
            data['previous_'+col]=data[col].shift(1)
    data['daily_return_recomputed']=close.pct_change(fill_method=None).replace([np.inf,-np.inf],np.nan).fillna(0.)
    data['overnight_gap_recomputed']=(adjusted.open-close.shift(1))/close.shift(1).clip(lower=1e-8)
    data['rolling_volatility_20_recomputed']=data.daily_return_recomputed.rolling(20).std()
    data['raw_return']=data.close.pct_change(fill_method=None)
    data['adjustment_factor']=data.adjusted_close_used/data.close.replace(0,np.nan)
    data['previous_adjustment_factor']=data.adjustment_factor.shift(1)
    data['instrument_changed']=data.instrument_id.notna() & data.previous_instrument_id.notna() & data.instrument_id.ne(data.previous_instrument_id)
    return data


def run(output,universe):
    output.mkdir(parents=True,exist_ok=False)
    symbols=sorted(set(s.strip().upper() for s in universe.read_text().split(',') if s.strip()))
    registry=load_security_discontinuities()
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':
        raise ValueError('US database required')
    stmt=text('SELECT symbol,`date`,`open`,high,low,`close`,adj_close,volume,vwap,is_filled,instrument_id '
              'FROM stock_bars_daily WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end ORDER BY symbol,`date`').bindparams(bindparam('symbols',expanding=True))
    atomic_json(output/'protocol.json',dict(universe=str(universe),universe_sha256=digest(universe),
        symbols=len(symbols),start='2012-12-27',end='2024-12-31',feature_scope_start='2016-01-01',
        sql_reads=True,sql_writes=False,training=False,models_modified=False,
        caveat='Current database and source; historical dataset snapshot unavailable',
        formulas='Current _build_adjusted_price_frame + daily return/gap/std20; same registered identity splits'))
    tops={f:[] for f in FEATURES}
    anomalies=[]
    total=0
    for offset in range(0,len(symbols),100):
        chunk=symbols[offset:offset+100]
        with engine.connect() as conn:
            conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            bars=pd.read_sql(stmt,conn,params=dict(symbols=chunk,start='2012-12-27',end='2024-12-31'),parse_dates=['date'])
        total+=len(bars)
        for symbol,group in bars.groupby('symbol'):
            for segment in split_frame_on_discontinuities(group,symbol,registry):
                data=diagnose_segment(segment)
                scope=data.loc[data.date.ge('2016-01-01')]
                for feature in FEATURES:
                    tops[feature].append(scope.nlargest(3,feature))
                anomalies.append(scope.loc[scope.daily_return_recomputed.abs().gt(1) | scope.overnight_gap_recomputed.abs().gt(1)])
        atomic_json(output/'progress.json',dict(status='RUNNING',symbols=min(offset+100,len(symbols)),total=len(symbols),bars=total))
        logging.info('Scanned %d/%d symbols, %d bars',min(offset+100,len(symbols)),len(symbols),total)
    ranking=[]
    for feature,parts in tops.items():
        top=pd.concat(parts,ignore_index=True).nlargest(30,feature).copy()
        top['ranked_feature']=feature
        ranking.append(top)
    ranked=pd.concat(ranking,ignore_index=True)
    ranked.to_parquet(output/'feature-maxima.parquet',index=False)
    bad=pd.concat(anomalies,ignore_index=True)
    bad.to_parquet(output/'large-jumps.parquet',index=False)
    suspects=sorted(set(ranked.loc[ranked.daily_return_recomputed.gt(100) | ranked.overnight_gap_recomputed.gt(100) | ranked.rolling_volatility_20_recomputed.gt(100),'symbol']))
    # Preserve full suspect histories for local replication/identity examination.
    if suspects:
        with engine.connect() as conn:
            conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            history=pd.read_sql(stmt,conn,params=dict(symbols=suspects,start='2012-12-27',end='2024-12-31'),parse_dates=['date'])
        history.to_parquet(output/'suspect-bars.parquet',index=False)
    summaries=[]
    for feature in FEATURES:
        row=ranked.loc[ranked.ranked_feature.eq(feature)].iloc[0]
        summaries.append(dict(feature=feature,symbol=row.symbol,date=str(row.date.date()),value=float(row[feature]),
            close=float(row.close),adj_close=float(row.adj_close),previous_close=float(row.previous_close),
            previous_adj_close=float(row.previous_adj_close),instrument_changed=bool(row.instrument_changed)))
    atomic_json(output/'report.json',dict(status='COMPLETED_READ_ONLY_SCAN',bars=total,large_jumps=len(bad),
        symbols_with_large_jumps=int(bad.symbol.nunique()),maxima=summaries,suspects=suspects,
        not_proven='Exact historical training rows; no claim of causality for 2024 losses'))
    atomic_json(output/'progress.json',dict(status='COMPLETED',symbols=len(symbols),bars=total))
    print(summaries)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--universe',type=Path,default=Path('config/univers/univers_filtred_tradable.txt'))
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.output,args.universe)
