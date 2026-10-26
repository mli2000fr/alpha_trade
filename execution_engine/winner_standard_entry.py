"""Zero-confirmation entries: standard DAY order, durable Winner lifecycle.

No extended-hours execution, no substitute for fresh native risk approval.
All entry terms are frozen at admission; later YAML changes cannot widen them.
"""
from datetime import timedelta
import math
from zoneinfo import ZoneInfo

from common.market_calendar import get_market_calendar
from common.winner_pyramiding import aware


def standard_initial(state):
    return state['policy']['confirmation_bars'] == 0 and not state['lots']


def standard_entry_window(state, now):
    """Submission window, NOT permission to execute before the next RTH open."""
    now = aware(now)
    if not standard_initial(state) or not aware(state['created_at']) <= now < aware(state['entry_expires_at']):
        return False
    terms = state.get('entry_policy')
    if not terms or terms['submission_window'] not in ('post_close', 'pre_open', 'both'):
        return False
    day = now.astimezone(ZoneInfo('America/New_York')).date()
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = [s for s in cal.sessions(day-timedelta(days=14), day+timedelta(days=14)) if s.is_open]
    current = next((s for s in sessions if s.open_at_utc <= now < s.close_at_utc), None)
    if current:
        return now >= aware(state['earliest_entry_open'])
    next_session = next((s for s in sessions if s.open_at_utc > now), None)
    previous = [s for s in sessions if s.close_at_utc <= now]
    if not previous or not next_session or next_session.open_at_utc < aware(state['earliest_entry_open']):
        return False
    # Same market-calendar distinction as the standard post-close/pre-open
    # submission contract. DAY orders are always regular-hours only.
    preopen = day == next_session.session_date
    return terms['submission_window'] in ('both', 'pre_open' if preopen else 'post_close')


def standard_order_terms(state):
    terms = state.get('entry_policy') or {}
    order_type = terms.get('order_type')
    reference = float(state['target']['entry_price'])
    if order_type not in ('market', 'limit') or not math.isfinite(reference) or reference <= 0:
        raise ValueError('Frozen standard entry type/reference missing')
    limit = (round(reference*(1+float(terms['limit_price_buffer_bps'])/10000), 2)
             if order_type == 'limit' else None)
    if limit is not None and (not math.isfinite(limit) or limit <= 0):
        raise ValueError('Invalid standard entry limit')
    return order_type, limit


def standard_risk_price(state, ask):
    """Reserve for a higher limit too; never enlarge the step-11 quantity."""
    _, limit = standard_order_terms(state)
    reference = float(state['target']['entry_price'])
    gap = float(state['entry_policy']['max_entry_gap_pct'])
    if gap > 0 and abs(ask/reference-1) > gap:
        raise ValueError('Standard entry gap exceeds approved maximum')
    return max(ask, limit or ask)


def submit_standard_plans(store, repo, broker, config, plans):
    """Called by step 12 WHILE its canonical account execution lock is held.

    Never re-acquire/release that lock, use the legacy buy/protection loop,
    or retry an ambiguous POST. The normal watcher takes over the same state.
    """
    from execution_engine.winner_runtime import WinnerCampaignRuntime
    from execution_engine.winner_broker import NativeWinnerBroker
    from execution_engine.winner_market import NativeWinnerMarket
    from execution_engine.winner_live_risk import NativeWinnerRisk
    runtime = WinnerCampaignRuntime(store, repo, NativeWinnerBroker(repo, broker, config), config,
        market=NativeWinnerMarket(repo.engine, config.resolved_account_id),
        risk=NativeWinnerRisk(repo, broker, config))
    runtime.metrics['standard_orders'] = []
    runtime.metrics['standard_filled_orders'] = 0
    for plan in plans:
        if plan['outcome'] != 'PLAN_ARMED':
            continue  # Re-launch cannot resubmit an existing campaign.
        record = store.get(plan['campaign_id'])
        if not record or not standard_initial(record['state']):
            continue
        runtime.state, runtime.version = record['state'], record['version']
        runtime.metrics['winner_plans_watched'] += 1
        runtime.now = runtime.clock()
        try:
            runtime.tick()
        except Exception as exc:
            runtime.metrics['winner_failures'] += 1
            runtime.blocked('STANDARD_ENTRY_RECONCILIATION_REQUIRED: '+str(exc))
        observed = store.get(plan['campaign_id'])['state']
        for operation in observed['operations']:
            if operation['action'] != 'ENTRY' or not operation.get('intent'):
                continue
            intent = operation['intent']
            filled = observed['parents'].get(intent['intent_id'], {}).get('booked_quantity', 0)
            runtime.metrics['standard_orders'].append(dict(symbol=observed['symbol'],
                status=operation['status'], requested_quantity=intent['qty'], filled_quantity=filled,
                broker_order_id=operation.get('broker_id')))
            runtime.metrics['standard_filled_orders'] += int(filled > 0)
    runtime.metrics['requires_reconciliation'] = bool(runtime.metrics['winner_failures'] or any(
        'RECONCILIATION' in detail['reason'] for detail in runtime.metrics['winner_details']))
    return runtime.metrics
