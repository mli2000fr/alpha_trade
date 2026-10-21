"""Read-only source/control and scalar audit; not independent human semantics.

Only writes a fresh audit artifact. No SQL, network, model, LLM or broker call.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_activist_13d_confirmation import mapping, parse_quarter, distinct, choose
from scripts.research.us_activist_13d_confirmation_replay import NOTES, full_calendar, PRICE
from scripts.research.us_activist_13d_confirmation_identity import plain_pbt_cover
from scripts.research.us_activist_13d_extension_review import section4
from scripts.research.us_activist_13d_extension_audit import close, scalar
from scripts.research.us_activist_13d_pilot import READ, parse
from scripts.research.us_activist_13d_review import check_clause, identity
from scripts.research.us_activist_13d_replay import price_path
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def expected_outcome(entry, horizon, calendar, cutoff):
    """Independent explicit entry-inclusive session slicing."""
    window=calendar[calendar>=pd.Timestamp(entry)][:horizon]
    if len(window)!=horizon or window[0]!=pd.Timestamp(entry):
        raise ValueError('Insufficient calendar')
    return str(window[-1].date()),bool(window[-1]<=pd.Timestamp(cutoff))


def audit(root):
    out=root/'replay-confirmation-final-v1'
    if (out/'audit.json').exists():
        raise ValueError('Fresh immutable audit required')
    protocol=READ(root/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    selection=READ(root/'selection.json');verify_hashes(root,selection['files'])
    docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    extraction=READ(root/'extraction.json');verify_hashes(root,extraction['files'])
    review=READ(root/'review-frozen-v1/protocol.json');verify_hashes(Path('.'),review['sources'])
    original=READ(root/'review-frozen-v1/identity-capture.json');verify_hashes(root,original['files'])
    ids=READ(root/'review-frozen-v1/identity-qualified-v1.json')
    verify_hashes(Path('.'),ids['sources']);verify_hashes(root,ids['files'])
    replay=READ(out/'protocol.json');verify_hashes(Path('.'),replay['sources'])
    report=READ(out/'report.json');verify_hashes(out,report['files'])
    if docs['stop'] or ids['stop'] or selection['stop'] or any(v!='COMPLETE_INDEXES' for v in selection['year_status'].values()):
        raise ValueError('Incomplete acquisition cannot pass')
    _,mapped,_=mapping();allrows={2025:[],2026:[]};indexcounts=[]
    for x in selection['indexes']:
        receipt=x['receipt'];body=(root/receipt['file']).read_bytes()
        if digest(root/receipt['file'])!=receipt['sha256']:
            raise ValueError('Index changed')
        rows=parse_quarter(body,x['year'],x['quarter']);unique=distinct(rows,mapped)
        if len(rows)!=x['index_rows'] or len(unique)!=x['initial_accessions']:
            raise ValueError('Wrong complete-index counters')
        allrows[x['year']].extend(rows)
        indexcounts.append(dict(year=x['year'],quarter=x['quarter'],initial_accessions=len(unique)))
    reconstructed=[]
    for year,rows in allrows.items():
        reconstructed.extend(dict(r,event_year=year) for r in choose(distinct(rows,mapped),protocol['noncurrent_probe_per_quarter']))
    reconstructed.sort(key=lambda r:(r['filed'],r['accession']))
    if reconstructed!=selection['selected']:
        raise ValueError('Outcome-blind selection changed')
    notes={r['accession']:r for r in READ(NOTES)['cases']}
    extracted={r['accession']:r for r in extraction['rows']}
    if set(notes)!=set(extracted) or len(notes)!=len(docs['documents']) or len(notes)!=len(reconstructed):
        raise ValueError('Missing source decision')
    objects={}
    for d in docs['documents']:
        accession=d['selection']['accession'];r=extracted[accession]
        if d['receipt']['status']!='OK' or r['status']!='READY_REVIEW':
            raise ValueError('Unresolved original')
        body=(root/d['receipt']['file']).read_bytes();obj=parse(body)
        if obj!=READ(root/r['review_file']) or section4(obj,body)!=(r['section4'],r['section_method']):
            raise ValueError('Original extraction mismatch')
        note=notes[accession]
        if obj['subject_cik']!=note['subject_cik']:
            raise ValueError('Subject/filer confusion')
        for clause in note.get('clauses',[]):
            check_clause(obj,clause['filename'],clause['contains'])
        objects[accession]=obj
    calendar=full_calendar();until={};admitted=[]
    for r in sorted(review['rows'],key=lambda x:(x['filed'],x['accession'])):
        entry=calendar.index[calendar.index>pd.Timestamp(r['filed'])][0]
        if str(entry.date())!=r['entry']:
            raise ValueError('Entry not first full session after SEC date')
        if r['decision'] in ['PRIMARY_EXPLICIT_INTERVENTION','SECONDARY_GOVERNANCE_ONLY']:
            if pd.Timestamp(objects[r['accession']]['accepted_utc'])>=calendar.loc[entry].market_open:
                raise ValueError('SEC acceptance after entry')
            j=calendar.index.get_loc(entry);allow=j>=until.get(r['cik'],-1)
            if allow!=r['admitted']:
                raise ValueError('CIK entry block changed')
            if allow:
                until[r['cik']]=j+60;admitted.append(r)
    if admitted!=replay['events']:
        raise ValueError('Replay altered frozen admissions/order')
    byevent={r['accession']:r for r in admitted}
    supported={}
    for item in ids['rows']:
        event=byevent[item['accession']]
        if item.get('supplement'):
            proof=item['supplement'];body=(root/proof['receipt']['file']).read_bytes()
            if event['symbol']=='PBT':
                expected=plain_pbt_cover(body,proof['receipt'],event['annual_metadata'])
                filed=event['annual_metadata']['filed']
            else:
                expected=identity(body,event['cik'],event['symbol']);filed=proof['quarterly_metadata']['filed']
        elif event.get('identity_clause'):
            clause=event['identity_clause'];check_clause(objects[event['accession']],clause['filename'],clause['contains'])
            expected=clause;filed=event['filed']
        else:
            expected=identity((root/item['receipt']['file']).read_bytes(),event['cik'],event['symbol'])
            filed=event['annual_metadata']['filed']
        if not expected or expected!=item['identity'] or filed>event['filed']:
            raise ValueError('Historical ticker/class unqualified')
        supported[item['accession']]=True
    if set(supported)!=set(byevent):
        raise ValueError('Missing admitted identity')
    frame=pd.read_csv(out/'event-results.csv',dtype={'cik':str})
    keys={(e['accession'],h) for e in admitted for h in [20,60]}
    if set(zip(frame.accession,frame.horizon))!=keys or len(frame)!=len(keys):
        raise ValueError('Missing/duplicate admitted outcome')
    prices=pd.read_parquet(out/'source-price-snapshot.parquet')
    source=pd.read_parquet(PRICE,filters=[('symbol','in',sorted({e['symbol'] for e in admitted}|{'SPY'})),
        ('date','>=',pd.Timestamp('2025-01-01')),('date','<=',pd.Timestamp(protocol['price_end']))])
    pd.testing.assert_frame_equal(prices,source)
    scores=pd.read_parquet(out/'oracle-context.parquet');bars=pd.read_parquet(out/'audited-mark-inputs.parquet')
    scoreframes=[]
    for y in [2025,2026]:
        path=next(Path(k) for k in replay['sources'] if Path(k).name==f'{y}-H20-scores.parquet')
        scoreframes.append(pd.read_parquet(path,columns=['date','symbol','rank','score'],
            filters=[('date','in',sorted(scores.loc[scores.date.dt.year.eq(y),'date'].unique()))]))
    pd.testing.assert_frame_equal(scores,pd.concat(scoreframes,ignore_index=True))
    groups={s:g for s,g in prices.groupby('symbol')};reserves=READ(PRICE.parent/'quality-reserves.json')['price_reserves']
    checked=0;expectedbarcount=0
    for r in frame.to_dict('records'):
        last,mature=expected_outcome(r['entry'],r['horizon'],calendar.index,protocol['price_end'])
        if last!=r['required_exit_session'] or mature!=r['mature']:
            raise ValueError('Entry-inclusive maturity mismatch')
        entry=pd.Timestamp(r['entry']);decision=calendar.index[calendar.index.get_loc(entry)-1]
        context=scores[(scores.date==decision)&scores.symbol.eq(r['symbol'])];n=int(scores.date.eq(decision).sum())
        if r['oracle_date']!=str(decision.date()) or r['oracle_count']!=n:
            raise ValueError('Oracle context date/population mismatch')
        if len(context)==1:
            rank=int(context.iloc[0]['rank'])
            if r['oracle_rank']!=rank or r['in_top10']!=(rank<=10) or r['in_top20pct']!=(rank<=int(np.ceil(.2*n))):
                raise ValueError('Oracle rank/pool mismatch')
        elif r['oracle_context_status']!='UNKNOWN' or not all(pd.isna(r[k]) for k in ['oracle_rank','in_top10','in_top20pct']):
            raise ValueError('Unknown Oracle context silently made false')
        paths={};problems=[]
        if mature:
            for s in [r['symbol'],'SPY']:
                path,why=price_path(groups.get(s,pd.DataFrame(columns=prices.columns)),calendar.index,entry,r['horizon'],reserves.get(s))
                if path is None:
                    problems.append(s+':'+why)
                else:
                    paths[s]=path
        expectedstatus='IMMATURE' if not mature else 'UNKNOWN' if problems else 'EXPLORATORY_ADJUSTED_MARK'
        if r['status']!=expectedstatus:
            raise ValueError('Future availability affected admission/status')
        if expectedstatus!='EXPLORATORY_ADJUSTED_MARK':
            if not all(pd.isna(r[k]) for k in ['net_return','gross_return','benchmark_net_return','hypothetical_net_usd']):
                raise ValueError('Missing or immature PnL not null')
            if mature and r['reason']!=';'.join(problems):
                raise ValueError('Unknown reason differs from price checks')
            continue
        for s,path in paths.items():
            archived=bars[(bars.accession==r['accession'])&bars.horizon.eq(r['horizon'])&bars.symbol.eq(s)].sort_values('date')
            if list(archived.date)!=list(path.index):
                raise ValueError('Audited mark window mismatch')
            expectedbarcount+=len(path)
            for col in ['open','high','low','close']:
                np.testing.assert_allclose(archived[col].to_numpy(float),path[col].to_numpy(float),rtol=1e-12)
        stock=scalar(paths[r['symbol']]);spy=scalar(paths['SPY'])
        ratio=float(paths[r['symbol']].close.iloc[-1]/paths[r['symbol']].open.iloc[0])
        close(r['net_return'],stock);close(r['gross_return'],ratio-1)
        close(r['benchmark_net_return'],spy);close(r['excess_vs_spy'],stock-spy)
        close(r['stress_net_return'],scalar(paths[r['symbol']],bps=25.))
        close(r['hypothetical_net_usd'],1000*stock);close(r['friction_usd'],1+ratio);close(r['fixed_commissions_usd'],2.)
        checked+=1
    if len(bars)!=expectedbarcount:
        raise ValueError('Unexpected archived mark rows')
    for summary in report['summaries']:
        part=frame[(frame.event_year==summary['year'])&frame.scope.eq(summary['scope'])&frame.horizon.eq(summary['horizon'])]
        good=part[part.status=='EXPLORATORY_ADJUSTED_MARK']
        counts=dict(admitted=len(part),unique_issuers=part.cik.nunique(),qualified=len(good),mature=int(part.mature.sum()),
            unknown=int(part.status.eq('UNKNOWN').sum()),immature=int(part.status.eq('IMMATURE').sum()),
            positive_net=int(good.net_return.gt(0).sum()),negative_net=int(good.net_return.lt(0).sum()),
            oracle_known=int(good.oracle_context_status.eq('KNOWN').sum()),
            top10=int(good.in_top10.eq(True).sum()),top20pct=int(good.in_top20pct.eq(True).sum()))
        if any(summary[k]!=v for k,v in counts.items()):
            raise ValueError('Summary denominator mismatch')
        for key,col in [('mean_net','net_return'),('mean_spy','benchmark_net_return'),('mean_excess','excess_vs_spy'),('mean_stress','stress_net_return'),('median_net','net_return')]:
            expected=(good[col].median() if key=='median_net' else good[col].mean()) if len(good) else None
            if expected is None:
                if summary[key] is not None:
                    raise ValueError('Empty summary not null')
            else:
                close(summary[key],float(expected))
    receipts=[READ(f) for f in (root/'http').glob('*.json')];new=[r for r in receipts if not r.get('reused_from')]
    result=dict(status='PASS_EXPLORATORY_2025_2026_WITH_COVERAGE_RESERVES',finished_at_utc=datetime.now(timezone.utc).isoformat(),
        index_quarters_verified=indexcounts,selected_accessions=len(notes),originals_reparsed=len(objects),
        admitted_identities_checked=len(supported),event_horizon_rows=len(frame),qualified_scalar_pairs_checked=checked,
        unknown_rows=int(frame.status.eq('UNKNOWN').sum()),immature_rows=int(frame.status.eq('IMMATURE').sum()),
        archived_bar_rows_checked=expectedbarcount,all_admitted_retained=True,outcome_blind_sample_reconstructed=True,
        documentary_reserves=[dict(accession=r['accession'],issuer=r['subject_name'],decision=r['decision']) for r in review['rows'] if r['decision'].startswith('RESERVED_')],
        new_sec_requests=len(new),new_streamed_bytes=sum(r.get('streamed_bytes',0) for r in new),
        http_status_counts=dict(Counter(str(r.get('http_status')) for r in new)),
        same_assistant_not_independent_human=True,no_model_sql_llm_order_or_batch_change=True,
        sources={str(Path(__file__)):digest(Path(__file__)),str(out/'report.json'):digest(out/'report.json')})
    atomic_json(out/'audit.json',result);print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    audit(p.parse_args().output)
