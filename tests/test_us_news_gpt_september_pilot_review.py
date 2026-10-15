"""No SQL, network, provider, portfolio, API credentials or real artifacts."""
import pandas as pd
import pytest

from scripts.research import us_news_gpt_september_pilot_review as review


def test_native_macro_deferred_never_interpolates_or_creates_rows(tmp_path):
    frame=pd.DataFrame({'trade_date':pd.to_datetime(['2026-10-02']),'vix':[17.5]})
    result=review.archived_macro_only(tmp_path,frame,pd.date_range('2026-10-02','2026-10-07'))
    pd.testing.assert_frame_equal(result,frame,check_exact=True)
    assert result is not frame
    assert not (tmp_path/'macro-tail.parquet').exists()


def test_native_macro_nulls_are_not_filled(tmp_path):
    frame=pd.DataFrame({'trade_date':pd.to_datetime(['2026-10-02']),'vix':[float('nan')]})
    assert review.archived_macro_only(tmp_path,frame,frame.trade_date).vix.isna().all()
