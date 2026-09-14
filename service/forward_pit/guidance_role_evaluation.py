"""Evaluate a manually annotated frozen research queue, without fitting rules."""
import argparse
import hashlib
import json
from pathlib import Path


def evaluate(rows, labels):
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
    return {'candidates': len(rows), 'confusion_reference_to_prediction': confusion,
        'classified': classified, 'abstained': len(rows) - classified,
        'classified_precision': correct / classified if classified else None,
        'classification_coverage': classified / len(rows) if rows else None,
        'new_forecast_coverage_within_detected_candidates':
            confusion.get('NEW_FORECAST', {}).get('NEW_FORECAST', 0) / forecasts if forecasts else None,
        'limitations': ['Assistant review, not independent human adjudication',
            'Only already detected dollar ranges; no full-document extraction recall',
            'Repeated ranges and eight publications are not independent observations',
            'No prior-forecast or realized-result support if absent in reference',
            'No financial returns, no predictive validation']}


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
    report = evaluate(rows, labels)
    report['queue_sha256'] = reference['queue_sha256']
    report['status'] = 'INSUFFICIENT_TABLE_COVERAGE_AND_MISSING_CLASS_SUPPORT'
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
