"""Read-only audit views: scores are subjective, never shown as probabilities."""
import argparse
import json
from sqlalchemy import select
from .repository import Repository, evaluations, dumps


def report(engine, run_id):
    run, items = Repository(engine).get(run_id)
    rows = []
    for item in items:
        parsed = json.loads(item['assessment_json'] or '{}')
        rows.append({'symbol': item['symbol'], 'oracle_rank': item['oracle_rank'],
            'oracle_score_amplitude': item['oracle_score'], 'status': item['status'],
            'decision': parsed.get('decision'), 'confidence_uncalibrated': parsed.get('confidence'),
            'eligible': parsed.get('eligible', False), 'selected': item['selected'],
            'bull_case': parsed.get('bull_case'), 'bear_case': parsed.get('bear_case'),
            'sources': parsed.get('sources', []), 'error': item['error_message']})
    with engine.connect() as conn:
        realized = [dict(row) for row in conn.execute(select(evaluations).where(
            evaluations.c.run_id == run_id)).mappings()]
    for row in realized:
        decision = next((r['decision'] for r in rows if r['symbol'] == row['symbol']), None)
        row['directional_gross_return_pct'] = (-row['return_pct'] if decision == 'SHORT'
                                               else row['return_pct'] if decision == 'LONG' else None)
    return {'run_id': run_id, 'trade_date': str(run['trade_date']), 'batch_id': run['batch_id'],
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
