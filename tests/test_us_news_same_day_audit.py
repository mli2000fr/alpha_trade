from datetime import date, datetime, timezone
from types import SimpleNamespace
import pandas as pd
from scripts.research.us_news_same_day_audit import attach_sessions, aggregate


def test_real_session_boundaries_and_ambiguous_midnight():
    session=SimpleNamespace(session_date=date(2025,11,28),
        open_at_utc=datetime(2025,11,28,14,30,tzinfo=timezone.utc),
        close_at_utc=datetime(2025,11,28,18,tzinfo=timezone.utc))
    times=['2025-11-28T14:29Z','2025-11-28T14:30Z','2025-11-28T18:00Z','2025-11-28T00:00Z']
    data=pd.DataFrame(dict(published_at_utc=times,available_at=times))
    result=attach_sessions(data,[session])
    assert result.bucket.tolist()==['pre_open','regular','post_close','non_session']
    assert result.midnight_ambiguous.tolist()==[False,False,False,True]


def test_opposing_articles_are_mixed_and_threshold_is_strict():
    data=pd.DataFrame(dict(day=[pd.Timestamp('2025-01-02')]*3,symbol=['A','A','B'],
        article_id=['1','2','3'],positive_score=[.95,.1,.9],negative_score=[.1,.96,.1]))
    result=aggregate(data).set_index('symbol')
    assert result.loc['A','group']=='mixed'
    assert result.loc['B','group']=='no_strong_score'


def test_empty_available_view_is_valid_not_fabricated():
    data=pd.DataFrame(columns=['day','symbol','article_id','positive_score','negative_score'])
    assert aggregate(data).empty
