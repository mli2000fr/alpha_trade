import pandas as pd
import pytest
from tests.test_us_consensus_observed_revision_pilot import rows
from scripts.research.us_consensus_observed_window_diagnostic import endpoints


def test_no_backdating_or_qualification_from_two_snapshots():
    r,_=rows();f=endpoints(pd.DataFrame(r),'2026-10-13T13:30Z')
    assert len(f)==1 and f.iloc[0].old_id==1 and f.iloc[0].new_id==2
    assert f.iloc[0].pattern=='BOTH_UP' and not f.iloc[0].eligible_for_direction


def test_later_snapshot_excluded_by_cutoff():
    r,_=rows();assert endpoints(pd.DataFrame(r),'2026-10-12T12:00Z').empty


def test_single_snapshot_not_a_fake_week_of_history():
    r,_=rows();assert endpoints(pd.DataFrame(r[:1]),'2026-10-13T13:30Z').empty


def test_counts_change_explicit_not_same_analysts_revision():
    r,_=rows();r[1]['eps_analyst_count']=3
    assert endpoints(pd.DataFrame(r),'2026-10-13T13:30Z').iloc[0].analyst_counts_changed


def test_no_fiscal_rollover_bridge():
    r,_=rows();r[1]['horizon_raw']='+1q'
    assert endpoints(pd.DataFrame(r),'2026-10-13T13:30Z').empty


def test_duplicate_rejected():
    r,_=rows();r.append(r[1].copy())
    with pytest.raises(ValueError): endpoints(pd.DataFrame(r),'2026-10-13T13:30Z')
