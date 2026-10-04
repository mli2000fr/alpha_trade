"""Fixed development-only FR sensitivity replay. No SQL, network or fitting."""
import argparse
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd

from service.fr.economic_decision_13c import attribution
from service.fr.execution_costs import load_cost_profile
from service.fr.exploitable_scope_12e import sha
from service.fr.provider_exploratory_13b import load_frozen, write_json
from service.fr.provider_exploratory_metrics_13b import ledger_metrics
from service.fr.robustness_engine_13d import ReplayBlocked, replay_assumed


VARIANTS = {
    'baseline': {'delay_sessions': 0, 'position_cap_pct': None},
    'delay_1': {'delay_sessions': 1, 'position_cap_pct': None},
    'cap_10pct': {'delay_sessions': 0, 'position_cap_pct': '0.10'},
    'delay_1_cap_10pct': {'delay_sessions': 1, 'position_cap_pct': '0.10'},
}


def delayed_tape(tape, delay):
    """Retain original ranks, information and H5 endpoint; no fresh signals."""
    if type(delay) is not int or delay not in (0, 1):
        raise ValueError('Fixed delay 0/1 required')
    out = deepcopy(tape)
    if not delay:
        return out
    if tape['horizon'] <= delay:
        raise ValueError('Delay must precede original exit')
    out['horizon'] -= delay
    for candidate in out['candidates']:
        original = candidate['session']
        index = tape['sessions'].index(original)
        if index + tape['horizon'] >= len(tape['sessions']):
            raise ValueError('Original exit outside tape')
        shifted = tape['sessions'][index + delay]
        candidate['original_signal_session'] = original
        candidate['session'] = shifted
        out['decision_at'][shifted] = tape['decision_at'][original]
    return out


def run(source, output):
    source = Path(source)
    report = json.loads((source/'report.json').read_text(encoding='utf-8'))
    protocol = json.loads((source/'protocol.json').read_text(encoding='utf-8'))
    for name, digest in report['output_hashes'].items():
        if sha(source/name) != digest:
            raise ValueError(f'Archived output changed: {name}')
    for name, digest in protocol['local_hashes'].items():
        if sha(Path(name)) != digest:
            raise ValueError(f'Archived implementation/input changed: {name}')
    if report['blocked_cells'] or len(report['cells']) != 24 or report['confirmation_2026_evaluated']:
        raise ValueError('Complete fixed development required')
    config = protocol['config']
    cfg, scores, intents, _ = load_frozen(config)
    tax = pd.read_parquet(config['tax_review'])
    known = {f'{r.symbol}/{r.year}': True for r in tax.itertuples() if r.status.startswith('POSITIVE_')}
    costs = load_cost_profile(Path(config['cost_profile']))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    prereg = {
        'variants': VARIANTS, 'source': str(source), 'source_report_sha256': sha(source/'report.json'),
        'source_protocol_sha256': sha(source/'protocol.json'),
        'implementation_hashes': {str(p): sha(p) for p in (Path(__file__), Path('service/fr/robustness_engine_13d.py'))},
        'exit_convention': 'Original signal H5 close retained: delayed holding horizon = 4 sessions',
        'cap_convention': 'Entry all-in budget <= 10% opening marked equity; no forced post-entry rebalance',
        'information_convention': 'Original ranks/available_at; no re-ranking or confirmation at delayed entry',
        'post_observation_sensitivity_not_independent_validation': True,
        'confirmation_2026_evaluated': False, 'canonical_writes': False, 'serving_enabled': False,
        'decision_rule': 'No GO: development sensitivities cannot satisfy strict evidence gates; no best variant selected',
        'planned_cells': 96,
    }
    write_json(output/'protocol.json', prereg)  # Before the first economic replay.
    records = []
    for fold in cfg['folds']:
        shared = json.loads((source/f'fold-{fold}-supplier-shared.json').read_text(encoding='utf-8'))
        if any(d > '2025-12-31' for d in shared['sessions']):
            raise ValueError('Confirmation reserved')
        available = scores[scores.fold.eq(fold)].set_index(['decision_session_date','research_uid']).max_input_available_at
        for policy in cfg['policies']:
            selected = intents[intents.fold.eq(fold)&intents.policy.eq(policy)]
            tape = dict(shared)
            tape['candidates'] = [{'session': r.decision_session_date, 'uid': r.research_uid,
                'rank': int(r.candidate_rank), 'available_at': available.loc[(r.decision_session_date,r.research_uid)]}
                for r in selected.itertuples()]
            for variant, settings in VARIANTS.items():
                transformed = delayed_tape(tape, settings['delay_sessions'])
                for tax_name in config['tax_scenarios']:
                    for cost_name, multiplier in config['cost_scenarios'].items():
                        cell = {'fold': fold, 'policy': policy, 'variant': variant,
                            'tax_scenario': tax_name, 'cost_scenario': cost_name}
                        name = f'{fold}-{policy}-{variant}-{tax_name}-{cost_name}'
                        try:
                            result = replay_assumed(transformed, costs,
                                {'known_positive': known, 'unknown_liable': tax_name == 'unknown_taxed'},
                                stress_multiplier=Decimal(str(multiplier)), position_cap_pct=settings['position_cap_pct'])
                            metrics = ledger_metrics(result, data_kind='EXPLORATORY_PROVIDER_ASSUMED')
                            if variant == 'baseline':
                                old = next(c for c in report['cells'] if all(c[k] == cell[k]
                                    for k in ('fold','policy','tax_scenario','cost_scenario')))
                                if metrics != old['metrics']:
                                    raise ValueError('Baseline regression: exact metrics differ')
                            cell.update(status=result['status'], metrics=metrics,
                                attribution=attribution(result, shared['instruments']))
                        except ReplayBlocked as exc:
                            result = {'status': 'BLOCKED_EXPLORATORY_CELL', 'reason': str(exc), 'ledger': exc.ledger}
                            cell.update(status=result['status'], metrics=None, reason=str(exc))
                        write_json(output/f'{name}-ledger.json', result)
                        records.append(cell)
                        write_json(output/'progress.json', {'completed_cells': len(records), 'planned_cells': 96, 'last_cell': cell})
                        print(f'{len(records)}/96 {name}: {cell["status"]}', flush=True)
    comparisons = []
    for oracle in [c for c in records if c['policy'] == 'oracle_top20_long' and c['metrics']]:
        for reference in ('atr_top20_long','uniform_control_long'):
            other = next(c for c in records if c['policy'] == reference and all(c[k] == oracle[k]
                for k in ('fold','variant','tax_scenario','cost_scenario')))
            comparisons.append({k: oracle[k] for k in ('fold','variant','tax_scenario','cost_scenario')} | {
                'reference': reference, 'delta_return_pp': oracle['metrics']['net_return_pct']-other['metrics']['net_return_pct'] if other['metrics'] else None})
    final = {'status': 'COMPLETED_EXPLORATORY_SENSITIVITY', 'cells': records, 'paired_comparisons': comparisons,
        'blocked_cells': sum(c['metrics'] is None for c in records), 'baseline_exact_reproduction_cells': 24,
        'economic_go_allowed': False, 'serving_enabled': False, 'canonical_writes': False,
        'confirmation_2026_evaluated': False, 'best_variant_selected': False,
        'strict_sprint13_complete': False, 'protocol_sha256': sha(output/'protocol.json')}
    final['decision'] = 'NO_GO_PROMOTION_DEVELOPMENT_SENSITIVITY_ONLY'
    final['positive_both_folds'] = {
        variant: all(c['metrics'] is not None and c['metrics']['net_return_pct'] > 0
            for c in records if c['policy'] == 'oracle_top20_long' and c['variant'] == variant)
        for variant in VARIANTS}
    final['output_hashes'] = {p.name: sha(p) for p in output.glob('*.json') if p.name != 'report.json'}
    write_json(output/'report.json', final)
    return final


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(run(args.source, args.output)['status'])
