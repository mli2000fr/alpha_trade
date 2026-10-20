"""Offline bound review, exact quotes and predecessor evidence, never prices."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_news_information_vs_noise_feasibility import READ, review, prepare

NOTES = Path('doc/ml/sources/news_information_vs_noise_review_20261020.json')


def run(root):
    prepare(root)
    out = root / 'readout-v1'
    if out.exists():
        raise ValueError('Readout immutable')
    notes = READ(NOTES); compiled = {}; details = []
    prior = READ(root / 'prospective-prior-context.json')
    for panel in ('historical', 'prospective'):
        path = root / (panel + '-review-pack.json')
        if digest(path) != notes[panel + '_pack_sha256']:
            raise ValueError('Manual review does not match frozen pack')
        verify_hashes(root, READ(root / (panel + '-report.json'))['files'])
        pack = READ(path); annotations = notes[panel]
        if sorted(n['index'] for n in annotations) != list(range(len(pack))):
            raise ValueError('Incomplete manual review')
        rows = []
        for n in annotations:
            item = pack[n['index']]
            quotes = [dict(field='headline', text=item['headline'])]
            if n.get('support_text'):
                field = n['support_field']; quote = n['support_text']
                if quote not in item[field]:
                    raise ValueError('Manual quote absent')
                quotes.append(dict(field=field, text=quote))
            predecessor = None
            if n.get('prior_article_id'):
                found = [p for p in prior if p['article_id'] == n['prior_article_id'] and p['symbol'] == item['symbol']]
                if len(found) != 1 or n['prior_support_text'] not in found[0]['content']:
                    raise ValueError('Prior announcement proof absent')
                predecessor = found[0]
                if predecessor['temporal_reservations'] or predecessor['publication_utc'] >= item['publication_utc']:
                    raise ValueError('Prior announcement not available earlier')
            row = dict(evidence_key=item['evidence_key'], category=n['category'], subject=n['subject'],
                novelty=n['novelty'], note=n['note'], quotes=quotes, reviewed_by=notes['reviewer'])
            rows.append(row)
            details.append(dict(panel=panel, symbol=item['symbol'], article_id=item['article_id'],
                category=n['category'], subject=n['subject'], novelty=n['novelty'],
                temporal_status='HISTORICAL_UNQUALIFIED' if panel == 'historical' else
                    'RECEIPTS_QUALIFIED' if not item['temporal_reservations'] else 'RESERVED',
                body_truncated=item['body_truncated'], predecessor=predecessor, note=n['note'],
                eligible_new_event=False, no_news_certified=False))
        compiled[panel] = rows
    out.mkdir()
    paths = [Path(__file__), NOTES, root / 'protocol.json', root / 'historical-report.json',
             root / 'prospective-report.json', root / 'historical-review-pack.json',
             root / 'prospective-review-pack.json', root / 'prospective-prior-context.json']
    atomic_json(out / 'protocol.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(p): digest(p) for p in paths}, prices_read=False, llm_calls=0, sql_writes=False,
        purpose='Same-assistant bounded semantic reading, not independent human review or efficacy test'))
    atomic_json(out / 'review-notes.json', compiled)
    atomic_json(out / 'review-details.json', details)
    reviewed = review(root, out / 'review-notes.json')
    summary = {}
    for panel in ('historical', 'prospective'):
        rows = [r for r in details if r['panel'] == panel]
        own_candidates = [r for r in rows if r['category'] == 'FACTUAL_ANNOUNCEMENT_CANDIDATE' and r['subject'] == 'TEXTUAL_SUBJECT_MATCH']
        summary[panel] = dict(**reviewed[panel], own_factual_candidates=len(own_candidates),
            own_candidate_symbols=sorted({r['symbol'] for r in own_candidates}),
            other_issuer_factual_candidates=sum(r['category'] == 'FACTUAL_ANNOUNCEMENT_CANDIDATE' and r['subject'] == 'OTHER_ISSUER' for r in rows),
            no_news_certified=0, receipt_qualified=sum(r['temporal_status'] == 'RECEIPTS_QUALIFIED' for r in rows))
    result = dict(status='BLOCKED_CAUSAL_CONTRAST_NOT_EFFICACY_FAILURE', panels=summary,
        blockers=['Historical versions not available at historical decision',
            'No fully qualified new own-issuer event in recent reviewed panel',
            'Absence of identified article not evidence of no announcement; coverage unknown',
            'Novelty/first-publication and historical issuer identity unqualified'],
        prices_read=False, api_calls=0, llm_calls=0, sql_writes=False, training=False, orders=False,
        files={p.name: digest(p) for p in out.iterdir() if p.is_file()})
    atomic_json(out / 'report.json', result); return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    print(run(parser.parse_args().root))
