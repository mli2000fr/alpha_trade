"""Read-only refreshed options coverage and H5/H10 audit at Q051 selection stages."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import pandas as pd
from sqlalchemy import text
from scripts.research.us_consensus_observed_revision_pilot import connect_readonly
from scripts.research.us_collected_directional_refresh_20261105 import query
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_options_q051_top_fraction/20261115-v1')
UNIVERSE=Path('config/univers_batch/univers_filtred_tradable.txt')
START='2026-09-01'
BATCH='model-factory-20261107222627-db80b0'


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def inventory(root=ROOT):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    universe=sorted(set(s.upper() for s in re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig')) if s))
    cutoff=pd.Timestamp.now(tz='UTC');params=dict(start=START,cutoff=cutoff.tz_localize(None).to_pydatetime(),symbols=universe)
    result=dict(cutoff_utc=str(cutoff),universe_file=str(UNIVERSE),universe_count=len(universe),universe=universe,
        universe_sha256=digest(UNIVERSE),start=START,SQL_writes=0,provider_calls=0,orders=0)
    engine,conn=connect_readonly()
    try:
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
        result['schema']=query(conn,"SELECT TABLE_NAME,COLUMN_NAME,DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('stock_option_snapshots','stock_option_bars_delayed','oracle_extreme_predictions','oracle_path_prediction_lineage','oracle_path_directional_predictions')")
        for table in ['stock_option_snapshots','stock_option_bars_delayed']:
            value='open_interest' if table=='stock_option_snapshots' else 'volume'
            where="available_at>=:start AND available_at<=:cutoff AND observed_at<=:cutoff"
            result[table]=dict(
                overall=query(conn,f'''SELECT provider,feed,MIN(available_at) first_available,MAX(available_at) last_available,
                    COUNT(*) rows_n,COUNT(DISTINCT underlying_symbol) symbols,COUNT(DISTINCT DATE(available_at)) utc_dates
                    FROM {table} WHERE {where} GROUP BY provider,feed''',**{k:v for k,v in params.items() if k!='symbols'}),
                tradable_daily=query(conn,f'''SELECT provider,feed,DATE(available_at) utc_day,option_type,
                    COUNT(*) rows_n,COUNT(DISTINCT underlying_symbol) symbols,
                    COUNT(DISTINCT CASE WHEN {value} IS NOT NULL AND {value}>=0 THEN underlying_symbol END) numeric_symbols,
                    COUNT(DISTINCT CASE WHEN {value}>0 THEN underlying_symbol END) positive_symbols
                    FROM {table} WHERE {where} AND underlying_symbol IN :symbols
                    GROUP BY provider,feed,DATE(available_at),option_type ORDER BY utc_day''',**params),
                tradable_ever=query(conn,f'''SELECT underlying_symbol symbol,MIN(available_at) first_available,
                    MAX(available_at) last_available,COUNT(*) rows_n,
                    MAX(CASE WHEN option_type IN ('CALL','C','call') THEN 1 ELSE 0 END) has_call,
                    MAX(CASE WHEN option_type IN ('PUT','P','put') THEN 1 ELSE 0 END) has_put
                    FROM {table} WHERE {where} AND underlying_symbol IN :symbols GROUP BY underlying_symbol''',**params))
        result['oracle']=query(conn,'''SELECT p.batch_id,l.target_horizon,COUNT(*) rows_n,COUNT(DISTINCT p.prediction_date) dates,
            MIN(p.prediction_date) first_signal,MAX(p.prediction_date) last_signal,MIN(p.created_at) first_created,MAX(p.created_at) last_created
            FROM oracle_extreme_predictions p JOIN oracle_path_prediction_lineage l ON l.batch_id=p.batch_id
            AND l.symbol=p.symbol AND l.prediction_date=p.prediction_date WHERE p.prediction_date>=:start
            GROUP BY p.batch_id,l.target_horizon''',start=START)
        result['options_runs']=query(conn,'''SELECT batch_name,status,COUNT(*) runs,MAX(started_at) last_started,MAX(finished_at) last_finished
            FROM pit_collection_runs WHERE started_at>=:start AND batch_name IN ('oracle_options_indicative_snapshot','options_delayed_bars_sync')
            GROUP BY batch_name,status''',start=START)
        result['max_daily_price_date']=query(conn,"SELECT MAX(date) latest FROM stock_bars_daily WHERE symbol='SPY' AND data_source IN ('eodhd_eod','alpaca_sip')")
        conn.rollback()
    finally:conn.close();engine.dispose()
    atomic_json(root/'inventory.json',result)
    atomic_json(root/'progress.json',dict(status='INVENTORY_READY',universe=len(universe)))
    print(json.dumps(dict(cutoff=str(cutoff),universe=len(universe),oracle=result['oracle'],
        options={t:dict(overall=result[t]['overall'],tradable_ever=len(result[t]['tradable_ever'])) for t in ['stock_option_snapshots','stock_option_bars_delayed']},
        latest_price=result['max_daily_price_date']),default=str,ensure_ascii=False),flush=True)


def snapshot(root=ROOT):
    from common.config_loader import load_config
    from common.market_calendar import get_market_calendar
    from modelFactory.oracle_path.predict import load_contract,prediction_coverage_ratio
    from modelFactory.oracle_path.directional import load_manifest
    from backtesting.isolation import ReadOnlyReplay
    root=Path(root);inv=read(root/'inventory.json');cutoff=pd.Timestamp(inv['cutoff_utc']);symbols=inv['universe']
    if (root/'snapshot-seal.json').exists():raise FileExistsError('Immutable snapshot already sealed')
    model,contract,profile,folds=load_contract('artifacts/models',BATCH);manifest,mhash=load_manifest(model)
    if contract['horizon']!=10 or pd.Timestamp(contract['training_config']['data']['training_end_date'])>=pd.Timestamp('2026-01-01'):
        raise ValueError('Annual H10 model must precede 2026')
    if set(symbols)!=set(contract['universe']):raise ValueError('Tradable universe differs from model universe; define intersection before continuing')
    last=pd.Timestamp(inv['max_daily_price_date'][0]['latest'])
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    calendar=pd.DataFrame([dict(day=pd.Timestamp(s.session_date),opened=pd.Timestamp(s.open_at_utc),closed=pd.Timestamp(s.close_at_utc))
        for s in cal.sessions(pd.Timestamp(START).date(),pd.Timestamp('2026-12-15').date()) if s.is_open])
    calendar.to_parquet(root/'calendar.parquet',index=False)
    config=load_config();policy=dict(oracle_fraction=.10,oracle_top_n=179,long_top_n=5,min_long_probability=.5,min_long_auc=.5,
        options_normalization='same fixed TOP10% Oracle covered cohort for both stages',options_weights=[.5,.5],
        options_selection='upper half of covered Oracle pool, score strictly>.50, min4 covered; TOP5 is a subsequent subset, no refill',
        targets=['largest absolute signed movement inside H5/H10 from next-session open','independent LONG SL5/open6 or open11, fee8bps/leg'],
        thresholds_frozen=True,new_inference=False,training=False)
    protocol=dict(cutoff_utc=str(cutoff),start=START,last_price_date=str(last.date()),symbols=symbols,batch_id=BATCH,
        model_root=str(model),horizon=10,feature_profile_sha256=digest(model/'feature_profile.json'),folds=folds,
        manifest_sha256=mhash,oracle_coverage_ratio=prediction_coverage_ratio(),policy=policy,
        daily_price_config={'market_data':{'daily_bars_preferred_source':config.get('market_data',{}).get('daily_bars_preferred_source','eodhd')}},
        decision='5 minutes before next official session opening; all evidence received by this instant',
        physical_oracle='full ranking must be physically saved before decision to be prospective; otherwise retrospective with causal model only',
        SQL_writes=0,provider_calls=0,orders=0)
    atomic_json(root/'protocol.json',protocol)
    engine,conn=connect_readonly()
    try:
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
        with ReadOnlyReplay(root).install():
            params=dict(batch=BATCH,start=START,end=str(last.date()),cutoff=cutoff.tz_localize(None).to_pydatetime())
            sql='''SELECT p.prediction_date date,p.symbol,p.proba_extreme,p.fold_start,p.batch_id,
                p.created_at prediction_created_at,l.created_at lineage_created_at,l.fold_start lineage_fold_start,
                l.model_available_date,l.target_name,l.target_horizon,l.model_sha256,l.feature_profile_sha256,
                d.long_probability,d.short_probability,d.long_model_sha256,d.short_model_sha256,d.manifest_sha256,d.updated_at directional_created_at
                FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l ON l.batch_id=p.batch_id
                AND l.symbol=p.symbol AND l.prediction_date=p.prediction_date LEFT JOIN oracle_path_directional_predictions d
                ON d.batch_id=p.batch_id AND d.symbol=p.symbol AND d.prediction_date=p.prediction_date
                WHERE p.batch_id=:batch AND p.prediction_date BETWEEN :start AND :end AND p.created_at<=:cutoff'''
            f=pd.DataFrame(query(conn,sql,**params));f.to_parquet(root/'oracle-raw.parquet',index=False)
            atomic_json(root/'progress.json',dict(status='EXPORTING_READ_ONLY',oracle_rows=len(f)))
            specs={
                'snapshots':('stock_option_snapshots',"provider='alpaca' AND feed='indicative'",'''id,provider,feed,underlying_symbol symbol,contract_symbol,expiration_date,strike,
                    option_type,observed_at,available_at,provider_timestamp,open_interest,payload_hash,run_id'''),
                'volumes':('stock_option_bars_delayed',"provider='alpaca' AND timeframe='30Min'",'''id,provider,feed,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                    observed_at,available_at,bar_timestamp,volume,payload_hash,provenance_status,timeframe,run_id''')}
            receipts=[]
            for name,(table,where,cols) in specs.items():
                folder=root/'raw'/name;folder.mkdir(parents=True,exist_ok=True)
                for month in ['2026-09','2026-10','2026-11']:
                    start=pd.Timestamp(month+'-01');end=min(start+pd.offsets.MonthBegin(1),cutoff.tz_localize(None))
                    def export(a,b,label):
                        pp=dict(symbols=symbols,start=a.to_pydatetime(),end=b.to_pydatetime(),cutoff=cutoff.tz_localize(None).to_pydatetime())
                        condition=where+' AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end AND available_at<=:cutoff AND observed_at<=:cutoff'
                        n=int(query(conn,f'SELECT COUNT(*) n FROM {table} WHERE '+condition,**pp)[0]['n'])
                        if n>150000:
                            if b-a<=pd.Timedelta(days=1):raise ValueError('Further symbol partition required; no truncation')
                            for d in pd.date_range(a,b,freq='D',inclusive='left'):export(d,min(d+pd.Timedelta(days=1),b),str(d.date()))
                            return
                        rows=query(conn,'SELECT '+cols+' FROM '+table+' WHERE '+condition,**pp)
                        if len(rows)!=n:raise ValueError('Read-only export count mismatch')
                        target=folder/(label+'.parquet');pd.DataFrame(rows).to_parquet(target,index=False)
                        receipts.append(dict(kind=name,path=str(target.relative_to(root)),rows=n,sha256=digest(target)))
                        atomic_json(root/'progress.json',dict(status='EXPORTING_READ_ONLY',kind=name,partition=label,rows=n,partitions=len(receipts)))
                    export(start,end,month)
            pp=dict(symbols=symbols,start=START,end=str(last.date()))
            sql='''SELECT symbol,date,open,high,low,close,volume,is_filled,data_source,data_adjustment,instrument_id,
                ingested_at,last_updated FROM stock_bars_daily WHERE symbol IN :symbols AND date BETWEEN :start AND :end
                AND data_source IN ('eodhd_eod','alpaca_sip')'''
            n=int(query(conn,'SELECT COUNT(*) n FROM ('+sql+') x',**pp)[0]['n'])
            if n>300000:raise ValueError('Price export needs partition; no truncation')
            prices=pd.DataFrame(query(conn,sql,**pp))
            if len(prices)!=n:raise ValueError('Price count mismatch')
            prices.to_parquet(root/'prices.parquet',index=False)
            atomic_json(root/'export-receipts.json',receipts)
            conn.rollback()
    finally:conn.close();engine.dispose()
    atomic_json(root/'snapshot-seal.json',dict(files={str(p.relative_to(root)):digest(p) for p in root.rglob('*')
        if p.is_file() and p.name not in ('progress.json','isolation.json')},models={str(model/n):digest(model/n)
            for n in ['protocol.json','feature_profile.json','report.json','directional/manifest.json']}))
    atomic_json(root/'progress.json',dict(status='SNAPSHOT_READY',oracle_rows=len(f),prices=len(prices),partitions=len(receipts)))
    print(json.dumps(read(root/'progress.json')),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',default='inventory');p.add_argument('--output-dir',default=str(ROOT));args=p.parse_args()
    if args.phase=='inventory':inventory(args.output_dir)
    elif args.phase=='snapshot':snapshot(args.output_dir)
