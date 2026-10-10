"""Frozen, bounded historical call/put volume pilot (API GET and SQL SELECT only)."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sqlalchemy import text

from common.market_calendar import get_market_calendar
from database.connection import get_sqlalchemy_engine
from scripts.research.us_prospective_directional_collection_audit import query
from scripts.research.us_prospective_directional_check import directional_metrics
from service.alpaca.accounts import AccountRegistry
from service.alpaca.clientAlpaca import get_alpaca_credentials
from service.forward_pit.batch import _configure_alpaca_session

OUTPUT = Path('artifacts/research/alpaca_options_history/20261010-volume-pilot')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')


def paired_features(bars, contracts, spots):
    if bars.empty or contracts.empty:
        return pd.DataFrame(columns=['day', 'symbol', 'volume_call_minus_put_log'])
    bars = bars.merge(contracts, on='contract_symbol', validate='many_to_one')
    bars['day'] = pd.to_datetime(bars['t'], utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    bars['expiry'] = pd.to_datetime(bars.expiration_date)
    bars['volume'] = pd.to_numeric(bars.v, errors='coerce')
    bars['strike'] = pd.to_numeric(bars.strike_price, errors='coerce')
    bars = bars.merge(spots, on=['day', 'symbol'], validate='many_to_one')
    bars['dte'] = (bars.expiry-bars.day).dt.days
    bars['distance'] = (bars.strike/bars.spot-1).abs()
    bars = bars[bars.dte.between(15,25) & bars.distance.le(.05) & bars.volume.ge(0)]
    keys = ['day','symbol','expiry','strike']
    pairs = bars[bars.type.eq('call')].merge(bars[bars.type.eq('put')], on=keys, suffixes=('_call','_put'), validate='one_to_one')
    pairs['tenor_distance'] = (pairs.dte_call-20).abs()
    pairs = pairs.sort_values(['day','symbol','tenor_distance','distance_call','strike']).drop_duplicates(['day','symbol'])
    pairs['volume_call_minus_put_log'] = np.log1p(pairs.volume_call)-np.log1p(pairs.volume_put)
    return pairs


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw_universe = UNIVERSE.read_bytes()
    symbols = sorted(set(x for x in re.split(r'[,;\s]+',raw_universe.decode('utf-8-sig').strip()) if x))
    protocol = {'status':'PRE_REGISTERED_BEFORE_OPTIONS_DOWNLOAD','start':'2025-01-02','end':'2025-01-31',
        'universe':str(UNIVERSE),'universe_sha256':hashlib.sha256(raw_universe).hexdigest(),
        'selection':'40 largest median December 2024 dollar volumes within current tradable file',
        'pair':'same strike/expiry; nearest 20 calendar DTE within 15..25; nearest ATM within 5%',
        'feature':'log1p(call volume)-log1p(put volume); positive orientation fixed',
        'horizons':[3,5,10,20],'entry':'next US session open','exit':'Hth session close including entry',
        'labels':'signed-return deciles of full price-qualified current universe; min coverage 90%',
        'sql_writes':False,'models_trained':False,'threshold_tuning':False,
        'limits':'100 API pages per underlying, 40 selected underlyings; checkpoint API payloads',
        'historical_availability':'assumed next-session before open, NOT independently certified historical PIT'}
    (OUTPUT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
        prices = pd.DataFrame(query(conn, '''SELECT symbol,date,open,high,low,close,volume,is_filled,data_adjustment
            FROM alpha_trade.stock_bars_daily WHERE symbol IN :symbols
            AND date >= '2024-12-01' AND date <= '2025-03-07' ''',symbols))
        conn.rollback()
    engine.dispose()
    prices['date'] = pd.to_datetime(prices.date)
    for col in ['open','high','low','close','volume']:
        prices[col] = pd.to_numeric(prices[col],errors='coerce')
    prices['valid'] = (prices.is_filled.eq(0) & prices.data_adjustment.eq('split') & prices.open.gt(0)
        & prices.close.gt(0) & prices.volume.gt(0) & prices.high.ge(prices[['open','close']].max(axis=1))
        & prices.low.le(prices[['open','close']].min(axis=1)))
    past = prices[prices.date.lt('2025-01-01') & prices.valid].copy()
    past['dollar_volume'] = past.close*past.volume
    ranking = past.groupby('symbol').agg(median=('dollar_volume','median'),count=('date','size'))
    selected = ranking[ranking['count'].ge(15)].sort_values(['median'],ascending=False).head(40).index.tolist()
    protocol['selected_symbols'] = selected
    (OUTPUT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    key, secret = get_alpaca_credentials('default')
    mode = AccountRegistry.get().resolve('default').mode
    broker = 'https://paper-api.alpaca.markets' if mode=='paper' else 'https://api.alpaca.markets'
    errors, all_bars, all_contracts = [], [], []
    with requests.Session() as session:
        _configure_alpaca_session(session,use_system_trust_store=True)
        session.headers.update({'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret})
        def pages(name,url,params):
            saved = OUTPUT/f'{name}.json'
            if saved.exists():
                return json.loads(saved.read_text(encoding='utf-8'))
            payloads=[]
            for _ in range(100):
                response=session.get(url,params=params,timeout=40)
                if response.status_code!=200:
                    raise RuntimeError(f'HTTP {response.status_code}: {response.text[:300]}')
                payload=response.json();payloads.append(payload)
                token=payload.get('next_page_token')
                if not token:break
                params=params|{'page_token':token}
                time.sleep(.4)
            else:
                raise RuntimeError('Pagination limit reached: incomplete response excluded')
            saved.write_text(json.dumps(payloads),encoding='utf-8')
            time.sleep(.4)
            return payloads
        for index,symbol in enumerate(selected,1):
            try:
                catalog = pages(f'{symbol}-contracts',broker+'/v2/options/contracts',
                    {'underlying_symbols':symbol,'status':'inactive','expiration_date_gte':'2025-01-17',
                     'expiration_date_lte':'2025-02-25','limit':1000})
                contracts=[x for p in catalog for x in p.get('option_contracts',[])
                    if x.get('root_symbol')==symbol and str(x.get('size')) in {'100','100.0'}]
                # Restrict strike range using only the previous month's price distribution.
                reference = past.loc[past.symbol.eq(symbol),'close'].median()
                contracts=[x for x in contracts if .7*reference<=float(x['strike_price'])<=1.3*reference]
                for batch in range(0,len(contracts),100):
                    chunk=contracts[batch:batch+100]
                    data=pages(f'{symbol}-bars-{batch//100}', 'https://data.alpaca.markets/v1beta1/options/bars',
                        {'symbols':','.join(x['symbol'] for x in chunk),'timeframe':'1Day',
                         'start':'2025-01-02T00:00:00Z','end':'2025-02-01T00:00:00Z','limit':10000})
                    all_bars.extend({'contract_symbol':contract,**row} for p in data
                        for contract,rows in p.get('bars',{}).items() for row in rows)
                all_contracts.extend({'contract_symbol':x['symbol'],'symbol':symbol,
                    **{k:x[k] for k in ['expiration_date','strike_price','type']}} for x in contracts)
                print(f'{index}/{len(selected)} {symbol}: contracts={len(contracts)} total_bars={len(all_bars)}',flush=True)
            except Exception as exc:
                errors.append({'symbol':symbol,'error':str(exc)})
                print(f'{index}/{len(selected)} {symbol}: ERROR {exc}',flush=True)
            (OUTPUT/'progress.json').write_text(json.dumps({'status':'RUNNING','completed':index,'total':len(selected),
                'bars':len(all_bars),'errors':errors},indent=2),encoding='utf-8')
    bar_frame=pd.DataFrame(all_bars).drop_duplicates(['contract_symbol','t']) if all_bars else pd.DataFrame()
    contract_frame=pd.DataFrame(all_contracts).drop_duplicates('contract_symbol') if all_contracts else pd.DataFrame()
    spots=prices[prices.valid][['date','symbol','close']].rename(columns={'date':'day','close':'spot'})
    features=paired_features(bar_frame,contract_frame,spots)
    if not bar_frame.empty:bar_frame.to_parquet(OUTPUT/'downloaded_bars.parquet',index=False)
    features.to_parquet(OUTPUT/'features.parquet',index=False)
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    sessions=pd.DatetimeIndex(calendar.session_dates(date(2025,1,2),date(2025,3,7)))
    features['entry_date']=features.day.map({d:sessions[sessions>d][0] for d in features.day.unique()}) if not features.empty else pd.Series(dtype='datetime64[ns]')
    opens=prices.pivot(index='date',columns='symbol',values='open')
    closes=prices.pivot(index='date',columns='symbol',values='close')
    valid=prices.pivot(index='date',columns='symbol',values='valid')
    report={'status':'COMPLETED_RESEARCH_PILOT','protocol':protocol,'errors':errors,
        'downloaded_bars':len(bar_frame),'paired_symbol_days':len(features),'horizons':{},
        'limitations':['Current universe, survivorship bias; high-liquidity subset only',
            'Historical catalog observed today; adjusted/nonstandard roots excluded; not certified historical chain',
            'Split-adjusted stock spot may differ from historical raw strike reference after later splits',
            'Bars endpoint rejects feed parameter; provenance remains UNVERIFIED_OPRA',
            'Historical availability assumed, not archived as-known; overlapping returns; no PnL or promotion',
            'ATM matched-pair feature differs from aggregate-volume feature of prospective audit',
            'No historical open interest, IV, Greeks or NBBO downloaded']}
    for horizon in [3,5,10,20]:
        targets=[]
        for entry in sorted(features.entry_date.unique()):
            start=sessions.get_loc(entry);path=sessions[start:start+horizon]
            if len(path)!=horizon:continue
            good=valid.reindex(path).eq(True).all(axis=0)
            returns=closes.reindex([path[-1]]).iloc[0]/opens.reindex([entry]).iloc[0]-1
            returns=returns[good & np.isfinite(returns)]
            if len(returns)<.9*len(symbols):continue
            target=returns.rename('future_return').reset_index().sort_values(['future_return','symbol'],kind='stable')
            target['decile']=(np.floor(np.arange(len(target))*10/len(target))+1).astype(int)
            target['entry_date']=entry;targets.append(target)
        if not targets:
            report['horizons'][str(horizon)]={'status':'NO_QUALIFIED_LABELS'};continue
        joined=features.merge(pd.concat(targets),on=['entry_date','symbol'],validate='one_to_one')
        joined.to_parquet(OUTPUT/f'pairs_h{horizon}.parquet',index=False)
        report['horizons'][str(horizon)]=directional_metrics(joined,'volume_call_minus_put_log')
    (OUTPUT/'report.json').write_text(json.dumps(report,indent=2,default=str,allow_nan=False),encoding='utf-8')
    (OUTPUT/'progress.json').write_text(json.dumps({'status':'COMPLETED','bars':len(bar_frame),'paired_symbol_days':len(features)}),encoding='utf-8')
    print(json.dumps({h:{k:v.get(k) for k in ['samples','extreme_samples','entry_dates','auc_pooled_exploratory']}
        for h,v in report['horizons'].items()}),flush=True)


if __name__=='__main__':
    run()
