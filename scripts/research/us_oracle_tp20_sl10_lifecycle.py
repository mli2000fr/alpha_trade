"""Qualify the archived TOELY/TELWY name change and version local replay tapes."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read
from scripts.research.us_oracle_merger_ledger import EVENTS

EVIDENCE = Path('artifacts/research/us_oracle_tp20_sl10_new/toely-alpaca-diagnostic-20261012')
PRICES = Path('artifacts/research/us_oracle_tp20_sl10_new/toely-diagnostic-20261012-trusted')


def load_events(root):
    """Opt-in, hash-verified lifecycle; legacy campaigns keep their old events."""
    path=Path(root)/'lifecycle.json'
    if not path.exists():return EVENTS
    ready=read(Path(root)/'ready.json')
    if 'lifecycle.json' not in ready['files']:raise ValueError('Unversioned lifecycle')
    verify_hashes(Path(root),{'lifecycle.json':ready['files']['lifecycle.json']})
    saved=read(path);verify_hashes(Path('.'),saved['source_hashes'])
    expected=qualify_name_change(read(EVIDENCE/'corporate-actions.json'))
    if saved['events']!=[expected]:raise ValueError('Lifecycle differs from provider evidence')
    return (*EVENTS,expected)


def qualify_name_change(payload):
    if payload.get('next_page_token'):
        raise ValueError('Incomplete corporate-action page')
    events = payload['corporate_actions'].get('name_changes', [])
    matches = [e for e in events if e.get('old_symbol') == 'TOELY' and e.get('new_symbol') == 'TELWY']
    if len(matches) != 1 or len(events) != 1:
        raise ValueError('Missing or ambiguous name change')
    e = matches[0]
    if (e['process_date'], e['old_cusip'], e['new_cusip']) != ('2026-09-17','889110102','889110201'):
        raise ValueError('Unexpected name-change date or identity')
    for family, records in payload['corporate_actions'].items():
        if family not in ('name_changes','forward_splits') and records:
            raise ValueError(f'Additional corporate action requires qualification: {family}')
    # A name/CUSIP change is not a stock exchange or cash merger. Preserve
    # quantity and the original expiry. The later split is already neutralized
    # in the common split-adjusted tapes, so it must NOT be applied twice.
    return dict(source='TOELY',target='TELWY',day=e['process_date'],ratio='1',cash_fraction=False,
        trading_symbol='TELWY',event_type='NAME_CHANGE',evidence_event_id=e['id'],
        old_cusip=e['old_cusip'],new_cusip=e['new_cusip'])


def normalize_successor(raw, splits):
    if splits != [{'date':'2026-10-07','split':'5.000000/1.000000'}]:
        raise ValueError('Unexpected split history')
    frame = pd.DataFrame(raw)
    frame['date'] = pd.to_datetime(frame.date)
    if frame.empty or frame.date.duplicated().any():
        raise ValueError('Empty/duplicate successor dates')
    required = ['open','high','low','close','volume']
    if not np.isfinite(frame[required]).all().all() or frame[required].le(0).any().any():
        raise ValueError('Unqualified successor OHLCV')
    if frame.high.lt(frame[['open','close','low']].max(axis=1)).any() or frame.low.gt(frame[['open','close','high']].min(axis=1)).any():
        raise ValueError('Inconsistent successor OHLC')
    factor = np.where(frame.date.lt('2026-10-07'),5.,1.)
    frame[['open','high','low','close']] = frame[['open','high','low','close']].div(factor,axis=0)
    # This response's volume is already in the same vendor basis as the
    # predecessor archive (checked on 11 overlapping sessions). Multiplying
    # again would silently count the five-for-one split twice.
    return frame[['date',*required]]


def prepare(source,output):
    source,output=Path(source),Path(output)
    if output.exists():raise ValueError('Use a new output version')
    ready=read(source/'ready.json');verify_hashes(source,ready['files'])
    evidence=read(EVIDENCE/'report.json')
    if evidence['corporate_actions_http'] != 200:raise ValueError('Corporate-action access failed')
    verify_hashes(EVIDENCE,{'corporate-actions.json':evidence['corporate_actions_sha256']})
    price_proof=read(PRICES/'successor-report.json')
    for name in ('telwy-eod','telwy-splits'):
        if price_proof[name]['status'] != 'OK':raise ValueError('Missing successor evidence')
        verify_hashes(PRICES,{name+'.json':price_proof[name]['sha256']})
    event=qualify_name_change(read(EVIDENCE/'corporate-actions.json'))
    official_splits=read(EVIDENCE/'corporate-actions.json')['corporate_actions']['forward_splits']
    if len(official_splits)!=1 or official_splits[0]['symbol']!='TELWY' or official_splits[0]['ex_date']!='2026-10-07' \
            or official_splits[0]['new_rate']/official_splits[0]['old_rate']!=5:
        raise ValueError('Split not confirmed by the broker reference')
    new=normalize_successor(read(PRICES/'telwy-eod.json'),read(PRICES/'telwy-splits.json'))
    prices=pd.read_parquet(source/'prices.parquet')
    old=prices.loc[prices.symbol.eq('TOELY')]
    overlap=new.merge(old,on='date',suffixes=('_new','_old'),validate='one_to_one')
    if len(overlap)<10:raise ValueError('Insufficient share-basis overlap')
    discrepancies={}
    for c in ('open','high','low','close','volume'):
        relative=(overlap[c+'_new']/overlap[c+'_old']-1).abs()
        if not relative.le(.001).all():raise ValueError(f'Successor basis disagrees with archive: {c}')
        discrepancies[c]=float(relative.max())
    new=new.loc[new.date.ge(event['day'])].copy()
    calendar=nyse_sessions(pd.Timestamp(event['day']).date(),pd.Timestamp('2026-10-09').date())
    if set(new.date)!=set(calendar):raise ValueError('Incomplete successor tail')
    if prices.symbol.eq('TELWY').any():raise ValueError('Successor already exists; no overwrite')
    new['symbol']='TELWY';new['adj_close']=new.close;new['is_filled']=0
    new['vwap']=np.nan;new['daily_return']=np.nan
    new['instrument_id']='CUSIP:889110201'
    new['data_source']='EODHD_ARCHIVED_NAME_CHANGE_TAIL'
    prices=pd.concat([prices,new],ignore_index=True)
    prices['instrument_id']=prices.instrument_id.astype('string')
    output.mkdir(parents=True)
    for name in ('scores.parquet','features.parquet','macro.parquet','protocol.json','correction-audit.json',
                 'remediation-inputs.json'):
        shutil.copy2(source/name,output/name)
    prices.to_parquet(output/'prices.parquet',index=False)
    paths=[EVIDENCE/'corporate-actions.json',EVIDENCE/'report.json',PRICES/'telwy-eod.json',PRICES/'telwy-splits.json',
           PRICES/'successor-report.json',source/'ready.json',source/'prices.parquet']
    lifecycle=dict(events=[event],source_hashes={str(p):digest(p) for p in paths},
        source=str(source),code_sha256=digest(__file__),sql_writes=False,broker_orders=False,
        overlap_rows=len(overlap),maximum_relative_discrepancies=discrepancies,
        successor_rows=len(new),split_adjusted_basis=True,split_applied_twice=False,
        reserves=['current provider history, not independently archived at each historical date',
            'provider volume basis agrees with predecessor but is not independent OTC-volume certification',
            'atomic protection migration simulated, no observed broker replacement fills',
            'no observed account-specific corporate-action fees'])
    atomic_json(output/'lifecycle.json',lifecycle)
    verify_hashes(Path('.'),lifecycle['source_hashes'])
    names=['prices.parquet','scores.parquet','features.parquet','macro.parquet','protocol.json',
           'correction-audit.json','remediation-inputs.json','lifecycle.json']
    atomic_json(output/'ready.json',dict(ready,files={n:digest(output/n) for n in names}))
    atomic_json(output/'progress.json',dict(status='READY_BASELINE',lifecycle=event,successor_rows=len(new)))
    print(lifecycle,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:prepare(**vars(args))
    except Exception as exc:
        if args.output.exists():atomic_json(args.output/'progress.json',dict(status='FAILED',error=str(exc)))
        raise
