"""Reporting regressions: missing and provider failure must have separate denominators."""
from datetime import datetime, timezone
import hashlib
import json

from scripts.research.us_oracle_iex_sip_quote_audit import SCENARIOS, summarize


def sample(tmp_path, iex_payload, sip_payload):
    (tmp_path/'raw').mkdir()
    (tmp_path/'oracle_scores.parquet').write_bytes(b'fixture')
    case = dict(symbol='TEST', at='2026-10-19T13:35:00+00:00',
        opening='2026-10-19T13:30:00+00:00', oracle_rank=1,
        quote_day='2026-10-19', slot='open_plus_5m', signal_day='2026-10-16')
    plan = dict(cases=[case], max_requests=2, scenarios=SCENARIOS, max_spread_bps=50,
                batch_id='fixture', limitations=[])
    (tmp_path/'plan.json').write_text(json.dumps(plan), encoding='utf-8')
    for feed, payload in [('iex', iex_payload), ('sip', sip_payload)]:
        sig = json.dumps([case['symbol'], case['at'], feed], separators=(',', ':'))
        path = tmp_path/'raw'/(hashlib.sha256(sig.encode()).hexdigest()+'.json')
        evidence = dict(http_status=200, payload=payload) if payload is not None else dict(http_status=403)
        path.write_text(json.dumps(evidence), encoding='utf-8')
    return summarize(tmp_path, plan)


def test_all_missing_quotes_are_not_technical_errors_and_never_pass(tmp_path):
    report = sample(tmp_path, {'quotes': []}, {'quotes': []})
    assert report['status'] == 'COMPLETED'
    for scenario in SCENARIOS:
        result = report['groups']['TOP20']['scenarios'][scenario]
        assert result['comparable_cases'] == 1
        assert result['both_refuse'] == 1
        assert result['iex_status_counts'] == {'MISSING': 1}
        assert result['iex_refusals_among_sip_pass_pct'] is None
        assert result['excess_spread_bps']['n'] == 0


def test_access_error_does_not_become_missing_quote_or_comparable_pair(tmp_path):
    report = sample(tmp_path, None, {'quotes': []})
    assert report['status'] == 'PARTIAL_FAILED'
    result = report['groups']['TOP50']['scenarios']['risk']
    assert result['comparable_cases'] == 0
    assert result['both_refuse'] == 0
    assert result['iex_status_counts'] == {'TECHNICAL_ERROR': 1}


def test_clearly_wider_iex_spread_has_correct_signed_excess_and_denominator(tmp_path):
    def quote(bid, ask):
        return dict(bp=bid, ap=ask, bs=100, **{'as': 100}, t='2026-10-19T13:35:00Z')
    report = sample(tmp_path, {'quotes': [quote(99, 101)]}, {'quotes': [quote(99.99, 100.01)]})
    result = report['groups']['TOP10']['scenarios']['winner']
    assert result['iex_refuses_sip_passes'] == 1
    assert result['iex_refusals_among_sip_pass_pct'] == 100
    assert abs(result['excess_spread_bps']['median']-198) < 1e-8
