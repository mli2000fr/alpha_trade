"""Explicit, bounded rerun of archived directional candidates; never tradable.

No Oracle prediction, risk process or broker order is launched. Fresh API answers
are appended to the usual audit tables under a research-only run identifier.
"""
import argparse
import json
import logging
import math
from pathlib import Path

from .config import FilterConfig
from .repository import Repository, digest, dumps
from .runner import analyze
from .validation import parse_response
from .report import report


def prepare_subset(engine, parent_run_id, expected_symbols):
    parent, items = Repository(engine).get(parent_run_id)
    snapshot = json.loads(parent['input_json'])
    if parent['status'] != 'COMPLETED' or digest(snapshot) != parent['input_sha256']:
        raise ValueError('Analyse parent non finalisée ou snapshot altéré')
    contexts = {c['symbol']: c for c in snapshot['candidates']}
    if len(contexts) != len(items) or {i['symbol'] for i in items} != set(contexts):
        raise ValueError('Analyse parent incomplète')
    chosen, baseline = [], []
    config = FilterConfig(**json.loads(parent['config_json']))
    for item in items:
        raw = json.loads(item['response_json'] or 'null')
        if item['status'] != 'VALID' or digest(raw) != item['response_sha256']:
            raise ValueError('Réponse parent invalide ou altérée')
        previous = json.loads(item['assessment_json'])
        # Eligibility is deliberately NOT used to choose this diagnostic subset.
        if previous['decision'] not in ('LONG', 'SHORT'):
            continue
        context = contexts[item['symbol']]
        # MySQL FLOAT through the text protocol may expose six significant
        # digits. Hashed JSON remains authoritative; never use the rounded
        # column to construct the new request or change the original ranking.
        if (context['oracle_rank'] != item['oracle_rank'] or not math.isclose(
                context['oracle_score'], item['oracle_score'], rel_tol=0, abs_tol=5e-7)):
            raise ValueError('Classement parent altéré')
        request=json.loads(item['request_json'])
        requested_context=request.get('context') if request.get('provider')=='deepseek' else json.loads(request['input'])
        if requested_context != context:
            raise ValueError('Requête parent incompatible avec le snapshot')
        revised = parse_response(raw, item['symbol'], config, item['observed_at'],context=context)
        chosen.append(context)  # Never feed the previous verdict to the new model.
        baseline.append({'symbol': item['symbol'], 'oracle_rank': item['oracle_rank'],
            'original_decision': previous['decision'], 'original_confidence': previous['confidence'],
            'original_eligible': previous['eligible'],
            'requalified_eligible': revised['eligible'],
            'requalified_fresh_source_count': revised['fresh_source_count'],
            'requalified_selection_blockers': revised['selection_blockers']})
    if (not expected_symbols or len(set(expected_symbols)) != len(expected_symbols)
            or {c['symbol'] for c in chosen} != set(expected_symbols)):
        raise ValueError('Sous-ensemble différent des symboles explicitement autorisés')
    chosen.sort(key=lambda c: c['oracle_rank'])
    return parent, snapshot, config, chosen, baseline


def rerun(*, engine, parent_run_id, expected_symbols, run_id, output_dir, client=None):
    parent, snapshot, config, chosen, baseline = prepare_subset(
        engine, parent_run_id, expected_symbols)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'baseline.json').write_text(dumps({'parent_run_id': parent_run_id,
        'parent_input_sha256': parent['input_sha256'], 'research_only': True,
        'candidates': baseline}), encoding='utf-8')
    summary = analyze(engine=engine, batch_id=parent['batch_id'], trade_date=parent['trade_date'],
        symbol_source=snapshot['symbol_source'], capital_preset_key=snapshot['capital_preset_key'],
        config=config, run_id=run_id, inputs=chosen, client=client,
        research_parent_run_id=parent_run_id)
    view = report(engine, run_id)
    before = {b['symbol']: b for b in baseline}
    for row in view['candidates']:
        row['previous'] = before[row['symbol']]
    view['summary'] = summary
    view['warning'] += ' Sous-ensemble choisi après la première réponse : diagnostic, pas validation de performance.'
    (output / 'report.json').write_text(dumps(view), encoding='utf-8')
    return view


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-run-id', required=True)
    parser.add_argument('--symbols', required=True, help='Exact authorized symbol list, comma-separated')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(output / 'run.log', encoding='utf-8')])
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    try:
        view = rerun(engine=engine, parent_run_id=args.parent_run_id,
            expected_symbols=args.symbols.split(','), run_id=args.run_id, output_dir=output)
        logging.info('Research rerun complete run=%s selected_for_research=%s',
                     args.run_id, view['summary']['selected'])
    except Exception:
        logging.exception('Research rerun failed run=%s; no automatic retry', args.run_id)
        raise
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
