"""Offline SHORT checks; no real SQL, HTTP, credentials or orders."""
from functools import partial

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_news_gpt_bearish_portfolio as study
from scripts.research.us_concentrated_live_portfolio import run_portfolio,ArchivedMacro
from scripts.research.us_oracle_short_replay import ShortLedger


@pytest.mark.parametrize('decision,status,expected',[
    ('BEARISH','VALID',True),('BEARISH','INVALID',False),('BULLISH','VALID',False),
    ('ABSTAIN','VALID',False),('UNKNOWN_INVALID_RESPONSE',None,False)])
def test_only_valid_bearish(decision,status,expected):
    assert study.eligible_bearish(dict(decision=decision,technical_status=status,confidence=.62)) is expected


def run_native(tmp_path,*,allow_normal=True,hook=True,holding=2,end='2024-01-10'):
    days=pd.bdate_range('2023-01-02','2024-01-12')
    close=pd.DataFrame({'TEST':100.,'SPY':400.},index=days)
    frames=dict(opens=close.copy(),close=close.copy(),high=close*1.01,low=close*.99,
        volume=pd.DataFrame(10000000.,index=days,columns=close.columns))
    quality=pd.DataFrame([dict(date=d,symbol=s,is_filled=0,instrument_id=i+1) for d in days for i,s in enumerate(close)])
    scores=pd.DataFrame([dict(date=pd.Timestamp('2024-01-02'),symbol='TEST',proba_extreme=.99,keep=True)])
    macro=pd.DataFrame(dict(trade_date=days,vix=12.,vix9d=11.,vxn=16.,vix3m=15.,move=70.,rvx=16.,ten_y=4.,sentiment_score=0.))
    refs=[]
    class NativeExpiry(study.ShortMarkLedger):
        def corporate_action_open(self,*args):return ShortLedger.corporate_action_open(self,*args)
    def factory(cfg,**kwargs):
        cls=study.ShortMarkLedger if hook else NativeExpiry
        value=cls(cfg,quality=quality,study_end=end,holding_sessions=holding,events=[],**kwargs)
        refs.append(value);return value
    result=run_portfolio(frames=frames,scores=scores,sectors={'TEST':'Industrials','SPY':'ETF'},
        macro=ArchivedMacro(macro),market_config=study.long.grid.parse_market_regimes({'enabled':False}),
        policy='keep',variant='CURRENT_NO_EXPIRY',output=tmp_path,start_date='2024-01-02',end_date=end,
        decision_end_date='2024-01-02',quality=quality,ledger_factory=factory,
        session_factory=partial(study.ShortMarginSession,ledger_ref=refs),
        expiry_open_sessions=None if hook else holding,reject_constrained_entries=True,
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False),
        research_allow_short_normal=allow_normal,daily_exit_policy=study.margin_policy)
    bars=close.stack().rename('close').reset_index().rename(columns={'level_0':'date','level_1':'symbol'})
    bars['open']=bars.close;bars['high']=bars.close*1.01;bars['low']=bars.close*.99
    return result,refs[0],pd.read_parquet(tmp_path/'daily.parquet'),pd.read_parquet(tmp_path/'trades.parquet'),bars,days


def test_short_expiry_hook_has_exact_native_parity(tmp_path):
    old=run_native(tmp_path/'old',hook=False)
    new=run_native(tmp_path/'new')
    assert len(new[3])>0,'nonempty execution required'
    pd.testing.assert_frame_equal(old[2],new[2])
    pd.testing.assert_frame_equal(old[3],new[3])
    trade=new[3].iloc[0]
    assert trade.side=='sell' and trade.quantity==round(trade.quantity)
    assert trade.replay_initial_stop_price==pytest.approx(trade.entry_price*1.05)
    assert trade.replay_take_profit_price==pytest.approx(trade.entry_price*.8)
    assert trade.borrow_cost>0


def test_native_normal_block_is_not_silently_overridden(tmp_path):
    result,ledger,daily,trades,*_=run_native(tmp_path/'blocked',allow_normal=False)
    assert trades.empty and not ledger.state.positions
    assert result['return_pct']==0 and not result['research_allow_short_normal']


def test_open_short_credit_is_not_profit_and_borrow_is_in_reported_mtm(tmp_path):
    result,ledger,daily,trades,bars,days=run_native(tmp_path/'open',holding=20,end='2024-01-04')
    assert ledger.state.positions and trades.empty
    summary=study.summarize(result,ledger,daily,trades,bars,days,2024,'2024-01-04')
    assert ledger.state.settled_cash>4000
    assert summary['final_capital_usd']<4000
    assert summary['accrued_open_borrow_usd']>0
    assert summary['final_capital_usd']==pytest.approx(
        summary['native_equity_before_open_borrow_usd']-summary['accrued_open_borrow_usd'])
    assert ledger.reconciliation_error()==pytest.approx(0,abs=1e-7)
    with pytest.raises(ValueError,match='remaining positions'):
        # Base ledger must not be reused for an unfinished SHORT book.
        super(ShortLedger,ledger).reconciliation_error()


def test_short_maintenance_price_tiers_are_explicit_assumptions():
    from types import SimpleNamespace
    p={'A':SimpleNamespace(quantity=10),'B':SimpleNamespace(quantity=10),'C':SimpleNamespace(quantity=10)}
    assert study.short_maintenance(p,{'A':2.,'B':6.,'C':100.})==pytest.approx(25+50+300)
    with pytest.raises(ValueError):study.short_maintenance(p,{'A':np.nan,'B':6.,'C':100.})
