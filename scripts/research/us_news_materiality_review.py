"""Offline reconciliation of the bounded text feasibility audit; no SQL/API/prices."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.research.us_news_materiality_feasibility import audit_panel, raw_publication_reason
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest


def review(root):
    root=Path(root)
    report=json.loads((root/'report.json').read_text(encoding='utf-8'))
    protocol=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    for name,expected in report['hashes'].items():
        if digest(root/name)!=expected:
            raise ValueError('Changed audit artifact: '+name)
    source=Path(protocol['source'])
    if digest(source)!=protocol['candidate_sha256']:
        raise ValueError('Changed candidate archive')
    if report['price_outcomes_loaded'] or report['training'] or report['pnl'] or report['sql_writes']:
        raise ValueError('Audit-only scope violated')
    if report['truncations'] or report['query_errors']:
        raise ValueError('Incomplete metadata queries')
    news=pd.read_parquet(root/'news_metadata.parquet')
    saved=pd.read_parquet(root/'candidate_availability.parquet')
    candidates=pd.read_parquet(source,columns=['date','symbol','oracle_rank','year'])
    candidates['date']=pd.to_datetime(candidates.date).dt.normalize()
    candidates=candidates[candidates.date.dt.strftime('%Y-%m').isin(protocol['months'])]
    if len(saved)!=len(candidates):
        raise ValueError('Candidate coverage mismatch')
    closes=saved.drop_duplicates('date').set_index('date').cutoff_utc.to_dict()
    actual=audit_panel(candidates,news,closes)
    pd.testing.assert_frame_equal(actual.reset_index(drop=True),
        saved[actual.columns].reset_index(drop=True),check_dtype=False)
    if news.duplicated(['article_id','symbol']).any():
        raise ValueError('Duplicate article/ticker rows')
    # Confirm a known NYSE half-session, not a hard-coded 16:00 local close.
    if pd.Timestamp('2025-07-03') in closes:
        if closes[pd.Timestamp('2025-07-03')]!=pd.Timestamp('2025-07-03T17:00:00Z'):
            raise ValueError('Incorrect early close')
    samples=json.loads((root/'content_sample.json').read_text(encoding='utf-8'))
    manual=json.loads((root/'content_review.json').read_text(encoding='utf-8'))
    if set(manual['annotations'])!={x['article_id'] for x in samples}:
        raise ValueError('Content-review sample mismatch')
    if manual['sample_sha256']!=digest(root/'content_sample.json'):
        raise ValueError('Manual review refers to another sample')
    for row in samples:
        if row['changed_during_audit']:
            raise ValueError('Sample body changed during metadata read')
        if not row['excerpt_truncated'] and row['content_excerpt'] is not None:
            if hashlib.sha256(row['content_excerpt'].encode('utf-8')).hexdigest()!=row['content_sha256']:
                raise ValueError('Body excerpt hash mismatch')
    reasons=[raw_publication_reason(r.provider_publication,r.published_at_utc)
        for r in news.itertuples(index=False)]
    result=dict(status='ARTIFACTS_AVAILABILITY_PANEL_SAMPLE_HASHES_AND_CUTOFF_VERIFIED',
        report_sha256=digest(root/'report.json'),manual_review_sha256=digest(root/'content_review.json'),
        candidates=len(candidates),metadata_mappings=len(news),unique_articles=news.article_id.nunique(),
        original_timestamp_matches=sum(x is None for x in reasons),
        date_precision_reserved=sum(x is not None for x in reasons),
        sample_articles=len(samples),screened_sample_articles=sum(x['headline_screen'] for x in samples),
        recent_guarded_candidate_days=int(saved.recent_guarded_mappings.gt(0).sum()),
        last24h_guarded_candidate_days=int(saved.last_24h_guarded_mappings.gt(0).sum()),
        verdict=report['verdict'],financial_result_computed=False,
        independent_human_review=False,read_only_offline=True)
    atomic_json(root/'qualification_review.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    print(json.dumps(review(parser.parse_args().root),indent=2))
