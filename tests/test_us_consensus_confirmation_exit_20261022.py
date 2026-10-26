from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest

from scripts.research import us_consensus_confirmation_exit_20261022 as study


def chain(sign=1):
    return pd.DataFrame([dict(symbol='A',entry_idx=i+5,entry_date=pd.Timestamp('2026-10-13')+pd.Timedelta(days=i),
        fiscal_anchor=pd.Timestamp('2026-09-30'),revenue_technical_ok=True,revenue_count_group='UNCHANGED_COUNT',
        old_revenue_count=5,new_revenue_count=5,revenue_sign=sign,old_id=i+1,new_id=i+2,
        new_available=pd.Timestamp('2026-10-12T20:00Z')+pd.Timedelta(days=i),
        entry_open=pd.Timestamp('2026-10-13T13:30Z')+pd.Timedelta(days=i)) for i in range(3)])


def bars(ohlc):
    return pd.DataFrame(ohlc,columns=['open','high','low','close'])


def test_three_changes_need_four_chained_observations():
    result=study.confirmation(chain())
    assert result.one_sign.tolist()==[1,1,1]
    assert result.three_sign.tolist()==[0,0,1]
    assert result.iloc[-1].confirmation_reason=='PASS'


def test_three_negative_changes_are_short():
    assert study.confirmation(chain(-1)).three_sign.tolist()==[0,0,-1]


@pytest.mark.parametrize('field,value,reason',[
    ('revenue_sign',0,'ZERO_MISSING_OR_UNQUALIFIED_CHANGE'),
    ('revenue_sign',-1,'OPPOSITE_CHANGES'),
    ('revenue_technical_ok',False,'ZERO_MISSING_OR_UNQUALIFIED_CHANGE'),
    ('revenue_count_group','CHANGED_COUNT','ZERO_MISSING_OR_UNQUALIFIED_CHANGE'),
    ('fiscal_anchor',pd.Timestamp('2026-12-31'),'FISCAL_ROLLOVER'),
    ('new_id',999,'NOT_FOUR_LINKED_OBSERVATIONS')])
def test_breaks_confirmation_not_filled(field,value,reason):
    data=chain();data.loc[1,field]=value
    result=study.confirmation(data)
    assert result.iloc[-1].three_sign==0
    assert result.iloc[-1].confirmation_reason==reason


def test_missing_decision_day_does_not_join_last_three_rows():
    data=chain();data.loc[1,'entry_idx']=1
    assert not study.confirmation(data).three_sign.any()


def test_analyst_count_same_in_each_pair_but_not_across_sequence_reserved():
    data=chain();data.loc[1,['old_revenue_count','new_revenue_count']]=6
    result=study.confirmation(data)
    assert result.iloc[-1].confirmation_reason=='ANALYST_COUNT_CHANGED'


def test_inverse_only_known_later_open_and_same_anchor_count():
    f=study.confirmation(chain())
    entry=next(f.iloc[[-1]].itertuples())
    future=SimpleNamespace(**{k:getattr(entry,k) for k in f.columns})
    future.entry_idx+=1;future.revenue_sign=-1
    future.entry_open+=pd.Timedelta(days=1);future.new_available+=pd.Timedelta(days=1)
    assert study.first_inverse(entry,{('A',future.entry_idx):future},future.entry_idx)==future.entry_idx
    future.fiscal_anchor=pd.Timestamp('2026-12-31')
    assert study.first_inverse(entry,{('A',future.entry_idx):future},future.entry_idx) is None


def test_inverse_after_cutoff_is_error_not_same_open_exit():
    f=study.confirmation(chain());entry=next(f.iloc[[-1]].itertuples())
    future=SimpleNamespace(**{k:getattr(entry,k) for k in f.columns})
    future.entry_idx+=1;future.revenue_sign=-1;future.new_available=future.entry_open
    with pytest.raises(ValueError,match='not known'):study.first_inverse(entry,{('A',future.entry_idx):future},future.entry_idx)


def test_inverse_exit_uses_next_open_not_previous_close_or_future_low():
    data=bars([(100,103,98,101),(102,120,70,100),(100,101,99,100)])
    result=study.replay(data,1,inverse_offset=1)
    assert result['exit_reason']=='INVERSE_AT_OPEN'
    assert result['gross_pct']==pytest.approx(2)
    assert result['full_sessions_held']==1


def test_gap_stop_beats_inverse_and_loss_can_exceed_stop():
    data=bars([(100,103,98,101),(90,120,70,100)])
    result=study.replay(data,1,inverse_offset=1)
    assert result['exit_reason']=='STOP_GAP' and result['gross_pct']==pytest.approx(-10)
    assert result['full_sessions_held']==1


def test_same_bar_stop_and_tp_is_stop_first():
    result=study.replay(bars([(100,112,94,105)]),1)
    assert result['exit_reason']=='STOP_TOUCH_BOTH' and result['gross_pct']==pytest.approx(-5)


def test_short_stop_and_target_orientation():
    result=study.replay(bars([(100,101,89,95)]),-1)
    assert result['exit_reason']=='TP_TOUCH' and result['gross_pct']==pytest.approx(10)
    result=study.replay(bars([(100,106,98,104)]),-1)
    assert result['exit_reason']=='STOP_TOUCH' and result['gross_pct']==pytest.approx(-5)


def test_h1_fixed_and_dynamic_identical():
    data=bars([(100,103,98,102)])
    assert study.replay(data,1)==study.replay(data,1,inverse_offset=None)


def test_stable_consensus_not_inverse_and_no_intrabar_later_info():
    f=study.confirmation(chain());entry=next(f.iloc[[-1]].itertuples())
    future=SimpleNamespace(**{k:getattr(entry,k) for k in f.columns})
    future.entry_idx+=1;future.revenue_sign=0
    assert study.first_inverse(entry,{('A',future.entry_idx):future},future.entry_idx) is None


def test_future_mutation_cannot_change_previous_confirmations():
    f=chain();before=study.confirmation(f)
    future=f.iloc[[-1]].copy();future['entry_idx']+=1;future['old_id']=4;future['new_id']=5;future['revenue_sign']=-1
    after=study.confirmation(pd.concat([f,future],ignore_index=True))
    pd.testing.assert_frame_equal(before,after.iloc[:3].reset_index(drop=True))
