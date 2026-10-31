import pandas as pd
import pytest

from scripts.research.us_options_consensus_overlap_20261030 import current_consensus
from tests.test_us_consensus_options_topn_20261027 import fixture


def inputs(**kwargs):
    _,raw,runs,top=fixture(**kwargs)
    top['signal_day']=pd.Timestamp('2026-10-16')
    top['selected']=True;top['combined_score']=.8;top['reason']='SELECTED_LONG'
    return raw,runs,top


def test_received_same_anchor_features():
    raw,runs,top=inputs()
    f,_=current_consensus(raw,runs,top,pd.Timestamp('2026-10-20T00:00Z'))
    assert f.iloc[0].revisions30==pytest.approx(.6)
    assert f.iloc[0].eps30==pytest.approx(.2)
    assert f.iloc[0].consensus_reason=='RESEARCH_ONLY'


def test_october_snapshot_cannot_supply_september_signal():
    raw,runs,top=inputs()
    top['signal_day']=pd.Timestamp('2026-09-22')
    top['decision_at']=pd.Timestamp('2026-09-23T13:25Z')
    f,_=current_consensus(raw,runs,top,pd.Timestamp('2026-10-30T00:00Z'))
    assert pd.isna(f.iloc[0].consensus_id) and pd.isna(f.iloc[0].revisions30)


def test_missing_counter_and_unfinished_run_never_imputed():
    raw,runs,top=inputs(down=None)
    f,_=current_consensus(raw,runs,top,pd.Timestamp('2026-10-20T00:00Z'))
    assert pd.isna(f.iloc[0].revisions30)
    raw,runs,top=inputs();runs['run-2']['status']='RUNNING'
    f,_=current_consensus(raw,runs,top,pd.Timestamp('2026-10-20T00:00Z'))
    assert pd.isna(f.iloc[0].consensus_id)
