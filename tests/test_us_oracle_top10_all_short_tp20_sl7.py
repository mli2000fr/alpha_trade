from dataclasses import replace
from functools import partial

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_top10_all_short_tp20_sl7 as study
from scripts.research.us_concentrated_live_portfolio import run_portfolio,ArchivedMacro


def panel():
    return pd.DataFrame([dict(date=pd.Timestamp('2024-01-02'),symbol=f'S{i:02}',score=1-i/100,
        oracle_rank=i,fold_start='2023-01-01',model_available_date='2023-12-01',model_sha256='model',
        feature_profile_sha256='profile',batch_id=study.source.MODELS[2024],selected=i!=1,
        entry_quality_reason='REJECTED_J' if i==1 else 'OK',future_return=i,decision='BULLISH',
        confidence=.99,oracle_extreme10=True) for i in range(1,21)])


def test_top10_original_order_no_gpt_future_fields_or_replacement():
    raw=panel();result=study.freeze_top10(raw)
    assert result.symbol.tolist()==[f'S{i:02}' for i in range(1,11)]
    assert result[study.POLICY].sum()==9 and not result.iloc[0][study.POLICY]
    assert all(k not in result for k in ('future_return','decision','confidence','oracle_extreme10'))
    raw.future_return=-1e6;raw.decision='BEARISH';raw.confidence=0
    pd.testing.assert_frame_equal(result,study.freeze_top10(raw))


@pytest.mark.parametrize('fault',['rank','availability','model','duplicate'])
def test_incomplete_or_noncausal_archive_rejected(fault):
    values=panel()
    if fault=='rank':values.loc[0,'oracle_rank']=21
    if fault=='availability':values.loc[0,'model_available_date']='2024-01-03'
    if fault=='model':values.loc[0,'batch_id']='wrong'
    if fault=='duplicate':values=pd.concat([values,values.iloc[:1]],ignore_index=True)
    with pytest.raises(ValueError):study.freeze_top10(values)


def replay(tmp_path,*,high=101.,low=99.,last='2024-01-10',holding=2,signals=1):
    days=pd.bdate_range('2023-01-02','2024-01-12')
    close=pd.DataFrame({'TEST':100.,'SPY':400.},index=days)
    highs=close*1.01;lows=close*.99
    highs.loc['2024-01-03','TEST']=high;lows.loc['2024-01-03','TEST']=low
    frames=dict(opens=close.copy(),close=close.copy(),high=highs,low=lows,
        volume=pd.DataFrame(1e7,index=days,columns=close.columns))
    quality=pd.DataFrame([dict(date=d,symbol=s,is_filled=0,instrument_id=i+1) for d in days for i,s in enumerate(close)])
    dates=[pd.Timestamp('2024-01-02')+pd.offsets.BDay(i) for i in range(signals)]
    scores=pd.DataFrame([dict(date=d,symbol='TEST',proba_extreme=.99,keep=True) for d in dates])
    macro=pd.DataFrame(dict(trade_date=days,vix=12.,vix9d=11.,vxn=16.,vix3m=15.,move=70.,rvx=16.,ten_y=4.,sentiment_score=0.))
    refs=[]
    def factory(cfg,**kwargs):
        ledger=study.Top10ShortLedger(cfg,quality=quality,study_end=last,holding_sessions=holding,events=[],**kwargs)
        refs.append(ledger);return ledger
    result=run_portfolio(frames=frames,scores=scores,sectors={'TEST':'Industrials','SPY':'ETF'},
        macro=ArchivedMacro(macro),market_config=study.source.grid.parse_market_regimes({'enabled':False}),
        policy='keep',variant='CURRENT_NO_EXPIRY',output=tmp_path,start_date='2024-01-02',end_date=last,
        decision_end_date=str(dates[-1].date()),quality=quality,ledger_factory=factory,
        session_factory=partial(study.Top10ShortSession,ledger_ref=refs,study_arm=study.POLICY),
        reject_constrained_entries=True,protection_options=dict(take_profit_enabled=True,trailing_enabled=False),
        research_allow_short_normal=True,daily_exit_policy=study.short.margin_policy)
    daily=pd.read_parquet(tmp_path/'daily.parquet');trades=pd.read_parquet(tmp_path/'trades.parquet')
    bars=pd.concat([v.stack().rename(k) for k,v in [('open',frames['opens']),('high',highs),('low',lows),('close',close)]],axis=1)
    bars=bars.reset_index().rename(columns={'level_0':'date','level_1':'symbol'})
    return result,refs[0],daily,trades,bars,days


def test_native_short_sl7_tp20_actual_fill_and_integer_quantity(tmp_path):
    result,ledger,daily,trades,bars,days=replay(tmp_path)
    assert len(trades)>0 and trades.side.eq('sell').all()
    assert np.allclose(trades.replay_initial_stop_price,trades.entry_price*1.07)
    assert np.allclose(trades.replay_take_profit_price,trades.entry_price*.80)
    assert np.allclose(trades.quantity,trades.quantity.round())
    assert ledger.reconciliation_error()==pytest.approx(0,abs=1e-6)
    assert ledger.config.exec_config.leverage.max_leverage==2


def test_ohlc_collision_uses_stop_not_tp(tmp_path):
    *_,trades,bars,days=replay(tmp_path,high=110.,low=75.)
    assert len(trades)>0 and trades.iloc[0].exit_reason=='initial_stop'
    assert trades.iloc[0].exit_price==pytest.approx(trades.iloc[0].entry_price*1.07)


def test_open_short_sale_credit_is_not_profit_and_fee_deducted(tmp_path):
    result,ledger,daily,trades,bars,days=replay(tmp_path,last='2024-01-04',holding=20)
    assert ledger.state.positions and trades.empty
    summary=study.summarize(result,ledger,daily,trades,bars,days,2024,'2024-01-04')
    assert summary['final_capital_usd']<4000 and summary['accrued_open_borrow_usd']>0
    assert summary['calendar_end_capital_usd']==pytest.approx(summary['final_capital_usd'])


def test_held_symbol_is_not_reinforced(tmp_path):
    result,ledger,daily,trades,bars,days=replay(tmp_path,last='2024-01-05',holding=20,signals=3)
    assert len(ledger.state.positions)==1
    executions=study.source.read(tmp_path/'executions.json')
    assert sum(len(a['opened']) for a in executions)==1
