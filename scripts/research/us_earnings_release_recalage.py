"""Offline re-timing with source-release amounts and decision-price inputs only."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
PRICE=Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')


def source_values(proofs):
    """All four values must be in same exhibit/table, not a cross-table mixture."""
    groups={}
    for p in proofs:
        key=(p['release_accession'],p['exhibit_type'],p['table_index'])
        groups.setdefault(key,{}).setdefault(p['metric'],[]).append(tuple(p['reported_values']))
    candidates=set()
    for group in groups.values():
        if set(group)!= {'revenue','operating'}:continue
        rev=set(group['revenue']);op=set(group['operating'])
        if len(rev)==len(op)==1:candidates.add((*next(iter(rev)),*next(iter(op))))
    if len(candidates)!=1:return None
    return next(iter(candidates))


def accounting(values):
    if values is None:return 'ABSTAIN',None,None
    rev,oldrev,op,oldop=values
    if min(rev,oldrev)<=0:return 'ABSTAIN',None,None
    g=rev/oldrev-1;m=op/rev-oldop/oldrev
    return ('LONG' if g>0 and m>0 else 'SHORT' if g<0 and m<0 else 'ABSTAIN'),g,m


def price_reaction(rows):
    """Stock pair then SPY pair; no future path or missing-price zero."""
    if len(rows)!=4 or any(r is None for r in rows):return None,'UNKNOWN','MISSING_REACTION_PRICE'
    for row in rows:
        if any(row.get(k) is None or not np.isfinite(row[k]) or row[k]<=0 for k in ('open','high','low','close','adj_close','volume')):
            return None,'UNKNOWN','INVALID_REACTION_PRICE'
        if row['is_filled']!=0 or row['high']<max(row['open'],row['close']) or row['low']>min(row['open'],row['close']):
            return None,'UNKNOWN','INVALID_REACTION_PRICE'
    for pair in (rows[:2],rows[2:]):
        for k in ('instrument_id','data_source','data_adjustment'):
            if any(pd.isna(r.get(k)) or str(r[k]).upper() in ('UNKNOWN','','NONE','NAN') for r in pair) or pair[0][k]!=pair[1][k]:
                return None,'UNKNOWN','CHANGED_OR_UNKNOWN_PRICE_BASIS'
    value=rows[1]['adj_close']/rows[0]['adj_close']-rows[3]['adj_close']/rows[2]['adj_close']
    return value,('LONG' if value>0 else 'SHORT' if value<0 else 'ABSTAIN'),None


def run(parent,review,output):
    if output.exists():raise ValueError('Fresh re-timing directory required')
    for root in (parent,review):
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources'])
        r=READ(root/'report.json');verify_hashes(root,r['files'])
    files=[Path(__file__),Path('tests/test_us_earnings_release_recalage.py'),PRICE,
        PRICE.parent/'quality-reserves.json',parent/'reconstructed-cases.parquet',parent/'report.json',
        review/'table-evidence.json',review/'case-review.json',review/'report.json']
    output.mkdir(parents=True)
    atomic_json(output/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(x):digest(x) for x in files},scope='Same93 frozen cases. Literal first-release table amounts ONLY, first full session after explicit UTC SEC acceptance, revisedTOP10 membership. No future outcomes.',
        reserve='SEC acceptance is a public reconstruction proxy,not earliest worldwide IR publication or historical local receipt. Accounting/identity scope not independently certified.',
        sql=False,api_calls=0,llm_calls=0,training=False,orders=False))
    proofs=READ(review/'table-evidence.json')['proofs'];bycase={}
    for p in proofs:bycase.setdefault(p['case_accession'],[]).append(p)
    cases=pd.read_parquet(parent/'reconstructed-cases.parquet')
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2023-01-01',end_date='2026-10-20')
    keys=set();values={}
    for c in cases.itertuples():
        v=source_values(bycase.get(c.case_accession,[]));values[c.case_accession]=v
        if v is not None and pd.notna(c.corrected_reaction):
            j=schedule.index.get_loc(c.corrected_reaction)
            keys.update((s,d) for s in (c.symbol,'SPY') for d in (schedule.index[j-1],schedule.index[j]))
    columns=['symbol','date','open','high','low','close','adj_close','volume','is_filled','instrument_id','data_source','data_adjustment']
    # Date AND symbol filters: reaction features only, no H10/H20 targets.
    prices=pd.read_parquet(PRICE,columns=columns,filters=[('symbol','in',sorted({s for s,_ in keys})),('date','in',sorted({d for _,d in keys}))]) if keys else pd.DataFrame(columns=columns)
    prices=prices[[k in keys for k in zip(prices.symbol,prices.date)]]
    if prices.duplicated(['symbol','date']).any():raise ValueError('Duplicate feature price')
    lookup={(r['symbol'],r['date']):r for r in prices.to_dict('records')}
    old=pd.read_parquet(Path(READ(parent/'protocol.json')['parent'])/'top10-candidates.parquet')
    oldpatterns=dict(zip(old.accession_number,old.agreement_pattern));rows=[]
    for c in cases.itertuples():
        v=values[c.case_accession];side,growth,margin=accounting(v);relative=None;price_side='UNKNOWN';reason=None;entry=None
        if v is None:reason='FOUR_RELEASE_AMOUNTS_NOT_UNAMBIGUOUS_IN_SAME_TABLE'
        elif pd.isna(c.corrected_reaction):reason='CORRECTED_REACTION_UNAVAILABLE'
        else:
            j=schedule.index.get_loc(c.corrected_reaction)
            bars=[lookup.get((s,d)) for s in (c.symbol,'SPY') for d in (schedule.index[j-1],schedule.index[j])]
            relative,price_side,reason=price_reaction(bars)
            if j+1<len(schedule):entry=schedule.index[j+1]
        agree=side if reason is None and side in ('LONG','SHORT') and side==price_side else 'ABSTAIN'
        eligible=c.temporal_candidate_without_missing_documents and c.retained_in_corrected_top10 and reason is None
        rows.append(dict(symbol=c.symbol,case_accession=c.case_accession,release_accession=c.release_accession,
            original_reaction=c.original_reaction,corrected_reaction=c.corrected_reaction,potential_entry_date=entry,
            corrected_rank=c.corrected_rank,release_values=v,source_revenue_growth=growth,source_margin_change=margin,
            accounting_pattern=side,relative_reaction=relative,price_pattern=price_side,
            provisional_agreement=agree if eligible else 'ABSTAIN',old_unverified_agreement=oldpatterns[c.case_accession],
            feature_candidate=bool(eligible),reason=reason,qualified_direction='ABSTAIN',fully_qualified=False))
    frame=pd.DataFrame(rows);frame.to_parquet(output/'retimed-features.parquet',index=False)
    prices.to_parquet(output/'reaction-price-inputs.parquet',index=False)
    years=[]
    for year in (2024,2025,2026):
        sub=frame[pd.to_datetime(frame.original_reaction).dt.year.eq(year)]
        years.append(dict(year=year,cases=len(sub),table_amounts_verified=int(sub.release_values.notna().sum()),
            feature_candidates=int(sub.feature_candidate.sum()),provisional_agreements=sub.provisional_agreement.value_counts().to_dict()))
    result=dict(status='RECALAGE_COMPLETED_SOURCE_AMOUNTS_ONLY_NO_EFFICACY_TEST',cases=len(frame),
        four_amounts_unambiguous_same_table=int(frame.release_values.notna().sum()),feature_candidates=int(frame.feature_candidate.sum()),
        provisional_agreements=frame.provisional_agreement.value_counts().to_dict(),years=years,fully_qualified=0,
        reserve='Provisional feature agreement,not win-rate or PnL. Unqualified novelty/merger/issuer scope and unavailable original historical receipt remain explicit.',
        sql=False,api_calls=0,llm_calls=0,training=False,price_outcomes=False,orders=False,
        files={n:digest(output/n) for n in ['protocol.json','retimed-features.parquet','reaction-price-inputs.parquet']})
    atomic_json(output/'report.json',result);print(json.dumps({k:v for k,v in result.items() if k!='files'},default=str))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parent',required=True,type=Path);p.add_argument('--review',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();run(a.parent,a.review,a.output)
