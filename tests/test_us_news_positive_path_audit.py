import numpy as np
import pandas as pd
from scripts.research.us_news_positive_path_audit import aggregate_news, price_paths, metrics
from modelFactory.oracle.security_continuity import SecurityDiscontinuity


def test_all_articles_and_every_session_required():
    days = pd.bdate_range('2025-01-01', periods=4)
    news = pd.DataFrame(dict(article_id=['a','b','c','d'], symbol=['A']*4,
        published_at_utc=['2025-01-01 18:00Z','2025-01-01 19:00Z','2025-01-02 18:00Z','2025-01-06 18:00Z'],
        positive_score=[.99,.89,.96,.97],available_at=['2025-01-01 20:00Z']*4))
    groups, _ = aggregate_news(news, days)
    assert not groups.loc[0,'strong_1']  # max .99 cannot hide .89
    assert groups.loc[1,'strong_1']
    assert not groups.loc[1,'strong_2']
    assert not groups.loc[3,'strong_2']  # no article on preceding session
    assert groups.loc[2,'strong_lag_1']  # yesterday alone, despite no article today
    assert groups.loc[3,'strong_lag_2']


def bars(days):
    return pd.DataFrame(dict(date=days, open=100., high=101., low=99., close=100.,
        volume=1000., instrument_id='1',is_filled=0,data_adjustment='split'))


def test_peak_during_path_not_terminal_and_exact_window():
    days = pd.bdate_range('2025-01-01', periods=23)
    frame = bars(days)
    frame.loc[9,'high'] = 125.
    frame.loc[20,['close','low']] = [95.,94.]
    frame.loc[21,'high'] = 180.  # beyond J+20: excluded for J
    result = price_paths(frame,days)
    assert result.loc[0,'h0_h20_max_up_pct'] == 25.
    assert np.isclose(result.loc[0,'h0_h20_terminal_pct'],-5.)
    assert np.isclose(result.loc[0,'h1_h20_max_up_pct'],25.)
    assert not result.loc[3,'h0_h20_mature']
    assert np.isnan(result.loc[3,'h0_h20_max_up_pct'])


def test_h0_prepublication_peak_not_used_by_next_open_view():
    days = pd.bdate_range('2025-01-01',periods=22)
    frame = bars(days)
    frame.loc[0,'high']=130.
    result=price_paths(frame,days)
    assert np.isclose(result.loc[0,'h0_h20_max_up_pct'],30.)
    assert np.isclose(result.loc[0,'h1_h20_max_up_pct'],1.)


def test_missing_or_changed_identity_excludes_whole_path():
    days = pd.bdate_range('2025-01-01',periods=22)
    frame = bars(days)
    frame.loc[10,'instrument_id'] = '2'
    assert not price_paths(frame,days).loc[0,'h0_h20_qualified']
    frame.loc[10,'instrument_id'] = None
    assert not price_paths(frame,days).loc[0,'h1_h20_qualified']
    frame=bars(days).drop(index=10)
    assert not price_paths(frame,days).loc[0,'h1_h20_qualified']


def test_strict_threshold_not_inclusive():
    days=pd.bdate_range('2025-01-01',periods=1)
    news=pd.DataFrame(dict(article_id=['a'],symbol=['A'],published_at_utc=['2025-01-01 18:00Z'],
        positive_score=[.9],available_at=[None]))
    result,_=aggregate_news(news,days)
    assert not result.loc[0,'strong_1']
    assert not result.loc[0,'known_1']


def test_empty_metrics_do_not_fabricate_zero_success():
    frame=pd.DataFrame(columns=['date','symbol','h1_h20_max_up_pct','h1_h20_terminal_pct','h1_h20_min_down_pct'])
    assert metrics(frame,'h1_h20')['reached_pct']['20'] is None


def test_day0_bad_bar_does_not_invalidate_post_day0_path():
    days=pd.bdate_range('2025-01-01',periods=22)
    frame=bars(days)
    frame.loc[0,'is_filled']=1
    result=price_paths(frame,days)
    assert not result.loc[0,'h0_h20_qualified']
    assert result.loc[0,'h1_h20_qualified']


def test_registered_break_excluded_even_when_instrument_id_unchanged():
    days=pd.bdate_range('2025-01-01',periods=22)
    event=SecurityDiscontinuity('A',days[8],days[9],'known_alias_break')
    result=price_paths(bars(days),days,[event])
    assert not result.loc[0,'h0_h20_qualified']


def test_publication_day_is_new_york_not_utc():
    days=pd.bdate_range('2025-01-01',periods=3)
    news=pd.DataFrame(dict(article_id=['a'],symbol=['A'],published_at_utc=['2025-01-02 01:00Z'],
        positive_score=[.95],available_at=['2025-01-02 02:00Z']))
    result,_=aggregate_news(news,days)
    assert result.loc[0,'strong_1']
    assert not result.loc[1,'strong_1']


def test_friday_lag_used_on_monday_and_missing_score_fails():
    days=pd.bdate_range('2025-01-03',periods=2)
    news=pd.DataFrame(dict(article_id=['a','b'],symbol=['A']*2,
        published_at_utc=['2025-01-03 18:00Z','2025-01-06 18:00Z'],
        positive_score=[.99,np.nan],available_at=['2025-01-03 20:00Z']*2))
    result,_=aggregate_news(news,days)
    assert result.loc[1,'strong_lag_1']
    assert not result.loc[1,'strong_1']
    assert not result.loc[1,'strong_2']
