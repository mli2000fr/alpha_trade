"""Offline scalar audit of post13D eligibility and all hypothetical marks."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_activist_13d_pilot import READ,parse,parse_index
from scripts.research.us_activist_13d_review import freeze,check_clause
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def audit(root):
    out=root/'replay-v1'
    if (out/'audit.json').exists():raise ValueError('Immutable audit')
    p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources'])
    docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    reviewout,review=freeze(root);cap=READ(reviewout/'identity-capture.json');verify_hashes(root,cap['files'])
    rp=READ(out/'protocol.json');verify_hashes(Path('.'),rp['sources'])
    result=READ(out/'report.json');verify_hashes(out,result['files'])
    ledger=pd.read_csv(out/'event-results.csv');prices=pd.read_parquet(out/'source-price-snapshot.parquet')
    ranks=pd.read_parquet(out/'oracle-context.parquet');days=mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date='2024-09-30').index
    # Recompute identity exclusions directly from every original, not extraction labels.
    true=0;false=0
    for d in docs['documents']:
        original=parse((root/d['receipt']['file']).read_bytes())
        if original['subject_cik']==d['selection']['cik']:true+=1
        else:false+=1
    if (true,false)!=(10,13):raise ValueError('Filer/issuer classification changed')
    next_allowed={};selected=[]
    for e in sorted(review['rows'],key=lambda x:(x['filed'],x['accession'])):
        if not(e['active'] or e['secondary']):continue
        expected_entry=days[days>pd.Timestamp(e['filed'])][0]
        if str(expected_entry.date())!=e['entry']:raise ValueError('Backdated entry')
        j=days.get_loc(expected_entry);admitted=j>=next_allowed.get(e['symbol'],-1)
        if admitted:next_allowed[e['symbol']]=j+60;selected.append(e['accession'])
        if admitted!=e['admitted']:raise ValueError('Outcome-dependent admission')
    if set(ledger.accession)!=set(selected):raise ValueError('An eligible case was dropped')
    verified=0
    for r in ledger.to_dict('records'):
        if r['status']!='EXPLORATORY_ADJUSTED_MARK':continue
        j=days.get_loc(pd.Timestamp(r['entry']));dates=days[j:j+r['horizon']]
        calculated={}
        for s in [r['symbol'],'SPY']:
            w=prices[prices.symbol==s].set_index('date').reindex(dates)
            if len(w)!=r['horizon'] or w.is_filled.isna().any():raise ValueError('Incomplete audited endpoint path')
            a=w.iloc[0];b=w.iloc[-1]
            entry=float(a.open)*float(a.adj_close)/float(a.close);exit=float(b.adj_close)
            gross=exit/entry-1;net=gross-2/1000-.001*(1+exit/entry)
            calculated[s]=(gross,net,entry,exit)
        gross,net,entry,exit=calculated[r['symbol']]
        for actual,expected in [(r['gross_return'],gross),(r['net_return'],net),(r['entry_adjusted_mark'],entry),
            (r['exit_adjusted_mark'],exit),(r['benchmark_net_return'],calculated['SPY'][1]),
            (r['excess_vs_spy'],net-calculated['SPY'][1])]:
            if not np.isclose(actual,expected,rtol=0,atol=1e-10):raise ValueError('Scalar economic mark mismatch')
        decision=days[j-1];ctx=ranks[(ranks.date==decision)&ranks.symbol.eq(r['symbol'])]
        if len(ctx):
            rank=int(ctx.iloc[0]['rank']);n=int(ranks.date.eq(decision).sum())
            if r['oracle_rank']!=rank or bool(r['in_top10'])!=(rank<=10) or bool(r['in_top20pct'])!=(rank<=np.ceil(.2*n)):
                raise ValueError('Future or filtered Oracle membership')
        elif pd.notna(r['oracle_rank']):raise ValueError('Invented Oracle rank')
        verified+=1
    audit=dict(status='PASS_EXPLORATORY_POST13D_ONLY',originals_checked=len(docs['documents']),
        issuer_confirmed=true,filer_misattributions_prevented=false,scalar_event_horizons=verified,
        primary_issuers=review['primary_nonoverlap'],secondary_issuers=review['secondary_nonoverlap'],
        all_admitted_cases_retained=True,report_sha256=digest(out/'report.json'),
        same_assistant_not_human_independent=True,no_training_sql_llm_orders=True)
    atomic_json(out/'audit.json',audit);print(audit,flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    audit(a.parse_args().output)
