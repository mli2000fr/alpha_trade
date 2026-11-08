"""Read-only coverage inventory before ranking predictable ordinary shares."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import logging
import time

import pandas as pd
from sqlalchemy import text, bindparam
from database.connection import get_sqlalchemy_engine

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/research/us_predictable_symbols/20261103-v1'
SOURCE=ROOT/'config/univers_batch/action_ordinaire.txt'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    symbols=sorted(set(SOURCE.read_text(encoding='utf-8-sig').strip().split(',')))
    queries={
        'daily':'''SELECT symbol,data_source,MIN(date) first_date,MAX(date) last_date,
            COUNT(DISTINCT date) days,COUNT(*) rows_count,
            COUNT(DISTINCT CASE WHEN date BETWEEN '2023-01-01' AND '2025-12-31' THEN date END) days_2023_2025
            FROM stock_bars_daily FORCE INDEX (PRIMARY) WHERE symbol IN :symbols AND date<='2026-11-02'
            AND data_source IN ('eodhd_eod','alpaca_sip') AND COALESCE(is_filled,0)=0
            GROUP BY symbol,data_source''',
        'options_snapshots':'''SELECT underlying_symbol symbol,provider,feed,
            MIN(observed_at) first_observed,MAX(observed_at) last_observed,
            MIN(available_at) first_available,MAX(available_at) last_available,
            COUNT(DISTINCT DATE(available_at)) observed_days,COUNT(*) rows_count,
            SUM(open_interest IS NOT NULL) with_oi,
            COUNT(DISTINCT CASE WHEN option_type IN ('CALL','C') AND open_interest IS NOT NULL THEN DATE(available_at) END) call_oi_days,
            COUNT(DISTINCT CASE WHEN option_type IN ('PUT','P') AND open_interest IS NOT NULL THEN DATE(available_at) END) put_oi_days
            FROM stock_option_snapshots WHERE underlying_symbol IN :symbols
            GROUP BY underlying_symbol,provider,feed''',
        'options_volume':'''SELECT underlying_symbol symbol,provider,feed,timeframe,
            MIN(bar_timestamp) first_bar,MAX(bar_timestamp) last_bar,
            MIN(available_at) first_available,MAX(available_at) last_available,
            COUNT(DISTINCT DATE(bar_timestamp)) bar_days,
            COUNT(DISTINCT DATE(available_at)) receipt_days,COUNT(*) rows_count
            FROM stock_option_bars_delayed WHERE underlying_symbol IN :symbols AND timeframe='30Min'
            GROUP BY underlying_symbol,provider,feed,timeframe''',
        'consensus':'''SELECT symbol,MIN(snapshot_date) first_snapshot,MAX(snapshot_date) last_snapshot,
            MIN(available_at) first_available,MAX(available_at) last_available,
            COUNT(DISTINCT snapshot_date) days,COUNT(*) rows_count,
            COUNT(DISTINCT CASE WHEN horizon_raw='0q' THEN snapshot_date END) days_0q,
            COUNT(DISTINCT CASE WHEN horizon_raw='0q' AND revisions_up_30d IS NOT NULL
                AND revisions_down_30d IS NOT NULL THEN snapshot_date END) revision_days_0q,
            SUM(historical_pit_qualified=1) pit_qualified_rows,
            SUM(fiscal_identity_qualified=1 AND units_qualified=1) fiscal_units_qualified_rows
            FROM stock_analyst_consensus_eodhd_history WHERE symbol IN :symbols GROUP BY symbol''',
    }
    results={};engine=get_sqlalchemy_engine(db_name='alpha_trade')
    for name,sql in queries.items():
        started=time.monotonic()
        logging.info('Inventory %s',name)
        try:
            cached=OUT/(name+'-coverage.parquet')
            if cached.exists():
                frame=pd.read_parquet(cached)
            else:
                parts=[]
                chunks=[symbols[i:i+200] for i in range(0,len(symbols),200)] if name=='daily' else [symbols]
                for i,chunk in enumerate(chunks):
                    with engine.connect() as conn:
                        conn.execute(text('START TRANSACTION READ ONLY'))
                        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=30000'))
                        parts.append(pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,params={'symbols':chunk}))
                        conn.rollback()
                    logging.info('%s chunk %s/%s',name,i+1,len(chunks))
                frame=pd.concat(parts,ignore_index=True)
            frame.to_parquet(OUT/(name+'-coverage.parquet'),index=False)
            dates={c:{'min':str(frame[c].min()),'max':str(frame[c].max())} for c in frame.columns
                   if c.startswith(('first_','last_')) and frame[c].notna().any()}
            results[name]={'status':'EXPORTED','symbols':int(frame.symbol.nunique()),'groups':len(frame),
                'dates':dates,'elapsed_seconds':time.monotonic()-started}
        except Exception as exc:
            # Never expose connection credentials in research progress/errors.
            results[name]={'status':'ERROR','error_type':type(exc).__name__,
                'elapsed_seconds':time.monotonic()-started}
            logging.exception('Inventory %s failed',name)
        (OUT/'inventory-progress.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    report={'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'requested_symbols':len(symbols),'results':results,'sql_writes':False,'provider_calls':0}
    (OUT/'inventory-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    main()
