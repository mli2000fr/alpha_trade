"""Read-only Sprint 15 evidence audit; no collection, SQL, scheduler or notifications."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[2]
PARIS = ZoneInfo('Europe/Paris')
CORE = ('fr_daily_bars_sync', 'fr_corporate_actions_sync',
        'fr_amf_short_sync', 'fr_dila_disclosures_sync', 'fr_security_master_sync')


def observed_day(row: dict) -> str | None:
    try:
        stamp = datetime.fromisoformat(row['started_at'])
        return stamp.astimezone(PARIS).date().isoformat() if stamp.tzinfo else None
    except (KeyError, TypeError, ValueError):
        return None


def run_evidence(rows: list[dict], expected_days: list[str]) -> dict:
    # A historical catch-up window is not proof of daily contemporary operation.
    full = [r for r in rows if not r.get('dry_run') and not r.get('limited_smoke')
            and r.get('market_code') == 'FR_EQ' and observed_day(r)]
    full.sort(key=lambda r: datetime.fromisoformat(r['started_at']))
    latest_by_day = {observed_day(r): r for r in full}
    valid = [d for d in expected_days if d in latest_by_day
             and latest_by_day[d].get('status') == 'SUCCESS'
             and latest_by_day[d].get('failed_count', 0) == 0
             and latest_by_day[d].get('warning_count', 0) == 0]
    latest = full[-1] if full else {}
    return {'expected_sessions': expected_days, 'successful_sessions_without_alerts': valid,
            'missing_or_unqualified_sessions': [d for d in expected_days if d not in valid],
            'week_verified': len(expected_days) == 5 and len(valid) == 5,
            'latest_status': latest.get('status'), 'latest_started_at': latest.get('started_at'),
            'latest_failed': latest.get('failed_count'), 'latest_alerts': latest.get('warning_count'),
            'latest_errors': latest.get('errors', []),
            'latest_coverage_warnings': latest.get('coverage_warnings', []),
            'latest_window': latest.get('window')}


def audit(root: Path, *, as_of: date, expected_days: list[str]) -> dict:
    cfg = yaml.safe_load((root/'batch_fr.yaml').read_text(encoding='utf-8'))
    operations = root/'artifacts/fr/operations'
    collectors = {}
    for name in CORE:
        rows = [json.loads(p.read_text(encoding='utf-8'))
                for p in sorted((operations/'runs'/name).glob('*.json'))]
        collectors[name] = run_evidence(rows, expected_days)
    backups = {}
    for p in sorted((root/'backups/fr/qualification').glob('*/report.json')):
        row = json.loads(p.read_text(encoding='utf-8'))
        action = row.get('action')
        expected = {'database': 'RESTORE_VERIFIED', 'artifacts': 'EXTRACTION_VERIFIED'}
        if action not in expected or row.get('status') != expected[action]:
            continue
        paths = ([row.get('archive')] if action == 'database'
                 else [a.get('archive') for a in row.get('archives', [])])
        if not paths or not all(path and Path(path).is_file() for path in paths):
            continue
        if action == 'database' and row.get('source_database') != 'alpha_trade_fr':
            continue
        backups[action] = {'status': row['status'], 'report': str(p),
                           'scope': 'historical_qualification_not_current_content_or_rights_audit'}
    notifications = {}
    for name in CORE:
        log = root/'log/batch_fr'/f'{name}.txt'
        content = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
        notifications[name] = {'smtp_acceptance_logged': 'NOTIFY' in content and 'serveur SMTP' in content,
                               'telegram_success_logged': 'message Telegram OK' in content,
                               'telegram_failure_logged': 'message Telegram ERROR' in content,
                               'recipient_receipt_confirmed': False}
    blocked = {name: section.get('status') for name, section in cfg.items()
               if name.startswith('fr_') and isinstance(section, dict)
               and str(section.get('status', '')).startswith(('BLOCKED_', 'PENDING_'))}
    return {'as_of_paris': as_of.isoformat(), 'status': 'CLOSURE_WITH_RESERVES_NOT_FULL_GO',
            'market_code': 'FR_EQ', 'collectors': collectors, 'backup_qualifications': backups,
            'notifications': notifications, 'dormant_families': blocked,
            'observed_week_verified': all(c['week_verified'] for c in collectors.values()),
            'real_abrupt_stop_and_resume_verified': False,
            'daily_staging_sql_publication_verified': False,
            'historical_qualification_may_precede_rights_related_archive_purge': True,
            'sql_writes': False, 'collection_performed': False, 'scheduler_changed': False,
            'serving_enabled': False, 'trading_enabled': False}


def main():
    from common.market_calendar import get_market_calendar
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', type=date.fromisoformat,
                        default=datetime.now(PARIS).date())
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    sessions = get_market_calendar('FR_EQ').session_dates(
        args.as_of-timedelta(days=21), args.as_of-timedelta(days=1))
    report = audit(ROOT, as_of=args.as_of, expected_days=[str(s) for s in sessions[-5:]])
    content = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        target = args.output.resolve()
        allowed = (ROOT/'artifacts/fr/research/sprint15_closure').resolve()
        if not target.is_relative_to(allowed):
            raise ValueError('Rapport de clôture hors périmètre FR')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as stream:
            stream.write(content+'\n')
    print(content)


if __name__ == '__main__':
    main()
