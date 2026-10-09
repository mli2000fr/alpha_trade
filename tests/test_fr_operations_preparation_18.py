from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json

import pytest

from service.fr.operations_preparation_18 import (ROOT, DEFAULT_POLICY, SyntheticObservation,
    load_policy, evaluate_synthetic, build_report, run_drills, notification_preview)

NOW = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)


def fixture():
    return SyntheticObservation(D('4000'), D('4000'), D('0'), D('50'), D('0'), D('4000'), NOW, NOW)


def policy_root(tmp_path, mutation=None):
    policy = json.loads((ROOT / DEFAULT_POLICY).read_bytes())
    if mutation:
        mutation(policy)
    path = tmp_path / DEFAULT_POLICY
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(policy))
    return policy


def test_config_and_drills_never_authorize_execution():
    policy, limits, digest = load_policy()
    assert len(digest) == 64
    result = evaluate_synthetic(fixture(), limits, now=NOW)
    assert not result['reasons'] and not result['orders_allowed']
    report = run_drills(now=NOW)
    assert report['status'] == 'DRILLS_PASS_NOT_RELEASED'
    assert report['scenario_count'] == 17
    assert not report['live_allowed'] and not report['network_calls']


@pytest.mark.parametrize('key,value', [('live_enabled', True), ('orders_allowed', True),
    ('mode', 'live'), ('market_code', 'US_EQ'), ('currency', 'USD'),
    ('database_alias', 'us_primary'), ('account_context', 'default'),
    ('alert_delivery', 'send'), ('orders_allowed', 0)])
def test_unsafe_configuration_denied(tmp_path, key, value):
    policy_root(tmp_path, lambda p: p.update({key: value}))
    with pytest.raises(ValueError, match='Unsafe'):
        load_policy(root=tmp_path)


@pytest.mark.parametrize('key,value', [('max_order_notional_eur', 'NaN'),
    ('max_gross_exposure_ratio', '1'), ('max_daily_loss_ratio', '-.1'),
    ('max_order_notional_eur', 'not-a-number'),
    ('max_quote_age_seconds', True), ('max_account_age_seconds', 0)])
def test_bad_limits_denied(tmp_path, key, value):
    policy_root(tmp_path, lambda p: p['limits'].update({key: value}))
    with pytest.raises(ValueError):
        load_policy(root=tmp_path)


@pytest.mark.parametrize('field,value', [('equity_eur', D('0')), ('daily_pnl_eur', D('NaN')),
    ('available_cash_eur', D('-1')), ('planned_notional_eur', D('0')),
    ('unreconciled_orders', True), ('kill_active', 1), ('model_manifest_qualified', 'true'),
    ('equity_eur', '4000')])
def test_malformed_observation_denied(field, value):
    _, limits, _ = load_policy()
    with pytest.raises(ValueError):
        evaluate_synthetic(replace(fixture(), **{field: value}), limits, now=NOW)


def test_naive_time_not_assumed_paris_or_utc():
    _, limits, _ = load_policy()
    with pytest.raises(ValueError, match='aware'):
        evaluate_synthetic(replace(fixture(), quote_observed_at=NOW.replace(tzinfo=None)), limits, now=NOW)


def test_freshness_boundary_inclusive_and_future_denied():
    _, limits, _ = load_policy()
    assert not evaluate_synthetic(replace(fixture(), quote_observed_at=NOW-timedelta(seconds=60)), limits, now=NOW)['reasons']
    assert 'FUTURE_ACCOUNT_OBSERVED_AT' in evaluate_synthetic(
        replace(fixture(), account_observed_at=NOW+timedelta(seconds=1)), limits, now=NOW)['reasons']


def test_loss_and_drawdown_boundaries_stop_inclusively():
    _, limits, _ = load_policy()
    obs = replace(fixture(), equity_eur=D('3960'), daily_pnl_eur=D('-40'))
    assert 'DAILY_LOSS_LIMIT' in evaluate_synthetic(obs, limits, now=NOW)['reasons']
    obs = replace(fixture(), equity_eur=D('3800'))
    assert 'DRAWDOWN_LIMIT' in evaluate_synthetic(obs, limits, now=NOW)['reasons']


def test_missing_evidence_report_and_alert_draft_no_sql_or_network(tmp_path):
    policy_root(tmp_path)
    report = build_report(root=tmp_path, now=NOW)
    assert all(r['state'] == 'MISSING_OR_INVALID' for r in report['evidence'])
    assert report['status'] == 'BLOCKED_NO_LIVE_RELEASE'
    assert not report['orders_allowed'] and not report['sql_writes']
    assert notification_preview(report)['delivery'] == 'NOT_SENT_PREVIEW_ONLY'


def test_context_correct_archive_does_not_become_current_account_or_release(tmp_path):
    policy = policy_root(tmp_path)
    for role, relative in policy['evidence'].items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        data = {'market_code': 'FR_EQ', 'environment': 'DEMO', 'live_enabled': False,
                'sql_writes': False, 'orders_allowed': False}
        if role == 'collectors':
            data.update(as_of_paris='2026-10-09', collectors={}, trading_enabled=False,
                        scheduler_changed=False)
        elif role == 'mapping':
            data.update(status='MAPPING_FROZEN_RESEARCH_NOT_RELEASED', mapped_count=138)
        else:
            data.update(status='READONLY_REACHABLE_NOT_RELEASED', account_currency='EUR')
        path.write_text(json.dumps(data))
    report = build_report(root=tmp_path, now=NOW)
    assert all(r['state'].startswith('ARCHIVED_') for r in report['evidence'])
    assert not report['live_allowed']


def test_evidence_path_cannot_read_us_or_secrets(tmp_path):
    policy_root(tmp_path, lambda p: p['evidence'].update(mapping='../conf/secret.json'))
    report = build_report(root=tmp_path, now=NOW)
    assert report['evidence'][1]['state'] == 'MISSING_OR_INVALID'


def test_policy_outside_scope_denied(tmp_path):
    with pytest.raises(ValueError, match='outside'):
        load_policy('../config.yaml', root=tmp_path)
