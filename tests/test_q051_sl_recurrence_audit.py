"""Stop repetitions must not leak current/future outcomes or duplicate variants."""
import pandas as pd

from scripts.research.us_q051_sl_recurrence_audit_20261116 import prepare_trades,causal_prior_sl,per_symbol,unique_episodes,frozen_history_rules


def trades(rows):
    f=pd.DataFrame(rows,columns=['symbol','entry_date','exit_date','entry_price','pnl','exit_reason'])
    f['side']='buy';f['quantity']=1.;f['return_pct']=f.pnl/f.entry_price
    return prepare_trades(f,'TEST')


def test_gap_is_stop_but_horizon_loss_is_not_stop():
    f=trades([['X','2021-01-01','2021-01-02',100,-5,'STOP'],
        ['X','2021-01-03','2021-01-04',100,-8,'STOP_GAP'],
        ['X','2021-01-05','2021-01-06',100,-1,'HORIZON_OPEN'],
        ['X','2021-01-07','2021-01-08',100,-5,'STOP']])
    s=per_symbol(f).iloc[0]
    assert s.sl==3 and s.losses==4 and s.max_consecutive_sl==2 and s.max_consecutive_losses==4
    assert s.all_stops==False and s.always_loss==True


def test_current_and_same_timestamp_stop_is_not_known_at_entry():
    f=trades([['X','2021-01-01','2021-01-02',100,-5,'STOP'],
        ['X','2021-01-02','2021-01-02',100,-5,'STOP'],
        ['X','2021-01-03','2021-01-04',100,10,'HORIZON_OPEN']])
    r=causal_prior_sl(f).sort_values('entry_at')
    assert r.known_prior_sl.tolist()==[0,0,2]


def test_duplicate_variants_are_one_episode_and_conflicts_are_flagged():
    f=trades([['X','2021-01-01','2021-01-02',100,-5,'STOP']])
    g=f.copy();g['case']='OTHER';g['quantity']=2;g['pnl']*=2
    union,conflicts=unique_episodes(pd.concat([f,g],ignore_index=True))
    assert len(union)==1 and union.case_observations.iloc[0]==2 and conflicts.empty
    g['win']=True;g['loss']=False;g['net_return_pct']=10
    union,conflicts=unique_episodes(pd.concat([f,g],ignore_index=True))
    assert union.empty and len(conflicts)==2


def test_history_rule_does_not_use_a_later_loss_to_qualify_a_symbol():
    rows=[]
    for year in range(2020,2024):rows.append(['X',f'{year}-01-01',f'{year}-01-10',100,-5,'STOP'])
    rows += [['X','2025-01-01','2025-01-10',100,-5,'STOP'],
             ['Y','2024-12-30','2025-01-10',100,-5,'STOP']]
    f=trades(rows);result,names=frozen_history_rules(f)
    assert result.set_index('rule').loc['zero_win_min5','history_symbols']==0
    assert names.empty
