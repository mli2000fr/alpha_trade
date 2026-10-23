import pandas as pd
from scripts.research.us_consensus_confirmation_exit_split_20261022 import valid_window


def prices():
    days=pd.bdate_range('2026-10-13',periods=3)
    f=pd.DataFrame(dict(open=100,high=102,low=98,close=101,volume=100,
        is_filled=0,data_source='alpaca_sip',data_adjustment='split',instrument_id=7),index=days)
    return days,f


def test_actual_adjustment_kept_no_raw_relabelling():
    days,f=prices()
    result,status=valid_window(f,days,{},'A')
    assert result.data_adjustment.eq('split').all()
    assert status=='AVAILABLE_RESEARCH_NOT_PRODUCTION_QUALIFIED'


def test_missing_bar_not_ignored_even_if_exit_might_be_early():
    days,f=prices();f=f.drop(days[-1])
    result,status=valid_window(f,days,{},'A')
    assert result is None and status=='MISSING_OR_INVALID_FULL_WINDOW'


def test_no_other_feed_or_adjustment_fallback():
    days,f=prices()
    for col,value in [('data_adjustment','raw'),('data_source','eodhd_eod'),('data_source','alpaca_iex')]:
        g=f.copy();g.loc[days[1],col]=value
        assert valid_window(g,days,{},'A')[0] is None
