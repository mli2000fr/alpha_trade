from datetime import datetime,timezone

import pytest

from scripts.research import us_news_financing_review_20261016 as review
from scripts.research import us_news_event_qualification as evidence


def fixture_items():
    ids=list(review.NOTES)
    selected=ids[:16]+['eodhd:a9b78f8f0add2d36f16e9e5a']*3+['eodhd:c42b7d80e3215b5fb09cb083']+ids[16:]
    return [dict(evidence_key=str(index),article_id=aid,symbol=next(iter(review.NOTES[aid]['symbols']),'UNKNOWN'),
        screened=index<20,fields={'content':review.NOTES[aid]['quote']},temporal_reservations=[],
        text_available_at='2026-10-16T12:00:00Z',mapping_available_at='2026-10-16T12:00:00Z')
        for index,aid in enumerate(selected)]


def test_reading_is_bound_to_fixed_texts_and_exact_quotes_not_independent_or_signal():
    items=fixture_items()
    now=datetime(2026,10,16,14,tzinfo=timezone.utc)
    annotations=review.annotations(items,now,'reference-fixture')
    assert len(annotations)==30
    for item,row in zip(items,annotations):
        assert 'NOT independent' in row['reviewer']
        assert not row['prior_comparison_complete'] and not row['common_equity_scope_qualified']
        checked=evidence.qualify_review(item,row,now)
        assert checked['status']=='RESERVED' and not checked['tradable_signal']
        assert checked['available_at_utc']>=now


def test_unknown_text_or_changed_quote_never_silently_reused():
    items=fixture_items()
    items[0]['article_id']='unread'
    with pytest.raises(ValueError,match='exactly'):
        review.annotations(items,datetime.now(timezone.utc),'ref')
    items=fixture_items()
    items[0]['fields']['content']='Altered article'
    with pytest.raises(ValueError):
        review.annotations(items,datetime.now(timezone.utc),'ref')
