"""Offline reconciliation of selected cells; never promotes a complete account."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import json
from pathlib import Path


def review(report, evidence):
    index={(issuer['symbol'],a['id']):a for issuer in report['issuers'] for a in issuer['accounts']}
    checks=[]
    for rule in evidence['checks']:
        account=index.get((rule['symbol'],rule['id']))
        raw=(account or {}).get('amounts_source_units',{}).get(rule['field'])
        expected=Decimal(rule['expected_eur']); tolerance=Decimal(rule['tolerance_eur'])
        delta=Decimal(raw)-expected if raw is not None else None
        checks.append({**rule,'actual_source_units':raw,'delta_eur':str(delta) if delta is not None else None,
                       'status':'MISSING' if delta is None else ('MATCH_WITHIN_TOLERANCE' if abs(delta)<=tolerance else 'MISMATCH')})
    versions=[]
    for issuer in report['issuers']:
        periods=defaultdict(list)
        for account in issuer['accounts']:
            periods[(account['dateCloture'],account['typeBilan'])].append(account)
        for (closing,kind),accounts in periods.items():
            if len(accounts)>1:
                versions.append({'symbol':issuer['symbol'],'closing':closing,'type':kind,
                    'ids':[a['id'] for a in accounts],
                    'different_amounts':len({json.dumps(a['amounts_source_units'],sort_keys=True) for a in accounts})>1})
    return {'status':'SPOT_CHECKS_COMPLETE_REVIEW_REQUIRED','canonical_go':False,'sql_writes':False,
            'historical_pit_qualified':False,'counts':dict(Counter(c['status'] for c in checks)),
            'balance_counts':dict(Counter(a['balance_identity'] for a in index.values())),
            'technical_status_counts':dict(Counter(a['normalization_status'] for a in index.values())),
            'checks':checks,'duplicate_period_versions':versions,
            'limitations':['One matched field does not qualify other fields or years.',
                          'Source amounts are compared as-is; no automatic rescaling or period reassignment.',
                          'Current modified account versions are not certified historical vintages.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,default=Path('config/inpi_pilot_financial_checks_fr.json'))
    args=parser.parse_args()
    result=review(json.loads(args.report.read_text(encoding='utf-8')),
                  json.loads(args.evidence.read_text(encoding='utf-8')))
    target=args.report.with_name('financial_review.json')
    # Preserve any prior independent review; write a new output name on rerun.
    with target.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2)
    print(json.dumps({'report':str(target),'counts':result['counts'],'canonical_go':False}))


if __name__=='__main__': main()
