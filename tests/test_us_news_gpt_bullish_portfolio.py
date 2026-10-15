"""Offline tests; no API, real SQL or production orders."""
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_news_gpt_bullish_portfolio as study
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro,run_portfolio
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config


@pytest.mark.parametrize('decision,status,expected',[
    ('BULLISH','VALID',True),('BULLISH','INVALID',False),('BEARISH','VALID',False),
    ('ABSTAIN','VALID',False),('UNKNOWN_NO_QUALIFIED_TEXT',None,False)])
def test_only_valid_bullish(decision,status,expected):
    assert study.eligible_bullish(dict(decision=decision,technical_status=status,confidence=.62)) is expected


def native_case(tmp_path,hook,terminal,holding=2):
    days=pd.bdate_range('2023-01-02','2024-01-12')
    opens=pd.DataFrame({'SPY':400.,'TEST':20.},index=days)
    frames=dict(opens=opens,close=opens.copy(),high=opens*1.01,low=opens*.99,
        volume=pd.DataFrame(10000000.,index=days,columns=opens.columns))
    decision=pd.Timestamp('2024-01-02')
    scores=pd.DataFrame([dict(date=decision,symbol='TEST',proba_extreme=.99,keep=True)])
    macro=pd.DataFrame(dict(trade_date=days,vix=12.,vix9d=11.,vxn=16.,vix3m=15.,move=70.,rvx=16.,
        ten_y=4.,sentiment_score=0.))
    quality=pd.DataFrame([dict(date=d,symbol=s,is_filled=0,instrument_id=i+1) for d in days for i,s in enumerate(opens)])
    refs=[]
    def factory(cfg,**kwargs):
        cls=study.ExpiryMarkLedger if hook else study.grid.UnlimitedLedger
        extra=dict(quality=quality,holding_sessions=holding) if hook else {}
        value=cls(cfg,sl=.05,trail=.15,tp=.20,study_end=terminal,events=[],**extra,**kwargs)
        refs.append(value);return value
    result=run_portfolio(frames=frames,scores=scores,sectors={'SPY':'ETF','TEST':'Industrials'},
        macro=ArchivedMacro(macro),market_config=study.grid.parse_market_regimes({'enabled':False}),
        policy='keep',variant='CURRENT_NO_EXPIRY',output=tmp_path,start_date='2024-01-02',end_date=terminal,
        decision_end_date='2024-01-02',quality=quality,ledger_factory=factory,
        session_factory=partial(study.grid.MarginAwareSession,ledger_ref=refs),
        expiry_open_sessions=None if hook else holding,protection_options=dict(take_profit_enabled=True,trailing_enabled=False),
        reject_constrained_entries=True,daily_exit_policy=study.grid.margin_policy)
    return result,refs[0],pd.read_parquet(tmp_path/'daily.parquet'),pd.read_parquet(tmp_path/'trades.parquet')


def test_expiry_hook_matches_existing_native_loop(tmp_path):
    old=native_case(tmp_path/'old',False,'2024-01-10')
    new=native_case(tmp_path/'new',True,'2024-01-10')
    assert len(new[3])>0,'test requires actual entries, not two empty portfolios'
    pd.testing.assert_frame_equal(old[2],new[2])
    pd.testing.assert_frame_equal(old[3],new[3])
    assert not new[1].state.positions and new[1].expiry_audits


def test_unfinished_holding_stays_open_and_is_marked_not_sold(tmp_path):
    result,ledger,daily,trades=native_case(tmp_path/'mtm',True,'2024-01-04',holding=20)
    assert ledger.state.positions and trades.empty
    summary=study.summarize(result,ledger,daily,trades,2024,'2024-01-04')
    assert summary['status']=='COMPLETED_EXPLORATORY_OPEN_MTM'
    assert len(summary['open_positions'])==1 and summary['closed_positions']==0
    assert summary['final_capital_usd']==pytest.approx(4000+summary['unrealized_pnl_usd']-ledger.interest)
