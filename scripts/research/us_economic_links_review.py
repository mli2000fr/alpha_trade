"""Close the bounded documentary review using local receipts, without SQL or APIs."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import re

import pandas as pd

from scripts.research.us_economic_links_feasibility import read
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT = Path('artifacts/research/us_economic_links_feasibility/20261102-v4')
HISTORY_PROTOCOL = Path('artifacts/research/us_news_gpt_top20_history/20261015-v1/protocol.json')

# Decisions are a same-assistant documentary review, never a fitted classifier.
VERDICTS = {
    ('UCTT', 'AMAT'): ('DOCUMENTED_OPERATING_LINK', 'Explicit named customer and revenue concentration table.'),
    ('UCTT', 'LRCX'): ('DOCUMENTED_OPERATING_LINK', 'Explicit named customer in the same table; outside trading universe.'),
    ('FMC', 'CTVA'): ('DOCUMENTED_OPERATING_LINK', 'Supply/license agreement; 200m USD prepurchase is deferred revenue, not profit.'),
    ('TSEM', 'SMTC'): ('DOCUMENTED_OPERATING_LINK', 'Named multi-year foundry capacity agreement; no revenue weight proved.'),
    ('SITM', 'AVT'): ('EXCLUDED_ACQUIRED_BUSINESS_SCOPE', '13.2% belongs to the former Renesas Timing Product Business, not consolidated SiTime. Contracts are expressly excluded from transferred assets; continuity unproved.'),
    ('BAND', 'FIVN'): ('PARTNERSHIP_ONLY', 'Communications integration/partnership, financial dependence unquantified.'),
    ('FORM', 'TER'): ('PARTNERSHIP_ONLY', 'Technology collaboration and equity investment, not proof of a customer supply contract.'),
    ('MXL', 'INTC'): ('HISTORICAL_ACQUISITION', '2020 asset acquisition, not current operating supply evidence.'),
    ('VICR', 'BAC'): ('FINANCIAL_RELATION_ONLY', 'Investment/custody dispute, not operating customer/supplier.'),
    ('MRVL', 'BAC'): ('FINANCIAL_RELATION_ONLY', 'Loan administrative agent.'),
    ('UCTT', 'BCS'): ('FINANCIAL_RELATION_ONLY', 'Equity offering sales agent.'),
    ('PENG', 'NVDA'): ('PLATFORM_REFERENCE_ONLY', 'Nvidia technology/platform reference does not establish a direct supply contract.'),
    ('MRVL', 'SPGI'): ('RATING_REFERENCE', 'S&P Global Ratings in loan definitions; nearby selling word is unrelated.'),
    ('BAND', 'IT'): ('ANALYST_REFERENCE', 'Gartner ranking/analyst citation.'),
    ('FORM', 'NDAQ'): ('LISTING_REFERENCE', 'Nasdaq listing, not operating customer.'),
    ('TSEM', 'NDAQ'): ('LISTING_REFERENCE', 'Nasdaq listing, not operating customer.'),
    ('MXL', 'SCI'): ('ALIAS_FALSE_POSITIVE', 'Generic Service Interface Specifications.'),
    **{p: ('ALIAS_FALSE_POSITIVE', 'Generic word, not the proposed company identity.') for p in [
        ('FORM', 'BAND'), ('TSEM', 'BAND'), ('UCTT', 'BAND'), ('MXL', 'PKG'),
        ('FORM', 'PKG'), ('VICR', 'PKG'), ('TSEM', 'RS')]},
}
CONTROL_NOTES = {
    ('BAND', 'BAC'): 'Loan agent, non-operating finance.',
    ('BAND', 'DOCU'): 'Marketing trusted-by claim; not a certified negative or material contract.',
    ('BAND', 'GOOGL'): 'Marketing trusted-by claim; not a certified negative or material contract.',
    ('UCTT', 'EMR'): 'Management biography/directorship.',
    ('UCTT', 'MSA'): 'Mine Safety Disclosures, generic heading.',
    ('MXL', 'CME'): 'SOFR benchmark administrator.',
    ('MXL', 'INTC'): 'Historical 2020 acquisition.',
    ('MXL', 'MSA'): 'Mine Safety Disclosures, generic heading.',
    ('MXL', 'PKG'): 'Generic packaging wording.',
    ('MXL', 'PUK'): 'UK Prudential Regulation Authority, not Prudential company.',
}


def utc_receipt(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError('Missing local receipt')
    return stamp.tz_localize('UTC') if stamp.tzinfo is None else stamp.tz_convert('UTC')


def receipt_ready(doc):
    if not str(doc['run_status']).startswith('COMPLETED'):
        raise ValueError('Unfinished collection cannot be used')
    # SEC acceptance is deliberately absent: raw SGML clock has no qualified timezone here.
    return max(utc_receipt(doc[k]) for k in ('observed_at', 'available_at', 'collection_finished_at'))


def proof(root, doc, start, end):
    path = root / doc['visible_file']
    if digest(path) != doc['visible_sha256']:
        raise ValueError('Visible evidence changed')
    body = path.read_text(encoding='utf-8')
    left = body.index(start)
    right = body.index(end, left + len(start))
    quote = body[left:right].strip()
    right = left + len(quote)
    return dict(document_key=doc['document_key'], visible_file=doc['visible_file'],
                start=left, end=right, quote=quote,
                quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),
                visible_sha256=doc['visible_sha256'], raw_sha256=doc['raw_sha256'])


def run(root=ROOT):
    output = root / 'closure'
    output.mkdir(exist_ok=False)
    docs = read(root / 'screen-v2/visible-documents.json')
    bykey = {d['document_key']: d for d in docs}
    protocol = read(root / 'protocol.json')
    specifications = [
        ('UCTT', 'AMAT', '0001628280-26-067880-0',
         'The Company’s most significant customers', 'As of September 25, 2026, gross accounts'),
        ('UCTT', 'LRCX', '0001628280-26-067880-0',
         'The Company’s most significant customers', 'As of September 25, 2026, gross accounts'),
        ('FMC', 'CTVA', '0000037785-26-000171-0',
         'In June 2026, we entered into a co-exclusive', 'We periodically enter into prepayment'),
        ('TSEM', 'SMTC', '0001178913-26-004752-0',
         'MIGDAL HAEMEK, Israel, and Camarillo', 'AI’s next constraint'),
        ('SITM', 'AVT', '0001451809-26-000068-1',
         'The Business primarily sells its products', '10. RESEARCH AND DEVELOPMENT'),
    ]
    evidence = []
    for owner, peer, key, start, end in specifications:
        doc = bykey[key]
        item = dict(owner=owner, counterparty=peer, verdict=VERDICTS[(owner, peer)][0],
                    limits=VERDICTS[(owner, peer)][1], source_url=doc['url'],
                    receipt_ready_at_utc=receipt_ready(doc).isoformat(), proofs=[proof(root, doc, start, end)])
        rawpath = root / ('raw/' + doc['accession'] + '.txt')
        if digest(rawpath) != doc['raw_sha256']:
            raise ValueError('Archived raw source changed')
        raw = rawpath.read_text(encoding='utf-8')
        header = raw.split('</SEC-HEADER>')[0]
        header_cik = re.search(r'CENTRAL INDEX KEY:\s*(\d+)', header)
        if not header_cik or header_cik[1].zfill(10) != doc['owner_cik']:
            raise ValueError('Filer CIK mismatch')
        item['filer_cik'] = doc['owner_cik']
        siblings = [d for d in docs if d['accession'] == doc['accession']]
        item['issuer_identity'] = ('PARENT_DEI_CIK_AND_TICKER' if any(
            d['primary_cik_match'] and d['primary_symbol_match'] for d in siblings)
            else 'HEADER_CIK_AND_EXPLICIT_TICKERS_IN_PRESS_RELEASE')
        acceptance = re.search(r'<ACCEPTANCE-DATETIME>\s*(\d{14})', header)
        item['sec_acceptance_clock_raw'] = acceptance[1] if acceptance else None
        item['sec_acceptance_timezone_qualified'] = False
        if owner == 'TSEM':
            body = (root / doc['visible_file']).read_text(encoding='utf-8')
            if 'Nasdaq/TASE: TSEM' not in body or 'Nasdaq: SMTC' not in body:
                raise ValueError('Missing explicit issuer/counterparty tickers')
        if owner == 'SITM':
            item['proofs'].append(proof(root, doc,
                'Description of the Transaction', 'Basis of Presentation'))
            if 'excluding customer, supplier and foundry agreements' not in item['proofs'][-1]['quote']:
                raise ValueError('Acquired-business scope warning lost')
        evidence.append(item)

    union = {}
    for file in ['review-pairs.json', 'screen-v2/review-pairs.json']:
        for pair in read(root / file):
            union.setdefault((pair['owner_symbol'], pair['counterparty_symbol']), pair)
    # The two omitted counterparties were named in passages already reviewed, not selected by returns.
    for owner, peer in [('UCTT', 'LRCX'), ('TSEM', 'SMTC')]:
        union[(owner, peer)] = dict(owner_symbol=owner, counterparty_symbol=peer,
                                   origin='NAMED_IN_ALREADY_REVIEWED_PASSAGE')
    if set(union) != set(VERDICTS) or len(union) > 25:
        raise ValueError('Review scope changed')
    reviews = [dict(p, verdict=VERDICTS[key][0], review_note=VERDICTS[key][1]) for key, p in union.items()]
    controls = [dict(p, review_note=CONTROL_NOTES[(p['owner_symbol'], p['counterparty_symbol'])])
                for p in read(root / 'review-controls.json')]
    accepted = [e for e in evidence if e['verdict'] == 'DOCUMENTED_OPERATING_LINK']
    current = pd.read_parquet(root / 'current-top20.parquet')
    history = pd.read_parquet(root / 'historical-top20.parquet')
    closes = read(HISTORY_PROTOCOL)['closes']
    history_cutoffs = pd.to_datetime(history['date'].astype(str).str[:10].map(closes), utc=True)
    if history_cutoffs.isna().any():
        raise ValueError('Missing historical decision clock')
    covered = pd.Series(False, index=history.index)
    for item in accepted:
        covered |= (history.symbol == item['owner']) & (history_cutoffs >= pd.Timestamp(item['receipt_ready_at_utc']))
    snapshot_cutoff = utc_receipt(protocol['frozen_signal_cutoff_utc'])
    current_owners = {e['owner'] for e in accepted if pd.Timestamp(e['receipt_ready_at_utc']) < snapshot_cutoff}
    news = read(root / 'peer-news-coverage.json')
    admitted_peers = {e['counterparty'] for e in accepted}
    report = dict(status='COMPLETED_DOCUMENTARY_FEASIBILITY_NO_ECONOMIC_TEST',
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        original_top20=len(current), source_documents=len(read(root / 'document-inventory.json')),
        owners_with_source_documents=len({d['owner_symbol'] for d in docs}),
        owners_without_copied_source=sorted(set(current.symbol)-{d['owner_symbol'] for d in docs}),
        documented_operating_links=len(accepted), documented_owners=sorted(current_owners),
        documented_owner_coverage=len(current_owners)/len(current),
        source_cutoff_utc=protocol['frozen_signal_cutoff_utc'],
        historical_candidate_days=len(history), historical_receipt_supported_days=int(covered.sum()),
        historical_by_year=[dict(year=int(year), candidate_days=len(group),
            receipt_supported_days=int(covered.loc[group.index].sum()))
            for year,group in history.groupby(history.date.astype(str).str[:4])],
        excluded_scope_example='SITM/AVT: acquired Renesas business, continuity of customer contracts unproved',
        partnership_only_pairs=[list(k) for k,v in VERDICTS.items() if v[0]=='PARTNERSHIP_ONLY'],
        counterparty_news_metadata=[r for r in news['counts'] if r['symbol'] in admitted_peers],
        fully_qualified_news_signals=0, current_cache_is_historical_identity_proof=False,
        review=dict(candidate_pairs=len(reviews), controls=len(controls), initial_cap=20,
            amendment_cap=25, deviation='Original 20-pair bound exceeded during alias correction (22 distinct screened pairs); two outside-universe names from already-read passages bring total to24. No outcomes consulted. Review stopped.',
            reviewer='SAME_ASSISTANT_NOT_INDEPENDENT', exhaustive=False),
        limitations=['Max three recent filings per target; no absence-of-link inference.',
            'Metadata SQL window since2023 does not imply archived documents since2023; earliest retained filing2026-09-03.',
            'Current ticker cache does not establish historical counterparty identity.',
            'Local receipt times bound availability; SEC acceptance raw clock not normalized or used.',
            'COMPLETED_WITH_WARNINGS sources retained only after individual document hash/identity verification.',
            'Peer news metadata is not novelty, issuer-attribution, expectation-surprise or sentiment qualification.',
            'No profitability, AUC, direction or incremental benefit over sector factors measured.'],
        decision='HOLD_HISTORICAL_ALPHA_TEST_INSUFFICIENT_DATED_COVERAGE',
        llm_calls=0, provider_http_calls=0, cost_usd=0, sql_writes=False,
        prices_or_outcomes_read=False, production_changes=False)
    for filename, payload in [('evidence.json', evidence), ('reviewed-pairs.json', reviews),
                              ('reviewed-controls.json', controls), ('report.json', report)]:
        atomic_json(output / filename, payload)
    atomic_json(root / 'progress.json', report)
    return report


if __name__ == '__main__':
    import json
    print(json.dumps(run(), ensure_ascii=False))
