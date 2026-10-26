from datetime import date
import numpy as np
import pandas as pd
import pytest

from scripts.research import us_winner_bottom_rank_filter_20261022 as s
from common.market_calendar import get_market_calendar


def observable():
    return pd.DataFrame([dict(date=pd.Timestamp('2025-01-03'),symbol=f'S{i}',score=1-i/20,
        oracle_rank=i,vol_ratio_20_60=float(11-i),J_qualified=True) for i in range(1,11)])


def test_remove_estimated_bottom_not_original_oracle_bottom():
    a=s.freeze_ranks(observable())
    assert a.loc[a.DROP_BOTTOM3_KEEP7,'oracle_rank'].tolist()==list(range(4,11))
    assert a.loc[a.DROP_BOTTOM5_KEEP5,'oracle_rank'].tolist()==list(range(6,11))
    assert a.oracle_rank.tolist()==list(range(1,11))
    assert a.WINNER_ONLY.sum()==10


def test_future_losses_do_not_change_filter():
    a=observable();b=s.freeze_ranks(a)
    a['future_return']=np.arange(10)*100
    a['label']=1
    pd.testing.assert_frame_equal(b,s.freeze_ranks(a))


def test_unknown_is_excluded_everywhere_without_replacement():
    a=observable();a.loc[0,'vol_ratio_20_60']=np.nan
    b=s.freeze_ranks(a)
    assert not b.iloc[0][list(s.ARMS)].any()
    assert b.iloc[0].estimated_trend_rank==10
    assert b.WINNER_ONLY.sum()==9
    assert b.DROP_BOTTOM3_KEEP7.sum()==7


def test_ties_use_original_oracle_rank():
    a=observable();a.vol_ratio_20_60=1
    b=s.freeze_ranks(a)
    assert b.estimated_trend_rank.tolist()==list(range(1,11))


def test_bad_original_top10_rejected():
    with pytest.raises(ValueError):s.freeze_ranks(observable().iloc[:9])
    with pytest.raises(ValueError):s.freeze_ranks(pd.concat([observable(),observable().iloc[:1]]))


def test_seed_signal_for_annual_reset():
    a=observable();a.date=pd.Timestamp('2024-12-31')
    assert len(s.annual_signals(a,2025))==10
    a.date=pd.Timestamp('2024-12-30')
    assert s.annual_signals(a,2025).empty


def intraday():
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    session=next(x for x in cal.sessions(date(2025,1,3),date(2025,1,3)) if x.is_open)
    stamps=pd.date_range(session.open_at_utc,session.close_at_utc,freq='5min',inclusive='left')
    a=pd.DataFrame(dict(bar_timestamp=stamps,bar_end_timestamp=stamps+pd.Timedelta(minutes=5),
        open=100.,high=101.,low=99.,close=100.,volume=1000.,payload_hash='h'))
    return session,a


@pytest.mark.parametrize('bad',['missing','zero','hash','end','ohlc'])
def test_raw_session_never_fabricated(bad):
    session,a=intraday();assert s.qualify_session(a,session)
    if bad=='missing':a=a.iloc[:-1]
    if bad=='zero':a.loc[5,'volume']=0
    if bad=='hash':a.loc[5,'payload_hash']=None
    if bad=='end':a.loc[5,'bar_end_timestamp']+=pd.Timedelta(minutes=5)
    if bad=='ohlc':a.loc[5,'high']=90
    assert not s.qualify_session(a,session)


def test_existing_output_not_overwritten(tmp_path):
    with pytest.raises(FileExistsError):s.prepare(tmp_path)


def test_common_cohort_preserves_prior_ranks_even_with_missing_prices():
    a=s.freeze_ranks(observable());a['year']=2025
    ca=pd.DataFrame(columns=['symbol','ex_date'])
    out=s.common_cohort(a,{},ca,{f'S{i}':'Sector' for i in range(1,11)})
    assert not out.common_eligible.any()
    assert out.estimated_trend_rank.tolist()==a.estimated_trend_rank.tolist()
    assert out.oracle_rank.tolist()==a.oracle_rank.tolist()
