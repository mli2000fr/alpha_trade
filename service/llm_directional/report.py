"""Read-only audit views: scores are subjective, never shown as probabilities."""
import argparse
import json
from sqlalchemy import select
from .repository import Repository, evaluations, dumps
from .config import FilterConfig


def report(engine, run_id):
    run, items = Repository(engine).get(run_id)
    config = FilterConfig(**json.loads(run['config_json']))
    from .prompts import native_search_protocol
    native=config.provider=='deepseek' and native_search_protocol(run['protocol_version'])
    web_provider=('deepseek' if native else 'openai') if config.analysis_mode=='web_search' else None
    rows = []
    contexts={c['symbol']:c for c in json.loads(run['input_json']).get('candidates',[])}
    for item in items:
        parsed = json.loads(item['assessment_json'] or '{}')
        rows.append({'symbol': item['symbol'], 'oracle_rank': item['oracle_rank'],
            'oracle_score_amplitude': item['oracle_score'], 'status': item['status'],
            'decision': parsed.get('decision'), 'confidence_uncalibrated': parsed.get('confidence'),
            'direction_score': parsed.get('direction_score'),
            'direction_score_policy': parsed.get('direction_score_policy'),
            'eligible': parsed.get('eligible', False), 'selected': item['selected'],
            'assessment_outcome': parsed.get('assessment_outcome'),
            'fresh_source_count': parsed.get('fresh_source_count'),
            'selection_blockers': parsed.get('selection_blockers', []),
            'source_qualifications': parsed.get('source_qualifications', []),
            'excluded_sources': parsed.get('excluded_sources', []),
            'bull_case': parsed.get('bull_case'), 'bear_case': parsed.get('bear_case'),
            'sources': parsed.get('sources', []), 'error': item['error_message']})
        rows[-1].update(consensus_analysis=parsed.get('consensus_analysis'),
            context_analysis=parsed.get('context_analysis'),
            evidence_cutoff_utc=contexts.get(item['symbol'],{}).get('evidence_cutoff_utc'),
            local_data_status=contexts.get(item['symbol'],{}).get('local_data_status',{}),
            freshness_policy=contexts.get(item['symbol'],{}).get('freshness_policy',{}),
            local_evidence=parsed.get('local_evidence',[]),
            local_source_qualifications=parsed.get('local_source_qualifications',[]),
            fresh_local_source_count=parsed.get('fresh_local_source_count',0))
    with engine.connect() as conn:
        realized = [dict(row) for row in conn.execute(select(evaluations).where(
            evaluations.c.run_id == run_id)).mappings()]
    for row in realized:
        decision = next((r['decision'] for r in rows if r['symbol'] == row['symbol']), None)
        row['directional_gross_return_pct'] = (-row['return_pct'] if decision == 'SHORT'
                                               else row['return_pct'] if decision == 'LONG' else None)
    return {'run_id': run_id, 'trade_date': str(run['trade_date']), 'batch_id': run['batch_id'],
            'provider': config.provider, 'provider_label': config.provider_label,
            'analysis_model': config.analysis_model,'analysis_mode':config.analysis_mode,
            'web_provider': web_provider,
            'web_model': ('Search / Fetch API' if native else config.model) if web_provider else None,
            'research_only': json.loads(run['input_json']).get('research_only', False),
            'parent_run_id': json.loads(run['input_json']).get('parent_run_id'),
            'status': run['status'], 'started_at_utc': str(run['started_at']),
            'completed_at_utc': str(run['completed_at']), 'risk_run_id': run['risk_run_id'],
            'execution_started_at_utc': str(run['execution_started_at']),
            'configuration': json.loads(run['config_json']), 'candidates': rows,
            'evaluations': realized, 'error': run['error_message'],
            'warning': 'Notes subjectives non calibrées. Sources datées par le LLM, non certifiées PIT. PAPER uniquement.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    from database.connection import get_sqlalchemy_engine
    print(dumps(report(get_sqlalchemy_engine(), args.run_id)))


if __name__ == '__main__':
    main()
