import numpy as np
import pandas as pd
from scripts.research.us_q051_entry_ceiling_20261127 import ceiling_panel,expand_windows,CeilingTiming,adapted_replay


def test_atr_and_ceiling_are_causal_and_missing_history_is_unknown():
    days=pd.bdate_range('2021-01-01',periods=30)
    close=pd.DataFrame({'A':np.arange(100.,130.)},index=days)
    high=close+2;low=close-2
    signals=pd.DataFrame({'trade_date':[days[20],days[5]],'symbol':['A','A'],'rank':[1,1]})
    panel=ceiling_panel(signals,high,low,close)
    assert panel.atr20.iloc[0]==4 and panel.ceiling.iloc[0]==122
    assert panel.qualified.tolist()==[True,False]
    changed=close.copy();changed.loc[days[21]:]=10000
    actual=ceiling_panel(signals,high,low,changed)
    pd.testing.assert_frame_equal(actual,panel)


def test_windows_use_official_sessions_and_new_signal_supersedes_old_carry():
    days=pd.to_datetime(['2026-11-24','2026-11-25','2026-11-27','2026-11-30'])
    panel=pd.DataFrame([dict(trade_date=days[0],origin_signal_date=days[0],symbol='A',origin_id='old'),
                        dict(trade_date=days[1],origin_signal_date=days[1],symbol='A',origin_id='new')])
    expanded,superseded=expand_windows(panel,days)
    assert len(superseded)==1 and superseded.origin_id.iloc[0]=='old'
    assert expanded.loc[expanded.entry_day.eq(days[2]),'origin_id'].tolist()==['new']
    assert expanded.entry_day.max()==days[3]
    assert expanded.wait_session.max()==2


def test_daily_gate_same_price_or_lower_no_retry_after_offering_to_risk():
    day=pd.Timestamp('2026-11-27');rows=pd.DataFrame([
        dict(symbol='A',origin_id='A1',qualified=True,ceiling=100.,wait_session=1),
        dict(symbol='B',origin_id='B1',qualified=True,ceiling=100.,wait_session=1),
        dict(symbol='C',origin_id='C1',qualified=False,ceiling=np.nan,wait_session=1)])
    tape=CeilingTiming(pd.DataFrame({'A':[100.],'B':[100.01],'C':[99.]},index=[day]),None)
    kept=tape.at_daily_open(day.date(),day.date(),day,rows)
    assert kept.symbol.tolist()==['A']
    assert tape.at_daily_open(day.date(),day.date(),day,rows).empty
    assert len(tape.audit)==5  # A is not reconsidered after native risk refusal.


def test_adapter_validates_against_current_native_source():
    assert callable(adapted_replay())
