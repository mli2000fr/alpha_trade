import pandas as pd
import pytest
from types import SimpleNamespace

from scripts.research import us_gpt_short_august_2026 as study


def test_exact_veto_keeps_unknown_and_ten():
    f=pd.DataFrame(dict(gpt_status=['VALID']*5+['INVALID'],gpt_score=[5,6,7,9,10,7]))
    assert study.veto_mask(f,7).tolist()==[False,False,True,True,False,False]
    assert study.veto_mask(f,6).tolist()==[False,True,True,True,False,False]
    assert not study.veto_mask(f,None).any()
    with pytest.raises(ValueError):study.veto_mask(f,8)


def test_fresh_mirror_confirmation_not_just_two_falling_prices():
    assert study.confirmation([101,99,98],100,'sell')
    assert not study.confirmation([99,98,97],100,'sell')
    assert not study.confirmation([101,99,101],100,'sell')
    assert study.confirmation([99,101,102],100,'buy')
    assert not study.confirmation([99,101],100,'buy')


def test_short_stop_gap_and_first_entry_bar_and_horizon():
    assert study.stop_exit(SimpleNamespace(open=108,high=109,low=105),107,'sell')==(108.,'STOP_GAP','OPEN')
    assert study.stop_exit(SimpleNamespace(open=100,high=108,low=98),107,'sell')==(107,'STOP','INTRABAR')
    assert study.stop_exit(SimpleNamespace(open=95,high=108,low=94),107,'sell',due=True)==(95.,'HORIZON_OPEN','OPEN')
    assert study.stop_exit(SimpleNamespace(open=100,high=106,low=98),107,'sell') is None


def test_short_pnl_fees_borrow_are_not_negative_long_pnl():
    pnl,fees,borrow=study.net_trade(100,90,10,'sell',21)
    assert fees==pytest.approx(1.52)
    assert borrow==pytest.approx(.25)
    assert pnl==pytest.approx(98.23)
    long,_,_=study.net_trade(100,90,10,'buy',21)
    assert pnl != -long


def test_marked_collateral_cannot_reuse_short_proceeds():
    r=object.__new__(study.Replay);r.side='sell';r.cash=3999.2
    r.positions={'X':dict(quantity=10,entry_price=100)};r.marks={'X':110}
    assert r.equity()==pytest.approx(3899.2)
    assert r.gross()==1100
    assert r.equity()-r.gross()==pytest.approx(2799.2)


def test_exit_uses_own_sessions_and_reconciles_previous_borrow():
    r=object.__new__(study.Replay);r.side='sell';r.cash=3999.2-.1;r.loan=.1;r.fees=.8
    r.idx={pd.Timestamp('2026-08-03').date():0,pd.Timestamp('2026-08-04').date():1}
    day=pd.Timestamp('2026-08-04').date();entry_day=pd.Timestamp('2026-08-03').date()
    r.positions={'X':dict(quantity=10,entry_price=100,entry_day=entry_day,entry_fees=.8,accrued_borrow=.1)}
    r.trades=[];r.events=[]
    class Losses:
        def record(self,*a,**k):pass
    r.losses=Losses();r.close('X',90,pd.Timestamp('2026-08-04T13:30Z'),day,'HORIZON_OPEN')
    expected,_,loan=study.net_trade(100,90,10,'sell',2)
    assert r.cash==pytest.approx(4000+expected)
    assert r.loan==pytest.approx(loan)
    assert r.positions=={}
