"""Compare two suspect histories to fresh full EODHD split-only reconstruction."""
import argparse
from pathlib import Path
import ssl

import pandas as pd
import requests

from modelFactory.features import compute_features
from service.eodhd.adapters import eodhd_to_split_only,to_stock_bars_daily_row
from service.eodhd.clientEodhd import fetch_eod,fetch_splits
from service.eodhd.quota import EodhdQuotaTracker
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_oracle_feature_outliers import diagnose_segment


def run(source,output):
    output.mkdir(parents=True,exist_ok=False)
    local=pd.read_parquet(source/'suspect-bars.parquet')
    session=requests.Session()
    trust=output/'windows-trust.pem'
    trust.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in ssl.create_default_context().get_ca_certs(binary_form=True)),encoding='ascii')
    session.verify=str(trust.resolve())
    tracker=EodhdQuotaTracker(cache_dir=output/'provider-quota')
    summaries=[]
    comparisons=[]
    features=[]
    try:
        for symbol,group in local.groupby('symbol'):
            start=str(group.date.min().date())
            raw=fetch_eod(symbol,start=start,end='2024-12-31',session=session,tracker=tracker,feature='oracle_outlier_audit')
            splits=fetch_splits(symbol,session=session,tracker=tracker,feature='oracle_outlier_audit')
            atomic_json(output/f'{symbol}-bars-full.json',raw)
            atomic_json(output/f'{symbol}-splits-full.json',splits)
            canonical=pd.DataFrame([to_stock_bars_daily_row(row,symbol) for row in eodhd_to_split_only(raw,splits)])
            canonical['date']=pd.to_datetime(canonical.date)
            canonical['instrument_id']=group.instrument_id.iloc[0]
            canonical['is_filled']=0
            canonical.to_parquet(output/f'{symbol}-canonical.parquet',index=False)
            ld=diagnose_segment(group)
            fresh=diagnose_segment(canonical)
            cmp=ld.merge(fresh,on=['symbol','date'],suffixes=('_local','_fresh'),validate='one_to_one')
            cmp['price_ratio_local_fresh']=cmp.close_local/cmp.close_fresh
            comparisons.append(cmp)
            for name,data in [('local',group),('fresh_split_only',canonical)]:
                frame=compute_features(data,feature_set='expert',include_factors=True)
                frame['source_variant']=name
                frame['symbol']=symbol
                features.append(frame)
            event='2018-11-13' if symbol=='KNTK' else '2018-10-18'
            row=cmp.loc[cmp.date.eq(event)].iloc[0]
            summaries.append(dict(symbol=symbol,event=event,
                local_previous_close=float(row.previous_close_local),local_close=float(row.close_local),
                reconstructed_previous_close=float(row.previous_close_fresh),reconstructed_close=float(row.close_fresh),
                local_return=float(row.daily_return_recomputed_local),fresh_return=float(row.daily_return_recomputed_fresh),
                local_gap=float(row.overnight_gap_recomputed_local),fresh_gap=float(row.overnight_gap_recomputed_fresh),
                days_compared=len(cmp),nonconstant_scale_days=int(cmp.price_ratio_local_fresh.sub(1).abs().gt(.01).sum())))
    finally:
        session.close()
    pd.concat(comparisons,ignore_index=True).to_parquet(output/'comparison.parquet',index=False)
    pd.concat(features,ignore_index=True).to_parquet(output/'generator-comparison.parquet',index=False)
    atomic_json(output/'report.json',dict(status='COMPLETED_LOCAL_RECONSTRUCTION_ONLY',events=summaries,
        sql_writes=False,training=False,source_sha256=digest(source/'suspect-bars.parquet'),
        caveats=['Same vendor reread, not independent validation',
                 'Fresh split-only reconstruction kept in research only',
                 'No historical importer/version blame established',
                 'Nonconstant scale-days measure relative to current split history, not individually certified bad bars',
                 'Generator comparison omits benchmark/selector context']))
    print(summaries)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.source,args.output)
