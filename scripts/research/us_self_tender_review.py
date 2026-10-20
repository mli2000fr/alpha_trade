"""Explicit same-assistant documentary decisions, no economic outcomes.

Rules below were specified after source reading, before any price inspection.
SC TO-I does not imply US common-stock eligibility or broker acceptance.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import re

from scripts.research.us_activist_13d_pilot import READ
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

GROUPS={
 'EXCLUDE_CONVERTIBLE_DEBT':[
  '0000950123-24-000200','0001193125-24-039241','0001104659-24-039403','0001193125-24-240020',
  '0001580642-25-000374','0001104659-25-071933','0001193125-26-010350','0001193125-26-059472','0001104659-26-035526'],
 'EXCLUDE_SHARE_EXCHANGE':[
  '0001104659-24-023079','0001193125-24-089217','0001193125-25-236510','0001193125-26-152127'],
 'EXCLUDE_DUTCH_AUCTION':[
  '0001193125-24-054315','0000950103-24-004046','0001104659-24-058430','0001193125-24-142266',
  '0001140361-25-006098','0001178913-26-000759','0001193125-26-118703'],
 'EXCLUDE_FUND_NAV_OR_NONLISTED':[
  '0001859919-24-000017','0001193125-24-180429','0001193125-24-181053','0001193125-24-181683',
  '0001193125-24-181687','0001193125-24-188894','0001193125-24-238158','0001193125-24-238926',
  '0001193125-24-238928','0001193125-24-248793','0001628280-24-048255',
  '0001193125-25-011484','0001193125-25-011489','0001193125-25-060100','0001193125-25-082877',
  '0001193125-25-084387','0001193125-25-121347','0001213900-25-049114','0001193125-25-181580',
  '0001580642-25-006605','0001398344-26-001575','0001213900-26-057349','0001398344-26-013267','0001104659-26-108300'],
 'EXCLUDE_PREFERRED_CLASS':[
  '0001193125-24-132515','0001140361-24-045053','0001193125-25-052569'],
 'EXCLUDE_WARRANT': ['0001437749-24-027845','0001140361-25-006664'],
 'EXCLUDE_EMPLOYEE_AWARD': ['0000930413-24-002290'],
 'RESERVED_FIXED_LOCAL_SHARES_ADS_AND_RECORD_DATE': ['0001193125-25-286157'],
}

PATTERNS={
 'EXCLUDE_CONVERTIBLE_DEBT':[r'Convertible (?:Senior )?Notes due \d{4}'],
 'EXCLUDE_SHARE_EXCHANGE':[r'offer(?:s)? by.{0,100}?to exchange',r'offers by Visa to exchange'],
 'EXCLUDE_DUTCH_AUCTION':[r'not greater than.{0,60}?nor less than.{0,25}?per Share',r'not less than.{0,60}?nor greater than.{0,35}?per share'],
 'EXCLUDE_FUND_NAV_OR_NONLISTED':[r'net asset value',r'closed.end.{0,50}?investment company',r'Shares are not traded in any market'],
 'EXCLUDE_PREFERRED_CLASS':[r'(?:Cumulative|Noncumulative).{0,40}?Preferred Stock'],
 'EXCLUDE_WARRANT':[r'Warrants exercisable for shares',r'WARRANTS TO PURCHASE COMMON STOCK'],
 'EXCLUDE_EMPLOYEE_AWARD':[r'certain employee equity award holders'],
 'RESERVED_FIXED_LOCAL_SHARES_ADS_AND_RECORD_DATE':[r'tender offer price of ₹ 1,800'],
}


def flatten(text):
    return ' '.join(text.split())


def proof(parts,patterns):
    for pattern in patterns:
        for p in parts:
            text=flatten(p['text']);match=re.search(pattern,text,re.I)
            if match:
                return dict(filename=p['filename'],contains=text[max(0,match.start()-95):match.end()+170])
    raise ValueError('Specified manual decision lacks exact supporting clause')


def check_proof(parts,clause):
    matches=[p for p in parts if p['filename']==clause['filename']]
    if len(matches)!=1 or clause['contains'] not in flatten(matches[0]['text']):
        raise ValueError('Clause not uniquely traceable to original part')


def fee_gate(notional,fee):
    """Fee burden only, not a forecast or a simulated tender return."""
    if notional<=0 or fee<0:
        raise ValueError('Positive notional and nonnegative fee required')
    return dict(notional_usd=notional,election_fee_usd=fee,fee_to_notional=fee/notional,
                cash_needed_before_other_fees=notional+fee,not_a_pnl=True)


def run(root):
    out=root/'review-frozen-v1'
    if out.exists():
        raise ValueError('Fresh immutable documentary review required')
    proto=READ(root/'protocol.json');verify_hashes(Path('.'),proto['sources'])
    ext=READ(root/'extraction.json');verify_hashes(root,ext['files'])
    docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    if docs['status']!='COMPLETE_ATTEMPTS' or docs['stop']:
        raise ValueError('Incomplete capture; no complete sample review claim')
    supplement=root/'kim-primary-v1';sup=READ(supplement/'report.json');verify_hashes(supplement,sup['files'])
    verify_hashes(Path('.'),READ(supplement/'protocol.json')['sources'])
    rules={accession:category for category,accessions in GROUPS.items() for accession in accessions}
    if len(rules)!=sum(map(len,GROUPS.values())) or set(rules)!={r['accession'] for r in ext['rows']}:
        raise ValueError('Exactly one manual decision for EVERY selected source required')
    rows=[]
    for record in ext['rows']:
        accession=record['accession'];category=rules[accession]
        if record['status']=='READY_MANUAL_REVIEW':
            obj=READ(root/record['review_file']);parts=obj['parts'];subject=obj['subject_cik'];name=obj['subject_name']
            if subject not in record['indexed_ciks']:
                raise ValueError('Subject differs from indexed issuer')
            override=None
        elif accession==sup['accession'] and sup['status']=='PRIMARY_HTML_CAPTURED_NOT_ECONOMICALLY_TESTED':
            parts=[dict(filename=sup['filename'],text=sup['text'])];subject=record['indexed_ciks'][0];name=record['index_names'][0]
            override='kim-primary-v1/report.json'
        else:
            raise ValueError('Unresolved source must remain reserved, never silently excluded')
        clauses=[proof(parts,PATTERNS[category])]
        if category=='RESERVED_FIXED_LOCAL_SHARES_ADS_AND_RECORD_DATE':
            clauses.extend([proof(parts,[r'ADS holders to participate in the Buyback']),
                            proof(parts,[r'Record Date being November 14, 2025']),
                            proof(parts,[r'Buyback Window Opening Date November 20, 2025 Buyback Window Closing Date November 26, 2025'])])
        for clause in clauses:
            check_proof(parts,clause)
        rows.append(dict(accession=accession,filed=record['filed'],year=record['year'],cohort=record['cohort'],
            symbol_candidates=record['mapped_symbols'],subject_cik=subject,subject_name=name,decision=category,clauses=clauses,
            source_override=override,admitted=False,prices_read=False,
            fixed_price_in_local_currency=1800 if category.startswith('RESERVED_FIXED_LOCAL') else None,
            fixed_price_currency='INR' if category.startswith('RESERVED_FIXED_LOCAL') else None))
    out.mkdir();sources=[Path(__file__),Path('tests/test_us_self_tender_review.py'),root/'protocol.json',root/'census.json',root/'documents.json',root/'extraction.json',supplement/'protocol.json',supplement/'report.json']
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in sources},
        all_decisions_before_any_prices=True,same_assistant_not_independent_human=True,rows=rows,
        broker_feasibility=dict(broker='Alpaca US',documentation_checked_on='2026-10-20',
            current_published_election_fee_usd=100,not_proven_historical_account_tariff=True,
            source='https://docs.alpaca.markets/us/docs/voluntary-corporate-actions',
            requires_event_notice_eligibility_and_actual_election=True,no_broker_api_or_election_sent=True,
            paper_tender_lifecycle_not_qualified=True,trading212_support_not_qualified=True),
        fee_sensitivities=[fee_gate(n,100) for n in [1000,2000,4000]],
        status='NO_QUALIFIED_FIXED_CASH_TRADE_IN_REVIEWED_SAMPLE',no_economic_backtest=True)
    atomic_json(out/'report.json',protocol)
    print(dict(status=protocol['status'],decisions=dict(Counter(r['decision'] for r in rows)),
        current_decisions=dict(Counter(r['decision'] for r in rows if r['cohort']=='CURRENT_UNIVERSE_INDEX_ROUTE'))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
