import pandas as pd
from scripts.research.us_activist_13d_confirmation_audit import expected_outcome


def test_maturity_uses_entry_as_first_session_without_using_outcomes():
    sessions=pd.bdate_range('2026-09-01',periods=30)
    assert expected_outcome('2026-09-01',20,sessions,'2026-09-28')==('2026-09-28',True)
    assert expected_outcome('2026-09-01',20,sessions,'2026-09-25')==('2026-09-28',False)
