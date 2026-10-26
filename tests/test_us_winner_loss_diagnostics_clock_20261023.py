import pandas as pd
import pytest
from scripts.research.us_winner_loss_diagnostics_clock_20261023 import corrected_signatures


def test_stop_bar_end_reserves_high_and_keeps_first_post_exit_bar():
    f=pd.DataFrame(dict(open=[100,102,94,108],high=[103,120,109,110],low=[99,92,94,107],close=[102,93,108,109],volume=[100]*4))
    f['bar_timestamp']=pd.date_range('2026-01-02 15:00Z',periods=4,freq='5min')
    f['bar_end_timestamp']=f.bar_timestamp+pd.Timedelta(minutes=5)
    r=corrected_signatures(f.iloc[:3],f.iloc[3:],entry_time=f.bar_timestamp.iloc[0],exit_time=f.bar_end_timestamp.iloc[1],
        entry=100,exit_price=93,reason='STOP',threshold=99,fee=.0008,complete=True)
    assert r['mfe_lower_pct']==pytest.approx(3) and r['mfe_upper_pct']==pytest.approx(20)
    assert r['post_stop_1R_time']==f.bar_end_timestamp.iloc[2]
    assert r['post_stop_1R_calendar_days']==pytest.approx(5/1440)
    assert not r['immediate_observed']
