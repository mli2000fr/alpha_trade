"""Offline raw-index/source audit, not an independent human or PnL audit."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import re

from scripts.research.us_self_tender_feasibility import distinct_initials,choose,parse_original,discovery
from scripts.research.us_self_tender_review import check_proof,fee_gate
from scripts.research.us_activist_13d_extension import parse_quarter
from scripts.research.us_activist_13d_pilot import READ,UNIVERSE,MAPPING
from scripts.research.us_activist_13d_confirmation import allowed
from scripts.research.us_cash_merger_feasibility import visible
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def audit(root):
    target=root/'review-frozen-v1/audit.json'
    if target.exists():
        raise ValueError('Immutable audit')
    proto=READ(root/'protocol.json');verify_hashes(Path('.'),proto['sources'])
    census=READ(root/'census.json');docs=READ(root/'documents.json');ext=READ(root/'extraction.json')
    verify_hashes(root,docs['files']);verify_hashes(root,ext['files'])
    review=READ(root/'review-frozen-v1/report.json');verify_hashes(Path('.'),review['sources'])
    supdir=root/'kim-primary-v1';sup=READ(supdir/'report.json');verify_hashes(supdir,sup['files'])
    verify_hashes(Path('.'),READ(supdir/'protocol.json')['sources'])
    universe=set(filter(None,re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig'))));mapping={}
    for x in READ(MAPPING).values():
        if x['ticker'] in universe:
            mapping.setdefault(str(x['cik_str']).zfill(10),set()).add(x['ticker'])
    rows=[];forms=Counter();quarters=set()
    for index in census['indexes']:
        source=Path(index['source'])
        if digest(source)!=index['sha256']:
            raise ValueError('Archived quarter changed')
        parsed=parse_quarter(source.read_bytes(),index['year'],index['quarter']);quarters.add((index['year'],index['quarter']))
        subset=[x for x in parsed if x['form'] in ['SC TO-I','SC TO-I/A']]
        if len(parsed)!=index['index_rows'] or sum(x['form']=='SC TO-I' for x in subset)!=index['initial_rows'] or sum(x['form']=='SC TO-I/A' for x in subset)!=index['amendment_rows']:
            raise ValueError('Wrong quarter metadata counts')
        rows.extend(subset);forms.update((int(x['filed'][:4]),x['form']) for x in subset)
    if len(quarters)!=11:
        raise ValueError('Missing source quarter')
    initial=distinct_initials(rows,mapping)
    if initial!=census['initials'] or choose(initial)!=census['selected']:
        raise ValueError('Dedupe or outcome-blind source selection changed')
    for summary in census['summaries']:
        year=summary['year']
        expected=dict(initial_index_rows=forms[(year,'SC TO-I')],amendment_index_rows=forms[(year,'SC TO-I/A')],
            distinct_initials=sum(x['year']==year for x in initial),current_route=sum(x['year']==year and bool(x['mapped_symbols']) for x in initial),selected=sum(x['year']==year for x in census['selected']))
        if any(summary[k]!=v for k,v in expected.items()):
            raise ValueError('Wrong year summary')
    objects={};reparsed=0
    for d in docs['documents']:
        receipt=d['receipt'];acc=d['selection']['accession']
        if receipt['status']=='OK':
            obj=parse_original((root/receipt['file']).read_bytes());objects[acc]=obj
            e=next(x for x in ext['rows'] if x['accession']==acc)
            if obj!=READ(root/e['review_file']) or discovery(obj)!=e['discovery']:
                raise ValueError('Original extraction mismatch')
            if obj['subject_cik'] not in d['selection']['indexed_ciks']:
                raise ValueError('Wrong subject/filer issuer')
            reparsed+=1
        elif receipt['status']!='DOCUMENT_TOO_LARGE' or acc!=sup['accession']:
            raise ValueError('Unresolved source cannot be silently classified')
    primary=(supdir/sup['receipt']['file']).read_bytes()
    if visible(primary.decode('utf-8',errors='replace'))!=sup['text']:
        raise ValueError('Supplement extraction changed')
    objects[sup['accession']]=dict(parts=[dict(filename=sup['filename'],text=sup['text'])])
    if {x['accession'] for x in review['rows']}!=set(objects) or len(review['rows'])!=len(census['selected']):
        raise ValueError('Missing semantic decision')
    clauses=0
    for row in review['rows']:
        if row['admitted'] or row['prices_read'] or not row['clauses']:
            raise ValueError('Unqualified trade admission')
        for clause in row['clauses']:
            check_proof(objects[row['accession']]['parts'],clause);clauses+=1
    for x in review['fee_sensitivities']:
        if x!=fee_gate(x['notional_usd'],100):
            raise ValueError('Fee burden mismatch')
    receipts=[READ(f) for directory in [root/'http',supdir/'http'] for f in directory.glob('*.json')]
    if any(not allowed(r['url']) for r in receipts):
        raise ValueError('Non-SEC network source')
    result=dict(status='PASS_DOCUMENTARY_FEASIBILITY_ONLY_NO_BACKTEST',finished_at_utc=datetime.now(timezone.utc).isoformat(),
        complete_index_quarters=len(quarters),distinct_initial_accessions=len(initial),selected_accessions=len(census['selected']),
        current_route_accessions=sum(bool(r['mapped_symbols']) for r in initial),outside_route_probe=sum(r['cohort']=='OUTSIDE_ROUTE_HASH_PROBE' for r in census['selected']),
        original_complete_submissions_reparsed=reparsed,oversized_primary_supplements=1,exact_clauses_checked=clauses,
        decisions=dict(Counter(x['decision'] for x in review['rows'])),
        sec_new_requests=len(receipts),streamed_bytes=sum(r.get('streamed_bytes',0) for r in receipts),
        http_status_counts=dict(Counter(str(r.get('http_status')) for r in receipts)),
        same_assistant_not_independent_human=True,no_price_or_model_sql_llm_order_or_batch_changes=True,
        outside_probe_not_historical_market_census=True,no_qualified_economic_trade=True,
        sources={str(Path(__file__)):digest(Path(__file__)),str(root/'review-frozen-v1/report.json'):digest(root/'review-frozen-v1/report.json')})
    atomic_json(target,result);print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);audit(p.parse_args().output)
