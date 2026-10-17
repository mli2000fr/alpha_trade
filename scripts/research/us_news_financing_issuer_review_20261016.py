"""Fixed technical reading of two actual Iambic IPO texts, not a classifier.

Annotations written after reading the frozen texts. Never approves an issuer,
event novelty, independence or trade. Unknown texts are refused, not inferred.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json

from scripts.research import us_news_event_qualification as evidence

NOTES={
    'eodhd:4dfb14c73131447372f692b6': (
        'Iambic Therapeutics Inc. shares soared 16% in its trading debut after the clinical-stage '
        'cancer drugmaker and technology firm raised $150 million in a US initial public offering.',
        'The company trades on the Nasdaq Global Select Market under the symbol IAM.'),
    'eodhd:b3883986f16118c2d6c488e1': (
        'Late Wednesday, the San Diego-based AI-driven drug discovery firm priced the offering '
        'of roughly 9.4M shares at $16.00, targeting about $150M in gross proceeds.',
        'Iambic Therapeutics (IAM [https://seekingalpha.com/symbol/IAM])'),
}


def annotations(items,now):
    selected=[r for r in items if r['screened']]
    if len(selected)>20 or {r['article_id'] for r in selected}!=set(NOTES):
        raise ValueError('This technical reading belongs to exactly the two frozen IPO texts')
    reviews=[]
    for item in selected:
        if item['symbol'] not in {'ABBV','NVDA','TAK'}:
            raise ValueError('Unknown mapped symbol, requires a new reading')
        quotes=[]
        for quote in NOTES[item['article_id']]:
            start=item['fields']['content'].index(quote)
            quotes.append(dict(field='content',start=start,end=start+len(quote),text=quote))
        reviews.append(dict(evidence_key=item['evidence_key'],reviewer='Codex technical reading; NOT independent human review',
            reviewed_at_utc=now.isoformat(),issuer_name='Iambic Therapeutics, Inc. (IAM)',
            identity_verified=False,event_type='PRIMARY_EQUITY_FINANCING',
            new_announcement_verified=None,prior_comparison_complete=False,
            novelty_evidence='No prior-announcement/syndication comparison certified; issuer mismatch already blocks this pair.',
            quotes=quotes,facts=[],notes='IPO issuer is IAM, not the mapped partner/investor '+item['symbol']+
            '. No direct dilution of this mapped issuer is evidenced by this text. '
            'Do not infer direction for partners, or treat two articles about one IPO as independent events.',
            full_archived_body_read=True))
    return reviews


def run(root):
    report=json.loads((root/'report.json').read_text(encoding='utf-8'))
    for name,expected in report['files'].items():
        if Path(name).name!=name or evidence.sha(root/name)!=expected:
            raise ValueError('Changed evidence pack')
    items=json.loads((root/'evidence.json').read_text(encoding='utf-8'))
    rows=annotations(items,datetime.now(timezone.utc))
    evidence.save(root/'technical_review_filled.json',rows)
    result=evidence.review_pack(root,root/'technical_review_filled.json',root/'technical_review_result.json')
    summary=dict(status='ISSUER_MISMATCH_RESERVED_NOT_A_DIRECTION_SIGNAL',reviewed_pairs=len(rows),
        distinct_texts_read=2,distinct_ipo_subjects_in_texts=1,
        qualified_events=sum(r['status']=='QUALIFIED_RESEARCH_EVENT' for r in result['results']),
        wrong_event_issuer_pairs=len(rows),independent_review_certified=False,
        unreviewed_pairs=len(items)-len(rows),event_absence_proven=False,
        api_calls=0,sql_writes=False,training=False,orders=False,
        source_report_sha256=evidence.sha(root/'report.json'),code_sha256=evidence.sha(Path(__file__)))
    evidence.save(root/'technical_review_summary.json',summary)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True)
    print(json.dumps(run(parser.parse_args().pack),ensure_ascii=False))
