from datetime import datetime,timezone
from types import SimpleNamespace
import pandas as pd
from scripts.research.us_news_intraday_audit import prepare_news,valid_bars,event_returns,NS_MINUTE


def prices():
    start=pd.Timestamp('2025-01-02T14:30:00Z')
    return pd.DataFrame([dict(symbol='ABC',trade_date=start.date(),bar_timestamp=(start+pd.Timedelta(minutes=5*i)),
        bar_end_timestamp=start+pd.Timedelta(minutes=5*i+5),open=100,high=102,low=99,close=101,volume=100,
        is_filled=0,data_adjustment='raw',session_tag='regular') for i in range(20)])


def test_news_return_starts_after_publication_with_buffer():
    pub=pd.Timestamp('2025-01-02T14:31:00Z').value
    events=pd.DataFrame([dict(symbol='ABC',day=datetime(2025,1,2).date(),pub_ns=pub,group='positive_only',
        bucket='regular',articles=1,available_ns=pub,open_ns=pd.Timestamp('2025-01-02T14:30:00Z').value,
        close_ns=pd.Timestamp('2025-01-02T21:00:00Z').value)])
    result=event_returns(events,valid_bars(prices()))
    assert result.iloc[0].entry_at_utc=='2025-01-02T14:40:00+00:00'
    assert abs(result.iloc[0].post5_pct-1)<1e-8
    assert result.iloc[0].lag_minutes==9
    # One missing bar invalidates the full 30m window, not the valid 5m window.
    result=event_returns(events,valid_bars(prices().drop(index=4)))
    assert 'post30_pct' not in result and 'post5_pct' in result


def test_midnight_and_conflicting_scores():
    session=SimpleNamespace(session_date=datetime(2025,1,2).date(),open_at_utc=datetime(2025,1,2,14,30,tzinfo=timezone.utc),
                            close_at_utc=datetime(2025,1,2,21,tzinfo=timezone.utc))
    news=pd.DataFrame([dict(article_id=str(i),symbol='ABC',dedupe_hash=str(i),published_at_utc=stamp,
        available_at='2026-01-01',positive_score=p,negative_score=n) for i,(stamp,p,n) in enumerate([
            ('2025-01-02T00:00:00Z',.99,.01),('2025-01-02T15:00:00Z',.99,.01),('2025-01-02T15:00:00Z',.01,.99)])])
    result=prepare_news(news,[session])
    assert len(result)==1 and result.iloc[0]['group']=='mixed' and result.iloc[0].articles==2


def test_invalid_volume_not_filled():
    frame=prices();frame.loc[0,'volume']=0
    assert len(valid_bars(frame))==19
