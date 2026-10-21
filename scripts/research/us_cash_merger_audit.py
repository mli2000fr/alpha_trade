"""Offline integrity and coverage audit; no OHLC, returns or trade simulation."""
import argparse
from datetime import datetime,timezone
from pathlib import Path

from scripts.research.us_cash_merger_feasibility import READ,prepare
from scripts.research.us_cash_merger_review import validate_review,dates_from_receipt,prepare_coverage
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def audit(root):
    out=root/'audit-v1'
    if out.exists():raise ValueError('Immutable audit directory')
    prepare(root);coverage,protocol=prepare_coverage(root)
    for folder in [root,coverage]:verify_hashes(folder,READ(folder/'report.json')['files'])
    report=READ(coverage/'report.json');rows=validate_review(root)
    if len(rows)!=8 or len({r['accession'] for r in rows})!=8:raise ValueError('Incomplete initial sample')
    if [r['accession'] for r in report['rows']]!=[r['accession'] for r in rows]:raise ValueError('Selection changed')
    index=READ(root/'index.json');source_bodies=READ(root/'documents.json')
    if source_bodies['status']!='COMPLETE_ATTEMPTS':raise ValueError('Incomplete SEC acquisition')
    if not all(r['receipt']['status']=='OK' for r in source_bodies['documents']):raise ValueError('Unavailable SEC source')
    receipts=list((root/'http').glob('*.json'))
    if len(receipts)!=9:raise ValueError('Unexpected SEC request count')
    checked=[]
    for r in report['rows']:
        if not r['eligible']:continue
        symbol=r['symbol'];receipt=READ(coverage/f'{symbol}-alpaca.json');params=receipt['params']
        if params['symbols']!=symbol or params['feed']!='sip' or params['adjustment']!='raw' or params['asof']!='-':
            raise ValueError('Unexpected provider scope')
        actual=dates_from_receipt(receipt,symbol);expected=set(r['five_expected_sessions'])
        if len(actual['dates'])!=r['alpaca_first_five_present'] or not set(actual['dates']).issubset(expected):
            raise ValueError('Provider coverage discrepancy')
        if r['price_values_quality_qualified'] or r['full_lifecycle_price_coverage_qualified'] or r['deal_outcome_known']:
            raise ValueError('Unproven qualification promoted')
        checked.append(dict(symbol=symbol,first_five_dates=len(actual['dates']),local_rows=r['local_rows']))
    if not report['no_pnl'] or not report['no_sql_writes'] or not report['no_orders'] or report['candidates_are_winners']:
        raise ValueError('Scope or interpretation violation')
    out.mkdir()
    paths=[Path(__file__),root/'report.json',coverage/'report.json']
    result=dict(status='PASS_FEASIBILITY_INTEGRITY_NOT_STRATEGY_VALIDATION',created_at_utc=datetime.now(timezone.utc).isoformat(),
        index_rows=index['index_rows'],initial_index_rows=index['initial_rows'],unique_initial_filings=index['unique_initial_accessions'],
        sampled=8,excluded=sum(not r['eligible'] for r in rows),terms_only_candidates=checked,
        sec_requests=len(receipts),alpaca_requests=READ(coverage/'provider-report.json')['actual_new_requests'],
        complete_cash_merger_population=False,abandoned_deals_coverage_proven=False,
        pnl_or_effectiveness_measured=False,sql_writes=False,orders=False,
        reviewer='Same assistant, second technical check not independent human review',
        sources={str(p):digest(p) for p in paths})
    atomic_json(out/'report.json',result);print(result['status'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    audit(p.parse_args().root)
