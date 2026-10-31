"""Durable admission plans, separate from broker order requests.

This module never connects to a broker and never calls risk approval itself.
Only approved LONG targets may be staged; watching a plan is NOT an order.
Its parameters are frozen, not refreshed from a later YAML configuration.
"""
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import hashlib
import math

from common.winner_pyramiding import (WinnerPyramidingConfig, aware,
    confirmed_breakout, confirmed_winner, initial_quantities, new_campaign,
    reinforcement_quantity)


# Native runtime and intraday risk/replay adapters are connected. This switch
# is NOT operational approval: YAML stays off and admissions require a healthy
# matching watcher. A data/permission failure still rejects every new buy.
RUNTIME_READY = True


def require_runtime_ready():
    if not RUNTIME_READY:
        raise RuntimeError('winner_pyramiding: raccordement intraday non validé ; '
            'aucun ordre autorisé. Conserver enabled: false.')


def require_current_watcher_code(process):
    """Reject a running interpreter which has not loaded the current campaign code."""
    from pathlib import Path
    root = Path(__file__).parent
    files = ['winner_runtime.py', 'winner_live_risk.py', 'winner_risk.py', 'winner_broker.py',
        'winner_market.py', 'winner_campaign_store.py', 'winner_plans.py', 'winner_standard_entry.py',
        'protection_watcher.py']
    dependencies = [root / name for name in files] + [
        root.parent / 'risk_management' / name for name in
        ('live_factor_context.py', 'factor_inputs.py', 'factor_model.py', 'config.py')]
    dependencies.append(root.parent/'common'/'winner_pyramiding.py')
    dependencies.append(root.parent/'common'/'winner_delayed.py')
    if process.create_time() < max(path.stat().st_mtime for path in dependencies):
        raise ValueError('Redémarrer le watcher : son processus est antérieur à la mise à jour Winner')


def require_campaign_watcher(repo, config):
    """Require the actual local account-wide process, not merely an old heartbeat."""
    import socket
    from pathlib import Path
    import psutil
    from sqlalchemy import text
    if not repo.is_watcher_healthy(account_id=config.resolved_account_id, max_age_seconds=180):
        raise ValueError('Campagnes: démarrer le watcher protections local avant l’étape 12')
    with repo.engine.connect() as conn:
        row = conn.execute(text("SELECT pid, hostname FROM watcher_heartbeats WHERE account_id=:account "
            "AND watcher_name='execution_protection_watcher' ORDER BY last_heartbeat_at DESC LIMIT 1"),
            {'account': config.resolved_account_id}).mappings().first()
    if not row or str(row['hostname']).lower() != socket.gethostname().lower():
        raise ValueError('Campaign watcher must be verifiable on this computer')
    process = psutil.Process(int(row['pid']))
    command = process.cmdline()
    def flag(name, default=None):
        return command[command.index(name)+1] if name in command else default
    expected = Path(__file__).with_name('protection_watcher.py').resolve()
    script_ok = any(Path(v).name == expected.name and Path(v).resolve() == expected for v in command)
    if (not script_ok or flag('--mode') != 'service' or flag('--account', 'default') != config.resolved_account_id
            or flag('--broker-mode', 'paper') != config.broker_mode or '--exec-run-id' in command):
        raise ValueError('Campaign watcher process has incompatible mode/account/scope')
    require_current_watcher_code(process)


def plan_from_target(target, config, exec_run_id, *, now=None, calendar=None):
    """Build a frozen plan from a real step11 approval; no budget fabrication."""
    from common.market_calendar import get_market_calendar
    policy = config.winner_pyramiding
    if not policy.enabled or config.market_code != 'US_EQ':
        raise ValueError('Enabled US campaign required')
    if str(target.side or 'long').strip().lower() not in ('long', 'buy'):
        raise ValueError('Winner campaigns are LONG only; no silent SHORT conversion')
    symbol = str(target.symbol).strip().upper()
    if not symbol or not target.risk_run_id or not exec_run_id:
        raise ValueError('Approved target lineage missing')
    if (not math.isfinite(float(target.target_shares)) or target.target_shares <= 0
            or not float(target.target_shares).is_integer()):
        raise ValueError('Winner requires a whole-share step11 target; rerun risk with Winner active')
    risk_budget = target.risk_budget_dollars
    if risk_budget is None or not math.isfinite(float(risk_budget)) or risk_budget <= 0:
        raise ValueError('Missing explicit step11 campaign risk budget')
    now = aware(now or datetime.now(UTC))
    calendar = calendar or get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = [s for s in calendar.sessions(target.trade_date,
        target.trade_date+timedelta(days=policy.entry_valid_sessions*3+40)) if s.is_open]
    if (not sessions or sessions[0].session_date != target.trade_date
            or len(sessions) <= policy.entry_valid_sessions):
        raise ValueError('Qualified signal session and official calendar required')
    expires = aware(sessions[policy.entry_valid_sessions].close_at_utc)
    if now >= expires:
        raise ValueError('Expired step11 approval; a fresh risk run is required')
    full, initial = initial_quantities(target.target_shares, target.entry_price, risk_budget, policy)
    if initial < 1:
        raise ValueError('Campaign budget cannot fund one whole initial share')
    lineage = '|'.join((config.resolved_account_id, config.broker_mode, target.risk_run_id, symbol))
    key = 'wp-'+hashlib.sha256(lineage.encode()).hexdigest()[:40]
    state = new_campaign(key, symbol, full, initial, risk_budget, policy)
    state.update(exec_run_id=exec_run_id, signal_date=target.trade_date.isoformat(),
        account_policy=dict(account_type=config.account_type, leverage=asdict(config.leverage)),
        created_at=now.isoformat(), earliest_entry_open=aware(sessions[1].open_at_utc).isoformat(),
        entry_expires_at=expires.isoformat(), target=asdict(target), parents={}, operations=[],
        admission='STEP11_APPROVED_RECHECK_REQUIRED')
    if policy.confirmation_bars == 0 or policy.market_data_delay_seconds > 0:
        state['entry_policy'] = dict(order_type=config.entry_order_type,
            limit_price_buffer_bps=config.limit_price_buffer_bps,
            max_entry_gap_pct=config.max_entry_gap_pct, submission_window=config.submission_window)
    if policy.confirmation_bars == 0:
        from execution_engine.winner_standard_entry import standard_order_terms
        standard_order_terms(state, quote_check_enabled=policy.standard_entry_quote_check_enabled)
    return state


def stage_targets(store, targets, config, exec_run_id, *, now=None, calendar=None):
    """One active account/mode/symbol; re-running the same approval is idempotent.

    The caller must hold the canonical account execution lock. No production
    caller may invoke this until require_runtime_ready() succeeds.
    """
    if not config.winner_pyramiding.enabled:
        return list(targets), []
    # Validate the complete input before writing any plans.
    longs = [t for t in targets if str(t.side or 'long').lower() in ('long', 'buy')]
    others = [t for t in targets if t not in longs]
    candidates = [plan_from_target(t, config, exec_run_id, now=now, calendar=calendar) for t in longs]
    staged = []
    for state in candidates:
        created = store.create(state, config.resolved_account_id, config.broker_mode,
            state['target']['risk_run_id'])
        staged.append(dict(campaign_id=state['campaign_id'], symbol=state['symbol'],
            outcome='PLAN_ARMED' if created else 'EXISTING_PLAN_NOT_OVERWRITTEN',
            initial_quantity=state['initial_quantity'], full_quantity=state['full_quantity']))
    return others, staged


def next_plan_action(state, bars, *, now, prior_session_high=None,
        price=None, available_cash=0., capacity_quantity=0, new_entries_enabled=True):
    """Pure causal signal, NEVER authorization to submit an order.

    An ENTRY_SIGNAL/ADD_SIGNAL still needs a fresh native risk approval,
    account lock, durable operation reservation and broker reconciliation.
    Protections / deadlines remain due even when the entry switch is off.
    """
    now = aware(now)
    p = WinnerPyramidingConfig(**state['policy'])
    if state['status'] in ('CLOSED', 'CANCELED', 'EXPIRED'):
        return dict(action='TERMINAL')
    if state.get('due_open') and now >= aware(state['due_open']):
        return dict(action='EXIT_DUE', due_open=state['due_open'])
    if any(op['status'] in ('RESERVED', 'UNKNOWN', 'SUBMITTED') for op in state.get('operations', [])):
        return dict(action='RECONCILE_FIRST')
    if not state['lots'] and now >= aware(state['entry_expires_at']):
        return dict(action='EXPIRE_PLAN')
    if not new_entries_enabled:
        return dict(action='ENTRIES_DISABLED')
    if not state['lots']:
        if p.confirmation_bars == 0:
            from execution_engine.winner_standard_entry import standard_entry_window
            if state.get('initial_attempted'):
                return dict(action='INITIAL_ALREADY_ATTEMPTED')
            return (dict(action='ENTRY_SIGNAL', max_quantity=state['initial_quantity'])
                if standard_entry_window(state, now) else dict(action='WAIT_SUBMISSION_WINDOW'))
        if now < aware(state['earliest_entry_open']):
            return dict(action='WAIT_ENTRY_SESSION')
        if state.get('initial_attempted'):
            return dict(action='INITIAL_ALREADY_ATTEMPTED')
        if prior_session_high is not None and confirmed_breakout(bars, prior_session_high, p, now=now):
            return dict(action='ENTRY_SIGNAL', max_quantity=state['initial_quantity'])
    elif price is not None and confirmed_winner(state, bars, now=now):
        quantity = reinforcement_quantity(state, price, available_cash, capacity_quantity)
        if quantity > 0:
            return dict(action='ADD_SIGNAL', max_quantity=quantity)
    return dict(action='WAIT_CONFIRMATION')


def reserve_operation(store, state, version, *, action, quantity, approval, now):
    """CAS outbox written BEFORE HTTP; ambiguity never permits a second order.

    A native risk adapter must produce the approval at this very decision
    boundary. The token is not supplied by an LLM or a UI checkbox.
    """
    now = aware(now)
    if action not in ('ENTRY', 'ADD') or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError('Invalid campaign buy operation')
    if state['status'] in ('CLOSED', 'CANCELED', 'EXPIRED'):
        raise ValueError('Terminal campaign')
    if state.get('due_open') and now >= aware(state['due_open']):
        raise ValueError('Campaign deadline reached; no further buys')
    if action == 'ENTRY':
        from execution_engine.winner_standard_entry import standard_initial, standard_entry_window
        allowed = (standard_entry_window(state, now) if standard_initial(state) else
                   aware(state['earliest_entry_open']) <= now < aware(state['entry_expires_at']))
        if not allowed:
            raise ValueError('Outside approved campaign entry window')
    if any(o['status'] in ('RESERVED', 'UNKNOWN', 'SUBMITTED') for o in state['operations']):
        raise ValueError('Unresolved operation; reconcile before retry')
    from execution_engine.winner_standard_entry import standard_initial
    no_quote_approval = (action == 'ENTRY' and standard_initial(state)
        and state['policy'].get('standard_entry_quote_check_enabled', True) is False
        and approval.get('standard_entry_quote_check_enabled') is False
        and approval.get('realtime_sip_qualified') is False
        and approval.get('price_basis') == 'bounded_standard_limit'
        and bool(approval.get('reference_price_asof')))
    if no_quote_approval:
        from execution_engine.winner_standard_entry import standard_order_terms
        order_type, cap = standard_order_terms(state, quote_check_enabled=False)
        no_quote_approval = (approval.get('order_type') == order_type
            and approval.get('order_limit_price') == cap
            and float(approval.get('limit_price', 0)) >= cap)
    from common.winner_delayed import delayed_entry, delayed_price_limit
    delayed_approval=False
    if (approval.get('delayed_sip_qualified') is True and delayed_entry(state,action)
            and approval.get('realtime_sip_qualified') is False
            and approval.get('price_basis')=='bounded_delayed_sip_limit'):
        cap=delayed_price_limit(state,approval.get('delayed_evidence') or {},now)
        delayed_approval=(approval.get('order_type')=='limit'
            and approval.get('order_limit_price')==cap and approval.get('limit_price')==cap)
    if delayed_entry(state,action) and not delayed_approval:
        raise ValueError('Preuve native SIP retardée et plafond explicite requis')
    if (approval.get('producer') != 'native_intraday_risk'
            or approval.get('campaign_id') != state['campaign_id']
            or approval.get('account_id') != state['account_id']
            or approval.get('broker_mode') != state['broker_mode']
            or approval.get('state_version') != version
            or approval.get('side') != 'buy'
            or approval.get('entry_data_qualified') is not True
            or not (approval.get('realtime_sip_qualified') is True or no_quote_approval or delayed_approval)
            or approval.get('regime_qualified') is not True
            or not approval.get('config_hash') or not approval.get('portfolio_hash')
            or approval.get('qualified') is not True
            or approval.get('max_quantity', 0) < quantity
            or not aware(approval['available_at']) <= now <= aware(approval['valid_until'])
            or (now-aware(approval['available_at'])).total_seconds() > 60):
        raise ValueError('Fresh scoped native intraday risk approval required')
    if action == 'ENTRY':
        if state['lots'] or state.get('initial_attempted') or quantity > state['initial_quantity']:
            raise ValueError('Initial campaign entry already used or exceeds budget')
        state['initial_attempted'] = True
    else:
        p = WinnerPyramidingConfig(**state['policy'])
        if not p.reinforcement_enabled or state['add_attempted'] or p.initial_position_fraction == 1 or not state['lots']:
            raise ValueError('Reinforcement disabled or already attempted')
        if quantity > state['full_quantity']-sum(l['quantity'] for l in state['lots']):
            raise ValueError('Reinforcement exceeds frozen campaign target')
        state['add_attempted'] = True
    key = state['campaign_id']+'-'+action.lower()
    state['operations'].append(dict(key=key, action=action, quantity=quantity,
        status='RESERVED', reserved_at=now.isoformat(), approval=approval))
    return store.save(state, version), key
