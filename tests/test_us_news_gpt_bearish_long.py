"""Offline BEARISH inversion, native LONG TP10/SL10, gaps and expiry tests."""
from functools import partial

import pandas as pd
import pytest

from scripts.research import us_news_gpt_bearish_long as study


@pytest.mark.parametrize('decision,status,confidence,expected',[
    ('BEARISH','VALID',.67,True),('BEARISH','VALID',.99,True),('BEARISH','INVALID',.99,False),
    ('BULLISH','VALID',.99,False),('ABSTAIN','VALID',.9,False)])
def test_all_valid_bearish_without_confidence_filter(decision,status,confidence,expected):
    assert study.eligible(dict(decision=decision,technical_status=status,confidence=confidence)) is expected


def native_case(tmp_path,*,low=19.8,high=20.2,gap=None,holding=2,terminal='2024-01-10',hook=True):
    days=pd.bdate_range('2023-01-02','2024-01-12');opens=pd.DataFrame({'SPY':400.,'TEST':20.},index=days)
    frames=dict(opens=opens.copy(),close=opens.copy(),high=opens*1.01,low=opens*.99,
        volume=pd.DataFrame(10000000.,index=days,columns=opens.columns))
    frames['high'].at[pd.Timestamp('2024-01-03'),'TEST']=high
    frames['low'].at[pd.Timestamp('2024-01-03'),'TEST']=low
    if gap is not None:
        for field,factor in [('opens',1.),('close',1.),('high',1.01),('low',.99)]:
            frames[field].at[pd.Timestamp('2024-01-04'),'TEST']=gap*factor
    quality=pd.DataFrame([dict(date=d,symbol=s,is_filled=0,instrument_id=i+1) for d in days for i,s in enumerate(opens)])
    scores=pd.DataFrame([dict(date=pd.Timestamp('2024-01-02'),symbol='TEST',proba_extreme=.99,keep=True)])
    macro=pd.DataFrame(dict(trade_date=days,vix=12.,vix9d=11.,vxn=16.,vix3m=15.,move=70.,rvx=16.,ten_y=4.,sentiment_score=0.))
    refs=[]
    def factory(cfg,**kwargs):
        cls=study.native.ExpiryMarkLedger if hook else study.native.grid.UnlimitedLedger
        extra=dict(quality=quality,holding_sessions=holding) if hook else {}
        ledger=cls(cfg,sl=study.SL,trail=None,tp=study.TP,study_end=terminal,events=[],**extra,**kwargs)
        refs.append(ledger);return ledger
    result=study.native.run_portfolio(frames=frames,scores=scores,sectors={'SPY':'ETF','TEST':'Industrials'},
        macro=study.native.ArchivedMacro(macro),market_config=study.native.grid.parse_market_regimes({'enabled':False}),
        policy='keep',variant='CURRENT_NO_EXPIRY',output=tmp_path,start_date='2024-01-02',end_date=terminal,
        decision_end_date='2024-01-02',quality=quality,ledger_factory=factory,
        session_factory=partial(study.native.grid.MarginAwareSession,ledger_ref=refs),
        expiry_open_sessions=None if hook else holding,reject_constrained_entries=True,
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False),daily_exit_policy=study.native.grid.margin_policy)
    return result,refs[0],pd.read_parquet(tmp_path/'daily.parquet'),pd.read_parquet(tmp_path/'trades.parquet')


@pytest.mark.parametrize('low,high,gap,reason,price',[
    (19.8,22.2,None,'take_profit',22.),(17.8,20.2,None,'initial_stop',18.),
    (17.8,22.2,None,'initial_stop',18.),(19.8,20.2,None,'expiry_open',20.),
    (19.8,20.2,17.,'initial_stop_gap_open',17.),(19.8,20.2,23.,'take_profit_gap_limit',22.)])
def test_native_long_protections_gaps_and_collision(tmp_path,low,high,gap,reason,price):
    result,ledger,daily,trades=native_case(tmp_path,low=low,high=high,gap=gap)
    assert len(trades)==1 and trades.iloc[0].side=='buy' and trades.iloc[0].borrow_cost==0
    assert trades.iloc[0].exit_reason==reason and trades.iloc[0].exit_price==pytest.approx(price)
    assert trades.iloc[0].replay_take_profit_price==pytest.approx(22.)
    assert trades.iloc[0].replay_initial_stop_price==pytest.approx(18.)
    summary=study.summarize(result,ledger,daily,trades,2024,'2024-01-10')
    assert summary['side']=='LONG' and summary['tp']==.1 and summary['sl']==.1
    assert summary['closed_positions']==1 and not summary['open_positions']


def test_expiry_parity_and_open_mtm(tmp_path):
    old=native_case(tmp_path/'old',hook=False);new=native_case(tmp_path/'new')
    assert len(new[3])==1
    pd.testing.assert_frame_equal(old[2],new[2]);pd.testing.assert_frame_equal(old[3],new[3])
    result,ledger,daily,trades=native_case(tmp_path/'open',holding=20,terminal='2024-01-04')
    summary=study.summarize(result,ledger,daily,trades,2024,'2024-01-04')
    assert len(summary['open_positions'])==1 and summary['closed_positions']==0
    assert summary['winning_pct'] is None and summary['final_capital_usd']<4000
