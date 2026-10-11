"""Bounded raw/split cross-control of the largest audit discrepancies."""
from pathlib import Path
import json
import logging
import pandas as pd
from common.verified_http import verified_session
from service.market.intraday_backfill import atomic_json
from scripts.research.us_sip_daily_universe_audit import fetch,provider_frame,stats
from scripts.research.us_sip_daily_universe_audit import request_with_retry,RetryPolicy
from service.alpaca.clientAlpaca import _build_headers,ALPACA_ASSETS_ENDPOINT


def run(output):
    output=Path(output);protocol=json.loads((output/'protocol.json').read_text())
    pairs=pd.read_parquet(output/'comparison-all.parquet')
    anomalies=pd.read_csv(output/'price-by-symbol.csv')
    symbols=anomalies.sort_values('max_price_bps',ascending=False).head(20).symbol.tolist()
    cache=output/'diagnostic-raw-top20.json'
    if not cache.exists():
        raw,pages=fetch(verified_session(),symbols,protocol['start_date'],protocol['end_date'],adjustment='raw')
        atomic_json(cache,dict(symbols=symbols,bars=raw,pages=pages,
            selection_rule='20 symbols with largest absolute OHLC discrepancy; diagnostic only, no exclusions or corrections'))
    data=json.loads(cache.read_text())
    raw=provider_frame(data['bars']).rename(columns={col:col+'_raw' for col in ('open','high','low','close','volume','vwap')})
    joined=pairs[pairs.eligible&pairs.symbol.isin(symbols)].merge(raw,on=['symbol','date'])
    rows=[]
    for symbol,part in joined.groupby('symbol'):
        raw_error=(part.close_raw/part.close_local-1).abs()*10000
        split_error=(part.close_sip/part.close_local-1).abs()*10000
        rows.append(dict(symbol=symbol,rows=len(part),raw_vs_local_close_absolute_bps=stats(raw_error),
            split_vs_local_close_absolute_bps=stats(split_error),
            split_to_raw_ratio=stats(part.close_sip/part.close_raw),
            outlier_days_split=int(split_error.gt(100).sum()),outlier_days_raw=int(raw_error.gt(100).sum())))
    joined.to_csv(output/'diagnostic-raw-split-local.csv',index=False)
    atomic_json(output/'adjustment-diagnostics.json',dict(selection_rule=data['selection_rule'],symbols=rows,
        limitation='Raw matching local does not establish the correct corporate-action convention; independent action verification still required'))
    metadata_cache=output/'alpaca-current-assets.json'
    if not metadata_cache.exists():
        assets=[]
        for status in ('active','inactive'):
            response=request_with_retry(verified_session(),'GET',ALPACA_ASSETS_ENDPOINT,
                headers=_build_headers('default'),params=dict(status=status,asset_class='us_equity'),
                policy=RetryPolicy(max_attempts=3,timeout_seconds=45))
            assets.extend({key:asset.get(key) for key in ('symbol','exchange','status','tradable','name')}
                for asset in response.json() if asset.get('symbol') in protocol['symbols'])
        atomic_json(metadata_cache,dict(observed_at_utc=pd.Timestamp.now(tz='UTC').isoformat(),assets=assets,
            limitation='Current asset metadata, not historical listing eligibility'))
    metadata=pd.DataFrame(json.loads(metadata_cache.read_text())['assets']).drop_duplicates('symbol',keep='first')
    coverage=pd.read_csv(output/'coverage-by-symbol.csv')
    coverage.merge(metadata,on='symbol',how='left').to_csv(output/'coverage-with-current-assets.csv',index=False)
    partial=coverage[coverage.sip_rows.gt(0)&coverage.local_only.gt(0)].symbol.tolist()
    remap_path=output/'diagnostic-asof-remapping.json'
    if not remap_path.exists():
        remapped={};pages=0
        for offset in range(0,len(partial),25):
            mapped,count=fetch(verified_session(),partial[offset:offset+25],protocol['start_date'],
                protocol['end_date'],asof=protocol['end_date'])
            remapped.update(mapped);pages+=count
        atomic_json(remap_path,dict(bars=remapped,pages=pages,asof=protocol['end_date'],
            limitation='Diagnostic alias remapping only; do not silently merge history without identity qualification'))
    remapped=provider_frame(json.loads(remap_path.read_text())['bars'])
    diagnostic=[]
    for symbol in partial:
        before=set(pairs.loc[pairs.symbol.eq(symbol)&pairs._merge.ne('left_only'),'date'])
        after=set(remapped.loc[remapped.symbol.eq(symbol),'date'])
        local_dates=set(pairs.loc[pairs.symbol.eq(symbol)&pairs._merge.ne('right_only'),'date'])
        diagnostic.append(dict(symbol=symbol,unmapped_rows=len(before),mapped_rows=len(after),
            extra_local_dates_matched=len((after-before)&local_dates)))
    atomic_json(output/'alias-diagnostics.json',dict(symbols=diagnostic,
        extra_local_dates_matched=sum(x['extra_local_dates_matched'] for x in diagnostic),
        limitation='Primary report remains asof=-; additional matches require identity validation'))
    logging.info('Adjustment diagnostics complete')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO);run(args.output_dir)
