"""Scheduled US steps 1..9 using the same workflow engine as the Pipeline page."""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from common.market_calendar import get_market_calendar
from ihm.services.pipeline_runner import (
    build_pipeline_command, get_pipeline_steps, pipeline_page_default_options,
)

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]


def first_nine():
    steps = tuple(s for s in get_pipeline_steps() if s.num in {str(i) for i in range(1, 10)})
    if [s.num for s in steps] != [str(i) for i in range(1, 10)]:
        raise ValueError('US Pipeline definition must contain exactly steps 1..9 in order')
    return steps


def session_plan(now, *, calendar=None):
    """No weekday-only fallback; date is the actual NY session, frozen once."""
    if now.tzinfo is None:
        raise ValueError('Aware run timestamp required')
    paris, ny = now.astimezone(ZoneInfo('Europe/Paris')), now.astimezone(ZoneInfo('America/New_York'))
    day = ny.date()
    calendar = calendar or get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    if paris.weekday() >= 5 or day.weekday() >= 5:
        return day, 'NON_TRADING_DAY'
    sessions = calendar.sessions(day, day)
    opened = [s for s in sessions if s.is_open]
    if not opened:
        return day, 'NON_TRADING_DAY'
    if len(opened) != 1 or opened[0].close_at_utc is None:
        raise ValueError('Ambiguous US calendar session')
    if now < opened[0].close_at_utc:
        return day, 'SESSION_NOT_CLOSED'
    return day, None


def execute_pipeline(engine, cfg, run_id, dry_run, *, now=None):
    # Lazy import prevents the registration module from forming an import cycle.
    from service.forward_pit.batch import Outcome, BatchRunError
    from ihm.services.process_registry import start_pipeline_workflow, poll_pipeline_run
    if engine.url.database != 'alpha_trade':
        raise ValueError('US pipeline requires alpha_trade, never CN/FR')
    if cfg.get('market_code') != 'US_EQ':
        raise ValueError('US_EQ market scope required')
    day, skip = session_plan(now or datetime.now(UTC))
    steps = first_nine()
    if skip:
        return Outcome(details={'skip_reason': skip, 'trade_date': str(day), 'counter_unit': 'pipeline_steps'})
    options = pipeline_page_default_options(trade_date=str(day))
    plan = dict(market_code='US_EQ', trade_date=str(day), defaults='FRESH_PIPELINE_PAGE',
        date_override='PIN_CURRENT_US_SESSION_NO_OLD_SNAPSHOT', options=asdict(options),
        steps=[dict(number=s.num, key=s.key, command=build_pipeline_command(s.key, options)) for s in steps],
        counter_unit='pipeline_steps', training=False, execution_orders=False)
    outcome = Outcome(requested=len(steps), details=plan)
    if dry_run:
        LOGGER.info('US pipeline plan: %s', json.dumps(plan, default=str))
        return outcome
    directory = ROOT/'artifacts/operations/us_pipeline_1_9'/run_id
    directory.mkdir(parents=True, exist_ok=False)
    (directory/'plan.json').write_text(json.dumps(plan, indent=2, default=str), encoding='utf-8')
    record = start_pipeline_workflow(options, db_config={'name': 'alpha_trade'},
        selected_step_keys=tuple(s.key for s in steps))
    outcome.details.update(workflow_run_id=record.run_id, plan_path=str(directory/'plan.json'))
    LOGGER.info('US pipeline workflow=%s trade_date=%s steps=1..9', record.run_id, day)
    previous = None
    while True:
        snapshot = poll_pipeline_run(record.run_id)
        if snapshot is None:
            outcome.failed = 1
            raise BatchRunError('US workflow monitoring lost; no subsequent workflow launched', outcome)
        completed = int(snapshot.get('workflow_completed_steps') or 0)
        outcome.received = completed
        outcome.persisted = completed
        progress = (completed, snapshot.get('workflow_current_step_label'))
        if progress != previous:
            LOGGER.info('US pipeline %d/9 step=%s', *progress)
            previous = progress
        if snapshot.get('status') not in ('starting', 'running', 'scheduled'):
            outcome.details['workflow_status'] = snapshot.get('status')
            outcome.details['workflow_summary'] = snapshot.get('run_summary') or {}
            outcome.details['workflow_log'] = snapshot.get('combined_path')
            if snapshot.get('status') != 'completed' or completed != 9:
                outcome.failed = 1
                failed_step = snapshot.get('workflow_current_step_label') or 'voir journal workflow'
                raise BatchRunError(f'US pipeline interrupted after {completed}/9 steps ({failed_step}); '
                    f'status={snapshot.get("status")} workflow={record.run_id}', outcome)
            return outcome
        time.sleep(.5)
