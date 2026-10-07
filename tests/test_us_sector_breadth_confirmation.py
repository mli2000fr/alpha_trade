import numpy as np
import pandas as pd

from scripts.research.us_sector_breadth_confirmation import regime_mask, sector_context


def test_regime_capital_preservation_blocks_long_even_with_entries_true():
    frame=pd.DataFrame({'mode':['normal','capital_preservation','close_only','cash_only',None,'normal'],
                        'allow_new_entries':[1,1,0,0,1,None]})
    known, allowed=regime_mask(frame)
    assert allowed.tolist()==[True,False,False,False,False,False]
    assert known.tolist()==[True,True,True,True,False,False]


def test_leave_one_out_causal_support_and_missing_sessions():
    sessions=pd.bdate_range('2024-01-01',periods=45,name='date')
    names=[f'S{i}' for i in range(21)]
    sectors=pd.DataFrame({'symbol':names,'sector':['X']*21})
    bars=pd.concat([pd.DataFrame({'date':sessions,'symbol':name,
                     'adj_close':100+np.arange(45)*(2 if i==0 else 1)})
                    for i,name in enumerate(names)],ignore_index=True)
    first=sector_context(bars,sectors,sessions)
    row=first[first.symbol.eq('S0')&first.date.eq(sessions[20])].iloc[0]
    assert abs(row.relative20-.2)<1e-10
    assert row.sector_peers==20
    assert row.breadth20==1
    changed=bars.copy()
    changed.loc[changed.date.ge(sessions[30]),'adj_close']=900
    second=sector_context(changed,sectors,sessions)
    pd.testing.assert_frame_equal(first[first.date.lt(sessions[30])].reset_index(drop=True),
                                  second[second.date.lt(sessions[30])].reset_index(drop=True))
    missing=bars[~(bars.symbol.eq('S1')&bars.date.eq(sessions[10]))]
    third=sector_context(missing,sectors,sessions)
    assert third[third.symbol.eq('S0')&third.date.eq(sessions[20])].empty
