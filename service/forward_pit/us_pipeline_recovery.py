"""Explicit pre-open recovery of the last closed US session; never a date bypass.

Read-only qualification is repeated by the runner under the launcher's mutex.
Accounts already completed are preserved. Ambiguous risk/execution attempts
require reconciliation instead of blindly repeating orders.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from sqlalchemy import text

from common.market_calendar import get_market_calendar

ROOT = Path(__file__).resolve().parents[2]
SUCCESS = {'COMPLETED', 'COMPLETED_WITH_WARNINGS'}


def recovery_session(now, *, calendar=None):
    if now.tzinfo is None:
        raise ValueError('Aware recovery timestamp required')
    today = now.astimezone(ZoneInfo('Europe/Paris')).date()
    calendar = calendar or get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = [s for s in calendar.sessions(today-timedelta(days=21), today) if s.is_open]
    current = [s for s in sessions if s.session_date == today]
    if not current:
        return None
    if len(current) != 1 or current[0].open_at_utc is None:
        raise ValueError('Ambiguous US opening')
    if now >= current[0].open_at_utc:
        return None
    closed = [s for s in sessions if s.session_date < today and s.close_at_utc <= now]
    if not closed:
        raise ValueError('Previous closed US session unavailable')
    return max(closed, key=lambda s: s.session_date).session_date


def _record(root, run_id, *, workflow=False):
    if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid workflow identity')
    base = root/'artifacts/ihm_pipeline_runs'
    paths = [base/'pipeline_workflow'/run_id/'record.json'] if workflow else list(base.glob(f'*/{run_id}/record.json'))
    if len(paths) != 1:
        raise ValueError('Workflow receipt unavailable or ambiguous')
    record = json.loads(paths[0].read_text(encoding='utf-8'))
    if record.get('run_id') != run_id:
        raise ValueError('Workflow receipt identity mismatch')
    return record


def recovery_state(engine, *, now=None, calendar=None, root=None, exclude_run_id=None):
    now = now or datetime.now(UTC)
    target = recovery_session(now, calendar=calendar)
    state = dict(visible=False, eligible=False, trade_date=str(target) if target else None,
                 completed_accounts=[], source_run_ids=[], resume_options=None)
    if target is None:
        return state
    if engine is None or engine.url.database != 'alpha_trade':
        raise ValueError('Recovery requires the US alpha_trade database')
    root = Path(root) if root is not None else ROOT
    with engine.connect() as conn:
        rows = conn.execute(text('''SELECT run_id, status, finished_at, requested_count,
            persisted_count, failed_count, details_json FROM pit_collection_runs
            WHERE batch_name='us_pipeline' AND started_at>=:since
            ORDER BY started_at DESC, run_id DESC'''),
            {'since': datetime.combine(target-timedelta(days=1), datetime.min.time())}).mappings().all()
    relevant, active = [], False
    for row in rows:
        if row['run_id'] == exclude_run_id:
            continue
        details = json.loads(row['details_json'] or '{}')
        if row['status'] == 'RUNNING':
            active = True
        if str(details.get('trade_date')) != str(target) or details.get('skip_reason') or row['status'] in {'SKIPPED','DRY_RUN'}:
            continue
        if (row['status'] in SUCCESS and row['finished_at'] and (row['requested_count'] or 0) > 0
                and (row['persisted_count'] or 0) == row['requested_count'] and not row['failed_count']):
            return state  # A newer skipped/failed attempt cannot undo a completed session.
        relevant.append((row, details))
    state['visible'] = True
    if active:
        return dict(state, reason='Un batch US est encore en cours ; aucun rattrapage concurrent.')
    completed, frozen = set(), None
    try:
        for row, details in relevant:
            state['source_run_ids'].append(row['run_id'])
            workflows = details.get('account_workflows') or []
            if not workflows and details.get('workflow_run_id'):
                workflows = [dict(account_id=details.get('account_id'), workflow_run_id=details['workflow_run_id'])]
            if not workflows:
                # Only a proved failure before the workflow starts is replayable.
                if details.get('failed_account_id') and not row['persisted_count']:
                    continue
                raise ValueError('Historique incomplet : vérifier les étapes déjà tentées avant reprise.')
            for workflow in workflows:
                account = workflow['account_id']
                record = _record(root, workflow['workflow_run_id'], workflow=True)
                if record.get('account_id') != account:
                    raise ValueError('Compte du reçu différent du batch.')
                if record['status'] in {'starting','running','scheduled'}:
                    raise ValueError('Un workflow est encore actif ou non réconcilié.')
                count = record.get('workflow_total_steps') or 0
                if record['status'] == 'completed' and record.get('returncode') == 0 and count > 0 and record.get('workflow_completed_steps') == count:
                    completed.add(account)
                    if account == details.get('account_id'):
                        frozen = details.get('options')
                    continue
                if record.get('workflow_current_step_key') in {'risk_management','execution','corporate_actions_sync','corporate_actions_apply'}:
                    raise ValueError(f'{account} : risque/exécution déjà tenté ; réconcilier cette tentative avant rattrapage.')
                children = record.get('workflow_child_run_ids') or []
                for child_id in children:
                    child = _record(root, child_id)
                    if child.get('step_key') in {'risk_management','execution','corporate_actions_sync','corporate_actions_apply'}:
                        raise ValueError(f'{account} : risque/exécution déjà tenté ; réconcilier cette tentative avant rattrapage.')
                if record.get('workflow_completed_steps') and not children:
                    raise ValueError('Reçus des étapes manquants : reprise automatique refusée.')
        if completed and not frozen:
            raise ValueError('Sélection initiale introuvable ; ne pas remplacer les ordres déjà traités.')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return dict(state, reason=str(exc))
    state.update(eligible=True, completed_accounts=sorted(completed), resume_options=frozen)
    return state


def require_recovery(engine, requested, *, now=None, root=None, exclude_run_id=None):
    if type(requested) is not str or date.fromisoformat(requested).isoformat() != requested:
        raise ValueError('Recovery date must be YYYY-MM-DD')
    state = recovery_state(engine, now=now, root=root, exclude_run_id=exclude_run_id)
    if not state['eligible'] or state['trade_date'] != requested:
        raise ValueError(state.get('reason') or 'Rattrapage indisponible : séance déjà finalisée, date incorrecte ou marché ouvert.')
    return state
