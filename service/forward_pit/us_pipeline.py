"""Configurable scheduled US steps 1..12 using the Pipeline page workflow."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from common.market_calendar import get_market_calendar
from common.config_loader import load_config
from ihm.services.pipeline_runner import (
    build_pipeline_command, get_pipeline_steps, pipeline_page_default_options,
)

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]


def load_pipeline_policy():
    policy = load_config(str(ROOT/'config.yaml')).get('us_pipeline')
    if not isinstance(policy, dict):
        raise ValueError('Section us_pipeline required in config.yaml')
    return policy


def selected_steps(numbers, *, config_key='steps'):
    if (not isinstance(numbers, list) or not numbers or
            any(type(n) is not int or not 1 <= n <= 12 for n in numbers) or
            len(set(numbers)) != len(numbers)):
        raise ValueError(f'us_pipeline.{config_key} must be a nonempty list of unique integers 1..12')
    wanted = sorted(numbers)
    steps = tuple(s for s in get_pipeline_steps() if s.num in {str(n) for n in wanted})
    if [s.num for s in steps] != [str(n) for n in wanted]:
        raise ValueError('US Pipeline definition differs from selected numbered steps')
    return steps


def session_steps(policy, day):
    """Choose once from the US session, never from the clock of a later step."""
    key = 'steps_friday' if day.weekday() == 4 else 'steps'
    return key, selected_steps(policy.get(key), config_key=key)


def require_paper_account(account_id):
    # Fresh local registry, no broker request or credentials in the plan.
    from service.alpaca.accounts import AccountRegistry
    if AccountRegistry().resolve(account_id).mode != 'paper':
        raise ValueError('us_pipeline PAPER requires an Alpaca account configured in paper mode')


def execution_options(options, policy, steps):
    if options.execution_mode == 'live':
        raise ValueError('Scheduled us_pipeline forbids LIVE execution')
    mode = policy.get('execution_mode', 'simulate')
    account_id = policy.get('account_id', 'default')
    if mode not in ('simulate', 'paper'):
        raise ValueError('us_pipeline.execution_mode must be simulate or paper; LIVE forbidden')
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError('us_pipeline.account_id must be a nonempty account identifier')
    account_id = account_id.strip()
    if mode == 'paper' and any(s.num in ('11', '12') for s in steps):
        require_paper_account(account_id)
    return replace(options, execution_mode=mode, account_id=account_id)


def collection_options(options, cfg, day):
    """Pin collection windows to the session, not the wall clock after midnight."""
    from common.universe_files import universe_file_source_from_path
    values = {}
    bars = cfg.get('bars_collection') or {}
    values.update(eodhd_import_target_date=day.isoformat(),
                  eodhd_import_require_target_coverage=True,
                  eodhd_import_wait_for_publication=True,
                  eodhd_import_min_target_coverage=float(bars.get('min_coverage_ratio', .95)),
                  eodhd_import_benchmark_symbol=str(bars.get('benchmark_symbol', 'SPY')))
    shared_file = cfg.get('symbols_file')
    if shared_file:
        source = universe_file_source_from_path(shared_file, root=ROOT)
        values.update(screener_custom_universe_file=str(shared_file),
                      sentiment_pipeline_symbol_source=source,
                      ml_predict_symbol_source=source,
                      eodhd_import_symbol_source=source)
    for name in ('quotes', 'earnings'):
        policy = cfg.get(f'{name}_collection')
        if policy is None:
            continue
        prefix = f'data_integrity_{name}_'
        source = universe_file_source_from_path(shared_file or policy['symbols_file'], root=ROOT)
        lookback = int(policy['lookback_days'])
        forward = int(policy.get('forward_days', 0))
        if lookback < 0 or forward < 0:
            raise ValueError('Collection windows must be nonnegative')
        values.update({prefix+'symbol_source': source,
            prefix+'from_date': (day-timedelta(days=lookback)).isoformat(),
            prefix+'to_date': (day+timedelta(days=forward)).isoformat(),
            prefix+'batch_size': int(policy['batch_size'])})
        if name == 'earnings':
            values[prefix+'provider'] = policy.get('provider', 'finnhub')
            values[prefix+'resume'] = True
    return replace(options, **values)


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
    policy = load_pipeline_policy()
    if skip:
        return Outcome(details={'skip_reason': skip, 'trade_date': str(day), 'counter_unit': 'pipeline_steps'})
    steps_key, steps = session_steps(policy, day)
    options = collection_options(pipeline_page_default_options(trade_date=str(day)), cfg, day)
    options = execution_options(options, policy, steps)
    plan = dict(market_code='US_EQ', trade_date=str(day), defaults='FRESH_PIPELINE_PAGE',
        date_override='PIN_CURRENT_US_SESSION_NO_OLD_SNAPSHOT', options=asdict(options),
        steps=[dict(number=s.num, key=s.key, command=build_pipeline_command(s.key, options)) for s in steps],
        selected_step_numbers=[int(s.num) for s in steps],
        configuration_source='config.yaml:us_pipeline',
        steps_configuration_source=f'config.yaml:us_pipeline.{steps_key}',
        counter_unit='pipeline_steps', training=False,
        account_id=options.account_id,
        execution_mode=options.execution_mode,
        watcher_before_execution=any(s.num=='12' for s in steps) and options.execution_mode=='paper',
        execution_orders=any(s.num=='12' for s in steps) and options.execution_mode=='paper')
    outcome = Outcome(requested=len(steps), details=plan)
    if dry_run:
        LOGGER.info('US pipeline plan: %s', json.dumps(plan, default=str))
        return outcome
    directory = ROOT/'artifacts/operations/us_pipeline'/run_id
    directory.mkdir(parents=True, exist_ok=False)
    (directory/'plan.json').write_text(json.dumps(plan, indent=2, default=str), encoding='utf-8')
    def before_step(step, current_options, stop_event):
        if step.key != 'execution' or current_options.execution_mode != 'paper':
            return None
        from service.forward_pit.watcher_startup import ensure_watcher
        result = ensure_watcher(engine, current_options, directory=directory, stop_event=stop_event)
        outcome.details['watcher_before_execution_result'] = result
        return result
    try:
        record = start_pipeline_workflow(options, db_config={'name': 'alpha_trade'},
            selected_step_keys=tuple(s.key for s in steps), before_step=before_step)
    except Exception as exc:
        outcome.failed = 1
        raise BatchRunError(f'US pipeline could not start: {exc}', outcome) from exc
    outcome.details.update(workflow_run_id=record.run_id, plan_path=str(directory/'plan.json'))
    LOGGER.info('US pipeline workflow=%s trade_date=%s source=%s steps=%s',
        record.run_id, day, plan['steps_configuration_source'], plan['selected_step_numbers'])
    previous = None
    while True:
        try:
            snapshot = poll_pipeline_run(record.run_id)
        except Exception as exc:
            outcome.failed = 1
            raise BatchRunError(f'US workflow monitoring failed: {exc}', outcome) from exc
        if snapshot is None:
            outcome.failed = 1
            raise BatchRunError('US workflow monitoring lost; no subsequent workflow launched', outcome)
        completed = int(snapshot.get('workflow_completed_steps') or 0)
        outcome.received = completed
        outcome.persisted = completed
        progress = (completed, snapshot.get('workflow_current_step_label'))
        if progress != previous:
            LOGGER.info('US pipeline %d/%d step=%s', completed, len(steps), progress[1])
            previous = progress
        if snapshot.get('status') not in ('starting', 'running', 'scheduled'):
            outcome.details['workflow_status'] = snapshot.get('status')
            outcome.details['workflow_summary'] = snapshot.get('run_summary') or {}
            outcome.details['workflow_log'] = snapshot.get('combined_path')
            if snapshot.get('status') != 'completed' or completed != len(steps):
                outcome.failed = 1
                failed_step = progress[1] or 'voir journal workflow'
                children = snapshot.get('workflow_child_run_ids') or []
                if children:
                    last_child = poll_pipeline_run(children[-1]) or {}
                    failed_step = last_child.get('step_label') or failed_step
                    outcome.details['failed_child_run_id'] = children[-1]
                    outcome.details['failed_child_returncode'] = last_child.get('returncode')
                raise BatchRunError(f'US pipeline interrupted after {completed}/{len(steps)} steps ({failed_step}); '
                    f'status={snapshot.get("status")} workflow={record.run_id}', outcome)
            return outcome
        time.sleep(.5)
