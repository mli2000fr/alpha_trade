"""Read-only bar provenance and generator comparison summary for two symbols."""
import argparse
from pathlib import Path
import pandas as pd
from sqlalchemy import text,bindparam
from database.connection import get_sqlalchemy_engine
from scripts.research.us_concentrated_historical_tapes import atomic_json


def run(root,output=None):
    out=output or root/'provenance'
    out.mkdir(exist_ok=False)
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':
        raise ValueError('US database required')
    queries={
        'daily':'SELECT symbol,`date`,`close`,adj_close,volume,is_filled,data_source,data_adjustment,ingested_at,last_updated,instrument_id FROM stock_bars_daily WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end ORDER BY symbol,`date`',
        'bars':'SELECT symbol,timeframe,`timestamp`,close_price,volume,data_source,data_adjustment,ingested_at,instrument_id FROM stock_bars WHERE symbol IN :symbols AND timeframe=:tf AND `timestamp` BETWEEN :start AND :end ORDER BY symbol,`timestamp`'}
    summary={}
    for name,sql in queries.items():
        with engine.connect() as conn:
            conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            frame=pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,
                params=dict(symbols=['AMTB','KNTK'],start='2017-01-01',end='2024-12-31 23:59:59',tf='1D'))
        frame.to_parquet(out/f'{name}.parquet',index=False)
        summary[name]=frame.groupby(['symbol','data_source','data_adjustment'],dropna=False).size().reset_index(name='count').to_dict('records')
    frame=pd.read_parquet(root/'comparison/generator-comparison.parquet')
    comparisons=[]
    for symbol,group in frame.groupby('symbol'):
        local=group.loc[group.source_variant.eq('local')].set_index('date')
        fresh=group.loc[group.source_variant.eq('fresh_split_only')].set_index('date')
        dates=local.index.intersection(fresh.index)
        fields={}
        for col in ['daily_return','rolling_volatility_20','rolling_volatility_60','rolling_volatility_120','momentum_250']:
            delta=(local.loc[dates,col]-fresh.loc[dates,col]).abs()
            mask=delta.gt(1e-6)
            fields[col]=dict(differing_dates=int(mask.sum()),
                first=str(dates[mask].min()) if mask.any() else None,
                last=str(dates[mask].max()) if mask.any() else None,
                local_max=float(local.loc[dates,col].max()),fresh_max=float(fresh.loc[dates,col].max()))
        comparisons.append(dict(symbol=symbol,shared_generator_dates=len(dates),fields=fields))
    atomic_json(out/'report.json',dict(status='COMPLETED_READ_ONLY',source_summary=summary,
        feature_comparison=comparisons,sql_writes=False,
        caveat='Broad date-level differences are not all independently validated errors'))
    print(summary)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    run(args.root,args.output)
