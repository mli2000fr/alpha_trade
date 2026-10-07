"""Evaluate a manually annotated frozen research queue, without fitting rules."""
import argparse
import hashlib
import json
from pathlib import Path


def evaluate(rows, labels, known_missed=None):
    if len(labels) != len(rows):
        raise ValueError('Every candidate needs one reference label')
    confusion = {}
    classified = correct = forecasts = 0
    for row, truth in zip(rows, labels):
        if truth not in ['NEW_FORECAST', 'PRIOR_FORECAST', 'REALIZED_RESULT', 'NOT_A_RANGE', 'AMBIGUOUS']:
            raise ValueError('Unknown reference label')
        prediction = row['range_role']['role']
        confusion.setdefault(truth, {})[prediction] = confusion.setdefault(truth, {}).get(prediction, 0) + 1
        forecasts += truth == 'NEW_FORECAST'
        if prediction != 'AMBIGUOUS':
            classified += 1
            correct += prediction == truth
    role_metrics = {}
    for truth, predictions in confusion.items():
        support = sum(predictions.values())
        role_metrics[truth] = {'support': support,
            'coverage': (support - predictions.get('AMBIGUOUS', 0)) / support if support else None,
            'correct': predictions.get(truth, 0),
            'recall': predictions.get(truth, 0) / support if support else None}
    publications = {(r.get('source', {}).get('cik'), r.get('source', {}).get('accession')) for r in rows}
    missed_audited = known_missed is not None
    known_missed = known_missed or {}
    missed_count = int(known_missed.get('count', 0))
    missed_role = known_missed.get('role')
    detected_true = sum(label not in ['NOT_A_RANGE', 'AMBIGUOUS'] for label in labels)
    result = {'candidates': len(rows), 'unique_publications': len(publications),
        'confusion_reference_to_prediction': confusion, 'role_metrics': role_metrics,
        'classified': classified, 'abstained': len(rows) - classified,
        'classified_precision': correct / classified if classified else None,
        'classification_coverage': classified / len(rows) if rows else None,
        'new_forecast_coverage_within_detected_candidates':
            confusion.get('NEW_FORECAST', {}).get('NEW_FORECAST', 0) / forecasts if forecasts else None,
        'audited_true_range_detection': {
            'detected': detected_true,
            'known_missed': missed_count if missed_audited else None,
            'recall': detected_true / (detected_true + missed_count)
                if missed_audited and detected_true + missed_count else None},
        'limitations': ['Assistant review, not independent human adjudication',
            'Only already detected dollar ranges; no full-document extraction recall',
            'Repeated ranges within publications are not independent observations',
            'A role with absent or small support is not validated',
            'No financial returns, no predictive validation']}
    if missed_role == 'NEW_FORECAST':
        support = confusion.get('NEW_FORECAST', {})
        result['new_forecast_end_to_end_recall'] = (
            support.get('NEW_FORECAST', 0)
            / (sum(support.values()) + missed_count)
            if sum(support.values()) + missed_count else None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    body = args.queue.read_bytes()
    reference = json.loads(args.reference.read_text(encoding='utf-8'))
    if hashlib.sha256(body).hexdigest() != reference['queue_sha256']:
        raise ValueError('Reference does not match frozen queue')
    rows = json.loads(body)
    labels = [reference['default_role']] * len(rows)
    for index in reference['not_a_range_indices']:
        labels[index] = 'NOT_A_RANGE'
    for role, indices in reference.get('roles_by_index', {}).items():
        for index in indices:
            labels[index] = role
    missed = reference.get('known_true_ranges_missed_by_detector')
    report = evaluate(rows, labels, missed)
    report['queue_sha256'] = reference['queue_sha256']
    gates = reference.get('gates', {})
    failures = []
    if gates:
        if report['classified_precision'] < gates['classified_precision_min']:
            failures.append('CLASSIFIED_PRECISION')
        if report['role_metrics'].get('NEW_FORECAST', {}).get('coverage', 0) < gates['new_forecast_coverage_min']:
            failures.append('NEW_FORECAST_COVERAGE')
        false_accepted = sum(v for role, v in report['confusion_reference_to_prediction'].get('NOT_A_RANGE', {}).items() if role != 'AMBIGUOUS')
        if false_accepted > gates['false_intervals_accepted_max']:
            failures.append('FALSE_INTERVAL_ACCEPTED')
    report['gate_failures'] = failures
    report['status'] = 'FAIL' if failures else 'NO_GATES_OR_PASS_REQUIRES_CLASS_SUPPORT_REVIEW'
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
