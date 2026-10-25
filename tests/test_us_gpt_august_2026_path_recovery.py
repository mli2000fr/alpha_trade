from decimal import Decimal

import pandas as pd
import pytest

from scripts.research.us_gpt_august_2026_path_recovery import measure_numeric
from tests.test_us_gpt_august_2026_path_audit import fixture


def test_decimal_sql_extrema_keep_their_true_timestamp():
    frame,window,actions=fixture()
    for field in ('open','high','low','close','volume'):
        frame[field]=frame[field].map(lambda v:Decimal(str(v)))
    frame.loc[1,'high']=Decimal('118.12345678');frame.loc[2,'low']=Decimal('84.12345678')
    result=measure_numeric(frame,window,{},'ABC',actions)
    assert result['path_status']=='QUALIFIED_COMPLETE_5M'
    assert result['high_first_bar_utc']==pd.Timestamp(frame.loc[1,'bar_timestamp']).isoformat()
    assert result['low_first_bar_utc']==pd.Timestamp(frame.loc[2,'bar_timestamp']).isoformat()
    assert result['first_extremum']=='HIGH_FIRST'
    assert result['high_max_pct']==pytest.approx(18.12345678)
    assert result['low_min_pct']==pytest.approx(-15.87654322)


def test_recovery_keeps_quality_exclusions_and_same_bar_ambiguity():
    frame,window,actions=fixture()
    frame.loc[1,'low']=80.
    result=measure_numeric(frame,window,{},'ABC',actions)
    assert result['first_extremum']=='SAME_5M_BAR_UNRESOLVED'
    result=measure_numeric(frame.drop(index=3),window,{},'ABC',actions)
    assert result['path_status']=='UNQUALIFIED_OBSERVED_PATH'
    assert 'INCOMPLETE_5M_GRID' in result['quality_reasons']
