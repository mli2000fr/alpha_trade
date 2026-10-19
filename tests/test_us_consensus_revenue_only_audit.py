import pandas as pd
import pandas_market_calendars as mcal
import pytest
from scripts.research.us_consensus_revenue_only_audit import maturity


def test_h10_counts_entry_as_first_session_not_tenth_calendar_day():
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2026-10-01',end_date='2026-11-10')
    assert maturity('2026-10-13',schedule)==pd.Timestamp('2026-10-26T20:00Z')
    assert maturity('2026-10-19',schedule)==pd.Timestamp('2026-10-30T20:00Z')


def test_no_zero_session_horizon():
    with pytest.raises(ValueError):maturity('2026-10-19',None,horizon=0)
