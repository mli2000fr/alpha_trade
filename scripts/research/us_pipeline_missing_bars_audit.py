"""Bounded read-only audit of a failed session import. No SQL writes/orders."""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text

from common.verified_http import verified_session
from database.connection import get_sqlalchemy_engine
from dataIntegrityEngine.backfill_alpaca_history import convert
from service.alpaca.clientAlpaca import _build_headers, fetch_alpaca_assets
from service.alpaca.daily_history import fetch_daily_history
from service._http_retry import request_with_retry, RetryPolicy


def save(path, data):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, default=str)


def run(record_path, output):
    output=Path(output)
    if output.exists(): raise ValueError('Fresh output required')
    record_path=Path(record_path)
    record=json.loads(record_path.read_text(encoding='utf-8'))
    gate=record['run_summary']['target_coverage']
    missing=gate['missing_symbols']; day=gate['target_date']
    output.mkdir(parents=True)
    save(output/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        input=str(record_path), input_sha256=hashlib.sha256(record_path.read_bytes()).hexdigest(),
        target_date=day, missing_count=len(missing), writes_sql=False, orders=False,
        limits='Current broker metadata is not historical delisting evidence. No universe changes.',
        requested_calls='One assets listing; paginated exact-session missing bars; ACVA 7-day reproduction.'))
    engine=get_sqlalchemy_engine()
    query=text('''SELECT m.symbol,m.exchange,m.status,m.tradable,m.history_status,
        (SELECT MAX(b.date) FROM stock_bars_daily b WHERE b.symbol=m.symbol AND b.date<=:day) AS last_daily
        FROM stock_metadata m WHERE m.symbol IN :symbols''').bindparams(bindparam('symbols',expanding=True))
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':raise ValueError('US DB only')
        metadata={r.symbol:dict(r._mapping) for r in conn.execute(query,dict(symbols=missing,day=day))}
    with verified_session() as http:
        assets=fetch_alpaca_assets(account_id='default',session=http)
    if not isinstance(assets,list): raise ValueError('Assets list expected')
    save(output/'assets.json',assets)
    by_symbol={r['symbol']:r for r in assets}
    # The target is historical and fixed; no latest or indicative feed.
    beginning=datetime.fromisoformat(day).replace(tzinfo=ZoneInfo('America/New_York'))
    end=beginning+timedelta(days=1)
    params=dict(symbols=','.join(missing),timeframe='1Day',feed='sip',adjustment='split',asof='-',
        start=beginning.isoformat(),end=end.isoformat(),limit=10000,sort='asc')
    pages=[]; returned={}; seen=set()
    with verified_session() as http:
        while True:
            response=request_with_retry(http,'GET','https://data.alpaca.markets/v2/stocks/bars',
                headers=_build_headers('default'),params=params,
                policy=RetryPolicy(max_attempts=3,timeout_seconds=45))
            payload=response.json()
            if not isinstance(payload.get('bars'),dict):raise ValueError('Invalid bars payload')
            if set(payload['bars'])-set(missing):raise ValueError('Unexpected symbol')
            pages.append(payload)
            for symbol,bars in payload['bars'].items():returned.setdefault(symbol,[]).extend(bars)
            token=payload.get('next_page_token')
            if not token:break
            if token in seen or len(pages)>10:raise ValueError('Unexpected pagination')
            seen.add(token);params['page_token']=token
    save(output/'target-bar-pages.json',pages)
    rows=[]
    for symbol in missing:
        asset=by_symbol.get(symbol,{})
        rows.append(dict(symbol=symbol,local=metadata.get(symbol),
            current_asset={k:asset.get(k) for k in ('id','symbol','exchange','status','tradable','name')},
            asset_in_listing=bool(asset),target_rows=len(returned.get(symbol,[]))))
    save(output/'missing-symbols.json',rows)
    start=(datetime.fromisoformat(day).date()-timedelta(days=7)).isoformat()
    acva=fetch_daily_history('ACVA',start=start,end=day,feed='sip',account_id='default')
    save(output/'ACVA-seven-days.json',acva)
    try:
        daily,_=convert('ACVA',acva,'sip',start,day)
        acva_result=dict(status='VALID',rows=len(daily))
    except Exception as exc:
        acva_result=dict(status='ERROR',error_type=type(exc).__name__,message=str(exc))
    report=dict(target_date=day,missing_original=len(missing),
        current_groups=dict(Counter(f"{r['current_asset']['exchange']}|{r['current_asset']['status']}|{r['asset_in_listing']}|bars={r['target_rows']}" for r in rows)),
        target_symbols_returned=sum(bool(r['target_rows']) for r in rows),acva=acva_result,
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()})
    save(output/'report.json',report)
    print(json.dumps(report,indent=2,default=str))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record',required=True);parser.add_argument('--output-dir',required=True)
    args=parser.parse_args();run(args.record,args.output_dir)
