"""Local-only, price-blind second bounded reading of existing sealed archives.

No provider/LLM calls, database access, return calculations or production writes.
The same assistant's reading is not an independent human review.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from scripts.research import us_news_event_qualification as evidence


def verified_pack(pack):
    report = json.loads((pack/'report.json').read_text(encoding='utf-8'))
    if report['query_truncated']:
        raise ValueError('Truncated parent pack')
    for name, expected in report['files'].items():
        if Path(name).name != name or evidence.sha(pack/name) != expected:
            raise ValueError('Changed source pack')
    return report, json.loads((pack/'evidence.json').read_text(encoding='utf-8'))


def select_second(items, prior):
    seen = {r['text_hash'] for r in prior}
    selected = []
    for screened, cap in ((True, 20), (False, 10)):
        group = []
        for row in sorted(items, key=lambda r: r['evidence_key']):
            if (row['screened'] != screened or row['temporal_reservations']
                    or row['text_hash'] in seen):
                continue
            group.append(row)
            seen.add(row['text_hash'])
            if len(group) == cap:
                break
        selected.extend(group)
    return selected


def prepare(parent, prior, output):
    source_report, items = verified_pack(parent)
    _, previous = verified_pack(prior)
    known = {r['evidence_key']: r for r in items}
    if any(known.get(r['evidence_key']) != r for r in previous):
        raise ValueError('Prior sample does not belong to this parent')
    if output.exists():
        raise FileExistsError('Require fresh immutable directory')
    selected = select_second(items, previous)
    if not selected:
        raise ValueError('No unread eligible texts')
    output.mkdir(parents=True)
    protocol = json.loads((parent/'protocol.json').read_text(encoding='utf-8'))
    protocol.update(created_at_utc=datetime.now(timezone.utc).isoformat(),
        parent_report_sha256=evidence.sha(parent/'report.json'),
        parent_evidence_sha256=evidence.sha(parent/'evidence.json'),
        previous_report_sha256=evidence.sha(prior/'report.json'),
        selection='Stable evidence-key order, one pair per unread text; max 20 screened + 10 controls; no prices',
        review_is_independent=False, code_sha256=evidence.sha(Path(__file__)))
    evidence.save(output/'protocol.json', protocol)
    evidence.save(output/'evidence.json', selected)
    evidence.save(output/'review_template.json', evidence.review_template(selected))
    report = dict(status='SECOND_BOUNDED_REVIEW_PENDING', article_ids=len({r['article_id'] for r in selected}),
        confirmed_observations=source_report['confirmed_observations'],
        observations_count_scope='full parent corpus, not second sample',
        candidate_article_symbol_pairs=len(selected), screened_pairs=sum(r['screened'] for r in selected),
        unique_screened_texts=sum(r['screened'] for r in selected),
        pending_receipts=source_report['pending_receipts'], query_truncated=False,
        qualified_events=0, sample_not_complete_corpus=True,
        prior_texts_excluded=len({r['text_hash'] for r in previous}),
        remaining_eligible_screened_pairs=len([r for r in items if r['screened']
            and not r['temporal_reservations'] and r['evidence_key'] not in
            {v['evidence_key'] for v in previous+selected}]),
        api_calls=0, sql_writes=False, training=False, returns_computed=False,
        files={p.name:evidence.sha(p) for p in output.iterdir() if p.is_file()})
    evidence.save(output/'report.json', report)
    return report


def annotate(pack, notes_path):
    _, items = verified_pack(pack)
    notes = json.loads(notes_path.read_text(encoding='utf-8'))
    if set(notes) != {r['article_id'] for r in items}:
        raise ValueError('Notes must cover exactly the articles actually read')
    now = datetime.now(timezone.utc)
    reviews = []
    for row in items:
        note = notes[row['article_id']]
        quote = note['quote']
        start = row['fields']['content'].find(quote)
        if start < 0 or len(quote.strip()) < 10:
            raise ValueError('Exact archived quotation required')
        reviews.append(dict(evidence_key=row['evidence_key'],
            reviewer='Codex technical reading; NOT independent human review',
            reviewed_at_utc=now.isoformat(), issuer_name=note['issuer'],
            identity_verified=row['symbol'] in note['identity_symbols'],
            identity_meaning='Issuer/subject of the financing clause; not mere article association',
            event_type=note['event_type'], new_announcement_verified=note.get('new_announcement_verified'),
            prior_comparison_complete=False,
            novelty_evidence='Bounded archive does not certify earlier announcement history. '+note['notes'],
            quotes=[dict(field='content', start=start, end=start+len(quote), text=quote)],
            facts=[], notes=note['notes'], review_category=note['category'],
            instrument_class=note.get('instrument_class'), full_archived_body_read=True,
            current_reference_is_historical_pit=False, independent_review_certified=False,
            notes_sha256=evidence.sha(notes_path)))
    evidence.save(pack/'technical_review_filled.json', reviews)
    result = evidence.review_pack(pack, pack/'technical_review_filled.json', pack/'technical_review_result.json')
    summary = dict(created_at_utc=now.isoformat(), status='SECOND_READING_COMPLETED_NOT_A_SIGNAL',
        reviewed_pairs=len(reviews), reviewed_distinct_texts=len({r['text_hash'] for r in items}),
        categories=dict(Counter(r['review_category'] for r in reviews)),
        qualified_pairs=sum(r['status']=='QUALIFIED_RESEARCH_EVENT' for r in result['results']),
        identity_unverified_pairs=sum(not r['identity_verified'] for r in reviews),
        independent_review_certified=False, historical_availability_invented=False,
        api_calls=0, llm_calls=0, sql_writes=False, training=False, returns_computed=False,
        parent_report_sha256=evidence.sha(pack/'report.json'), notes_sha256=evidence.sha(notes_path))
    evidence.save(pack/'technical_review_summary.json', summary)
    return summary


def completion_summary(parent, prior, pack, coverage, universe, output):
    _, all_items = verified_pack(parent)
    _, previous = verified_pack(prior)
    _, selected = verified_pack(pack)
    protocol = json.loads((pack/'protocol.json').read_text(encoding='utf-8'))
    if evidence.sha(universe) != protocol['universe_sha256']:
        raise ValueError('Universe changed; current membership cannot stand for frozen scope')
    covered = json.loads((coverage/'report.json').read_text(encoding='utf-8'))
    if covered['source_hashes'][str(pack/'evidence.json')] != evidence.sha(pack/'evidence.json'):
        raise ValueError('Coverage belongs to another evidence pack')
    review = json.loads((pack/'technical_review_summary.json').read_text(encoding='utf-8'))
    symbols = set(filter(None, re.split(r'[,;\s]+', universe.read_text(encoding='utf-8-sig'))))
    eligible = [r for r in all_items if r['screened'] and not r['temporal_reservations']]
    seen = {r['text_hash'] for r in previous+selected}
    remaining = {r['text_hash'] for r in eligible}-seen
    result = dict(status='SECOND_BOUNDED_READING_DELIVERED_NO_QUALIFIED_UNIVERSE_EVENT',
        created_at_utc=datetime.now(timezone.utc), publication_cutoff_unchanged=protocol['cutoff_utc'],
        first_sample_pairs=len(previous), second_sample_pairs=len(selected),
        total_distinct_read_texts=len(seen),
        eligible_screened_texts_total=len({r['text_hash'] for r in eligible}),
        eligible_screened_texts_read=len({r['text_hash'] for r in eligible}&seen),
        unread_eligible_screened_texts=len(remaining),
        no_event_absence_claim_for_unreviewed_corpus=True,
        review=review, technical_window_counts=covered['technical_window_counts'],
        current_frozen_file_membership={s:s in symbols for s in ('IONQ','IAM','BSP','GSK','CWT','NICE','OWL','AFL')},
        membership_is_not_historical_pit=True, universe_sha256=evidence.sha(universe),
        retrospective_publication_window_not_executable_signal=True,
        independent_review_certified=False, api_calls=0, sql_writes=False,
        llm_calls=0, training=False, economic_test=False, returns_computed=False,
        source_hashes={str(p):evidence.sha(p) for p in (
            parent/'report.json', prior/'report.json', pack/'report.json',
            pack/'technical_review_filled.json', pack/'technical_review_result.json',
            pack/'technical_review_summary.json', coverage/'report.json')})
    evidence.save(output, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path)
    parser.add_argument('--prior', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--notes', type=Path)
    parser.add_argument('--coverage', type=Path)
    parser.add_argument('--universe', type=Path)
    args = parser.parse_args()
    if args.pack and args.coverage and args.universe and args.parent and args.prior and args.output:
        result = completion_summary(args.parent, args.prior, args.pack, args.coverage, args.universe, args.output)
    elif args.pack and args.notes:
        result = annotate(args.pack, args.notes)
    elif args.parent and args.prior and args.output:
        result = prepare(args.parent, args.prior, args.output)
    else:
        parser.error('Require parent/prior/output or pack/notes')
    print(json.dumps(evidence.archive.json_value(result), ensure_ascii=False))
