"""Summarize frozen source/review/coverage artifacts, without DB or network."""
from datetime import datetime,timezone
import argparse
import json
from pathlib import Path
import statistics

from scripts.research import us_news_event_qualification as evidence
from scripts.research.us_news_financing_feasibility import read_pack


def lag_stats(values):
    return dict(count=len(values),min_hours=min(values) if values else None,
        median_hours=statistics.median(values) if values else None,max_hours=max(values) if values else None)


def run(pack,validation,feasibility,output):
    validated=json.loads((validation/'report.json').read_text(encoding='utf-8'))
    if validated['status']!='VALIDATED_COLLECTION_ONLY':
        raise ValueError('Collection validation not successful')
    prep=json.loads((pack/'preparation_report.json').read_text(encoding='utf-8'))
    if (prep['validation_sha256']!=evidence.sha(validation/'report.json') or
            prep['run_id']!=validated['run_id'] or not prep['partition_manifest']['exhaustive']):
        raise ValueError('Validation/partition lineage mismatch')
    full=pack/'full'
    full_report=json.loads((full/'report.json').read_text(encoding='utf-8'))
    for name,expected in full_report['files'].items():
        if evidence.sha(full/name)!=expected:
            raise ValueError('Changed full source pack')
    protocol,source,selected,review=read_pack(pack/'bounded_review')
    if protocol['parent_report_sha256']!=evidence.sha(full/'report.json'):
        raise ValueError('Changed parent report')
    coverage=json.loads((feasibility/'report.json').read_text(encoding='utf-8'))
    for path,expected in coverage['source_hashes'].items():
        if evidence.sha(path)!=expected:
            raise ValueError('Changed coverage source')
    for name,expected in coverage['files'].items():
        if evidence.sha(feasibility/name)!=expected:
            raise ValueError('Changed coverage result')
    items=json.loads((full/'evidence.json').read_text(encoding='utf-8'))
    eligible=[r for r in items if not r['temporal_reservations']]
    first_association={}
    for item in eligible:
        lag=(max(evidence.utc(item['text_available_at']),evidence.utc(item['mapping_available_at']))-
             evidence.utc(item['publication_utc'])).total_seconds()/3600
        first_association[item['article_id']]=min(first_association.get(item['article_id'],lag),lag)
    sample_lags=[(max(evidence.utc(r['text_available_at']),evidence.utc(r['mapping_available_at']))-
                 evidence.utc(r['publication_utc'])).total_seconds()/3600 for r in selected]
    result=dict(status='COLLECTION_VALIDATED_REVIEW_BOUNDED_FEASIBILITY_BLOCKED',
        created_at_utc=datetime.now(timezone.utc),run_id=validated['run_id'],
        cutoff_utc=prep['cutoff_utc'],publication_since_utc=prep['since_utc'],
        collection_status=validated['status'],successful_cycle_checkpoints=validated['scoped_successful_cycle_checkpoints'],
        archive_articles=full_report['article_ids'],archive_article_symbol_pairs=len(items),
        eligible_article_symbol_pairs=len(eligible),eligible_distinct_articles=len(first_association),
        eligible_screened_pairs=prep['eligible_screened_pairs'],
        reviewed_pairs=len(review['results']),reviewed_distinct_articles=len({r['article_id'] for r in selected}),
        qualified_new_primary_equity_events=sum(r['status']=='QUALIFIED_RESEARCH_EVENT' for r in review['results']),
        technical_window_counts=coverage['technical_window_counts'],
        windows_ended_before_evidence_available=coverage['windows_ended_before_evidence_available'],
        lag_hours_eligible_articles_first_qualified_association=lag_stats(list(first_association.values())),
        lag_hours_reviewed_pairs=lag_stats(sample_lags),
        daily_ingestion_configured=coverage['collection_configuration']['separate_daily_ingestion_configured'],
        daily_sentiment_scoring_demonstrated=False,blockers=coverage['blockers'],
        no_event_absence_claim_on_unreviewed_corpus=True,independent_review_certified=False,
        source_hashes={str(p):evidence.sha(p) for p in (validation/'report.json',pack/'preparation_report.json',
            full/'report.json',pack/'bounded_review/technical_review_summary.json',feasibility/'report.json')},
        sql_writes=False,api_calls=0,llm_calls=0,training=False,returns_computed=False,economic_test=False,
        code_sha256=evidence.sha(Path(__file__)))
    evidence.save(output,result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pack','validation','feasibility','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    result=run(args.pack,args.validation,args.feasibility,args.output)
    print(json.dumps(evidence.archive.json_value(result),ensure_ascii=False))
