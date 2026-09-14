import pytest
from service.forward_pit.guidance_role_evaluation import evaluate


def test_abstention_does_not_become_correct_classification():
    rows = [{'range_role': {'role': r}} for r in ['NEW_FORECAST', 'AMBIGUOUS']]
    result = evaluate(rows, ['NEW_FORECAST', 'NEW_FORECAST'])
    assert result['classified_precision'] == 1
    assert result['new_forecast_coverage_within_detected_candidates'] == .5


def test_incomplete_reference_rejected():
    with pytest.raises(ValueError):
        evaluate([{'range_role': {'role': 'AMBIGUOUS'}}], [])
