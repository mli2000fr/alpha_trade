from datetime import datetime, timezone

import pytest

from scripts.research import us_news_financing_issuer_review_20261016 as review
from scripts.research import us_news_event_qualification as evidence


def items():
    return [dict(article_id=aid,symbol='NVDA',screened=True,evidence_key=aid,
        fields={'content':' '.join(quotes)},temporal_reservations=[],
        text_available_at='2026-10-16T00:00:00Z',mapping_available_at='2026-10-16T00:00:00Z')
        for aid,quotes in review.NOTES.items()]


def test_partner_is_not_ipo_issuer_and_never_auto_approved():
    now=datetime(2026,10,16,1,tzinfo=timezone.utc)
    source=items()
    rows=review.annotations(source,now)
    for item,row in zip(source,rows):
        result=evidence.qualify_review(item,row,now)
        assert result['status']=='RESERVED' and 'ISSUER_IDENTITY_UNVERIFIED' in result['reasons']
        assert not result['tradable_signal'] and not result['independent_review_certified']


def test_unknown_text_or_ticker_is_not_generalized():
    source=items(); source[0]['article_id']='unknown'
    with pytest.raises(ValueError): review.annotations(source,datetime.now(timezone.utc))
    source=items(); source[0]['symbol']='IAM'
    with pytest.raises(ValueError): review.annotations(source,datetime.now(timezone.utc))


def test_changed_quote_refused_without_inventing_source():
    source=items(); source[0]['fields']['content']='Unrelated content'
    with pytest.raises(ValueError): review.annotations(source,datetime.now(timezone.utc))
