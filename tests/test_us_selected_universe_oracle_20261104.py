import numpy as np
import pandas as pd

from scripts.research.us_selected_universe_oracle_20261104 import (
    POLICY, freeze_top, replay, split_year)


def fixture(n=9):
    days = pd.bdate_range('2024-01-02', periods=n)
    p = np.tile([100., 101., 99., 100.], (n, 1))
    prices = {'AAA': (p, np.ones(n, dtype=bool), np.ones(n), np.array(['sip']*n))}
    top = pd.DataFrame(dict(date=[days[0]], symbol=['AAA'], score=[.9], oracle_rank=[1]))
    return days, prices, top


def test_chronological_purge_and_inference_without_future_label():
    d = pd.DataFrame(dict(date=pd.to_datetime(['2022-12-01','2022-12-30','2023-11-01','2023-12-29','2024-01-02']),
        oracle_available_date=pd.to_datetime(['2022-12-20','2023-01-10','2023-11-20','2024-01-15',None]),
        target=[1.,0.,0.,1.,np.nan]))
    fit, val, test = split_year(d, 2024, 'target')
    assert fit.date.tolist()==[pd.Timestamp('2022-12-01')]
    assert val.date.tolist()==[pd.Timestamp('2023-11-01')]
    assert len(test)==1 and test.target.isna().all()


def test_top5_priority_is_independent_of_realised_labels():
    scores=pd.DataFrame(dict(date=[pd.Timestamp('2024-01-02')]*7,
        symbol=list('ABCDEFG'),score=[.3,.5,.9,.8,.8,.2,.1],future_label=[0]*7))
    first=freeze_top(scores)
    scores.future_label=1
    assert first.symbol.tolist()==freeze_top(scores).symbol.tolist()==list('CDEBA')


def test_next_open_expiry_and_cost_cash_identity():
    days, prices, top=fixture()
    result, daily, trades, audit=replay(top,prices,days,days[0],days[-1],2)
    assert len(trades)==1 and trades.iloc[0].entry_date==days[1]
    assert trades.iloc[0].exit_date==days[3] and trades.iloc[0].reason=='TIME_OPEN'
    assert trades.iloc[0].holding_sessions==2
    assert trades.iloc[0].entry_price==100. and trades.iloc[0].exit_price==100.
    assert result['final_equity'] < POLICY['initial_equity']
    assert np.isclose(result['final_equity']-4000.,trades.pnl.sum())
    assert np.isclose(result['estimated_transaction_costs'],-trades.pnl.sum())
    assert (daily.cash>=0).all() and (daily.gross<=daily.equity).all()


def test_overnight_stop_gap_fills_worse_open():
    days, prices, top=fixture()
    prices['AAA'][0][2]=[90.,91.,89.,90.]
    result, daily, trades, audit=replay(top,prices,days,days[0],days[-1],5)
    assert trades.iloc[0].reason=='SL_GAP' and trades.iloc[0].exit_price==90.


def test_entry_session_stop_is_active():
    days, prices, top=fixture()
    prices['AAA'][0][1,2]=94.
    result, daily, trades, audit=replay(top,prices,days,days[0],days[-1],5)
    assert trades.iloc[0].reason=='SL' and trades.iloc[0].exit_price==95.
    assert trades.iloc[0].holding_sessions==1


def test_missing_window_excludes_one_entry_date_not_whole_symbol():
    days, prices, top=fixture(12)
    prices['AAA'][1][2]=False
    top=pd.concat([top,pd.DataFrame(dict(date=[days[4]],symbol=['AAA'],score=[.8],oracle_rank=[1]))],ignore_index=True)
    result, daily, trades, audit=replay(top,prices,days,days[0],days[-1],3)
    assert result['excluded_missing_entry_days']==1
    assert result['buys']==1 and trades.iloc[0].entry_date==days[5]
    assert '2024-01-04' in audit[audit.status.eq('INCOMPLETE_OBSERVED_HOLDING_WINDOW')].iloc[0].missing_dates


def test_open_positions_are_marked_not_forced_closed():
    days, prices, top=fixture()
    result, daily, trades, audit=replay(top,prices,days,days[0],days[3],10)
    assert trades.empty and result['final_positions']==1
    assert result['no_forced_terminal_liquidation']


def test_intraday_stop_proceeds_do_not_fund_opening_buy():
    days, prices, top=fixture()
    p,good,identity,source=prices['AAA']
    prices['BBB']=(p.copy(),good.copy(),identity.copy(),source.copy())
    prices['AAA'][0][2,2]=90.
    top=pd.concat([top,pd.DataFrame(dict(date=[days[1]],symbol=['BBB'],score=[.8],oracle_rank=[1]))],ignore_index=True)
    policy=dict(POLICY,max_position_weight=1.,risk_per_trade_pct=1.)
    result, daily, trades, audit=replay(top,prices,days,days[0],days[-1],5,policy=policy)
    assert result['buys']==1
    assert audit[audit.symbol.eq('BBB')].iloc[0].status=='INSUFFICIENT_CASH_OR_SIZING'
