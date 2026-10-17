"""Version the user's TP15/SL7 amendment without altering frozen TP10/SL10.

Reuse only verified observable populations and input inventory, never old
economic outcomes. No labels, fitting, SQL, API, broker or replay is invoked.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from scripts.research import us_oracle_path_profit_filter_protocol as original


SPEC = Path('config/research/oracle_path_profit_filter_tp15_sl7.json')
PARENT = Path('artifacts/research/us_oracle_path_profit_filter/20261015-protocol-v1')
EXPERIMENT = 'ORACLE_PATH_CONDITIONAL_LONG_PROFIT_TP15_SL7'
COMPARISON_AMENDMENT = dict(
    protection_source='target_in_this_protocol_not_parent_replay_protections',
    source_replay_used_as='data_calendar_native_guards_and_cost_template_only',
    fresh_all_long_control_required=True, reuse_parent_economic_results=False,
    risk_budget_pct_before_native_guards=.028)


def resolve_spec(path=SPEC):
    change = original.read(path)
    if set(change) != {'extends', 'experiment', 'amendment', 'target_overrides', 'comparison_amendment'}:
        raise ValueError('Only the explicit TP15/SL7 amendment is permitted')
    if Path(change['extends']) != original.SPEC or change['experiment'] != EXPERIMENT:
        raise ValueError('Wrong parent or amended experiment')
    if change['target_overrides'] != {'take_profit_pct': .15, 'stop_loss_pct': .07}:
        raise ValueError('This amendment requires exactly TP15/SL7')
    if change['comparison_amendment'] != COMPARISON_AMENDMENT:
        raise ValueError('A fresh matched TP15/SL7 control is required')
    result = deepcopy(original.read(original.SPEC))
    result['experiment'] = EXPERIMENT
    result['target'].update(change['target_overrides'])
    result['future_portfolio_comparison'].update(change['comparison_amendment'])
    return result


def prepare(output, spec_path=SPEC):
    output = Path(output)
    spec_path = Path(spec_path)
    if output.resolve() == PARENT.resolve():
        raise ValueError('Never overwrite the TP10/SL10 preparation')
    marker = output/'report.json'
    if marker.exists():
        report = original.read(marker)
        if report['experiment'] != EXPERIMENT:
            raise ValueError('Wrong output experiment')
        manifest = original.read(output/'manifest.json')
        if manifest['spec_path'] != str(spec_path):
            raise ValueError('Changed amendment path; use a fresh output')
        for name, expected in report['files'].items():
            original.require_hash(output/name, expected)
        for name, expected in manifest['sources'].items():
            original.require_hash(name, expected)
        return report
    if (output/'manifest.json').exists():
        raise ValueError('Incomplete amendment; use a fresh output')
    spec = resolve_spec(spec_path)
    previous = original.read(PARENT/'report.json')
    if previous['status'] != 'PREPARED_NOT_TRAINED' or any(previous[k] != 0 for k in ('model_fits', 'labels_computed', 'portfolio_runs')):
        raise ValueError('Expected untouched pre-label/pre-training preparation')
    old_manifest = original.read(PARENT/'manifest.json')
    sources = dict(old_manifest['sources'])
    sources[str(PARENT/'report.json')] = original.digest(PARENT/'report.json')
    for name, expected in previous['files'].items():
        sources[str(PARENT/name)] = expected
    for name, expected in sources.items():
        original.require_hash(name, expected)
    if original.read(PARENT/'protocol.json') != original.read(original.SPEC):
        raise ValueError('Frozen parent specification changed')
    for path in [spec_path, Path(__file__), Path('tests/test_us_oracle_path_profit_filter_tp15_sl7_protocol.py')]:
        sources[str(path)] = original.digest(path)
    inventory = {k:v for k,v in previous['inventory'].items() if k != 'old_TOP5_60_session_outcomes_reused_as_TP10SL10'}
    inventory.update(target_take_profit_pct=.15, target_stop_loss_pct=.07,
        historical_top20_path=str(PARENT/'historical-top20.parquet'),
        parent_outcomes_or_economic_results_reused=False,
        TP15_SL7_native_label_parity_verified=False, TP15_SL7_baseline_computed=False)
    nondup = original.read(PARENT/'non-duplication.json')
    nondup.update(active_experiment=EXPERIMENT,
        user_amendment='TP15/SL7 chosen before labels/fit/replay; all other learner/features/splits/gates unchanged',
        old_TP10_SL10_results_are_new_baseline=False)
    output.mkdir(parents=True, exist_ok=True)
    original.atomic_json(output/'protocol.json', spec)
    original.atomic_json(output/'readiness.json', inventory)
    original.atomic_json(output/'non-duplication.json', nondup)
    original.atomic_json(output/'manifest.json', dict(spec_path=str(spec_path),
        parent_preparation=str(PARENT), sources=sources, parent_modified=False,
        candidate_population_reused=True, economic_outcomes_reused=False))
    report = dict(status='PREPARED_NOT_TRAINED', experiment=EXPERIMENT,
        verdict='TP15_SL7_AMENDMENT_FROZEN_BEFORE_LABELS_OR_FIT',
        take_profit_pct=.15, stop_loss_pct=.07, inventory=inventory,
        remaining_before_fit=['J-only TOP20 features and prefix checks',
            'native isolated TP15SL7 labels, costs and financing parity',
            'J22 availability, purge and coverage checks',
            'new explicit GO before label implementation or fitting'],
        future_replay_requires_fresh_TP15_SL7_unfiltered_baseline=True,
        model_fits=0, labels_computed=0, portfolio_runs=0, sql_reads=0, sql_writes=0,
        API_calls=0, broker_calls=0, live_changes=False, statistical_gain_measured=False,
        files={name:original.digest(output/name) for name in (
            'protocol.json', 'readiness.json', 'non-duplication.json', 'manifest.json')})
    for name, expected in sources.items():
        original.require_hash(name, expected)
    original.atomic_json(marker, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--spec', type=Path, default=SPEC)
    args = parser.parse_args()
    with original.exclusive_run(args.output):
        report = prepare(args.output, args.spec)
        print(json.dumps({k:v for k,v in report.items() if k not in ('files', 'inventory')}, ensure_ascii=False))
