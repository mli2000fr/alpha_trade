"""Local readout of frozen results: all clock buckets, no retuning or SQL."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from scripts.research import us_news_price_descriptive_20261016 as pilot
from scripts.research import us_news_event_qualification as evidence


def run(experiment):
    root=experiment/'results'
    report=pilot.read(root/'report.json')
    for name,sha in report['files'].items():
        if Path(name).name!=name or evidence.sha(root/name)!=sha:
            raise ValueError('Result input changed')
    rows=pilot.read(root/'cases.json')
    groups={anchor:{bucket:pilot.summary([r for r in rows if r['plan'].get('bucket')==bucket],anchor)
        for bucket in ('regular_session','outside_regular_session')} for anchor in ('publication','receipt')}
    result=dict(status='DESCRIPTIVE_CLOCK_READOUT_NOT_A_STRATEGY',created_at_utc=datetime.now(timezone.utc),
        clock_stratification_requested_after_initial_results=True,
        cohorts_labels_thresholds_or_returns_changed=False,not_validation_of_a_clock_filter=True,
        all_prespecified_clock_buckets_displayed=True,groups=groups,
        complete_publication_windows_ended_before_receipt=sum(r['anchor']=='publication'
            and r['metrics'] is not None and r['publication_window_ended_before_receipt'] for r in rows),
        case_rows=[{k:r[k] for k in ('symbol','tone','publication_ny_date','metrics','legacy_keyword_control')}
            | {'clock_bucket':r['plan'].get('bucket'),'article_id':r['article_id']}
            for r in rows if r['anchor']=='publication' and r['metrics'] is not None],
        report_sha256=evidence.sha(root/'report.json'),no_new_prices=True,
        sql_access=False,api_calls=0,training=False,economic_test=False)
    evidence.save(experiment/'clock_readout.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',type=Path,required=True)
    result=run(parser.parse_args().experiment)
    print(json.dumps(evidence.archive.json_value(result['groups']['publication']),ensure_ascii=False))
