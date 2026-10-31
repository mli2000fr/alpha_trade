"""Matched historical quotes: no missing-as-zero, future quotes or fake freshness."""
from datetime import datetime, timedelta, timezone

import pytest

from scripts.research.us_oracle_iex_sip_quote_audit import gate, quote_metrics

AT = datetime(2026, 10, 27, 13, 35, tzinfo=timezone.utc)
OPEN = AT-timedelta(minutes=5)


def quote(**changes):
    return {'bp': 100, 'ap': 100.1, 'bs': 100, 'as': 100, 't': AT.isoformat(), **changes}


def test_freshness_measured_from_fixed_historical_cutoff_not_collection_clock():
    metrics = quote_metrics(quote(t=(AT-timedelta(seconds=31)).isoformat()), AT, OPEN)
    assert metrics['age_seconds'] == 31
    assert gate(metrics, age_seconds=30, sizes_required=False, max_spread_bps=50) == 'STALE'
    assert gate(metrics, age_seconds=60, sizes_required=True, max_spread_bps=50) == 'PASS'


def test_missing_has_no_zero_spread():
    metrics = quote_metrics(None, AT, OPEN)
    assert metrics['spread_bps'] is None
    assert gate(metrics, age_seconds=300, sizes_required=False, max_spread_bps=50) == 'MISSING'


@pytest.mark.parametrize('row', [quote(t=(AT+timedelta(seconds=1)).isoformat()),
    quote(t=(OPEN-timedelta(seconds=1)).isoformat()), quote(bp='NaN'), quote(ap=100), quote(bs=0, bp=101)])
def test_invalid_quotes_cannot_pass(row):
    metrics = quote_metrics(row, AT, OPEN)
    assert not metrics['valid']


def test_same_cutoff_comparison_can_refuse_iex_only():
    iex = quote_metrics(quote(bp=99, ap=101), AT, OPEN)
    sip = quote_metrics(quote(bp=99.99, ap=100.01), AT, OPEN)
    assert gate(iex, age_seconds=300, sizes_required=False, max_spread_bps=50) == 'WIDE'
    assert gate(sip, age_seconds=300, sizes_required=False, max_spread_bps=50) == 'PASS'


def test_size_is_an_independent_winner_check():
    metrics = quote_metrics(quote(bs=0), AT, OPEN)
    assert gate(metrics, age_seconds=300, sizes_required=False, max_spread_bps=50) == 'PASS'
    assert gate(metrics, age_seconds=60, sizes_required=True, max_spread_bps=50) == 'INVALID_SIZE'
