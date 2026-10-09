"""FR operational preparation: read-only evidence and offline safety drills.

No credentials, broker, SQL, notification sender or scheduler. Never authorizes
orders, even when synthetic checks pass. Not an execution-engine gate adapter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from service.fr.prediction_contract_16a import ROOT, scoped_path

DEFAULT_POLICY = 'config/research_fr/operations_preparation_18.json'
BLOCKERS = ('SHADOW_DATA_NOT_RELEASED', 'ECONOMIC_SIGNAL_NOT_RELEASED',
            'EXECUTION_BROKER_NOT_CONNECTED', 'NATIVE_PROTECTION_NOT_QUALIFIED',
            'EXECUTION_MIC_NOT_QUALIFIED', 'PAPER_FULL_PARITY_NOT_VALIDATED',
            'NO_EXPLICIT_LIVE_SIGNOFF')


def number(value, name, *, positive=False):
    if type(value) not in (str, int, Decimal):
        raise ValueError(f'Invalid numeric field {name}')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError(f'Invalid numeric field {name}') from None
    if not result.is_finite() or (positive and result <= 0):
        raise ValueError(f'Invalid numeric field {name}')
    return result


@dataclass(frozen=True)
class Limits:
    max_order_notional_eur: Decimal
    max_gross_exposure_ratio: Decimal
    max_daily_loss_ratio: Decimal
    max_drawdown_ratio: Decimal
    max_quote_age_seconds: int
    max_account_age_seconds: int

    def validate(self):
        for name in ('max_order_notional_eur', 'max_gross_exposure_ratio',
                     'max_daily_loss_ratio', 'max_drawdown_ratio'):
            if not isinstance(getattr(self, name), Decimal):
                raise ValueError('Decimal limits required')
            result = number(getattr(self, name), name, positive=True)
            if name.endswith('ratio') and result >= 1:
                raise ValueError('Ratio limit must be below one')
        for name in ('max_quote_age_seconds', 'max_account_age_seconds'):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError('Positive integer freshness limit required')


def load_policy(path=DEFAULT_POLICY, *, root=ROOT):
    file = (root / path).resolve()
    if not file.is_relative_to((root / 'config/research_fr').resolve()):
        raise ValueError('Policy outside FR research configuration')
    raw = file.read_bytes()
    policy = json.loads(raw)
    expected = {'schema_version': 1, 'market_code': 'FR_EQ', 'database_alias': 'fr_primary',
                'currency': 'EUR', 'account_context': 'fr_simulated',
                'mode': 'preparation_only', 'orders_allowed': False,
                'live_enabled': False, 'alert_delivery': 'preview_only'}
    for key, value in expected.items():
        if policy.get(key) != value or type(policy.get(key)) is not type(value):
            raise ValueError(f'Unsafe preparation policy: {key}')
    values = dict(policy['limits'])
    for key in list(values):
        if not key.endswith('_seconds'):
            values[key] = number(values[key], key, positive=True)
    limits = Limits(**values)
    limits.validate()
    return policy, limits, hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SyntheticObservation:
    """One hypothetical LONG order. Not a provider/account snapshot."""
    equity_eur: Decimal
    available_cash_eur: Decimal
    existing_gross_eur: Decimal
    planned_notional_eur: Decimal
    daily_pnl_eur: Decimal
    peak_equity_eur: Decimal
    quote_observed_at: datetime
    account_observed_at: datetime
    market_code: str = 'FR_EQ'
    currency: str = 'EUR'
    account_context: str = 'fr_simulated'
    unreconciled_orders: int = 0
    kill_active: bool = False
    market_open: bool = True
    model_manifest_qualified: bool = True
    dataset_pit_qualified: bool = True


def aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Timezone-aware timestamp required')
    return value.astimezone(timezone.utc)


def evaluate_synthetic(observation, limits, *, now):
    if type(observation) is not SyntheticObservation:
        raise ValueError('SyntheticObservation required')
    limits.validate()
    now = aware(now)
    for key in ('equity_eur', 'available_cash_eur', 'existing_gross_eur',
                'planned_notional_eur', 'daily_pnl_eur', 'peak_equity_eur'):
        if not isinstance(getattr(observation, key), Decimal):
            raise ValueError('Decimal synthetic observation required')
        number(getattr(observation, key), key)
    if (observation.equity_eur <= 0 or observation.peak_equity_eur < observation.equity_eur
            or observation.available_cash_eur < 0 or observation.existing_gross_eur < 0
            or observation.planned_notional_eur <= 0):
        raise ValueError('Incoherent synthetic account/order quantities')
    if type(observation.unreconciled_orders) is not int or observation.unreconciled_orders < 0:
        raise ValueError('Invalid unreconciled count')
    for key in ('kill_active', 'market_open', 'model_manifest_qualified', 'dataset_pit_qualified'):
        if type(getattr(observation, key)) is not bool:
            raise ValueError('Explicit boolean synthetic evidence required')
    reasons = []
    if (observation.market_code, observation.currency, observation.account_context) != (
            'FR_EQ', 'EUR', 'fr_simulated'):
        reasons.append('WRONG_MARKET_ACCOUNT_OR_CURRENCY')
    for field, threshold in (('quote_observed_at', limits.max_quote_age_seconds),
                             ('account_observed_at', limits.max_account_age_seconds)):
        age = (now - aware(getattr(observation, field))).total_seconds()
        if age < 0:
            reasons.append('FUTURE_' + field.upper())
        elif age > threshold:
            reasons.append('STALE_' + field.upper())
    if observation.kill_active:
        reasons.append('KILL_ACTIVE')
    if observation.unreconciled_orders:
        reasons.append('ORDERS_UNRECONCILED')
    if not observation.market_open:
        reasons.append('SESSION_CLOSED')
    if not observation.model_manifest_qualified:
        reasons.append('MODEL_NOT_QUALIFIED')
    if not observation.dataset_pit_qualified:
        reasons.append('DATA_PIT_NOT_QUALIFIED')
    if observation.planned_notional_eur > limits.max_order_notional_eur:
        reasons.append('ORDER_NOTIONAL_LIMIT')
    if observation.planned_notional_eur > observation.available_cash_eur:
        reasons.append('INSUFFICIENT_AVAILABLE_CASH')
    if (observation.existing_gross_eur + observation.planned_notional_eur >
            limits.max_gross_exposure_ratio * observation.equity_eur):
        reasons.append('GROSS_EXPOSURE_LIMIT')
    # Inclusive hard stops; fixed session-start equity proxy supplied by the fixture.
    session_start_equity = observation.equity_eur - observation.daily_pnl_eur
    if session_start_equity <= 0:
        raise ValueError('Incoherent daily PnL/equity')
    if -observation.daily_pnl_eur >= limits.max_daily_loss_ratio * session_start_equity:
        reasons.append('DAILY_LOSS_LIMIT')
    drawdown = (observation.peak_equity_eur - observation.equity_eur) / observation.peak_equity_eur
    if drawdown >= limits.max_drawdown_ratio:
        reasons.append('DRAWDOWN_LIMIT')
    return {'status': 'SYNTHETIC_BLOCKED' if reasons else 'SYNTHETIC_CHECKS_PASS_NOT_RELEASED',
            'reasons': reasons, 'orders_allowed': False, 'live_allowed': False,
            'notification_sent': False, 'scope': 'HYPOTHETICAL_LONG_NO_FEES_OR_FILLS',
            'stop_breach_does_not_close_positions': True}


def build_report(*, policy_path=DEFAULT_POLICY, root=ROOT, now=None):
    now = aware(now or datetime.now(timezone.utc))
    policy, _, policy_hash = load_policy(policy_path, root=root)
    checks = []
    for role, relative in policy['evidence'].items():
        row = {'role': role, 'path': relative, 'state': 'MISSING_OR_INVALID'}
        try:
            raw = scoped_path(relative, root).read_bytes()
            evidence = json.loads(raw)
            if evidence.get('market_code') != 'FR_EQ' or evidence.get('sql_writes') is not False:
                raise ValueError('Wrong evidence context')
            if role != 'collectors' and (evidence.get('environment') != 'DEMO'
                    or evidence.get('live_enabled') is not False):
                raise ValueError('Wrong DEMO context')
            if role == 'demo_readonly':
                if evidence.get('status') != 'READONLY_REACHABLE_NOT_RELEASED' or evidence.get('account_currency') != 'EUR':
                    raise ValueError('DEMO reads not qualified')
                row['read_endpoint_count'] = len(evidence.get('endpoint_receipts', {}))
            elif role == 'mapping':
                if evidence.get('status') != 'MAPPING_FROZEN_RESEARCH_NOT_RELEASED' or evidence.get('orders_allowed') is not False:
                    raise ValueError('Wrong mapping')
                row['mapped_count'] = evidence['mapped_count']
            elif role == 'collectors':
                if evidence.get('trading_enabled') is not False or evidence.get('scheduler_changed') is not False:
                    raise ValueError('Wrong collector review context')
                row['as_of_paris'] = evidence['as_of_paris']
                row['collectors'] = [{
                    'batch': name, 'latest_status': value.get('latest_status'),
                    'latest_failed': value.get('latest_failed'), 'latest_alerts': value.get('latest_alerts'),
                    'latest_started_at': value.get('latest_started_at'),
                    'week_verified': value.get('week_verified'),
                } for name, value in evidence['collectors'].items()]
                row['backup_qualification_roles'] = sorted(evidence.get('backup_qualifications', {}))
            else:
                raise ValueError('Unknown evidence role')
            row.update(state='ARCHIVED_COLLECTOR_REVIEW_NOT_SQL_PROOF' if role == 'collectors'
                       else 'ARCHIVED_CONTEXT_CONSISTENT_NOT_CURRENT_ACCOUNT_PROOF',
                       sha256=hashlib.sha256(raw).hexdigest())
        except (OSError, ValueError, TypeError, KeyError):
            pass
        checks.append(row)
    return {'schema_version': 1, 'market_code': 'FR_EQ', 'database_alias': 'fr_primary',
            'currency': 'EUR', 'mode': 'preparation_only',
            'status': 'BLOCKED_NO_LIVE_RELEASE', 'observed_at': now.isoformat(),
            'policy_path': policy_path, 'policy_sha256': policy_hash,
            'configured_synthetic_limits': policy['limits'], 'evidence': checks,
            'blockers': list(BLOCKERS), 'orders_allowed': False, 'live_allowed': False,
            'sql_writes': False, 'network_calls': False, 'notification_sent': False,
            'message': 'Infrastructure de préparation seulement : aucun ordre, pas de surveillance active.'}


def run_drills(*, policy_path=DEFAULT_POLICY, root=ROOT, now=None):
    now = aware(now or datetime.now(timezone.utc))
    _, limits, policy_hash = load_policy(policy_path, root=root)
    base = SyntheticObservation(Decimal('4000'), Decimal('4000'), Decimal('0'),
        min(Decimal('50'), limits.max_order_notional_eur,
            limits.max_gross_exposure_ratio * Decimal('4000') / 2), Decimal('0'), Decimal('4000'), now, now)
    scenarios = {
        'clean_fixture': (base, None),
        'wrong_market': (replace(base, market_code='US_EQ'), 'WRONG_MARKET_ACCOUNT_OR_CURRENCY'),
        'wrong_currency': (replace(base, currency='USD'), 'WRONG_MARKET_ACCOUNT_OR_CURRENCY'),
        'real_account': (replace(base, account_context='live'), 'WRONG_MARKET_ACCOUNT_OR_CURRENCY'),
        'kill_switch': (replace(base, kill_active=True), 'KILL_ACTIVE'),
        'pending_unknown_order': (replace(base, unreconciled_orders=1), 'ORDERS_UNRECONCILED'),
        'session_closed': (replace(base, market_open=False), 'SESSION_CLOSED'),
        'model_changed': (replace(base, model_manifest_qualified=False), 'MODEL_NOT_QUALIFIED'),
        'missing_pit': (replace(base, dataset_pit_qualified=False), 'DATA_PIT_NOT_QUALIFIED'),
        'stale_quote': (replace(base, quote_observed_at=now-timedelta(seconds=limits.max_quote_age_seconds+1)), 'STALE_QUOTE_OBSERVED_AT'),
        'stale_account': (replace(base, account_observed_at=now-timedelta(seconds=limits.max_account_age_seconds+1)), 'STALE_ACCOUNT_OBSERVED_AT'),
        'future_quote': (replace(base, quote_observed_at=now+timedelta(seconds=1)), 'FUTURE_QUOTE_OBSERVED_AT'),
        'no_cash': (replace(base, available_cash_eur=Decimal('0')), 'INSUFFICIENT_AVAILABLE_CASH'),
        'oversized_order': (replace(base, planned_notional_eur=limits.max_order_notional_eur+1), 'ORDER_NOTIONAL_LIMIT'),
        'gross_cap': (replace(base, existing_gross_eur=limits.max_gross_exposure_ratio*base.equity_eur), 'GROSS_EXPOSURE_LIMIT'),
        'daily_loss': (replace(base, daily_pnl_eur=-(limits.max_daily_loss_ratio*base.equity_eur)/(1-limits.max_daily_loss_ratio)-Decimal('.01')), 'DAILY_LOSS_LIMIT'),
        'drawdown': (replace(base, equity_eur=base.peak_equity_eur*(1-limits.max_drawdown_ratio)), 'DRAWDOWN_LIMIT'),
    }
    results = []
    for name, (fixture, expected) in scenarios.items():
        result = evaluate_synthetic(fixture, limits, now=now)
        passed = expected in result['reasons'] if expected else not result['reasons']
        results.append({'scenario': name, 'expected_blocker': expected, 'passed': passed, **result})
    return {'status': 'DRILLS_PASS_NOT_RELEASED' if all(r['passed'] for r in results) else 'DRILLS_FAILED',
            'policy_path': policy_path, 'policy_sha256': policy_hash,
            'observed_at': now.isoformat(), 'market_code': 'FR_EQ', 'scenario_count': len(results),
            'scenarios': results, 'orders_allowed': False, 'live_allowed': False,
            'sql_writes': False, 'network_calls': False, 'notification_sent': False}


def notification_preview(report):
    """Draft only, never calls SMTP/Telegram and never includes private responses."""
    return {'delivery': 'NOT_SENT_PREVIEW_ONLY', 'market_code': 'FR_EQ',
            'severity': 'BLOCKED', 'title': 'France — LIVE désactivé',
            'message': 'Préparation hors ligne. Blocages : ' + ', '.join(report.get('blockers', BLOCKERS))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('audit', 'drills'), default='audit')
    parser.add_argument('--policy', default=DEFAULT_POLICY)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    report = (build_report if args.phase == 'audit' else run_drills)(policy_path=args.policy)
    if args.phase == 'audit':
        report['notification_preview'] = notification_preview(report)
    if args.output_dir:
        output = scoped_path(args.output_dir, ROOT)
        output.mkdir(parents=True, exist_ok=False)
        (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        # Preserve the exact policy bytes alongside the report for reproducibility.
        (output / 'policy.json').write_bytes((ROOT / args.policy).read_bytes())
    print(json.dumps(report, ensure_ascii=False))
    # Audit can successfully produce a BLOCKED report. Never means release.
    if report['status'] == 'DRILLS_FAILED':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
