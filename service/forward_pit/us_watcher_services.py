"""Hourly supervisor of the existing local US PAPER protection services.

Starting a watcher delegates protection management to the ordinary 12.bis
service. This supervisor never replaces a living process or runs steps 11/12.
"""
from dataclasses import replace
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from threading import Event
from zoneinfo import ZoneInfo

from common.market_calendar import get_market_calendar
from execution_engine.db_io import ExecutionRepository
from ihm.services.pipeline_runner import PipelineLaunchOptions
from service.alpaca.accounts import AccountRegistry
from service.forward_pit.outcomes import BatchRunError, Outcome
from service.forward_pit.watcher_startup import (
    ensure_watcher, find_running_service, healthy_service,
)

ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(UTC)


def market_state(now=None):
    now = now if now is not None else _utcnow()
    if now.tzinfo is None:
        raise ValueError('Horodatage UTC explicite requis')
    now = now.astimezone(UTC)
    day = now.astimezone(ZoneInfo('America/New_York')).date()
    sessions = get_market_calendar('US_EQ', allow_us_weekday_fallback=False).sessions(day, day)
    session = next((s for s in sessions if s.is_open), None)
    return dict(checked_at_utc=now.isoformat(), session_date=str(day),
                market_open=bool(session and session.open_at_utc <= now < session.close_at_utc),
                open_at_utc=session.open_at_utc.isoformat() if session else None,
                close_at_utc=session.close_at_utc.isoformat() if session else None)


def collect(engine, cfg, run_id, dry_run):
    if engine.url.database != 'alpha_trade' or cfg.get('market_code') != 'US_EQ':
        raise ValueError('Supervision watchers réservée à alpha_trade / US_EQ PAPER')
    state = market_state()
    outcome = Outcome(details=dict(market=state, accounts=[], started=0, already_running=0,
                                   broker_mode='paper', services_survive_batch_exit=True))
    if not state['market_open']:
        outcome.details['skip_reason'] = 'US_MARKET_CLOSED'
        LOGGER.info('Watchers : marché US fermé, aucun service démarré ou arrêté')
        return outcome
    accounts = cfg.get('account_ids')
    if (not isinstance(accounts, list) or not accounts
            or any(not isinstance(a, str) or not a.strip() or a != a.strip() for a in accounts)
            or len(accounts) != len(set(accounts))):
        raise ValueError('account_ids : liste non vide de comptes uniques requise')
    timeout = cfg.get('startup_timeout_seconds', 120)
    if type(timeout) is not int or not 1 <= timeout <= 300:
        raise ValueError('startup_timeout_seconds : entier entre 1 et 300 requis')
    # Validate the whole scope before starting any service; never silently adopt
    # another account or a LIVE credential when a configured account is missing.
    registry = AccountRegistry()
    for account in accounts:
        if registry.resolve(account).mode != 'paper':
            raise ValueError(f'Compte {account} : service réservé au mode PAPER')
    outcome.requested = len(accounts)
    repo = ExecutionRepository(engine)
    folder = ROOT/'artifacts/operations/us_watcher_services'/run_id

    def save(name):
        if not dry_run:
            folder.mkdir(parents=True, exist_ok=True)
            target = folder/name
            temp = target.with_suffix('.tmp')
            temp.write_text(json.dumps(outcome.__dict__, indent=2, ensure_ascii=False), encoding='utf-8')
            temp.replace(target)

    save('progress.json')
    # Sequential starts avoid contention on the shared heartbeat/leader tables.
    for account in accounts:
        row = dict(account_id=account)
        try:
            existing = find_running_service(account)
            if existing is not None:
                row.update(status='ALREADY_RUNNING', pid=existing.pid)
                outcome.details['already_running'] += 1
                # Presence prevents a duplicate even during startup or a health
                # failure. An unhealthy living service is reported, never killed.
                if not healthy_service(repo, account):
                    raise RuntimeError('Service présent mais heartbeat non sain ; aucun redémarrage automatique')
                outcome.received += 1
                LOGGER.info('Watchers : compte=%s déjà démarré pid=%s, conservé', account, existing.pid)
            elif not market_state()['market_open']:
                row.update(status='SKIPPED_MARKET_CLOSED')
                outcome.empty += 1
            elif dry_run:
                row.update(status='WOULD_START')
            else:
                options = replace(PipelineLaunchOptions(), execution_mode='paper', account_id=account,
                                  q051_paper_enabled=False)
                result = ensure_watcher(engine, options, directory=folder, stop_event=Event(),
                                        timeout_seconds=timeout)
                row.update(result)
                if result['status'] not in ('READY', 'REUSED_HEALTHY'):
                    raise RuntimeError(f"Disponibilité watcher non confirmée : {result['status']}")
                outcome.received += 1
                if result['status'] == 'READY':
                    outcome.persisted += 1
                    outcome.details['started'] += 1
                else:
                    outcome.details['already_running'] += 1
        except Exception as exc:
            row.update(status='NEEDS_ATTENTION', error=str(exc))
            outcome.failed += 1
            outcome.warnings.append(f'{account} : {exc}')
            LOGGER.error('Watchers : compte=%s : %s', account, exc)
        outcome.details['accounts'].append(row)
        save('progress.json')
    outcome.details['finished_at_utc'] = _utcnow().isoformat()
    save('report.json')
    LOGGER.info('Watchers : %s/%s disponibles, %s démarré(s), %s déjà présent(s), %s erreur(s)',
                outcome.received, outcome.requested, outcome.details['started'],
                outcome.details['already_running'], outcome.failed)
    if outcome.failed:
        raise BatchRunError('Supervision watchers incomplète ; consulter les comptes en erreur', outcome)
    return outcome
