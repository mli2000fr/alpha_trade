import pandas as pd
import pytest

from scripts.research.us_top10_2024_context_audit import group_metrics


def test_group_metrics_preserve_unknown_labels_in_coverage():
    frame = pd.DataFrame(dict(year=[2024]*3,date=pd.to_datetime(['2024-01-02']*3),
        target_quality_valid=[1,1,0],local_endpoint_ok=[True]*3,
        future_return=[.1,-.2,99.],oracle_decile=[10,1,10]))
    result = group_metrics(frame,['year'])[0]
    assert result['count'] == 3
    assert result['qualified'] == 2
    assert result['days'] == 1
    assert result['d1_pct'] == 50
    assert result['d10_pct'] == 50
    assert result['mean_return_pct'] == pytest.approx(-5.)


def test_no_valid_label_does_not_create_zero_return():
    frame = pd.DataFrame(dict(year=[2024],date=pd.to_datetime(['2024-01-02']),
        target_quality_valid=[0],local_endpoint_ok=[True],future_return=[.1],oracle_decile=[10]))
    result = group_metrics(frame,['year'])[0]
    assert result['qualified'] == 0
    assert 'mean_return_pct' not in result
