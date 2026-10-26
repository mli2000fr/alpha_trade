import numpy as np
import pandas as pd
import pytest

from scripts.research import us_news_symbol_sensitivity as audit


def schedule(n=50, start='2025-01-02'):
    days = pd.bdate_range(start, periods=n)
    return pd.DataFrame(dict(day=days,
        open_at=pd.to_datetime(days, utc=True)+pd.Timedelta(hours=14, minutes=30),
        close_at=pd.to_datetime(days, utc=True)+pd.Timedelta(hours=21)))


def news(times, symbols=None, hashes=None, pos=None, neg=None, available=None):
    n = len(times)
    return pd.DataFrame(dict(article_id=np.arange(n), symbol=symbols or ['A']*n,
        published_at_utc=times, available_at=available or times,
        dedupe_hash=hashes if hashes is not None else [str(i) for i in range(n)],
        positive_score=pos or [.95]*n, negative_score=neg or [.01]*n))


def test_open_margin_uses_strict_next_open_and_overnight_mapping():
    s = schedule(3)
    n = news(['2025-01-02T14:24:59Z', '2025-01-02T14:25:00Z',
              '2025-01-02T16:00:00Z', '2025-01-03T22:00:00Z'], symbols=['A','B','C','D'])
    events, _ = audit.make_events(n, s)
    assert events.set_index('symbol').entry_idx.to_dict() == dict(A=0, B=1, C=1, D=2)


def test_mixed_and_strict_point_nine():
    n = news(['2025-01-02T13:00Z']*3, symbols=['A','A','B'], pos=[.95,.01,.9], neg=[.01,.96,.01])
    events, _ = audit.make_events(n, schedule())
    assert events.set_index('symbol').tone.to_dict() == dict(A='mixed', B='no_strong_score')


def test_midnight_unknown_hour_and_invalid_scores_reserved():
    n = news(['2025-01-02T00:00Z', '2025-01-02T13:00Z', '2025-01-02T13:01Z'], pos=[.95,1.1,.95])
    events, stats = audit.make_events(n, schedule())
    assert len(events) == 1
    assert stats['ambiguous_midnight'] == 1
    assert stats['invalid_scores_or_time'] == 1


def test_content_dedup_across_days_not_across_symbols():
    n = news(['2025-01-02T13:00Z','2025-01-03T13:00Z','2025-01-03T13:00Z'],
             symbols=['A','A','B'], hashes=['repeat']*3)
    events, stats = audit.make_events(n, schedule())
    assert len(events) == 2 and stats['duplicate_symbol_contents'] == 1


def test_absent_hash_uses_article_not_one_shared_null():
    n = news(['2025-01-02T13:00Z','2025-01-03T13:00Z'], hashes=[None,None])
    events, stats = audit.make_events(n, schedule())
    assert len(events) == 2 and stats['duplicate_symbol_contents'] == 0


def test_availability_uses_all_articles_unknown_or_late_is_not_available():
    n = news(['2025-01-02T13:00Z']*3, symbols=['A','A','B'],
             available=['2025-01-02T13:01Z',None,'2025-01-04T12:00Z'])
    events, _ = audit.make_events(n, schedule())
    assert not events.availability_proxy_before_entry.any()


def test_current_headline_requires_exact_non_null_content_hash():
    n = news(['2025-01-02T13:00Z']*2, symbols=['A','B'], hashes=['old','same'])
    head = pd.DataFrame(dict(article_id=[0,1], headline=['Earnings results','Analyst upgrades'],
                             dedupe_hash=['changed','same']))
    events, stats = audit.make_events(n, schedule(), head)
    assert stats['headline_hash_matched_rows'] == 1
    assert events.set_index('symbol').loc['A','family'] == 'MISSING_ARCHIVED_TEXT'
    assert events.set_index('symbol').loc['B','family'] == 'ANALYST_ACTION_SCREEN'


def test_family_multiple_not_falsely_validated_event():
    assert audit.screen('Earnings outlook and public offering') == 'MULTIPLE_SCREEN'
    assert audit.screen('Stock rises today') == 'OTHER_UNCLASSIFIED'


def test_spaced_reserves_missing_and_mixed_before_price_qualification():
    frame = pd.DataFrame(dict(symbol=['A']*4, entry_idx=[1,2,5,6], exit_idx=[5,6,9,10],
                              return_pct=[np.nan,10,2,3], tone=['mixed']*4))
    result = audit.spaced(frame)
    assert result.entry_idx.tolist() == [1,6]


def test_bh_monotone_in_original_order_and_empty():
    result = audit.bh([.04,.001,.02,1])
    assert result == pytest.approx([.053333333333,.004,.04,1])
    assert len(audit.bh([])) == 0


def test_wilson_does_not_make_small_sample_certain():
    assert audit.wilson(1,1) < .5
    assert audit.wilson(100,100) > .95
    assert audit.wilson(0,0) == 0


def test_price_validity_no_fill_and_ohlc_checks():
    s = schedule(3)
    frame = pd.DataFrame(dict(date=s.day, symbol=['A']*3, open=[10,10,10], close=[11,11,11],
        high=[12,9,12],low=[9,9,9],volume=[10,10,0],is_filled=[0,0,0],data_adjustment=['split']*3))
    panels, quality = audit.price_panels(frame,s)
    assert quality['invalid'] == 2
    assert panels['open'].iloc[:,0].notna().tolist() == [True,False,False]


def test_outcomes_entry_included_h1_and_gap_not_mixed_with_remaining_return():
    s = schedule(4)
    bars = []
    for symbol in ['A','SPY']:
        for i, day in enumerate(s.day):
            bars.append(dict(date=day,symbol=symbol,open=100+i*10 if symbol=='A' else 100,
                close=105+i*10 if symbol=='A' else 100,high=200,low=1,volume=100,
                is_filled=0,data_adjustment='split'))
    panels, _ = audit.price_panels(pd.DataFrame(bars),s)
    events, _ = audit.make_events(news(['2025-01-03T13:00Z']),s)
    r = audit.outcomes(events,panels,s,{},1,{})
    assert r.iloc[0].return_pct == pytest.approx((115/110-1)*100)
    assert r.iloc[0].bridge_to_entry_pct == pytest.approx((110/105-1)*100)
    assert r.iloc[0].exit_date == pd.Timestamp('2025-01-03')


def test_missing_intermediate_day_invalidates_entire_horizon():
    s = schedule(4)
    panels = {'open':pd.DataFrame(dict(A=[10,np.nan,10,10],SPY=[100]*4),index=s.day),
              'close':pd.DataFrame(dict(A=[11,np.nan,11,11],SPY=[100]*4),index=s.day)}
    events, _ = audit.make_events(news(['2025-01-02T13:00Z']),s)
    assert pd.isna(audit.outcomes(events,panels,s,{},3,{}).iloc[0].return_pct)


def test_sector_comparison_excludes_own_return():
    s = schedule(2)
    symbols = list('ABCDEFG')+['SPY']
    opens = pd.DataFrame(100.,index=s.day,columns=symbols)
    closes = opens.copy()
    closes.loc[s.day[0], 'A'] = 120
    events, _ = audit.make_events(news(['2025-01-02T13:00Z']),s)
    result = audit.outcomes(events,{'open':opens,'close':closes},s,{x:'X' for x in 'ABCDEFG'},1,{})
    assert result.iloc[0].signed_excess_sector_nonpit_pct == pytest.approx(20)


def test_training_selection_ignores_test_returns_and_unmatured_december():
    rows = []
    for symbol in ['A','B']:
        for day in pd.date_range('2025-01-02','2025-12-01',freq='7D'):
            rows.append(dict(symbol=symbol,tone='positive_only',entry_date=day,exit_date=day+pd.Timedelta(days=5),
                year=2025,signed_excess_spy_pct=1 if symbol=='A' else -1,
                signed_after_assumed_16bps_pct=1 if symbol=='A' else -1))
    train = pd.DataFrame(rows)
    result = audit.memberships(train,5)
    assert result.set_index('symbol').loc['A','selected_pre_bh']
    test = train.iloc[:5].copy()
    test[['entry_date','exit_date']] += pd.Timedelta(days=365)
    test['year'] = 2026
    test['signed_excess_spy_pct'] = 1000
    pd.testing.assert_frame_equal(result, audit.memberships(pd.concat([train,test]),5))
    late = train.iloc[:1].copy()
    late['entry_date'] = pd.Timestamp('2025-12-30')
    late['exit_date'] = pd.Timestamp('2026-01-06')
    pd.testing.assert_frame_equal(result, audit.memberships(pd.concat([train,late]),5))


def test_real_calendar_handles_us_dst_and_early_close():
    s = audit.schedule_frame()
    march7 = s[s.day.eq('2025-03-07')].iloc[0]
    march10 = s[s.day.eq('2025-03-10')].iloc[0]
    assert march7.open_at.hour == 14 and march10.open_at.hour == 13
    short = s[s.day.eq('2025-11-28')].iloc[0]
    assert short.close_at.hour == 18


def test_duplicate_daily_source_is_error_not_silent_choice():
    s = schedule(2)
    row = dict(date=s.day.iloc[0],symbol='A',open=10,close=10,high=10,low=10,
               volume=100,is_filled=0,data_adjustment='split')
    with pytest.raises(ValueError,match='Duplicate daily'):
        audit.price_panels(pd.DataFrame([row,row]),s)


def test_known_identity_break_is_reserved_not_returned():
    from modelFactory.oracle.security_continuity import SecurityDiscontinuity
    s = schedule(4)
    panels = {col:pd.DataFrame(dict(A=[10]*4,SPY=[100]*4),index=s.day) for col in ('open','close')}
    events, _ = audit.make_events(news(['2025-01-02T13:00Z']),s)
    registry = {'A':(SecurityDiscontinuity('A',s.day.iloc[0],s.day.iloc[1],'test'),)}
    result = audit.outcomes(events,panels,s,{},3,registry)
    assert result.iloc[0].identity_break and not result.iloc[0].qualified_path
    assert pd.isna(result.iloc[0].return_pct)


def test_unknown_proxy_is_not_a_negative_or_neutral_label():
    n = news(['2025-01-02T13:00Z'],available=[None])
    events, _ = audit.make_events(n,schedule())
    assert events.iloc[0].tone == 'positive_only'
    assert not events.iloc[0].availability_proxy_before_entry
