import pandas as pd
import pytest
from scripts.research.us_oracle_lineage_audit import extract_window,classify_scope


def test_window_requires_unique_evidence():
    line="build_folds_adaptive windows=12 first=('2018-07-05', '2019-01-03') last=('2024-01-08', '2024-07-09')"
    assert extract_window([line])['last_end']=='2024-07-09'
    with pytest.raises(ValueError):
        extract_window([line,line])
    with pytest.raises(ValueError):
        extract_window([])


def test_scope_does_not_certify_future_unknown_or_post_test():
    frame=pd.DataFrame(dict(date=['2024-07-09','2024-07-10','2023-01-01','2024-01-01'],
        fold_start=['2024-01-08','2024-01-08','2024-01-08',None]))
    scopes=classify_scope(frame,['2024-01-08'],'2018-07-05','2024-07-09').scope.tolist()
    assert scopes==['LOGGED_TEST_ENVELOPE_NOT_FULL_PIT','POST_TEST_HISTORICAL_SERVING',
                    'UNQUALIFIED_CHAMPION_OR_DATE','UNQUALIFIED_CHAMPION_OR_DATE']
