from datetime import datetime,timezone

from scripts.research.us_news_issuer_readiness_20261016 import issuer_anchor,planned_request


def item(symbol,body,key='fixture'):
    return dict(symbol=symbol,evidence_key=key,fields={'headline':'','summary':'','content':body})


def reference(name,exchange='NYSE'):
    return dict(company_name=name,exchange=exchange)


def test_foreign_same_ticker_is_reserved_not_silently_mapped_to_us():
    result=issuer_anchor(item('SUN','Stardust Solar (TSXV: SUN) (OTCQB: SUNXF)'),reference('Sunoco L.P.'))
    assert result['status']=='RESERVED_EXPLICIT_CROSS_MARKET_COLLISION'
    result=issuer_anchor(item('RGLD','Red Lake Gold (CSE: RGLD)'),reference('Royal Gold, Inc.','NASDAQ'))
    assert result['status']=='RESERVED_EXPLICIT_CROSS_MARKET_COLLISION'


def test_explicit_us_ticker_in_roundup_is_never_issuer_approval():
    result=issuer_anchor(item('FLEX','Flex (NASDAQ: FLEX); SentinelOne offers convertible notes.'),reference('Flex Ltd.'))
    assert result['status']=='REVIEW_REQUIRED_EXPLICIT_US_TICKER'
    assert not result['issuer_of_financing_clause_verified'] and not result['event_qualified']
    assert not result['identity_qualified'] and not result['tradable_signal']


def test_dual_listing_requires_review_not_automatic_foreign_rejection():
    result=issuer_anchor(item('BN','Brookfield (TSX: BN) (NYSE: BN)'),reference('Brookfield Corporation'))
    assert result['status']=='REVIEW_REQUIRED_EXPLICIT_US_TICKER'
    assert not result['identity_qualified']


def test_missing_reference_and_cross_ticker_comparator_stay_reserved():
    assert issuer_anchor(item('FBK','First BanCorp (FBP)'),None)['status']=='RESERVED_CURRENT_REFERENCE_MISSING'
    result=issuer_anchor(item('FBK','First BanCorp (FBP) earnings and financial expectations'),reference('FB Financial Corporation'))
    assert result['status']=='RESERVED_NO_EXPLICIT_LOCAL_ISSUER_ANCHOR'


def test_same_company_name_is_hint_not_historical_cross_listing_proof():
    result=issuer_anchor(item('CCJ','Cameco (TSX: CCO)'),reference('Cameco Corporation'))
    assert result['status']=='REVIEW_REQUIRED_NAME_HINT_ONLY'
    assert not result['name_hint_is_identity_proof'] and not result['metadata_is_historical_pit']


def test_backfill_request_filters_subject_mismatch_and_respects_current_session_guard():
    items=[item('SUN','',key='wrong'),item('BN','',key='right')]
    reviews=[dict(evidence_key='wrong',identity_verified=False),dict(evidence_key='right',identity_verified=True)]
    gates=[dict(evidence_key='wrong',status='RESERVED_EXPLICIT_CROSS_MARKET_COLLISION'),
           dict(evidence_key='right',status='REVIEW_REQUIRED_EXPLICIT_US_TICKER')]
    request=planned_request(items,reviews,gates,datetime(2026,10,16,14,tzinfo=timezone.utc))
    assert request['symbols']==['BN'] and request['end_date']=='2026-10-15'
    assert request['deferred_dates']==['2026-10-16']
    assert request['requires_explicit_collection_go'] and not request['universe_file_created']
    assert not request['creates_historical_news_availability']
