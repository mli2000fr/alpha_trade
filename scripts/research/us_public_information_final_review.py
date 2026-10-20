"""Bounded offline adjudication; preserve sealed predecessors and read no outcomes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_public_information_review import (
    READ, PARENT, COMPACT, primary_parts, exhibits, visible, load_bodies,
)
from scripts.research.us_earnings_release_table_review import numbers
from scripts.research.us_earnings_release_recalage import accounting, price_reaction, PRICE

REVIEW = Path('artifacts/research/us_public_information_followup/review-20261020-v1')
NOTES = Path('doc/ml/sources/qualification_publique_20261020.json')


def normalized(text):
    return ' '.join(text.split())


def source_text(get, accession):
    body, refs, _ = get(accession)
    return body, refs, normalized(' '.join(visible(part) for _, part in primary_parts(body) + exhibits(body)))


def period_review(row, note, get):
    if note is None:
        return None
    quote = row['period_quotes'][note['quote_index']]
    if quote['accession'] != note['accession'] or quote['end'] != note['end']:
        raise ValueError('Review note no longer matches evidence')
    body, refs, text = source_text(get, note['accession'])
    if not body or normalized(quote['quote']) not in text:
        raise ValueError('Period quote absent from archived source')
    if any(token.casefold() not in quote['quote'].casefold() for token in note['required']):
        raise ValueError('Revenue period review guard failed')
    companion = None
    if note.get('companion'):
        at = text.find(note['companion'])
        companion = text[at:at + 650] if at >= 0 else ''
        if note['companion_required'] not in companion:
            raise ValueError('Quarterly revenue companion absent')
    return dict(actual_end=note['end'], provider_anchor=row['anchor'],
                accession=note['accession'], quote=quote['quote'], companion=companion,
                note=note['note'], source_refs=refs)


def reviewed_table(body, note):
    parts = [part for form, part in exhibits(body) if form == note['exhibit']]
    if len(parts) != 1:
        raise ValueError('Ambiguous original exhibit')
    soup = BeautifulSoup(parts[0], 'html.parser')
    for node in soup(['script', 'style', 'ix:header', 'ix:hidden']):
        node.decompose()
    table = soup.find_all('table')[note['table']]
    text = normalized(' '.join(table.stripped_strings))
    whole = normalized(' '.join(soup.stripped_strings))
    at = whole.find(text)
    preceding = whole[max(0, at - 700):at]
    if note['header'] not in text[:500] or note['scale_literal'].casefold() not in (preceding + text[:500]).casefold():
        raise ValueError('Quarter columns / monetary scale not verified')
    proof = {}; values = []
    for key in ('revenue_label', 'operating_label'):
        matches = []
        for row in table.find_all('tr'):
            cells = [normalized(' '.join(c.stripped_strings)) for c in row.find_all(['td', 'th'], recursive=False)]
            nonempty = [(i, x) for i, x in enumerate(cells) if x]
            if nonempty and nonempty[0][1] == note[key]:
                index = nonempty[0][0]
                matches.append((numbers(' '.join(cells[index + 1:])), ' '.join(cells)))
        if len(matches) != 1 or len(matches[0][0]) != 4:
            raise ValueError('Expected two quarter and two year-to-date amounts')
        ns, literal = matches[0]
        values.extend(ns[i] * note['scale'] for i in (note['current_column'], note['prior_column']))
        proof[key] = literal
    return values, dict(header=text[:500], preceding=preceding, rows=proof, review=note)


def causal_dates(acceptance, schedule):
    stamp = pd.Timestamp(acceptance)
    if stamp.tzinfo is None:
        raise ValueError('No invented acceptance timezone')
    eligible = schedule[schedule.market_open > stamp]
    if len(eligible) < 2:
        raise ValueError('Calendar horizon insufficient')
    return str(eligible.index[0])[:10], str(eligible.index[1])[:10]


def run(root):
    if root.exists():
        raise ValueError('Fresh immutable output required')
    evidence = READ(REVIEW / 'evidence.json'); notes = READ(NOTES); get = load_bodies()
    for parent in (PARENT, COMPACT, REVIEW):
        verify_hashes(Path('.'), READ(parent / 'protocol.json')['sources'])
    verify_hashes(REVIEW, READ(REVIEW / 'event-report.json')['files'])
    # Verify every archived successful receipt, including compact index/partial plans.
    receipts = {}
    for parent in (PARENT, COMPACT):
        manifest = READ(parent / 'documents.json')
        verify_hashes(parent, manifest['files'])
        for record in manifest['documents']:
            candidates = [record.get('receipt', {})] + [p['receipt'] for p in record.get('pieces', [])]
            if record.get('index_receipt'):
                candidates.append(record['index_receipt'])
            for receipt in candidates:
                if receipt.get('status') == 'OK':
                    path = parent / receipt['file']
                    if digest(path) != receipt['sha256']:
                        raise ValueError('Archived receipt mismatch')
                    receipts[str(path)] = receipt['sha256']
    root.mkdir(parents=True)
    inputs = [Path(__file__), Path('tests/test_us_public_information_final_review.py'), NOTES,
              REVIEW / 'evidence.json', REVIEW / 'event-report.json', REVIEW / 'q1-event-cohort.parquet',
              PARENT / 'q1-top10.parquet', PARENT / 'document-plan.json', PRICE]
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
                    sources={str(p): digest(p) for p in inputs}, archived_receipts=receipts,
                    reviewer=notes['reviewer'], historical_receipt=False,
                    sql=False, training=False, pnl=False, llm_calls=0, downloads=0, orders=False,
                    purpose='Context qualification and source/causality checks, not a performance test or production admission.')
    atomic_json(root / 'protocol.json', protocol)
    consensus = []; currency_details = []; period_details = []
    for row in evidence['consensus']:
        symbol = row['symbol']; currency = row['currency']; kind = 'INLINE_REVENUE_REPORTING_UNIT' if currency else None
        if symbol in notes['currency_text']:
            note = notes['currency_text'][symbol]
            _, refs, text = source_text(get, note['accession'])
            at = text.find(note['literal'])
            if at < 0:
                raise ValueError('Explicit reporting currency proof absent')
            currency = note['currency']; kind = 'EXPLICIT_REPORTING_CURRENCY_NOT_USD_CONVENIENCE'
            currency_details.append(dict(symbol=symbol, currency=currency, quote=text[max(0, at - 100):at + 700],
                                         accession=note['accession'], source_refs=refs, note=note['note']))
        period = period_review(row, notes['periods'].get(symbol), get)
        if period:
            period_details.append(dict(symbol=symbol, **period))
        reasons = []
        if currency is None:
            reasons.append('REPORTING_CURRENCY_NOT_RESOLVED')
        if period is None:
            reasons.append('EXPLICIT_TARGET_REVENUE_QUARTER_NOT_RESOLVED')
        if currency not in (None, 'USD'):
            reasons.append('VENDOR_DENOMINATION_NOT_CONFIRMED_FOR_NON_USD_REPORTER')
        consensus.append(dict(symbol=symbol, oracle_rank=row['rank'], reporting_currency=currency,
            currency_evidence_kind=kind, provider_anchor=row['anchor'], actual_quarter_end=period['actual_end'] if period else None,
            context_complete=not reasons, numeric_pattern=row['pattern'], relative_change=row['relative'],
            reasons=';'.join(reasons), review_note=notes['rejected_period_candidates'].get(symbol, ''),
            provider_record_currency_certified=False, qualification_backdated=False, live_qualified=False))
    c = pd.DataFrame(consensus)
    c.to_csv(root / 'consensus-context-review.csv', index=False)
    c.to_parquet(root / 'consensus-context-review.parquet', index=False)
    atomic_json(root / 'context-proofs.json', dict(period=period_details, currency_text=currency_details))

    schedule = mcal.get_calendar('NYSE').schedule(start_date='2023-12-01', end_date='2024-04-08')
    top = pd.read_parquet(PARENT / 'q1-top10.parquet')
    membership = set(zip(pd.to_datetime(top.date).dt.strftime('%Y-%m-%d'), top.symbol))
    all_releases = evidence['releases']
    selected = [r for r in all_releases if (r['reaction_date'], r['symbol']) in membership]
    if len(selected) != 24 or {r['accession'] for r in selected} != {r['accession'] for r in all_releases if r['in_q1_top10']}:
        raise ValueError('Admission differs from exact-day frozen TOP10')
    first = {}
    for row in sorted(all_releases, key=lambda r: (r['metadata']['acceptanceDateTime'], r['accession'])):
        if row['period_end']:
            first.setdefault((row['symbol'], row['period_end']), row['accession'])
    source_reviews = []; keys = set(); selected_reviews = []
    for row in selected:
        reaction, entry = causal_dates(row['metadata']['acceptanceDateTime'], schedule)
        if reaction != row['reaction_date']:
            raise ValueError('Acceptance / reaction calendar mismatch')
        values = row['values']; table_proof = None; reasons = []
        if row['symbol'] in notes['event_tables']:
            note = notes['event_tables'][row['symbol']]
            if row['accession'] != note['accession']:
                raise ValueError('Wrong manually reviewed accession')
            body, refs, text = source_text(get, row['accession'])
            values, table_proof = reviewed_table(body, note)
            if note.get('prior_release_date'):
                if note['prior_release_literal'] not in text:
                    raise ValueError('Earlier release date proof absent')
                reasons.append('KNOWN_RELEASE_PRECEDES_SEC_ACCEPTANCE_REACTION_NOT_NOVEL')
            source_reviews.append(dict(symbol=row['symbol'], accession=row['accession'], source_refs=refs, **table_proof))
        if row['period_end'] is None:
            reasons.append('EXPLICIT_ACTUAL_QUARTER_NOT_RESOLVED')
        elif first[(row['symbol'], row['period_end'])] != row['accession']:
            reasons.append('REPEATED_PARSED_SEC_PERIOD')
        if not row['complete_document'] or not row['metadata_complete']:
            reasons.append('INCOMPLETE_PUBLIC_DOCUMENT_POPULATION')
        if values is None:
            reasons.append('QUARTERLY_SOURCE_TABLE_QUARTET_UNRESOLVED')
        if not reasons:
            j = schedule.index.get_loc(pd.Timestamp(reaction))
            keys.update((s, d) for s in (row['symbol'], 'SPY') for d in (schedule.index[j - 1], schedule.index[j]))
        selected_reviews.append(dict(source=row, reaction=reaction, entry=entry, values=values, reasons=reasons))
    columns = ['symbol', 'date', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'is_filled', 'instrument_id', 'data_source', 'data_adjustment']
    prices = pd.read_parquet(PRICE, columns=columns, filters=[('symbol', 'in', sorted({s for s, _ in keys})),
        ('date', 'in', sorted({d for _, d in keys}))]) if keys else pd.DataFrame(columns=columns)
    prices = prices[[key in keys for key in zip(prices.symbol, prices.date)]]
    if prices.duplicated(['symbol', 'date']).any():
        raise ValueError('Duplicate reaction price')
    lookup = {(r['symbol'], r['date']): r for r in prices.to_dict('records')}; events = []
    for reviewed in selected_reviews:
        row = reviewed['source']; reasons = reviewed['reasons']; relative = None; price_side = 'UNKNOWN'
        side, growth, margin = accounting(reviewed['values'])
        if not reasons:
            j = schedule.index.get_loc(pd.Timestamp(reviewed['reaction']))
            relative, price_side, reason = price_reaction([lookup.get((s, d)) for s in (row['symbol'], 'SPY')
                for d in (schedule.index[j - 1], schedule.index[j])])
            if reason:
                reasons.append(reason)
        agreement = side if not reasons and side in ('LONG', 'SHORT') and side == price_side else 'ABSTAIN'
        events.append(dict(symbol=row['symbol'], accession=row['accession'], reaction=reviewed['reaction'],
            potential_entry=reviewed['entry'], source_values=reviewed['values'], accounting_pattern=side,
            revenue_growth=growth, operating_margin_change=margin, relative_reaction=relative,
            price_pattern=price_side, provisional_agreement=agreement, reasons=reasons,
            first_worldwide_release_verified=False, historical_identity_verified=False, fully_qualified=False))
    event_frame = pd.DataFrame(events)
    event_frame.to_parquet(root / 'q1-reviewed-events.parquet', index=False)
    prices.to_parquet(root / 'reaction-price-inputs.parquet', index=False)
    atomic_json(root / 'manual-table-proofs.json', source_reviews)
    files = [p for p in root.iterdir() if p.is_file()]
    report = dict(status='BOUNDED_REVIEW_COMPLETE_EVIDENCE_PARTIAL_NO_EFFICACY_TEST',
        consensus=dict(reviewed=len(c), reporting_currency=c.reporting_currency.value_counts().to_dict(),
            unresolved_reporting_currency=c.loc[c.reporting_currency.isna(), 'symbol'].tolist(),
            context_complete_symbols=c.loc[c.context_complete, 'symbol'].tolist(),
            context_complete_patterns=c.loc[c.context_complete, 'numeric_pattern'].value_counts().to_dict(),
            reserved=int((~c.context_complete).sum()), earlier_DOCN_FUN_contexts_not_overwritten=True,
            vendor_currency_not_certified=True, qualification_backdated=False, live_qualified=0),
        events=dict(calendar='2024Q1', admitted_before_financial_filters=len(events), source_quartets=sum(e['source_values'] is not None for e in events),
            provisional_agreements=event_frame.provisional_agreement.value_counts().to_dict(),
            reason_counts=dict(Counter(reason for e in events for reason in e['reasons'])),
            fully_qualified=0, prior_93_cases_used_for_admission=False,
            no_prices_after_reaction=True, price_input_rows=len(prices)),
        successful_receipts_verified=len(receipts), reviewed_by=notes['reviewer'],
        caveat='Original SGML acquisition INCOMPLETE; compact plan processed, not exhaustive original-document coverage. Same assistant, no independent human review.',
        files={p.name: digest(p) for p in files})
    atomic_json(root / 'report.json', report)
    print(report, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
