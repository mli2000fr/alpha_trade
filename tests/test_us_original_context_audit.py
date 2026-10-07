import pandas as pd

from scripts.research.us_original_context_audit import compare, lag_on_sessions


def test_lag_uses_calendar_not_previous_observation():
    sessions=pd.DatetimeIndex(['2026-01-02','2026-01-05','2026-01-06','2026-01-07'])
    frame=pd.DataFrame({'date':pd.to_datetime(['2026-01-02','2026-01-06']), 'value':[10,20]})
    lagged=lag_on_sessions(frame,sessions)
    assert lagged.date.tolist()==list(pd.to_datetime(['2026-01-05','2026-01-07']))
    assert pd.Timestamp('2026-01-06') not in set(lagged.date)
    assert (lagged.observed_date < lagged.date).all()


def sample():
    return pd.DataFrame({'date':pd.to_datetime(['2026-01-02']*3),'symbol':['A','B','C'],
        'target_quality_valid':[1,1,1], 'oracle_decile':[10,1,10], 'future_return':[.1,-.2,.3],
        'mode':['normal','capital_preservation',None], 'allow_new_entries':[1,0,None],
        'term':[.8,1.1,None], 'spy_ret20':[.1,-.1,None],
        'relative20':[.1,-.1,None], 'breadth20':[.6,.4,None]})


def test_unknown_is_neither_removed_nor_known():
    result=compare(sample())['REGIME_NORMAL_ENTRIES']
    assert result['known']['rows']==2
    assert result['kept']['rows']==1
    assert result['removed']['rows']==1
    assert result['unknown']['rows']==1
    assert result['negative_events_removed_pct']==100
    assert result['positive_events_removed_pct']==0


def test_future_outcomes_do_not_change_context_partition():
    frame=sample()
    first=compare(frame)
    frame['future_return']=-frame.future_return
    second=compare(frame)
    for name in first:
        assert first[name]['kept']['rows']==second[name]['kept']['rows']
        assert first[name]['unknown']['rows']==second[name]['unknown']['rows']
