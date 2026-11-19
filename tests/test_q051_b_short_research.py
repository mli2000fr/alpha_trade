"""Frozen SHORT ranking and independent daily capital replay qualification."""
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from scripts.research.us_q051_b_short_20261118 import rank_short
from scripts.research.us_q051_b_short_replay_20261118 import DailyShortReplay, config
from common.market_calendar import get_market_calendar


def test_short_top10_before_thresholds_and_no_refill_from_rank11_or_outside_oracle():
    dates = pd.Timestamp('2025-01-02')
    oracle = pd.DataFrame(dict(date=dates, symbol=[f'S{i:03}' for i in range(200)], proba_extreme=np.linspace(.99,.01,200)))
    probabilities = oracle[['date','symbol']].copy()
    probabilities['short_probability'] = np.linspace(.99,.51,200)
    probabilities['short_auc'] = .6;probabilities['short_available'] = pd.Timestamp('2024-12-31')
    probabilities.loc[0,'short_auc'] = .49
    probabilities.loc[179:,'short_probability'] = 1.
    out = rank_short(oracle, probabilities)
    assert out[out.selected].symbol.tolist() == [f'S{i:03}' for i in range(1,10)]
    assert not out[out.selected].symbol.eq('S010').any()
    assert out[out.selected].side.eq('short').all()
    probabilities.loc[1,'short_available'] = dates
    with pytest.raises(ValueError, match='future'):
        rank_short(oracle, probabilities)


def fixture(*, ending='2025-01-22', stop_high=None, gap=None, borrow=.03):
    sessions = [s for s in get_market_calendar('US_EQ', allow_us_weekday_fallback=False).sessions(
        date(2024,12,31), date.fromisoformat(ending)) if s.is_open]
    index = pd.DatetimeIndex([s.session_date for s in sessions])
    pivots = {c: pd.DataFrame({'TEST': np.full(len(index), value)}, index=index)
              for c,value in [('open',100.),('high',101.),('low',99.),('close',100.),('volume',100000.)]}
    if stop_high:
        day, price = stop_high;pivots['high'].at[pd.Timestamp(day),'TEST'] = price
    if gap:
        day, price = gap
        for c in ['open','high','low','close']:
            pivots[c].at[pd.Timestamp(day),'TEST'] = price
    signals = pd.DataFrame([dict(date=pd.Timestamp('2024-12-31'), symbol='TEST', rank=1, short_probability=.8)])
    cfg = replace(config(), start_date=date(2025,1,1), end_date=date.fromisoformat(ending))
    actions = pd.DataFrame(columns=['symbol','ca_type','ex_date','payable_date','amount_per_share','currency'])
    return DailyShortReplay(pivots, {'TEST':'Tech'}, actions, signals, sessions, cfg, borrow)


def test_direct_entry_j_plus1_exit_open11_and_fees_borrow_reconcile():
    replay = fixture().run()
    assert len(replay.book.trades) == 1
    t = replay.book.trades[0]
    assert t['entry_date'].date() == date(2025,1,2) and t['exit_reason'] == 'HORIZON_OPEN'
    start = replay.calendar.get_loc(pd.Timestamp(t['entry_date'].date()))
    end = replay.calendar.get_loc(pd.Timestamp(t['exit_date'].date()))
    assert end-start == 10 and t['side'] == 'sell' and t['quantity'] == 8
    assert t['borrow_fees'] == pytest.approx(8*100*.03/252*11)
    assert t['pnl'] == pytest.approx(-1.28-t['borrow_fees'])
    assert replay.book.equity() == pytest.approx(4000+t['pnl'])
    assert not replay.book.positions()


def test_short_stop_on_first_entry_session_and_adverse_gap_are_not_capped_at5percent():
    r = fixture(stop_high=('2025-01-02',106.)).run()
    assert r.book.trades[0]['exit_price'] == 105. and r.book.trades[0]['exit_reason'] == 'STOP'
    assert r.book.trades[0]['entry_date'].date() == r.book.trades[0]['exit_date'].date()
    r = fixture(gap=('2025-01-03',130.)).run()
    assert r.book.trades[0]['exit_price'] == 130. and r.book.trades[0]['exit_reason'] == 'STOP_GAP'
    assert r.book.trades[0]['pnl'] < -240.


def test_future_daily_bars_cannot_change_an_earlier_entry():
    first = fixture();second = fixture()
    for c in ['open','high','low','close']:
        second.pivots[c].loc['2025-01-06':,'TEST'] *= 1.2
    a = first.run();b = second.run()
    assert a.entries == b.entries
    assert a.curve[:2] == b.curve[:2]


def test_open_short_marks_have_correct_sign_and_no_sale_proceeds_create_equity():
    r = fixture(ending='2025-01-03', borrow=0)
    for c in ['open','high','low','close']:
        r.pivots[c].at[pd.Timestamp('2025-01-03'),'TEST'] = 90.
    r.run()
    assert r.book.positions()[0]['side'] == 'short'
    assert r.book.equity() == pytest.approx(4000-.64+80)
    assert r.book.gross() == 720
    assert r.book.financing_balance() == pytest.approx(3999.36)


def test_known_dividend_is_owed_by_short_and_counted_once():
    r = fixture()
    r.actions = pd.DataFrame([dict(symbol='TEST', ca_type='cash_dividend', ex_date='2025-01-03',
        payable_date='2025-01-10', amount_per_share=1., currency='USD')])
    r.run();t = r.book.trades[0]
    assert t['dividends'] == -8
    assert r.book.equity() == pytest.approx(4000+t['pnl'])


def test_missing_future_holding_price_is_an_error_not_a_free_unchanged_mark():
    r = fixture()
    r.pivots['close'].at[pd.Timestamp('2025-01-03'),'TEST'] = np.nan
    with pytest.raises(ValueError, match='Unqualified'):
        r.run()


def test_entry_does_not_consult_same_day_high_or_close_before_sizing():
    a = fixture();b = fixture()
    b.pivots['high'].at[pd.Timestamp('2025-01-02'),'TEST'] = 110.
    b.pivots['close'].at[pd.Timestamp('2025-01-02'),'TEST'] = 107.
    a.run();b.run()
    assert a.entries[0] == b.entries[0]


def test_missing_entry_day_later_range_is_not_used_as_a_pre_entry_filter():
    r = fixture()
    r.pivots['close'].at[pd.Timestamp('2025-01-02'),'TEST'] = np.nan
    with pytest.raises(ValueError, match='Unqualified'):
        r.run()
    assert len(r.entries) == 1 and r.entries[0]['entry_price'] == 100.


def test_short_sale_cash_cannot_fund_more_than_native_one_times_equity():
    r = fixture(ending='2025-01-03', borrow=0)
    for frame in r.pivots.values():
        for i in range(8):frame['X'+str(i)] = frame.TEST
    r.signals = pd.DataFrame([dict(date=pd.Timestamp('2024-12-31'),symbol='X'+str(i),
        rank=i+1,short_probability=.9) for i in range(8)])
    r.run()
    assert r.book.cash > 7000 and r.book.gross() < 4000 and r.book.equity() < 4000
    for entry in r.entries:
        assert entry['gross_before']+entry['quantity']*entry['entry_price'] <= entry['equity_before']+1e-7
        assert entry['quantity']*entry['entry_price'] <= entry['equity_before']*.2+1e-7


def test_report_drawdown_includes_initial_capital_before_first_loss():
    from scripts.research.us_q051_b_short_report_20261118 import curve_metrics
    result = curve_metrics(pd.Series([3900.,4100.,3600.]))
    assert result['return_pct'] == pytest.approx(-10.)
    assert result['daily_close_dd_pct'] == pytest.approx(100*(3600/4100-1))
    assert curve_metrics(pd.Series([3000.]))['daily_close_dd_pct'] == -25.
