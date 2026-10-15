"""No SQL/API; confidence bins use initial signal, group partial exits, exclude open lots."""
import pandas as pd
import pytest

from scripts.research.us_news_gpt_confidence_analysis import confidence_bins,metrics,position_rows


def test_bins_are_left_inclusive_and_exact_thresholds():
    assert confidence_bins(pd.Series([0.,.6999,.7,.7999,.8,.8999,.9,.9499,.95,1.])).tolist()==[
        '<0.70','<0.70','0.70-<0.80','0.70-<0.80','0.80-<0.90','0.80-<0.90',
        '0.90-<0.95','0.90-<0.95','0.95-1.00','0.95-1.00']


@pytest.mark.parametrize('bad',[None,float('nan'),float('inf'),-.01,1.01])
def test_bad_confidence_not_silently_binned(bad):
    with pytest.raises((TypeError,ValueError)):confidence_bins(pd.Series([bad]))


def test_partial_exits_count_once_and_open_lot_not_as_win():
    panel=pd.DataFrame([dict(date=pd.Timestamp('2025-01-02'),symbol='TEST',decision='BULLISH',
        technical_status='VALID',confidence=.9,cache_key='saved',oracle_rank=2)])
    trades=pd.DataFrame([dict(symbol='TEST',side='buy',signal_date=pd.Timestamp('2025-01-02'),quantity=1.,
        entry_date=pd.Timestamp('2025-01-03'),exit_date=pd.Timestamp(day),entry_price=100.,pnl=pnl)
        for day,pnl in [('2025-01-06',10.),('2025-01-07',-5.)]])
    positions=position_rows(trades,panel,[],year=2025,side='LONG')
    assert len(positions)==1 and positions.iloc[0].closed
    summary=metrics(positions)
    assert summary['n']==1 and summary['wins']==1 and summary['net_pnl_usd']==5.
    assert summary['mean_net_trade_return_pct']==pytest.approx(2.5)
    assert positions.iloc[0].confidence_bin=='0.90-<0.95'
    open_rows=position_rows(trades,panel,[dict(symbol='TEST',entry_date='2025-01-03')],year=2025,side='LONG')
    assert not open_rows.iloc[0].closed


def test_short_returns_use_entry_notional_not_reciprocal():
    panel=pd.DataFrame([dict(date=pd.Timestamp('2025-01-02'),symbol='TEST',decision='BEARISH',
        technical_status='VALID',confidence=.96,cache_key='saved',oracle_rank=1)])
    trades=pd.DataFrame([dict(symbol='TEST',side='sell',signal_date=pd.Timestamp('2025-01-02'),quantity=2.,
        entry_date=pd.Timestamp('2025-01-03'),exit_date=pd.Timestamp('2025-01-06'),entry_price=100.,pnl=39.,borrow_cost=1.)])
    result=position_rows(trades,panel,[],year=2025,side='SHORT')
    assert result.iloc[0].net_trade_return_pct==pytest.approx(19.5)
    assert metrics(result)['borrow_usd']==1.
