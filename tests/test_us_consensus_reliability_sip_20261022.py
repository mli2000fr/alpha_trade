import pandas as pd
import pytest
from scripts.research.us_consensus_reliability_sip_20261022 import sip_only


def test_two_providers_are_not_arbitrary_duplicate_choice():
    f=pd.DataFrame(dict(symbol=['A','A'],date=['2026-10-13']*2,data_source=['eodhd_eod','alpaca_sip'],close=[10,11]))
    result=sip_only(f)
    assert len(result)==1 and result.iloc[0].close==11


def test_no_fallback_to_eodhd_or_iex():
    f=pd.DataFrame(dict(symbol=['A','A'],date=['2026-10-13']*2,data_source=['eodhd_eod','alpaca_iex']))
    with pytest.raises(ValueError,match='No SIP'):sip_only(f)


def test_duplicates_inside_sip_still_fail_closed():
    f=pd.DataFrame(dict(symbol=['A','A'],date=['2026-10-13']*2,data_source=['alpaca_sip']*2))
    with pytest.raises(ValueError,match='Duplicate within SIP'):sip_only(f)
