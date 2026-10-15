"""Reproduce the bounded Codex technical reading of nine pilot article versions.

Not an independent human review, general classifier, direction score or API call.
Interpretations below were written after reading the actual frozen source texts.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.research import us_news_event_qualification as pilot


ANNOTATIONS = {
    'eodhd:20f345f34288ad8af9b172ed': ('OTHER', 'HPE', 'Analyst downgrade, short article preview; no verified primary equity financing.'),
    'eodhd:2797d6bd7a3a1da666fa44a7': ('OTHER', 'Cisco Systems', 'Investment commentary, old results/guidance and competitors, not a new offering.'),
    'eodhd:38c4c1181538420664ffd179': ('OTHER', 'Keystone Law Group', 'AIM:KEYS denotes the UK law firm in this article, not US Keysight Technologies. ENTITY_MISMATCH.'),
    'eodhd:399a6aa537927f3465fb425a': ('OTHER', None, 'Multi-company AI-market commentary and historical examples, not an issuer financing announcement.'),
    'eodhd:3cb646b70cc16de0f4492dae': ('OTHER', 'Keysight Technologies', 'Short preview of price outperformance/AI supply, no verified primary financing.'),
    'eodhd:44f4b155343298fdc697b8a1': ('OTHER', 'Southern Copper', 'Valuation commentary and capital expenditure are not primary equity financing. SO mapping is not SCCO. ENTITY_MISMATCH for SO.'),
    'eodhd:70c8c47bac7859ec6994194d': ('OTHER', 'General Mills', 'Multi-company value commentary; cash savings program is not new equity issuance.'),
    'eodhd:b77ed8f54767cfa831be607e': ('OTHER', 'Southern Copper', 'Valuation opinion about already known projects and historical performance, not a new equity offering.'),
    'eodhd:d28dc83d1e4bbae0dd8cc510': ('PRIMARY_EQUITY_FINANCING', 'Synopsys, Inc.',
        'Article explicitly dates the placement to 2025. Old financing recalled in investment commentary, not a new 2026 announcement. '
        'The issuer is SNPS, not competitors KEYS/SIEGY. ENTITY_MISMATCH for KEYS and SIEGY.'),
}
OLD_FINANCING_QUOTE = ('In 2025, Synopsys issued about 4.8 million shares in a private placement '
    'with NVIDIA for $2 billion of net proceeds.')


def run(root):
    report = json.loads((root/'report.json').read_text(encoding='utf-8'))
    for name, expected in report['files'].items():
        if pilot.sha(root/name) != expected:
            raise ValueError('Evidence pack changed')
    evidence = json.loads((root/'evidence.json').read_text(encoding='utf-8'))
    templates = json.loads((root/'review_template.json').read_text(encoding='utf-8'))
    selected = {r['evidence_key']: r for r in evidence if r['evidence_key'] in {v['evidence_key'] for v in templates}}
    if {r['article_id'] for r in selected.values()} != set(ANNOTATIONS):
        raise ValueError('This technical reading belongs only to the fixed nine-article sample')
    now = datetime.now(timezone.utc)
    reviews = []
    mismatch = []
    for key, item in selected.items():
        kind, issuer, note = ANNOTATIONS[item['article_id']]
        field, quote = 'headline', item['fields']['headline']
        identity = None
        facts = []
        if item['article_id'] == 'eodhd:d28dc83d1e4bbae0dd8cc510':
            field, quote = 'content', OLD_FINANCING_QUOTE
            identity = item['symbol'] == 'SNPS'
            facts = [dict(name='shares_issued', literal='4.8 million', quote_index=0),
                     dict(name='offering_amount', literal='$2 billion', quote_index=0)]
            if not identity:
                mismatch.append(key)
        elif item['article_id'] == 'eodhd:38c4c1181538420664ffd179':
            field, quote, identity = 'content', 'Keystone Law Group (AIM:KEYS)', False
            mismatch.append(key)
        elif item['article_id'] == 'eodhd:44f4b155343298fdc697b8a1' and item['symbol'] == 'SO':
            field, quote, identity = 'content', 'Companies discussed in this article include SCCO.', False
            mismatch.append(key)
        start = item['fields'][field].index(quote)
        reviews.append(dict(evidence_key=key, reviewer='Codex technical reading; NOT independent human review',
            reviewed_at_utc=now.isoformat(), issuer_name=issuer, identity_verified=identity,
            event_type=kind, new_announcement_verified=False,
            prior_comparison_complete=False, novelty_evidence='No exhaustive prior-announcement comparison claimed; '+note,
            quotes=[dict(field=field, start=start, end=start+len(quote), text=quote)],
            facts=facts, notes=note, full_archived_body_read=True))
    pilot.save(root/'technical_review_filled.json', reviews)
    result = pilot.review_pack(root,root/'technical_review_filled.json',root/'technical_review_result.json')
    summary = dict(status='BOUNDED_TECHNICAL_READING_COMPLETED_NO_QUALIFIED_NEW_EVENT',
        article_symbol_pairs_read=len(reviews), distinct_archived_articles_read=len(ANNOTATIONS),
        screened_pairs=sum(item['screened'] for item in selected.values()),
        screened_distinct_articles=len({item['article_id'] for item in selected.values() if item['screened']}),
        qualified_events=sum(r['status']=='QUALIFIED_RESEARCH_EVENT' for r in result['results']),
        apparent_wrong_event_issuer_or_market_pairs=len(mismatch), mismatch_evidence_keys=mismatch,
        event_absence_proven=False, independent_human_review=False, api_calls=0, sql_writes=False,
        training=False, financial_result=False, production_changes=False,
        code_sha256=pilot.sha(Path(__file__)), source_report_sha256=pilot.sha(root/'report.json'),
        review_filled_sha256=pilot.sha(root/'technical_review_filled.json'),
        review_result_sha256=pilot.sha(root/'technical_review_result.json'))
    pilot.save(root/'technical_review_summary.json', summary)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    print(json.dumps(run(parser.parse_args().root),ensure_ascii=False))
