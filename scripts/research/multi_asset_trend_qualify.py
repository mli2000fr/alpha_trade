"""Offline ETF reconciliation, with one separately requested public DBC evidence receipt."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.multi_asset_trend_data import prepare, READ
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

DBC_URL = 'https://www.sec.gov/Archives/edgar/data/1328237/000156459019005072/dbc-10k_20181231.htm'


def capture_proof(root):
    from common.verified_http import verified_session
    out = root / 'dbc-proof-v1'
    if out.exists(): raise ValueError('Evidence directory immutable')
    agent = os.getenv('SEC_EDGAR_USER_AGENT', '')
    if '@' not in agent or 'example.com' in agent: raise ValueError('Identified SEC user agent required')
    out.mkdir()
    with verified_session() as session:
        response = session.get(DBC_URL, headers={'User-Agent': agent}, timeout=(10,45))
    if len(response.content) > 8*1024*1024: raise ValueError('Evidence size cap')
    (out / 'source.html').write_bytes(response.content)
    atomic_json(out / 'receipt.json', dict(url=DBC_URL, status_code=response.status_code,
        observed_at_utc=datetime.now(timezone.utc).isoformat(), sha256=digest(out/'source.html')))
    if response.status_code != 200: raise RuntimeError(f'SEC evidence HTTP {response.status_code}; no bypass')


def sessions(start, end):
    return mcal.get_calendar('NYSE').valid_days(start_date=start, end_date=end).tz_localize(None)


def load_bars(root, kind):
    records = []
    for item in READ(root / 'download.json')['kinds'][kind]:
        data = READ(root / item['file'])['payload']['bars']
        for symbol, rows in data.items():
            for row in rows:
                records.append(dict(symbol=symbol,
                    date=pd.Timestamp(row['t']).tz_convert('America/New_York').tz_localize(None).normalize(),
                    open=row['o'], high=row['h'], low=row['l'], close=row['c'], volume=row['v']))
    return pd.DataFrame(records).sort_values(['symbol','date']).reset_index(drop=True)


def validate_prices(frame, symbols, days):
    if set(frame.symbol) != set(symbols) or frame.duplicated(['symbol','date']).any():
        raise ValueError('Wrong universe or duplicate prices')
    for symbol, group in frame.groupby('symbol'):
        if not pd.DatetimeIndex(group.date.sort_values()).equals(days):
            raise ValueError(f'Incomplete calendar {symbol}')
    values=frame[['open','high','low','close','volume']].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values<=0).any(): raise ValueError('Invalid OHLCV')
    if ((frame.low>frame[['open','close','high']].min(axis=1)+1e-8) |
        (frame.high<frame[['open','close','low']].max(axis=1)-1e-8)).any():
        raise ValueError('Inconsistent OHLC')


def rates_match(precise, rounded):
    # Provider decimal precision is observable, not a tolerance fitted to returns.
    quantum = Decimal(str(rounded)).as_tuple().exponent
    tolerance = float(Decimal(10) ** quantum) / 2 + 1e-10
    return abs(float(precise)-float(rounded)) <= tolerance


def proof_valid(root):
    from bs4 import BeautifulSoup
    folder=root/'dbc-proof-v1'; receipt=READ(folder/'receipt.json')
    if receipt['url']!=DBC_URL or receipt['status_code']!=200 or digest(folder/'source.html')!=receipt['sha256']:
        raise ValueError('Invalid DBC evidence')
    text=' '.join(BeautifulSoup((folder/'source.html').read_bytes(),'html.parser').stripped_strings)
    required=['On December 31, 2018, the Fund paid a distribution of $0.18853',
              'holders of record as of December 26, 2018',
              'A distribution for the year ended December 31, 2018 was paid on December 31, 2018']
    if not all(s in text for s in required): raise ValueError('Annual distribution evidence not found')
    return dict(url=DBC_URL, sha256=receipt['sha256'], conclusion='One2018 distribution .18853USD, recordDec26, paidDec31; corroborates duplicate record-date row, not a second dividend.')


def reconcile_dividends(root, cfg):
    proof=proof_valid(root); alpaca={}; rejected=[]
    for item in READ(root/'download.json')['kinds']['actions']:
        payload=READ(root/item['file'])['payload']['corporate_actions']
        for kind, rows in payload.items():
            if kind!='cash_dividends' and rows: raise ValueError(f'Unsupported action {kind}')
        for row in payload.get('cash_dividends',[]):
            key=(row['symbol'], row['ex_date'])
            if key in alpaca: raise ValueError('Duplicate same-date cash action')
            alpaca[key]=row
    rows=[]; matched=set()
    for symbol in cfg['symbols']:
        for item in READ(root/'supplement-v1'/f'{symbol}-dividends.json')['payload']:
            ex=pd.Timestamp(item['date']); pay=pd.Timestamp(item['paymentDate'])
            if item['currency']!='USD' or pd.isna(pay) or pay<ex:
                raise ValueError('Unqualified distribution currency/paydate')
            key=(symbol,item['date']); source=alpaca.get(key)
            amount=float(item['unadjustedValue'])
            if source:
                if not rates_match(source['rate'],amount): raise ValueError(f'Distribution amount mismatch {key}')
                if source.get('payable_date') and pd.Timestamp(source['payable_date'])!=pay:
                    raise ValueError(f'Payment date mismatch {key}')
                amount=float(source['rate']);matched.add(key)
            if not np.isfinite(amount) or amount<=0: raise ValueError('Invalid dividend')
            rows.append(dict(symbol=symbol,ex_date=ex,pay_date=pay,amount=amount,
                amount_source='alpaca_precision_eodhd_corroborated' if source else 'eodhd_only_rounded',
                date_source='eodhd',eodhd_amount=item['unadjustedValue'],
                record_date=item.get('recordDate'),declaration_date_unqualified=item.get('declarationDate')))
    keys={(r['symbol'],str(r['ex_date'].date())) for r in rows}
    if len(keys)!=len(rows): raise ValueError('Duplicate EODHD action')
    for key, row in alpaca.items():
        if key in matched: continue
        if key==('DBC','2018-12-26') and row['rate']==.18853 and ('DBC','2018-12-24') in keys:
            rejected.append(dict(source='alpaca',symbol=key[0],ex_date=key[1],amount=row['rate'],
                reason='DUPLICATED_RECORD_DATE_2018_DISTRIBUTION',evidence=proof))
        else: raise ValueError(f'Unreconciled Alpaca distribution {key}')
    return pd.DataFrame(rows).sort_values(['symbol','ex_date']), rejected


def run(root):
    cfg=prepare(root)['config']; sup=root/'supplement-v1'; out=root/'qualified-v1'
    if out.exists(): raise ValueError('Qualified output immutable')
    verify_hashes(root,READ(root/'download.json')['files'])
    verify_hashes(Path('.'),READ(sup/'protocol.json')['sources'])
    verify_hashes(sup,READ(sup/'report.json')['files'])
    raw=load_bars(root,'raw'); split=load_bars(root,'split'); adjusted=load_bars(root,'all')
    days=sessions(cfg['start'],cfg['end']); validate_prices(raw,cfg['symbols'],days)
    for other in [split,adjusted]: validate_prices(other,cfg['symbols'],days)
    if not raw[['symbol','date']].equals(split[['symbol','date']]): raise ValueError('Split keys differ')
    if not np.allclose(raw[['open','high','low','close']],split[['open','high','low','close']],atol=1e-8,rtol=0):
        raise ValueError('Split adjustment present; explicit split lifecycle required')
    warm=pd.read_parquet(sup/'warmup-local.parquet'); warm['date']=pd.to_datetime(warm.date)
    for column in ['open','high','low','close','volume']:
        warm[column]=pd.to_numeric(warm[column]).astype(float)
    if warm.is_filled.fillna(True).astype(bool).any(): raise ValueError('Filled warmup')
    if not warm.data_source.eq('eodhd_eod').all() or not warm.data_adjustment.eq('split').all():
        raise ValueError('Unknown warmup provenance')
    overlap=warm.merge(raw,on=['symbol','date'],suffixes=('_local','_alpaca'))
    if len(overlap)!=20: raise ValueError('Expected five overlapping sessions per ETF')
    max_rel={c:float((overlap[c+'_local']/overlap[c+'_alpaca']-1).abs().max()) for c in ['open','high','low','close']}
    if max(max_rel.values())>.001: raise ValueError('Warmup seam >10bps')
    pre=warm[warm.date<days[0]][['symbol','date','open','high','low','close','volume']].copy()
    pre['source']='eodhd_eod_split_no_splits_qualified';raw['source']='alpaca_sip_raw'
    prices=pd.concat([pre,raw],ignore_index=True).sort_values(['symbol','date'])
    validate_prices(prices,cfg['symbols'],sessions(cfg['history_start'],cfg['end']))
    dividends,rejected=reconcile_dividends(root,cfg)
    if any(d not in prices.date.unique() for d in dividends.loc[dividends.ex_date<=pd.Timestamp(cfg['end']),'ex_date']):
        raise ValueError('Distribution date outside available sessions')
    # Quantization-aware diagnostic: cent-rounded adjusted closes can imply ~2c
    # of phantom cash. 5c cutoff flags only material missing events, never sets a rule.
    diag=[]; extras=[]; eodhd_only=[]
    for symbol in cfg['symbols']:
        a=adjusted[adjusted.symbol==symbol].set_index('date').close
        r=raw[raw.symbol==symbol].set_index('date').close
        f=a/r; implied=r.shift(1)*(1-f.shift(1)/f)
        known=set(dividends.loc[dividends.symbol==symbol,'ex_date'])
        for day, amount in implied.items():
            if pd.notna(amount) and abs(amount)>.05:
                diag.append(dict(symbol=symbol,date=str(day.date()),implied_cash_diagnostic=float(amount),
                    in_qualified_events=day in known))
                if day not in known: extras.append((symbol,str(day.date())))
        for row in dividends[(dividends.symbol==symbol)&dividends.amount_source.eq('eodhd_only_rounded')].itertuples():
            if days[0]<row.ex_date<=days[-1]:
                eodhd_only.append(dict(symbol=symbol,date=str(row.ex_date.date()),amount=row.amount,
                    adjusted_alpaca_corroborates=abs(float(implied.get(row.ex_date,0)))>.05,
                    limitation='EODHD dates/amount accepted for exploratory pilot, not issuer-certified exhaustive distribution history.'))
    if extras!=[('DBC','2018-12-26')]: raise ValueError(f'Unexpected adjusted-price events {extras}')
    out.mkdir()
    paths=[Path(__file__),Path('tests/test_multi_asset_trend_qualify.py'),root/'protocol.json',root/'download.json',
        sup/'report.json',root/'dbc-proof-v1'/'receipt.json']
    atomic_json(out/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(p):digest(p) for p in paths}, data_only_no_performance=True))
    prices.to_parquet(out/'prices.parquet',index=False);dividends.to_parquet(out/'dividends.parquet',index=False)
    atomic_json(out/'reconciliation.json',dict(rejected=rejected,eodhd_only_missing_in_alpaca_actions=eodhd_only,
        adjustment_diagnostic=diag,adjusted_alpaca_series_used=False,
        note='Historical source reconciliation only; no production correction. Declaration dates unreliable and unused. No historical-vintage PIT claim.'))
    report=dict(status='QUALIFIED_EXPLORATORY_RECONSTRUCTION',symbols=cfg['symbols'],
        bars=len(prices),test_sessions=len(days),warmup_sessions=len(pre)//4,
        overlap_rows=len(overlap),max_overlap_relative_difference=max_rel,
        dividend_rows=len(dividends),rejected_duplicate_actions=len(rejected),
        fees_certified=False,production_or_live_parity=False,
        files={p.name:digest(p) for p in out.iterdir() if p.is_file()})
    atomic_json(out/'report.json',report);print(report['status'],report['bars'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--phase',choices=['proof','qualify'],required=True);a=p.parse_args()
    (capture_proof if a.phase=='proof' else run)(a.root)
