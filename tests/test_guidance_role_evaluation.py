import pytest
from service.forward_pit.guidance_role_evaluation import evaluate


def test_abstention_does_not_become_correct_classification():
    rows = [{'range_role': {'role': r}} for r in ['NEW_FORECAST', 'AMBIGUOUS']]
    result = evaluate(rows, ['NEW_FORECAST', 'NEW_FORECAST'])
    assert result['classified_precision'] == 1
    assert result['new_forecast_coverage_within_detected_candidates'] == .5
    assert result['role_metrics']['NEW_FORECAST']['coverage'] == .5
    assert result['role_metrics']['NEW_FORECAST']['recall'] == .5
    assert result['unique_publications'] == 1


def test_incomplete_reference_rejected():
    with pytest.raises(ValueError):
        evaluate([{'range_role': {'role': 'AMBIGUOUS'}}], [])


def test_prior_forecast_is_measured_separately():
    rows = [{'range_role': {'role': 'PRIOR_FORECAST'}}]
    result = evaluate(rows, ['PRIOR_FORECAST'])
    assert result['confusion_reference_to_prediction']['PRIOR_FORECAST']['PRIOR_FORECAST'] == 1
    assert result['audited_true_range_detection']['recall'] is None


def test_known_missed_ranges_are_visible_in_detection_and_end_to_end_recall():
    rows = [{'range_role': {'role': 'NEW_FORECAST'}}]
    result = evaluate(rows, ['NEW_FORECAST'],
        {'count': 1, 'role': 'NEW_FORECAST'})
    assert result['audited_true_range_detection'] == {
        'detected': 1, 'known_missed': 1, 'recall': .5}
    assert result['new_forecast_end_to_end_recall'] == .5
