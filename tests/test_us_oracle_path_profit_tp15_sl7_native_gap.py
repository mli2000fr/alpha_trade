"""Exact native floating-point boundary; no epsilon or selected-case exception."""
import pandas as pd
import pytest

from scripts.research import us_oracle_path_profit_tp15_sl7_native_gap as study


def fixture(previous,opening):
    days=pd.bdate_range('2022-10-03',periods=25)
    raw=pd.DataFrame(dict(date=days,symbol='UNIT',open=previous,high=previous*1.1,
        low=previous*.9,close=previous,adj_close=previous,volume=1e7,is_filled=0,
        instrument_id=1,data_source='frozen',data_adjustment='split'))
    raw.loc[1,['open','high','low','close']]=[opening,opening*1.01,opening*.99,opening]
    grid,_=study.base.market_frames(raw,days)
    return grid,days


@pytest.mark.parametrize('previous,opening,allowed',[(6.,6.18,True),(100.,103.,True),(100.,103.0001,False),
                                                    (100.,96.9999,False),(100.,97.,True)])
def test_all_cases_use_native_boundary(previous,opening,allowed):
    grid,days=fixture(previous,opening)
    assert (study.qualify_path(grid,0,days,'UNIT',{})=='') is allowed
    assert allowed is (not study.should_skip_entry_for_gap(previous,opening,max_gap_pct=.03))


def test_invalid_paths_stay_invalid_not_rescued_by_gap_fix():
    grid,days=fixture(6.,6.18)
    grid.loc[days[5],'volume']=0
    assert study.qualify_path(grid,0,days,'UNIT',{})=='MISSING_NONPOSITIVE_PATH'


def test_exact_boundary_matches_full_native_execution():
    days=pd.bdate_range('2022-08-01',periods=80);j=30
    raw=pd.DataFrame(dict(date=days,symbol='UNIT',open=6.,high=6.05,low=5.95,close=6.,volume=1e7))
    raw.loc[j+1,['open','high','low','close']]=[6.18,6.20,6.15,6.18]
    _,frames=study.base.market_frames(raw,days)
    assert study.base.assert_native_parity(frames,j,study.base.unit_config(days[0],days[-1]))['native_parity']
