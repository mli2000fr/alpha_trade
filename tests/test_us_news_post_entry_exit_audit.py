from types import SimpleNamespace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from scripts.research.us_news_post_entry_exit_audit import NewsSignals, MODES, resolve_exit, frozen_curve


def sessions():
    return [SimpleNamespace(is_open=True,session_date=date(2025,1,d),
        open_at_utc=pd.Timestamp(f'2025-01-{d:02} 14:30Z'),
        close_at_utc=pd.Timestamp(f'2025-01-{d:02} 21:00Z')) for d in (3,6,7)]


def news(times, positive=None, negative=None, available=None):
    n=len(times)
    return pd.DataFrame(dict(symbol=['A']*n,published_at_utc=times,
        available_at=available or times,positive_score=positive or [.01]*n,
        negative_score=negative or [.99]*n))


def test_all_articles_not_max_and_news_after_entry_only():
    f=news(['2025-01-03 12:00Z','2025-01-03 18:00Z','2025-01-03 19:00Z'],negative=[.99,.99,.8])
    signals=NewsSignals(f,sessions(),MODES[0])
    result=signals.get(pd.Timestamp('2025-01-03'),'A',pd.Timestamp('2025-01-03'))
    assert result['label']=='OTHER'
    assert result['articles']==2  # pre-entry article excluded


def test_afterhours_weekend_and_at_close_wait_until_next_close():
    f=news(['2025-01-03 21:00Z','2025-01-04 18:00Z'])
    signals=NewsSignals(f,sessions(),MODES[0])
    assert signals.get(pd.Timestamp('2025-01-03'),'A',pd.Timestamp('2025-01-03'))['label']=='NONE'
    result=signals.get(pd.Timestamp('2025-01-06'),'A',pd.Timestamp('2025-01-03'))
    assert result['label']=='NEGATIVE'
    assert result['articles']==2


def test_availability_guard_does_not_backdate_score():
    f=news(['2025-01-03 18:00Z'],available=['2025-01-06 19:00Z'])
    signals=NewsSignals(f,sessions(),MODES[1])
    assert signals.get(pd.Timestamp('2025-01-03'),'A',pd.Timestamp('2025-01-03'))['label']=='NONE'
    assert signals.get(pd.Timestamp('2025-01-06'),'A',pd.Timestamp('2025-01-03'))['label']=='NEGATIVE'


def test_positive_news_confirm_keep_label_without_changing_protections():
    f=news(['2025-01-03 18:00Z'],positive=[.99],negative=[.01])
    result=NewsSignals(f,sessions(),MODES[0]).get(pd.Timestamp('2025-01-03'),'A',pd.Timestamp('2025-01-03'))
    assert result['label']=='POSITIVE'


def test_future_article_not_visible_at_earlier_close():
    f=news(['2025-01-06 18:00Z'])
    result=NewsSignals(f,sessions(),MODES[0]).get(pd.Timestamp('2025-01-03'),'A',pd.Timestamp('2025-01-03'))
    assert result['label']=='NONE'


def test_strict_threshold_and_midnight_uncertain_excluded():
    f=news(['2025-01-03 18:00Z','2025-01-04 00:00Z'],negative=[.9,.99])
    signals=NewsSignals(f,sessions(),MODES[0])
    assert signals.ambiguous_excluded==1
    assert signals.get(pd.Timestamp('2025-01-03'),'A',pd.Timestamp('2025-01-03'))['label']=='OTHER'


def trade(**overrides):
    row=dict(entry_date=pd.Timestamp('2025-01-03'),exit_date=pd.Timestamp('2025-01-07'),
        entry_price=100.,exit_price=90.,quantity=1.,entry_cost=100.,proceeds=90.,side='buy',symbol='A',
        replay_initial_stop_price=90.,replay_take_profit_price=120.,exit_reason='initial_stop')
    row.update(overrides)
    return SimpleNamespace(**row)


def test_stop_gap_first_and_expiry_first():
    t=trade(exit_reason='initial_stop_gap_open',exit_price=85.)
    result=resolve_exit(t,pd.Timestamp('2025-01-06'),pd.Timestamp('2025-01-07'),85.)
    assert result['priority']=='NATIVE_OPEN_FIRST'
    assert result['price']==85.
    t=trade(exit_reason='expiry_open',exit_price=101.)
    assert resolve_exit(t,pd.Timestamp('2025-01-06'),pd.Timestamp('2025-01-07'),101.)['priority']=='NATIVE_OPEN_FIRST'


def test_news_exit_at_open_before_later_intraday_stop():
    t=trade()
    result=resolve_exit(t,pd.Timestamp('2025-01-06'),pd.Timestamp('2025-01-07'),98.)
    assert result['price']==98.
    assert result['reason']=='news_negative_next_open'


def test_profit_gap_has_priority_and_unconsumed_gap_fails_closed():
    t=trade(exit_reason='take_profit_gap_limit',exit_price=120.)
    result=resolve_exit(t,pd.Timestamp('2025-01-06'),pd.Timestamp('2025-01-07'),130.)
    assert result['priority']=='NATIVE_OPEN_FIRST'
    assert result['price']==120.
    with pytest.raises(ValueError,match='not consumed'):
        resolve_exit(trade(),pd.Timestamp('2025-01-03'),pd.Timestamp('2025-01-06'),85.)


def test_closed_position_not_resurrected():
    with pytest.raises(ValueError,match='surviving'):
        resolve_exit(trade(),pd.Timestamp('2025-01-07'),pd.Timestamp('2025-01-08'),100.)


def test_counterfactual_curve_same_entry_and_cash_not_reinvested():
    t=trade()
    rows=pd.DataFrame([vars(t)])
    days=pd.DatetimeIndex(['2025-01-03','2025-01-06','2025-01-07'])
    daily=pd.DataFrame({'date':days})
    bars={'A':pd.DataFrame({'close':[100.,98.,90.]},index=days)}
    base,metrics=frozen_curve(rows,daily,bars,{})
    assert metrics['capital_final_usd']==3990.
    changed,m=frozen_curve(rows,daily,bars,{0:dict(date=days[1],proceeds=98.,reason='news_negative_next_open')})
    assert m['capital_final_usd']==3998.
    assert changed.positions.tolist()==[1,0,0]
    assert np.isclose(changed.cash.iloc[0],base.cash.iloc[0])
