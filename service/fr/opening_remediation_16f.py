"""Audit a completed FR remediation warmup as known now, never at a past opening.

Optional bounded ESMA catalogue probes archive public index metadata, not prices
or a proof that an absent publication means no reference change.
"""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from service.fr.bootstrap_qualification_16c import qualify
from service.fr.eodhd_daily_15b import atomic
from service.fr.esma_firds_download import _tls_context
from service.fr.prediction_contract_16a import ROOT, aware, scoped_path
from service.fr.security_master_daily_15e import delta_index, validate_index

ORIGINAL = 'artifacts/fr/research/opening_confirmation_16f/opening-20261007-v1/report.json'
NEW_PROTOCOL = 'config/research_fr/opening_confirmation_16f_remediation.json'


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe_catalogue(days, now, *, loader=delta_index, context_factory=_tls_context):
    if len(set(days)) != len(days) or len(days) > 2:
        raise ValueError('At most two distinct bounded ESMA probe days')
    today = now.astimezone(ZoneInfo('Europe/Paris')).date()
    if any(day > today for day in days):
        raise ValueError('Cannot probe a future publication day')
    context = context_factory()
    rows = []
    for day in days:
        try:
            files = loader(day, day, context)
            missing = validate_index(files, day, day)
            rows.append({'day': str(day), 'files': files, 'missing_days': missing,
                'status': 'INDEX_FRAGMENTS_PRESENT_NOT_REFERENCE_QUALIFICATION' if not missing
                          else 'PUBLICATION_ABSENT_OR_UNKNOWN',
                'checked_at': datetime.now(UTC).isoformat(),
                'continuity_qualified': False})
        except Exception as exc:
            rows.append({'day': str(day), 'status': 'PROBE_FAILED',
                         'error_type': type(exc).__name__, 'continuity_qualified': False})
    return rows


def audit(bootstrap, *, root=ROOT, now=None, probe_days=()):
    root = root.resolve()
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError('Aware audit time required')
    original_path = scoped_path(ORIGINAL, root)
    original_hash = hash_file(original_path)
    original = json.loads(original_path.read_bytes())
    if original.get('phase') != 'confirm' or original.get('decision_at') != '2026-10-07T07:00:00+00:00':
        raise ValueError('Original October 7 confirmation required, without changed cutoff')
    if aware(original['audit_at']) > now:
        raise ValueError('Original audit not yet available')
    result = qualify(bootstrap, root=root, audit_at=now)
    plan_path = (root/NEW_PROTOCOL).resolve()
    if not plan_path.is_relative_to((root/'config/research_fr').resolve()):
        raise ValueError('Protocol outside config/research_fr')
    plan = json.loads(plan_path.read_bytes())
    from service.fr.opening_confirmation_16f import validate
    validate(plan)
    if plan['decision_date'] == '2026-10-07':
        raise ValueError('Remediation must not rewrite the original decision')
    probes = probe_catalogue(list(probe_days), now) if probe_days else []
    if hash_file(original_path) != original_hash:
        raise ValueError('Original report changed during audit')
    return {'schema_version': 1, 'market_code': 'FR_EQ',
        'status': 'REMEDIATION_AUDITED_SHADOW_BLOCKED', 'audit_at': now.isoformat(),
        'audit_role': 'CURRENT_WARMUP_NOT_OCTOBER7_REPLAY_NOT_NEXT_OPENING_CONFIRMATION',
        'original_report_sha256': original_hash,
        'original_decision_at': original['decision_at'],
        'original_features_computed': original['daily_assembly']['features_computed_count'],
        'original_candidate_rows': original['daily_assembly']['candidate_rows_count'],
        'warmup': result, 'esma_catalogue_probes': probes,
        'next_protocol': plan, 'next_protocol_sha256': hash_file(plan_path),
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False,
        'next_gates': ['ACTUAL_NEXT_OPENING', 'CURRENT_SESSION_REFERENCE',
                       'HISTORICAL_ESMA_CONTINUITY', 'INDEPENDENT_ACTION_QUALIFICATION',
                       'CURRENCY_AND_IDENTITY_RESERVES', 'MODEL_RELEASE_REVIEW'],
        'note': 'New observations retain actual availability; no repair of past PIT availability.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('catalogue', 'qualify'), default='qualify')
    parser.add_argument('--bootstrap-dir', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--probe-day', type=date.fromisoformat, action='append', default=[])
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT/'artifacts/fr/research/opening_remediation_16f').resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error('New isolated FR remediation output directory required')
    if args.phase == 'catalogue':
        if not args.probe_day:
            parser.error('Catalogue phase requires explicit bounded probe days')
        report = {'market_code': 'FR_EQ', 'status': 'CATALOGUE_PROBED_NO_QUALIFICATION',
            'audit_at': datetime.now(UTC).isoformat(),
            'esma_catalogue_probes': probe_catalogue(args.probe_day, datetime.now(UTC)),
            'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}
    else:
        if args.bootstrap_dir is None:
            parser.error('Qualification phase requires a completed bootstrap')
        report = audit(args.bootstrap_dir, probe_days=args.probe_day)
    output.mkdir(parents=True, exist_ok=False)
    atomic(output/'report.json', report)
    warmup = report.get('warmup', {})
    print(json.dumps({'status': report['status'],
        'features_computed': warmup.get('numeric_features_ready_count'),
        'local_checks_passed': warmup.get('local_checks_without_global_reserves_passed_count'),
        'servable': warmup.get('servable_count'), 'sql_writes': False}))


if __name__ == '__main__':
    main()
