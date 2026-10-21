from dataclasses import asdict
from types import SimpleNamespace

import pandas as pd

from scripts.research import us_winner_context_headroom as study
from scripts.research.us_winner_context_headroom_audit import scalar_exit


def test_scalar_trailing_prior_high_and_adverse_collision():
    start=pd.Timestamp('2026-01-05 14:30Z')
    frame=pd.DataFrame([dict(bar_timestamp=start,bar_end_timestamp=start+pd.Timedelta(minutes=5),
        open=100,high=120,low=99,close=110),dict(bar_timestamp=start+pd.Timedelta(minutes=5),
        bar_end_timestamp=start+pd.Timedelta(minutes=10),open=110,high=140,low=100,close=130)])
    x=scalar_exit(frame,100,start+pd.Timedelta(days=1),asdict(study.BASE),.0008)
    assert x['reason']=='STOP' and x['exit_time']==start+pd.Timedelta(minutes=10)


def entry_frames():
    schedule=study.calendar_frame();day=pd.Timestamp('2026-01-05');prior=pd.Timestamp('2026-01-02')
    opening=schedule.set_index('date').loc[day,'market_open']
    times=pd.date_range(opening,periods=5,freq='5min')
    current=pd.DataFrame(dict(bar_timestamp=times,bar_end_timestamp=times+pd.Timedelta(minutes=5),
        close=[100,102,102,103,103],open=[100,102,102,103,103],high=[101,103,103,104,104]))
    previous=pd.DataFrame(dict(high=[101]))
    return schedule,prior,day,current,{('A',prior):previous,('A',day):current}


def test_entry_three_same_session_bars_and_next_open():
    schedule,prior,day,current,groups=entry_frames()
    entry,why=study.first_entry(SimpleNamespace(oracle_date=prior,symbol='A'),groups,schedule)
    assert why is None and entry['timestamp']==current.bar_timestamp.iloc[3]
    assert entry['price']==103 and entry['delay']==1


def test_first_missing_session_is_reserved_not_skipped_to_later_signal():
    schedule,prior,day,current,groups=entry_frames()
    del groups['A',day]
    entry,why=study.first_entry(SimpleNamespace(oracle_date=prior,symbol='A'),groups,schedule)
    assert entry is None and why=='ENTRY_SCAN_MISSING_SESSION'


def test_entry_does_not_use_future_high_or_future_close():
    schedule,prior,day,current,groups=entry_frames()
    a,_=study.first_entry(SimpleNamespace(oracle_date=prior,symbol='A'),groups,schedule)
    current.loc[4,['high','close']]=[10000,9999]
    b,_=study.first_entry(SimpleNamespace(oracle_date=prior,symbol='A'),groups,schedule)
    assert a==b
