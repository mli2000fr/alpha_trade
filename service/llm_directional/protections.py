"""Frozen, prospective protection policy for new GPT-selected US PAPER entries.

The existing llm_directional_runs.config_json is the durable source, not today's
YAML. No extra table is necessary. Ordinary, manual, FR and CN trades are excluded.
"""
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta, time
import json
import math
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ProtectionProfile:
    enabled: bool = True
    stop_loss_pct: float = .07
    exit_session: int = 21  # Actual entry session = 1.
    trailing_stop_pct: float = .20

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError('protections.enabled doit être booléen')
        for key in ('stop_loss_pct', 'trailing_stop_pct'):
            value = getattr(self, key)
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value < 1:
                raise ValueError(f'protections.{key} doit être dans ]0,1[')
        if type(self.exit_session) is not int or not 2 <= self.exit_session <= 252:
            raise ValueError('protections.exit_session : entier entre 2 et 252')


def archived_profile(config_json):
    value = json.loads(config_json).get('protections')
    if value is None:
        return None  # Older analyses keep the historical policy.
    profile = ProtectionProfile(**value)
    return profile if profile.enabled else None


def profile_for_risk(engine, risk_run_id, symbol, *, account_id, broker_mode):
    """Read the exact bound run, even months later; never use latest or expiry."""
    if account_id != 'default' or broker_mode != 'paper':
        return None
    from sqlalchemy import inspect, text
    if engine.dialect.name == 'mysql' and engine.url.database != 'alpha_trade':
        return None
    if not inspect(engine).has_table('llm_directional_runs'):
        return None
    with engine.connect() as conn:
        rows = conn.execute(text('''SELECT config_json, selected_json
            FROM llm_directional_runs WHERE risk_run_id=:risk AND account_id='default'
            AND status='COMPLETED' '''), {'risk': risk_run_id}).mappings().all()
    if len(rows) > 1:
        raise ValueError('Plusieurs analyses GPT liées au même risque')
    if not rows or symbol not in json.loads(rows[0]['selected_json']):
        return None
    return archived_profile(rows[0]['config_json'])


def scoped_execution_config(config, profile):
    if profile is None or not profile.enabled:
        return config
    if config.market_code != 'US_EQ' or config.broker_mode != 'paper' or config.resolved_account_id != 'default':
        raise ValueError('Protections GPT réservées au compte default US PAPER')
    return replace(config, llm_protection_profile=asdict(profile),
                   trailing_pct_override=profile.trailing_stop_pct,
                   swing_only=False,  # Dedicated stops must protect from the fill, not tomorrow.
                   time_stop=replace(config.time_stop, enabled=False))


def safe_trailing_trigger(fill_price, profile, side='buy'):
    # Never replace the 7% stop with a looser 20% stop. At the handover, the
    # trailing floor must be >= the original floor: .8*price >= .93*entry.
    from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
    from core.direction import is_short_side
    if is_short_side(side):
        ceiling = Decimal(str(round(fill_price*(1+profile.stop_loss_pct), 2)))
        threshold = min(Decimal(str(fill_price)), ceiling/(1+Decimal(str(profile.trailing_stop_pct))))
        return float(threshold.quantize(Decimal('.0001'), rounding=ROUND_FLOOR))
    # Same cent-rounded SL as the order builder; round activation upwards.
    floor = Decimal(str(round(fill_price*(1-profile.stop_loss_pct), 2)))
    threshold = max(Decimal(str(fill_price)), floor/(1-Decimal(str(profile.trailing_stop_pct))))
    return float(threshold.quantize(Decimal('.0001'), rounding=ROUND_CEILING))


def persist_order(repo, intent, order, *, account_id):
    """Critical GPT protection lineage must not silently fail to persist."""
    from execution_engine.order_intents import intent_to_alpaca_payload
    repo.upsert_execution_order_request_from_intent(intent, account_id=account_id, status=order.status)
    repo.upsert_execution_broker_order(intent, order, account_id=account_id,
        raw_payload=intent_to_alpaca_payload(intent))


def submit_order(repo, broker, intent, *, account_id):
    """Record intent before HTTP; keep NEW on an ambiguous transport failure.

    Synchronisation / operator review must resolve unknown state before retry.
    A definite 4xx rejection can be retried after the next reconciliation.
    """
    from execution_engine.models import OrderStatus
    from service.alpaca.trading_client import BrokerApiError
    repo.upsert_execution_order_request_from_intent(intent, account_id=account_id, status=OrderStatus.NEW)
    try:
        order = broker.submit_intent(intent)
    except BrokerApiError as exc:
        if 400 <= exc.status_code < 500 and exc.status_code != 429 and 'client_order_id' not in str(exc.body):
            repo.upsert_execution_order_request_from_intent(intent, account_id=account_id,
                status=OrderStatus.REJECTED, failure_reason=str(exc)[:500])
        raise
    persist_order(repo, intent, order, account_id=account_id)
    return order


def exit_open(opened_at, profile, *, calendar=None):
    from common.market_calendar import get_market_calendar
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=UTC)  # Broker fills persisted UTC.
    day = opened_at.astimezone(ZoneInfo('America/New_York')).date()
    calendar = calendar or get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = [s for s in calendar.sessions(day, day+timedelta(days=profile.exit_session*3+32)) if s.is_open]
    if not sessions or sessions[0].session_date != day or len(sessions) < profile.exit_session:
        raise ValueError('Calendrier US insuffisant pour la sortie GPT')
    due = sessions[profile.exit_session-1]
    if due.open_at_utc is None:
        raise ValueError('Heure officielle d’ouverture US absente')
    return due.open_at_utc


def exit_action(due, *, now=None, calendar=None):
    """Queue MOO only for the immediately next session; recover late in RTH."""
    from common.market_calendar import get_market_calendar
    now = now or datetime.now(UTC)
    if now.tzinfo is None or due.tzinfo is None:
        raise ValueError('Horodatages UTC explicites requis')
    calendar = calendar or get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    ny = now.astimezone(ZoneInfo('America/New_York'))
    opened = [s for s in calendar.sessions(ny.date(), ny.date()+timedelta(days=10)) if s.is_open]
    current = next((s for s in opened if s.session_date == ny.date()), None)
    if now >= due:
        return 'LATE_MARKET' if current and current.open_at_utc <= now < current.close_at_utc else None
    next_session = next((s for s in opened if s.open_at_utc > now), None)
    if next_session is None or next_session.open_at_utc != due:
        return None
    # Alpaca OPG: accepted before 09:28 ET, or from 19:00 ET for next open.
    if ny.date() == due.astimezone(ZoneInfo('America/New_York')).date():
        return 'MOO' if ny.time() < time(9, 28) else None
    return 'MOO' if ny.time() >= time(19) else None


def apply_scheduled_exit(watcher, row, profile, metrics, *, now=None):
    """Lot deadline independent of profit; stable client ID and strict cancel.

    A stop filled during cancellation wins the race: no second sale is sent.
    """
    import hashlib
    from execution_engine.models import IntentRole, OrderIntent, OrderStatus, EventType
    from execution_engine.audit import make_event
    from common.quantity_utils import is_effectively_integer_quantity
    now = now or datetime.now(UTC)
    due = exit_open(row['opened_at'], profile)
    action = exit_action(due, now=now)
    if action is None:
        return
    account = str(row['account_id'])
    broker_mode = str(row.get('broker_mode') or 'paper')
    if account != 'default' or broker_mode != 'paper':
        raise ValueError('Sortie temporelle GPT réservée au compte default PAPER')
    parent, symbol = str(row['parent_intent_id']), str(row['symbol'])
    if watcher._repo.has_open_exit_order_for_symbol(account_id=account, symbol=symbol):
        return
    broker = watcher._broker_for(broker_mode, account)
    children = watcher._repo.load_open_child_orders(parent)
    for child in children:
        if not child.broker_order_id:
            raise RuntimeError('Protection sans identifiant broker ; sortie GPT bloquée')
        if not broker.cancel_broker_order(child.broker_order_id):
            raise RuntimeError('Annulation non confirmée ; sortie GPT bloquée')
        latest = broker.poll_order_status(child.broker_order_id, child.intent_id)
        if latest.status == OrderStatus.FILLED:
            return
        if latest.status not in {OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED}:
            raise RuntimeError('Protection encore active ; nouvelle vente GPT interdite')
        child_intent = watcher._build_existing_child_intent(
            _parent_context(parent, row), child,
            IntentRole.TRAILING_STOP if child.order_type == 'trailing_stop' else IntentRole.INITIAL_STOP)
        persist_order(watcher._repo, child_intent, latest, account_id=account)
    position = broker.get_position(symbol)
    short = str(row.get('parent_side') or 'buy') in ('sell', 'short')
    if not position or str(position.get('side') or 'long') != ('short' if short else 'long'):
        return
    qty = min(float(row['remaining_qty']), abs(float(position.get('qty') or 0)))
    if qty <= 0:
        return
    if not is_effectively_integer_quantity(qty):
        raise ValueError('Quantité fractionnaire : sortie MOO GPT indisponible')
    # An expired/rejected opening order must not prevent a late market recovery.
    # Stable within one attempt/session; a later session is a distinct retry.
    attempt = action if action == 'MOO' else f'{action}:{now.astimezone(ZoneInfo("America/New_York")).date()}'
    key = hashlib.sha256(f'gpt-exit:{parent}:{due.isoformat()}:{attempt}'.encode()).hexdigest()[:32]
    intent = OrderIntent(intent_id=key[:16], risk_run_id=str(row['parent_risk_run_id']),
        exec_run_id=str(row['parent_exec_run_id']), symbol=symbol, side='buy' if short else 'sell', qty=qty,
        order_type='market', limit_price=None, trail_percent=None, broker_mode='paper',
        parent_intent_id=parent, intent_role=IntentRole.EXIT, idempotency_key=key,
        decision_price=float(row['avg_entry_price']), submission_key=key,
        time_in_force='opg' if action == 'MOO' else None)
    order = submit_order(watcher._repo, broker, intent, account_id=account)
    if order.status in {OrderStatus.REJECTED, OrderStatus.FAILED}:
        raise RuntimeError('Sortie temporelle GPT rejetée : réconciliation et réarmement requis')
    metrics['time_stop_submitted'] = int(metrics.get('time_stop_submitted', 0)) + 1
    watcher._persist_event(make_event(intent.exec_run_id, EventType.ORDER_SUBMITTED,
        f'GPT sortie séance {profile.exit_session} : {action} {symbol}', symbol=symbol,
        intent_id=intent.intent_id, broker_order_id=order.broker_order_id,
        payload={'policy': asdict(profile), 'due_open_utc': due.isoformat(),
                 'action': action, 'late': action != 'MOO', 'time_in_force': intent.time_in_force or 'day'}))


def _parent_context(parent, row):
    from types import SimpleNamespace
    return SimpleNamespace(intent_id=parent, exec_run_id=str(row['parent_exec_run_id']),
        risk_run_id=str(row['parent_risk_run_id']), symbol=str(row['symbol']),
        broker_mode=str(row.get('broker_mode') or 'paper'),
        decision_price=float(row['avg_entry_price']), decision_fingerprint=None)
