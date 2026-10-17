"""Close the frozen eligible financing screen, using local archives only.

Four final full bodies were read; previous readings are rebound to all eligible
article/symbol pairs. No SQL, external API, LLM call, price or return calculation.
This is neither independent human review nor an exhaustive review of all news.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from scripts.research import us_news_event_qualification as evidence
from scripts.research import us_news_financing_review_20261016 as first_reading
from scripts.research.us_news_financing_second_review_20261016 import verified_pack

NEW_NOTES = {
    'eodhd:84dfcbb322615b4f51ff787a': dict(
        issuer='Bending Spoons', identity_symbols=['BSP'], event_type='PRIMARY_EQUITY_FINANCING',
        category='OTHER_ISSUER_REPEATED_PLACEMENT', instrument_class='ORDINARY_SHARES',
        quote='will issue 10 million ordinary shares at a price of $33 apiece',
        notes='BSP is the issuer, not mapped NVDA. Same Berkshire USD330m placement as two previously read articles. The Miro-related proposed investment is a separate conditional transaction, not merged into the Berkshire placement.'),
    'eodhd:a4025d7acbfdeff372b8876c': dict(
        issuer='Solidigm / SK Hynix', identity_symbols=[], event_type='OTHER',
        category='OTHER_ISSUER_POSSIBLE_FUTURE_IPO',
        quote='Solidigm is also weighing an initial public offering as early as next year',
        notes='AMAT is an equipment supplier; the potential IPO concerns Solidigm. Export licence and factory plans are not a new Applied Materials share issue; no priced or final IPO established.'),
    'eodhd:45c58a76bee88f72a32c21fa': dict(
        issuer='Antero Midstream', identity_symbols=['AM'], event_type='BUYBACK',
        category='DIVIDEND_AND_HISTORICAL_BUYBACK_NOT_NEW_ISSUANCE',
        quote='Antero Midstream repurchased 1.3 million shares for approximately $27 million',
        notes='Quarterly dividend and third-quarter repurchases. IPO reference is November 2014. Return of capital, not new primary equity funding; earnings release date is not an offering date.'),
    'eodhd:cfa65032370fe1813939a1e6': dict(
        issuer='CoreWeave', identity_symbols=['CRWV'], event_type='OTHER',
        category='OTHER_ISSUER_DEBT_COMMENTARY_AND_HISTORICAL_IPO',
        quote='its troubled initial public offering in March 2025',
        notes='CoreWeave debt/market commentary; Nvidia is a shareholder and supplier, not the financing issuer. Historical IPO and possible future capital needs do not establish a new NVDA raise. No historical share-price claim is used as a selection criterion.')
}

# Exact textual reconciliation, not automated fuzzy matching or a count of all
# financing operations mentioned in the bodies. Separate tranches/updates and
# separate issuers must not be merged by ticker or broad keyword alone.
REPEATS = {
    'IONQ_20261014_EQUITY_AND_WARRANTS': dict(issuer='IonQ', issuer_symbols=['IONQ'],
        instrument='COMMON_SHARES_AND_WARRANTS',
        articles=['eodhd:ff92f25a0c589c9b5e01d58d', 'eodhd:532efc1c6f244967762172f3'],
        rationale='Same named issuer, USD2bn financing and October pricing; one roundup and one issuer announcement. NVDA/BAC/other context tickers are not issuers.'),
    'IAMBIC_20261015_IPO': dict(issuer='Iambic Therapeutics', issuer_symbols=['IAM'],
        instrument='IPO_COMMON_SHARES',
        articles=['eodhd:4dfb14c73131447372f692b6', 'eodhd:b3883986f16118c2d6c488e1'],
        rationale='Same IAM IPO, USD16 offer price and approximately USD150m size. ABBV/NVDA/TAK are not the IPO issuer.'),
    'BSP_BERKSHIRE_20261014_PLACEMENT': dict(issuer='Bending Spoons', issuer_symbols=['BSP'],
        instrument='ORDINARY_SHARES_PRIVATE_PLACEMENT',
        articles=['eodhd:05b73e8a127fdcee05c52124', 'eodhd:edebe79a2965247e575341af',
                  'eodhd:84dfcbb322615b4f51ff787a'],
        rationale='Same Berkshire additional USD330m investment; two articles specify 10m new shares at USD33. Transcript is a previously read control, not a neutral no-event article. Do not merge July IPO or separate Miro-related proposed investment.')
}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def checked_reading(pack):
    report, items = verified_pack(pack)
    rows = load_json(pack/'technical_review_filled.json')
    result = load_json(pack/'technical_review_result.json')
    if (result['report_sha256'] != evidence.sha(pack/'report.json') or
            result['review_sha256'] != evidence.sha(pack/'technical_review_filled.json')):
        raise ValueError('Review not bound to source pack')
    keys = {r['evidence_key'] for r in items}
    if (len(keys) != len(items) or {r['evidence_key'] for r in rows} != keys or
            len(rows) != len(keys) or {r['evidence_key'] for r in result['results']} != keys):
        raise ValueError('Incomplete or duplicate prior reading')
    for item, row in ((r, next(v for v in rows if v['evidence_key']==r['evidence_key'])) for r in items):
        if not row.get('full_archived_body_read'):
            raise ValueError('Prior body not read')
        for q in row['quotes']:
            if item['fields'][q['field']][q['start']:q['end']] != q['text']:
                raise ValueError('Prior quotation changed')
    return report, items, rows


def eligible_and_remaining(items, first, second):
    known = {r['evidence_key']:r for r in items}
    if len(known)!=len(items) or any(known.get(r['evidence_key'])!=r for r in first+second):
        raise ValueError('Samples not bound to same parent')
    eligible = sorted((r for r in items if r['screened'] and not r['temporal_reservations']),
                      key=lambda r:r['evidence_key'])
    seen = {r['text_hash'] for r in first+second}
    remaining = {r['article_id'] for r in eligible if r['text_hash'] not in seen}
    return eligible, remaining


def all_notes():
    notes = {key:dict(issuer=r['issuer'], identity_symbols=sorted(r['symbols']),
        event_type=r['kind'], category=r['category'], quote=r['quote'],
        notes=r['explanation'], instrument_class=r['instrument'])
        for key,r in first_reading.NOTES.items()}
    second_path = Path(__file__).with_name('us_news_financing_second_reading_notes_20261016.json')
    second = load_json(second_path)
    if set(notes)&set(second) or (set(notes)|set(second))&set(NEW_NOTES):
        raise ValueError('Overlapping note sources')
    return {**notes, **second, **NEW_NOTES}, second_path


def check_note_lineage(items, prior_rows, notes):
    """Do not silently replace the substance of a previously sealed reading."""
    by_key={r['evidence_key']:r for r in prior_rows}
    for item in items:
        row=by_key[item['evidence_key']]
        n=notes[item['article_id']]
        if (row['issuer_name']!=n['issuer'] or row['event_type']!=n['event_type'] or
                row['identity_verified']!=(item['symbol'] in n['identity_symbols']) or
                not any(q['field']=='content' and q['text']==n['quote'] for q in row['quotes'])):
            raise ValueError('Changed prior interpretation; explicit new adjudication required')


def annotations(items, notes, now):
    rows = []
    for item in items:
        n = notes[item['article_id']]
        quote = n['quote']
        start = item['fields']['content'].find(quote)
        if start < 0 or len(quote.strip())<10:
            raise ValueError('Exact quotation required for every final pair')
        # New per-pair assessment now; previous reviews are cited separately.
        # No copying an old annotation time to newly assessed associations.
        rows.append(dict(evidence_key=item['evidence_key'],
            reviewer='Codex technical consolidation; NOT independent human review',
            reviewed_at_utc=now.isoformat(), issuer_name=n['issuer'],
            identity_verified=item['symbol'] in n['identity_symbols'],
            identity_meaning='Subject of reviewed clause, not proof of new common-equity financing',
            event_type=n['event_type'], new_announcement_verified=None,
            prior_comparison_complete=False,
            novelty_evidence='Earlier history is not certified by this bounded archive. '+n['notes'],
            quotes=[dict(field='content',start=start,end=start+len(quote),text=quote)],
            facts=[], notes=n['notes'], review_category=n['category'],
            instrument_class=n.get('instrument_class'), full_archived_body_read=True,
            independent_review_certified=False, current_reference_is_historical_pit=False))
    return rows


def repeat_groups(items, notes, symbols, now):
    groups = []
    for key, group in REPEATS.items():
        members = [r for r in items if r['article_id'] in group['articles']]
        if {r['article_id'] for r in members} != set(group['articles']):
            raise ValueError('Missing repeat-family source article')
        citations = []
        for article in group['articles']:
            row = next(r for r in members if r['article_id']==article)
            quote = notes[article]['quote']
            start = row['fields']['content'].find(quote)
            if start<0:
                raise ValueError('Repeat source quote changed')
            citations.append(dict(article_id=article, raw_version_id=row['raw_version_id'],
                text_hash=row['text_hash'], quote=quote, start=start,end=start+len(quote)))
        groups.append(dict(family_id=key, **group, citations=citations,
            source_article_count=len(group['articles']), mapped_pair_count=len(members),
            associated_symbols=sorted({r['symbol'] for r in members}),
            issuer_symbols_in_frozen_file=sorted(set(group['issuer_symbols'])&symbols),
            earliest_selected_pair_available_at=min(max(evidence.utc(r['text_available_at']),
                evidence.utc(r['mapping_available_at'])) for r in members),
            annotation_available_at=now,
            first_ever_announcement_or_syndication_certified=False,
            exhaustive_all_transaction_mentions=False, tradable_signal=False))
    return groups


def run(parent, first, second, universe, output):
    source_report, all_items = verified_pack(parent)
    _, first_items, first_rows = checked_reading(first)
    _, second_items, second_rows = checked_reading(second)
    protocol = load_json(parent/'protocol.json')
    if evidence.sha(universe) != protocol['universe_sha256']:
        raise ValueError('Universe changed since frozen evidence')
    eligible, remaining = eligible_and_remaining(all_items, first_items, second_items)
    if remaining != set(NEW_NOTES):
        raise ValueError('Require exactly the four final texts actually read')
    notes, second_path = all_notes()
    check_note_lineage(first_items, first_rows, notes)
    check_note_lineage(second_items, second_rows, notes)
    if {r['article_id'] for r in eligible}-set(notes):
        raise ValueError('Unreviewed eligible article')
    controls = [r for r in first_items+second_items if not r['screened']]
    union = eligible+controls
    if len({r['evidence_key'] for r in union})!=len(union):
        raise ValueError('Duplicate final evidence keys')
    now = datetime.now(timezone.utc)
    rows = annotations(union, notes, now)
    symbols = set(filter(None, re.split(r'[,;\s]+', universe.read_text(encoding='utf-8-sig'))))
    groups = repeat_groups(union, notes, symbols, now)
    article_rows = []
    by_key = {r['evidence_key']:r for r in rows}
    family_by_article = {aid:g['family_id'] for g in groups for aid in g['articles']}
    for article in sorted({r['article_id'] for r in eligible}):
        related = [r for r in eligible if r['article_id']==article]
        n = notes[article]
        matches = [r for r in related if r['symbol'] in n['identity_symbols']]
        article_rows.append(dict(article_id=article, text_hash=related[0]['text_hash'],
            headline=related[0]['fields']['headline'], reviewed_issuer=n['issuer'],
            event_type=n['event_type'], category=n['category'], instrument_class=n.get('instrument_class'),
            associated_symbols=sorted(r['symbol'] for r in related),
            matched_subject_symbols=sorted(r['symbol'] for r in matches),
            repeat_family_id=family_by_article.get(article), quotes=by_key[related[0]['evidence_key']]['quotes'],
            pairs=[dict(symbol=r['symbol'], evidence_key=r['evidence_key'],
                publication_utc=r['publication_utc'], text_available_at=r['text_available_at'],
                mapping_available_at=r['mapping_available_at'],
                evidence_available_at=max(evidence.utc(r['text_available_at']),evidence.utc(r['mapping_available_at'])),
                identity_verified=by_key[r['evidence_key']]['identity_verified']) for r in related],
            earliest_selected_text_available_at=min(evidence.utc(r['text_available_at']) for r in related),
            annotation_available_at=now, historical_first_publication_certified=False,
            prior_comparison_complete=False, qualified_for_experiment=False,
            explanation=n['notes']))
    if output.exists():
        raise FileExistsError('Fresh immutable output required')
    output.mkdir(parents=True)
    protocol.update(created_at_utc=now.isoformat(),
        selection='All frozen screened pairs without temporal reservations plus the 20 previously read controls; no new controls',
        parent_report_sha256=evidence.sha(parent/'report.json'),
        prior_review_hashes={str(p/'technical_review_result.json'):evidence.sha(p/'technical_review_result.json') for p in (first,second)},
        original_cutoff_not_shifted=True,review_is_independent=False, code_sha256=evidence.sha(Path(__file__)))
    evidence.save(output/'protocol.json',protocol)
    evidence.save(output/'evidence.json',union)
    evidence.save(output/'review_template.json',evidence.review_template(union,cap=len(eligible),controls=len(controls)))
    report=dict(status='FINAL_ELIGIBLE_SCREEN_REVIEW_PENDING_VALIDATION',article_ids=len({r['article_id'] for r in union}),
        confirmed_observations=source_report['confirmed_observations'], observations_count_scope='full parent corpus',
        candidate_article_symbol_pairs=len(union),screened_pairs=len(eligible),
        unique_screened_texts=len({r['text_hash'] for r in eligible}), pending_receipts=source_report['pending_receipts'],
        query_truncated=False,sample_not_complete_corpus=True,qualified_events=0,
        files={p.name:evidence.sha(p) for p in output.iterdir() if p.is_file()})
    evidence.save(output/'report.json',report)
    evidence.save(output/'technical_review_filled.json',rows)
    result=evidence.review_pack(output,output/'technical_review_filled.json',output/'technical_review_result.json')
    evidence.save(output/'financing_article_ledger.json',article_rows)
    evidence.save(output/'repeat_families.json',groups)
    new_details=[r for r in article_rows if r['article_id'] in NEW_NOTES]
    evidence.save(output/'four_final_texts_review.json',new_details)
    final=dict(status='CLOSED_ELIGIBLE_FINANCING_SCREEN_NO_QUALIFIED_UNIVERSE_EVENT',
        created_at_utc=now,source_publication_cutoff_unchanged=protocol['cutoff_utc'],
        screened_pairs_reviewed=len(eligible), screened_distinct_texts_read=len({r['text_hash'] for r in eligible}),
        unread_eligible_screened_texts=0, unreviewed_eligible_screened_pairs=0,
        prior_controls_retained=len(controls), total_pairs=len(union), total_distinct_read_texts=len({r['text_hash'] for r in union}),
        newly_read_distinct_texts=len(NEW_NOTES),
        new_pair_assessments=len({r['evidence_key'] for r in union}-{r['evidence_key'] for r in first_items+second_items}),
        matching_subject_screened_articles=sum(bool(r['matched_subject_symbols']) for r in article_rows),
        qualified_primary_pairs=sum(r['status']=='QUALIFIED_RESEARCH_EVENT' for r in result['results']),
        mapped_subject_candidate_symbols=sorted({s for r in article_rows for s in r['matched_subject_symbols']}),
        event_type_article_counts=dict(Counter(r['event_type'] for r in article_rows)),
        repeated_families=len(groups), repeated_family_articles=sum(g['source_article_count'] for g in groups),
        repeated_family_mapped_pairs=sum(g['mapped_pair_count'] for g in groups),
        prior_history_certified=False, independent_review_certified=False,
        full_unscreened_corpus_reviewed=False, screened_temporally_reserved_pairs_not_promoted=True,
        no_general_event_absence_claim=True, prices_used_for_selection=False,
        api_calls=0,llm_calls=0,sql_reads=0,sql_writes=False,training=False,returns_computed=False,economic_test=False,
        active_universe_or_batches_changed=False,
        source_hashes={str(p):evidence.sha(p) for p in (
            parent/'report.json', first/'technical_review_result.json', second/'technical_review_result.json',
            Path(first_reading.__file__),Path(__file__),second_path,universe)},
        files={p.name:evidence.sha(p) for p in output.iterdir() if p.is_file()})
    evidence.save(output/'closure_report.json',final)
    return final


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('parent','first','second','universe','output'):
        parser.add_argument('--'+flag,type=Path,required=True)
    args=parser.parse_args()
    result=run(**vars(args))
    print(json.dumps({k:result[k] for k in ('status','screened_pairs_reviewed','screened_distinct_texts_read',
        'unread_eligible_screened_texts','total_distinct_read_texts','new_pair_assessments',
        'qualified_primary_pairs','mapped_subject_candidate_symbols','repeated_families',
        'repeated_family_articles','repeated_family_mapped_pairs')},ensure_ascii=False))
