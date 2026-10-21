from types import SimpleNamespace

import pandas as pd

from scripts.research.us_intraday_fidelity_readiness import row_reasons


NOW = pd.Timestamp('2025-01-02 15:00Z')


def case(side='buy', status='SIGNAL'):
    return SimpleNamespace(symbol='ABC', side=side, status=status, decision_time=NOW)


def quote(stamp=NOW, received=NOW):
    return pd.DataFrame([dict(symbol='ABC', source_timestamp=stamp,
        collected_at=received, provider='alpaca', feed='sip', bid_price=99., ask_price=101.,
        bid_size=10., ask_size=10., raw_payload_sha256='a'*64, raw_payload_path='archived.json')])


def test_daily_end_quote_cannot_qualify_morning_decision():
    r = row_reasons(case(), quote(NOW+pd.Timedelta(hours=6), NOW+pd.Timedelta(hours=6)), pd.DataFrame())
    assert r['quote_candidates'] == 0
    assert 'NO_CONTEMPORANEOUS_5M_SIP_QUOTE_RECEIPT' in r['reasons']


def test_historical_timestamp_downloaded_now_is_not_as_known_receipt():
    r = row_reasons(case(), quote(NOW, NOW+pd.Timedelta(days=600)), pd.DataFrame())
    assert r['quote_candidates'] == 0
    assert r['market_event_quote_candidates'] == 1


def test_fresh_quote_is_only_candidate_not_full_qualification():
    r = row_reasons(case(), quote(), pd.DataFrame())
    assert r['quote_candidates'] == 1
    assert r['status'] == 'BLOCKED_FULL_PARITY'
    assert 'QUOTE_RAW_RECEIPT_REVIEW_REQUIRED' in r['reasons']


def test_empty_ca_or_borrow_never_fabricated_as_no_events_free_borrow():
    r = row_reasons(case('sell'), pd.DataFrame(), pd.DataFrame())
    assert 'UNPROVEN_COMPLETE_CORPORATE_ACTION_COVERAGE' in r['reasons']
    assert 'MISSING_HISTORICAL_LOAN_FEES_LOCATES_RECALLS' in r['reasons']
    assert r['borrow_candidates'] == 0


def test_future_borrow_not_usable_in_past():
    b = pd.DataFrame([dict(symbol='ABC', available_at=NOW+pd.Timedelta(days=1), provider='alpaca', payload_hash='a'*64)])
    r = row_reasons(case('sell'), quote(), b)
    assert r['borrow_candidates'] == 0


def test_no_signal_separate_from_unqualified_or_losing_trade():
    assert row_reasons(case(status='NO_SIGNAL'), pd.DataFrame(), pd.DataFrame())['status'] == 'NO_SIGNAL'


def test_infinite_prices_or_wrong_provider_not_candidate():
    q = quote()
    q.loc[0, 'ask_price'] = float('inf')
    assert row_reasons(case(), q, pd.DataFrame())['quote_candidates'] == 0
    q = quote()
    q.loc[0, 'provider'] = 'unknown'
    assert row_reasons(case(), q, pd.DataFrame())['quote_candidates'] == 0
