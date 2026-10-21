import pytest
from scripts.research.us_cash_merger_readiness import no_future_completion,validate_bar_values


def test_future_closing_not_observed_completion():
    for text in ['expects to complete on March 22','will complete merger','anticipated closing']:
        with pytest.raises(ValueError,match='future'):no_future_completion(text)
    no_future_completion('completed its acquisition on March 12, 2024')


def test_price_quality_never_missing_zero_or_bad_extrema():
    assert validate_bar_values([])==['NO_BARS']
    row=dict(t='2024-01-26T05:00:00Z',o=10.,h=11.,l=9.,c=10.,v=100)
    assert validate_bar_values([row])==[]
    assert 'DUPLICATE_DATES' in validate_bar_values([row,row])
    assert 'INCONSISTENT_OHLC' in validate_bar_values([dict(row,h=8.)])
    assert 'NONPOSITIVE_OR_NONFINITE_OHLCV' in validate_bar_values([dict(row,v=0)])
