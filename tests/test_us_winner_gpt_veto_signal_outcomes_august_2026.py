from datetime import date
from types import SimpleNamespace

import pandas as pd

from scripts.research.us_winner_gpt_veto_signal_outcomes_august_2026 import first_confirmation, vector_exit


def bars():
    stamps = pd.date_range('2026-08-04T13:30Z', periods=5, freq='5min')
    return pd.DataFrame(dict(trade_date=[pd.Timestamp('2026-08-04')]*5,
        bar_timestamp=stamps, bar_end_timestamp=stamps+pd.Timedelta(minutes=5),
        open=[100.]*5, high=[102.]*5, low=[99.]*5, close=[99.,101.,101.,101.,101.]))


def test_confirmation_uses_three_completed_bars_then_next_open():
    f = bars()
    previous = f.iloc[:1].copy()
    previous['trade_date'] = pd.Timestamp('2026-08-03')
    previous['high'] = 100.
    got = first_confirmation(pd.concat([previous, f]), date(2026,8,3),
        [date(2026,8,3),date(2026,8,4)])
    assert got.bar_timestamp == f.iloc[3].bar_timestamp
    f.loc[0,'close'] = 101.
    assert first_confirmation(pd.concat([previous, f]), date(2026,8,3),
        [date(2026,8,3),date(2026,8,4)]) is None  # No fresh cross.


def test_gap_intrabar_and_horizon_priorities():
    f = bars()
    f.loc[1,'low'] = 92.
    due = f.iloc[4].bar_timestamp
    assert vector_exit(f, f.iloc[0].bar_timestamp, 100., due) == (f.iloc[1].bar_end_timestamp,93.,'STOP')
    f.loc[1,'open'] = 90.
    assert vector_exit(f, f.iloc[0].bar_timestamp, 100., due) == (f.iloc[1].bar_timestamp,90.,'STOP_GAP')
    due = f.iloc[1].bar_timestamp
    assert vector_exit(f, f.iloc[0].bar_timestamp, 100., due) == (due,90.,'HORIZON_OPEN')
