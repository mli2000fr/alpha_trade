from pathlib import Path
import pandas as pd
import pytest
from scripts.research.us_winner_sl3_tp7_tr3_open11_20261023 import variant_config,source,PARENT
from scripts.research.us_winner_sl3_tp7_tr3_open11_audit_20261023 import scalar_exit


def path(values):
    f=pd.DataFrame(values,columns=['open','high','low','close'])
    f['bar_timestamp']=pd.date_range('2026-01-02 15:00Z',periods=len(f),freq='5min')
    f['bar_end_timestamp']=f.bar_timestamp+pd.Timedelta(minutes=5)
    f['session_close']=pd.Timestamp('2026-01-02 21:00Z')
    return f


def test_only_four_policy_values_change():
    p=source.read(PARENT/'protocol.json');base=source.engine_config(p,2025);cfg=variant_config(p,2025)
    before=base.exec_config.winner_pyramiding.__dict__;after=cfg.exec_config.winner_pyramiding.__dict__
    assert {k for k in before if before[k]!=after[k]}=={'stop_loss_pct','take_profit_pct','trailing_stop_pct','horizon_sessions'}
    assert cfg.risk_config==base.risk_config and cfg.exec_config.leverage==base.exec_config.leverage
    assert cfg.initial_equity==4000 and cfg.exec_config.winner_pyramiding.entry_valid_sessions==20


def test_intrabar_stop_precedes_tp_and_is_logged_at_bar_end():
    f=path([[100,108,96,101]])
    assert scalar_exit(f,f.bar_timestamp.iloc[0],100,pd.Timestamp('2026-02-01Z'.replace('Z',''),tz='UTC'))==(f.bar_end_timestamp.iloc[0],97,'STOP')


def test_high_does_not_tighten_retroactively_in_its_own_bar():
    f=path([[100,106,98,105],[105,105,102,103]])
    stamp,price,reason=scalar_exit(f,f.bar_timestamp.iloc[0],100,pd.Timestamp('2026-02-01',tz='UTC'))
    assert stamp==f.bar_end_timestamp.iloc[1] and price==102.82 and reason=='STOP'


def test_gap_on_newly_tightened_stop_uses_open_not_level():
    f=path([[100,106,98,105],[101,103,100,102]])
    assert scalar_exit(f,f.bar_timestamp.iloc[0],100,pd.Timestamp('2026-02-01',tz='UTC'))==(f.bar_timestamp.iloc[1],101.,'TIGHTENED_STOP_GAP')


def test_tp_gap_capped_and_old_stop_gap_unlimited():
    f=path([[100,101,99,100],[110,111,109,110]])
    assert scalar_exit(f,f.bar_timestamp.iloc[0],100,pd.Timestamp('2026-02-01',tz='UTC'))[1:]==(107.,'TP_GAP_CAPPED')
    f.loc[1,['open','high','low','close']]=[90,91,89,90]
    assert scalar_exit(f,f.bar_timestamp.iloc[0],100,pd.Timestamp('2026-02-01',tz='UTC'))[1:]==(90.,'STOP_GAP')


def test_horizon_auction_is_not_intrabar_high():
    f=path([[100,102,99,101],[95,110,90,105]])
    due=f.bar_timestamp.iloc[1]
    assert scalar_exit(f,f.bar_timestamp.iloc[0],100,due)==(due,95.,'HORIZON_OPEN')


def test_final_completed_high_may_trigger_at_close():
    f=path([[100,106,98,101]])
    f['session_close']=f.bar_end_timestamp
    assert scalar_exit(f,f.bar_timestamp.iloc[0],100,pd.Timestamp('2026-02-01',tz='UTC'))==(f.bar_end_timestamp.iloc[0],101.,'TIGHTENED_STOP_GAP')
