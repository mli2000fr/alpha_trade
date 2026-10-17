"""Offline matched LONG policies; no GPT, SQL, training, or orders."""
import hashlib
import pandas as pd
import pytest

from scripts.research import us_news_gpt_long_comparison as study
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config


def test_only_selection_differs_and_unfiltered_keeps_unknown_opinions():
    panel=pd.DataFrame([dict(date=pd.Timestamp('2025-01-02'),symbol=str(i),decision=decision,
        technical_status=status,selected=selected,score=.99-i*.01,proba_extreme=.99-i*.01,confidence=confidence)
        for i,(decision,status,selected,confidence) in enumerate([
            ('BEARISH','VALID',True,.67),('BULLISH','VALID',True,.62),('ABSTAIN','VALID',True,.95),
            ('UNKNOWN_NO_QUALIFIED_TEXT',None,True,None),('BEARISH','INVALID',True,.99),
            ('BEARISH','VALID',False,.99),('BULLISH','VALID',False,.99)])])
    original=panel.copy(deep=True);result=study.add_policies(panel)
    assert result.GPT_BEARISH_AS_LONG.tolist()==[True,False,False,False,False,False,False]
    assert result.GPT_BULLISH_AS_LONG.tolist()==[False,True,False,False,False,False,False]
    assert result.ORACLE_TOP20_ALL_LONG.tolist()==[True,True,True,True,True,False,False]
    pd.testing.assert_frame_equal(panel,original)
    pd.testing.assert_series_equal(result.score,panel.score);pd.testing.assert_series_equal(result.proba_extreme,panel.proba_extreme)


def test_duplicate_candidates_are_rejected():
    panel=pd.DataFrame([dict(date='2025-01-02',symbol='TEST',decision='BULLISH',technical_status='VALID',selected=True)]*2)
    with pytest.raises(ValueError,match='Duplicate'):study.add_policies(panel)


def test_only_proven_python_crlf_equivalence_is_allowed(tmp_path):
    original=b'answer = 42\nprint(answer)\n';expected=hashlib.sha256(original).hexdigest()
    path=tmp_path/'frozen.py';path.write_bytes(original.replace(b'\n',b'\r\n'))
    current,equivalence=study.verify_original_sources({str(path):expected})
    assert current[str(path)]==hashlib.sha256(path.read_bytes()).hexdigest()
    assert equivalence[0]['normalized_lf_sha256']==expected
    path.write_bytes(b'answer = 43\r\nprint(answer)\r\n')
    with pytest.raises(ValueError,match='content changed'):study.verify_original_sources({str(path):expected})
    data=tmp_path/'config.yaml';data.write_bytes(original.replace(b'\n',b'\r\n'))
    with pytest.raises(ValueError,match='content changed'):study.verify_original_sources({str(data):expected})


def test_control_uses_exact_same_native_long_ledger_and_risk_formula():
    days=pd.bdate_range('2023-01-02','2024-01-12');close=pd.DataFrame({'SPY':400.,'TEST':20.},index=days)
    frames=dict(opens=close,close=close.copy(),high=close*1.01,low=close*.99,
        volume=pd.DataFrame(10000000.,index=days,columns=close.columns))
    quality=pd.DataFrame([dict(date=d,symbol=s,is_filled=0,instrument_id=i+1) for d in days for i,s in enumerate(close)])
    cfg=frozen_backtest_config('2024-01-02','2024-01-10');refs=[]
    ledger=study.make_ledger(cfg,dict(events=[]),quality,refs,terminal='2024-01-10',sector_map={'SPY':'ETF','TEST':'Industrials'},**frames)
    assert type(ledger) is study.base.native.ExpiryMarkLedger and refs==[ledger]
    assert ledger.tp_pct==.1 and ledger.sl_pct==.1 and ledger.trail is None
    assert ledger.holding_sessions==20 and cfg.risk_config.fixed_stop_pct==.1
    assert cfg.risk_config.risk_per_trade_pct==pytest.approx(.04)
    assert cfg.risk_config.max_gross_exposure==2. and cfg.margin_interest_rate_annual==.065
