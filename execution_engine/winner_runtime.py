"""Durable five-minute campaign coordinator. Market/risk/broker are explicit ports.

Entry confirmation is never an approval. Existing lots are reconciled and
protected before an optional new-entry path is attempted. No HTTP is retried
after a reserved operation; restart discovers the exact stable client ID.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime, time, timedelta
import logging
import math
import uuid
from zoneinfo import ZoneInfo

from common.winner_pyramiding import (WinnerPyramidingConfig, add_fill, aware,
    confirmed_breakout, confirmed_winner, observe_completed_bar, reinforcement_quantity)
from execution_engine.models import IntentRole, OrderIntent
from execution_engine.winner_broker import client_key, entry_limit, make_intent
from execution_engine.winner_plans import next_plan_action, reserve_operation

LOG = logging.getLogger(__name__)
TERMINAL = {'filled', 'canceled', 'cancelled', 'rejected', 'expired'}
LIVE = {'new', 'accepted', 'pending_new', 'held', 'partially_filled'}


class WinnerCampaignRuntime:
    def __init__(self, store, repo, broker, config, *, market, risk, now=None):
        self.store, self.repo, self.broker, self.config = store, repo, broker, config
        self.market, self.risk = market, risk
        self.clock = (lambda: aware(now)) if now is not None else lambda: datetime.now(UTC)
        self.now = self.clock()
        self.metrics = dict(winner_plans_watched=0, winner_buys_submitted=0,
            winner_fills_reconciled=0, winner_protections_submitted=0, winner_stops_tightened=0,
            winner_exits_submitted=0, winner_entries_blocked=0, winner_failures=0, winner_details=[])

    def run(self, records):
        if not records:
            return self.metrics
        account = self.config.resolved_account_id
        # execution_locks.locked_by_run_id is VARCHAR(32). A fresh owner is
        # also required when two coordinators share the same clock instant.
        lock_id = 'ww-'+uuid.uuid4().hex[:29]
        if not self.repo.acquire_execution_lock(account_id=account, exec_run_id=lock_id):
            self.metrics['winner_entries_blocked'] += len(records)
            self.metrics['winner_details'].append({'reason': 'ACCOUNT_EXECUTION_LOCKED'})
            return self.metrics
        try:
            for record in records:
                state = record['state']
                if state['account_id'] != account or state['broker_mode'] != self.config.broker_mode:
                    raise ValueError('Campaign account/mode differs from watcher')
                # Reload under lock: a pipeline admission can have changed it.
                row = self.store.get(state['campaign_id'])
                self.state, self.version = row['state'], row['version']
                self.metrics['winner_plans_watched'] += 1
                try:
                    self.tick()
                except Exception as exc:
                    self.metrics['winner_failures'] += 1
                    self.metrics['winner_details'].append(dict(symbol=state['symbol'], reason=str(exc)[:500]))
                    LOG.exception('Campaign %s needs reconciliation; no blind retry', state['campaign_id'])
        finally:
            self.repo.release_execution_lock(account_id=account, exec_run_id=lock_id)
        return self.metrics

    def save(self):
        self.version = self.store.save(self.state, self.version)

    def pending(self):
        return [o for o in self.state['operations'] if o['status'] in ('RESERVED', 'UNKNOWN', 'SUBMITTED')]

    def reserve(self, kind, intent, **extra):
        operation = dict(key=intent.intent_id, action=kind, intent=asdict(intent), status='RESERVED',
            reserved_at=self.now.isoformat(), **extra)
        self.state['operations'].append(operation)
        self.save()  # Durable before every POST/PATCH, including protection.
        return operation

    def tick(self):
        if self.state['status'] in ('CLOSED', 'EXPIRED', 'CANCELED'):
            return
        self.reconcile()
        self.rearm_failed_exit()
        self.protect()
        self.reconcile_lots()
        if (self.state['policy']['confirmation_bars'] == 0
                and (not self.config.winner_pyramiding.enabled or self.config.blocks_new_entries
                     or self.now >= aware(self.state['entry_expires_at']))):
            # A queued standard order is still a possible future buy. Disabling
            # entries cancels its remainder, but never discards a raced fill.
            for operation in self.pending():
                if operation['action'] == 'ENTRY' and operation.get('broker_id'):
                    self.broker.cancel(operation['broker_id'])
            self.reconcile()
            self.protect()
        if self.pending():
            if any(o['action'] == 'EXIT' and o['status'] in ('RESERVED', 'UNKNOWN') for o in self.pending()):
                raise ValueError('Horizon sell response unknown after protection cancel; urgent broker reconciliation required')
            return
        if self.state['lots'] and not any(l['remaining'] for l in self.state['lots']):
            self.state['status'] = 'CLOSED'
            self.save()
            return
        if self.deadline():
            return  # No market-data/SIP dependency for an overdue close.
        if not self.state['lots'] and self.now >= aware(self.state['entry_expires_at']):
            self.state['status'] = 'EXPIRED'
            self.save()
            return
        from common.winner_pyramiding import held_market_data_required
        if self.state['lots'] and not held_market_data_required(self.state):
            # Reconciliation, missing protections and due-open exits above
            # still run. There is no trailing or add signal left to observe.
            return
        from execution_engine.winner_standard_entry import (standard_initial, standard_entry_window,
            standard_order_terms)
        standard = standard_initial(self.state)
        if not self.state['lots']:
            if not self.config.winner_pyramiding.enabled:
                return
            if standard:
                if not standard_entry_window(self.state, self.now):
                    return
            elif self.now < aware(self.state['earliest_entry_open']):
                return
        try:
            snapshot = self.market(self.state, self.now)
        except Exception as exc:
            self.blocked('MARKET_DATA_UNQUALIFIED: '+str(exc))
            return
        self.now = self.clock()
        self.tighten(snapshot['bars'])
        self.reconcile_lots()  # A tightened stop can execute immediately at the current price.
        if self.state['lots'] and not any(l['remaining'] for l in self.state['lots']):
            self.state['status'] = 'CLOSED'
            self.save()
            return
        if self.pending():
            return
        action = next_plan_action(self.state, snapshot['bars'], now=self.now,
            prior_session_high=snapshot.get('prior_session_high'), price=snapshot.get('ask'),
            available_cash=snapshot.get('available_cash', float('inf')),
            capacity_quantity=self.state['full_quantity'],
            new_entries_enabled=self.config.winner_pyramiding.enabled and not self.config.blocks_new_entries)
        if action['action'] not in ('ENTRY_SIGNAL', 'ADD_SIGNAL'):
            return
        kind = 'ENTRY' if action['action'] == 'ENTRY_SIGNAL' else 'ADD'
        reserved = False
        try:
            approved = self.risk(self.state, self.version, action['max_quantity'], snapshot, self.now, kind)
            self.now = self.clock()
            quantity = math.floor(min(action['max_quantity'], approved['max_quantity']))
            if quantity < 1:
                self.blocked(approved.get('reason', 'NATIVE_RISK_REJECTED'))
                return
            # Zero uses the frozen standard order, not a fake breakout/IOC.
            order_type, limit = (standard_order_terms(self.state,
                quote_check_enabled=approved.get('standard_entry_quote_check_enabled', True)) if standard and kind == 'ENTRY'
                                 else ('limit', entry_limit(approved['limit_price'])))
            if limit is not None and limit > approved['limit_price']+1e-8:
                raise ValueError('Risk approval must cover the rounded executable price')
            self.version, key = reserve_operation(self.store, self.state, self.version,
                action=kind, quantity=quantity, approval=approved, now=self.now)
            reserved = True
            operation = self.state['operations'][-1]
            intent = make_intent(self.state, key, quantity=quantity, order_type=order_type,
                price=limit if limit is not None else float(self.state['target']['entry_price']),
                tif='day' if standard and kind == 'ENTRY' else 'ioc',
                entry_mode='standard' if standard and kind == 'ENTRY' else None)
            operation['intent'] = asdict(intent)
            self.state['parents'][intent.intent_id] = dict(action=kind, booked_quantity=0, booked_notional=0.)
            self.save()  # The exact OMS intent survives a crash before HTTP.
            order = self.broker.submit(self.state, intent)
            operation.update(status='SUBMITTED', broker_id=order.broker_order_id)
            self.save()
            self.metrics['winner_buys_submitted'] += 1
            self.reconcile()
            self.protect()  # Protect an immediate fill in the same cycle.
        except Exception as exc:
            # RESERVED persists even when the process died between POST/response.
            self.blocked(('BUY_REQUIRES_RECONCILIATION: ' if reserved else 'NATIVE_RISK_REJECTED: ')+str(exc))

    def blocked(self, reason):
        self.metrics['winner_entries_blocked'] += 1
        self.metrics['winner_details'].append(dict(symbol=self.state['symbol'], reason=reason[:500]))

    def reconcile(self):
        for operation in list(self.pending()):
            if 'intent' not in operation:
                raise ValueError('Reserved buy has no exact OMS intent; operator review required')
            intent = OrderIntent(**operation['intent'])
            raw = (self.broker.get(operation['broker_id']) if operation.get('broker_id')
                else self.broker.lookup(intent))
            if raw is None:
                operation['status'] = 'UNKNOWN'
                self.save()
                continue  # 404 after a crash is NOT authorization to send again.
            self.broker.persist(self.state, intent, raw)
            operation['broker_id'] = raw['id']
            if operation['action'] in ('ENTRY', 'ADD'):
                self.book_buy(intent, operation, raw)
            elif operation['action'] == 'PROTECT':
                lot = self.state['lots'][operation['lot_index']]
                if lot['tp'] is None:
                    lot['stop_order_id'] = raw['id']
                else:
                    legs = raw.get('legs') or []
                    stop = next((x for x in legs if x.get('type') == 'stop'), None)
                    if stop is None:
                        raise ValueError('OCO exists but stop leg is unqualified; never submit a duplicate')
                    lot['tp_order_id'], lot['stop_order_id'] = raw['id'], stop['id']
                operation['status'] = 'DONE'
            elif operation['action'] == 'TIGHTEN':
                lot = self.state['lots'][operation['lot_index']]
                # A rejected replacement must not overwrite the existing stop.
                if raw.get('status') in LIVE:
                    stop = float(raw.get('stop_price') or 0)
                    if stop+1e-8 < operation['old_stop']:
                        raise ValueError('Replacement stop looser than the original')
                    lot['stop_order_id'], lot['stop'] = raw['id'], stop
                    operation['status'] = 'DONE'
                elif raw.get('status') in TERMINAL:
                    operation['status'] = 'DONE'
            elif operation['action'] == 'REARM':
                if raw.get('status') in LIVE or raw.get('status') == 'filled':
                    lot = self.state['lots'][operation['lot_index']]
                    lot.update(stop_order_id=raw['id'], tp_order_id=None)
                    operation['status'] = 'DONE'
                elif raw.get('status') in TERMINAL:
                    operation['status'] = 'MANUAL_REVIEW'
                    raise ValueError('Emergency rearm rejected; held position needs immediate operator action')
            elif operation['action'] == 'EXIT':
                self.book_sell(operation, raw)
            if operation['action'] in ('ENTRY', 'ADD', 'EXIT'):
                operation['status'] = 'DONE' if raw.get('status') in TERMINAL else 'SUBMITTED'
            self.save()

    def rearm_failed_exit(self):
        """A definitively failed horizon sell must not leave canceled stops.

        Unknown sells are NOT automatically replaced: an ambiguous fill could
        cause an oversell. They remain reserved for broker reconciliation.
        A confirmed rejection/cancel rearms a single standing stop per lot,
        then freezes the campaign for explicit operator review (no new buy).
        """
        failed = [o for o in self.state['operations'] if o['action'] == 'EXIT' and o['status'] == 'DONE'
            and any(l['remaining'] for l in self.state['lots'])]
        if not failed:
            return
        operation = failed[-1]
        raw = ({'status': 'rejected'} if operation.get('definitive_rejection')
            else self.broker.get(operation['broker_id']))
        if raw.get('status') not in ('canceled', 'cancelled', 'expired', 'rejected'):
            return
        positions = self.broker.positions()
        own = next((p for p in positions if p['symbol'] == self.state['symbol'] and p['side'] == 'long'), None)
        if own is None or float(own['qty']) < sum(l['remaining'] for l in self.state['lots']):
            raise ValueError('Failed exit: broker holding unqualified; urgent reconciliation required')
        for index, lot in enumerate(self.state['lots']):
            if not lot['remaining'] or any(o['action'] == 'REARM' and o.get('lot_index') == index
                    for o in self.state['operations']):
                continue
            for key in ('stop_order_id', 'tp_order_id'):
                if lot.get(key):
                    canceled = self.broker.cancel(lot[key])
                    self.apply_lot_sale(lot, canceled)
                    self.save()
                    if canceled.get('status') not in TERMINAL:
                        raise ValueError('Failed exit: protection cancel still ambiguous')
            if not lot['remaining']:
                continue
            stop = make_intent(self.state, operation['key']+'-rearm-'+str(index), quantity=lot['remaining'],
                side='sell', role=IntentRole.INITIAL_STOP, order_type='stop', stop=lot['stop'],
                parent=lot['parent_intent_id'])
            repair = self.reserve('REARM', stop, lot_index=index)
            submitted = self.broker.submit(self.state, stop)
            repair.update(status='SUBMITTED', broker_id=submitted.broker_order_id)
            self.save()
        self.reconcile()
        self.state['manual_review'] = 'Horizon exit failed; safety stops restored where confirmed. Operator review required.'
        self.save()

    def book_buy(self, intent, operation, raw):
        parent = self.state['parents'][intent.intent_id]
        quantity = float(raw.get('filled_qty') or 0)
        if not quantity.is_integer() or quantity < parent['booked_quantity'] or quantity > intent.qty:
            raise ValueError('Unqualified cumulative campaign fill quantity')
        delta = int(quantity)-parent['booked_quantity']
        if not delta:
            return
        average = float(raw.get('filled_avg_price') or 0)
        price = (quantity*average-parent['booked_notional'])/delta
        if (not math.isfinite(price) or price <= 0
                or intent.limit_price is not None and price > intent.limit_price+1e-6):
            raise ValueError('Invalid cumulative fill price / IOC limit breached')
        try:
            stamp = self.broker.actual_fill_time(raw, self.state)
        except Exception:
            # Do not invent an hour to unblock a position. Protect known shares
            # immediately and retain the unresolved parent for a later fill receipt.
            self.emergency_stop(intent, delta, price, int(quantity))
            raise
        fragment = client_key(intent.intent_id+'-fill-'+str(int(quantity)))
        add_fill(self.state, parent_id=fragment, quantity=delta, price=price, filled_at=stamp,
            is_add=operation['action'] == 'ADD', initial_fragment=parent['booked_quantity'] > 0)
        lot = self.state['lots'][-1]
        lot.update(parent_intent_id=intent.intent_id, sell_seen={}, last_bar_end=None)
        parent.update(booked_quantity=int(quantity), booked_notional=quantity*average)
        self.metrics['winner_fills_reconciled'] += 1
        self.save()

    def emergency_stop(self, parent, quantity, price, cumulative):
        # A reserved operation is deliberately not retried after ambiguity.
        key = parent.intent_id+'-unqualified-'+str(cumulative)
        # SQL request identity and broker identity are distinct. Reconcile the
        # durable client key, including older operations whose key used it too.
        broker_key = client_key(key)
        existing = next((o for o in self.state['operations']
            if o.get('intent', {}).get('submission_key') == broker_key or o['key'] == broker_key), None)
        if existing:
            return
        p = WinnerPyramidingConfig(**self.state['policy'])
        intent = make_intent(self.state, key, quantity=quantity, side='sell', order_type='stop',
            role=IntentRole.INITIAL_STOP, stop=round(price*(1-p.stop_loss_pct), 2), parent=parent.intent_id)
        operation = self.reserve('EMERGENCY_STOP', intent)
        order = self.broker.submit(self.state, intent)
        operation.update(status='MANUAL_REVIEW', broker_id=order.broker_order_id)
        self.state['manual_review'] = 'Fill timestamp unavailable; protective stop placed. Reconcile before any further buy.'
        self.save()

    def protect(self):
        if self.state.get('manual_review'):
            raise ValueError(self.state['manual_review'])
        for i, lot in enumerate(self.state['lots']):
            if not lot['remaining'] or lot['stop_order_id']:
                continue
            if any(o.get('lot_index') == i and o['action'] == 'PROTECT' for o in self.state['operations']):
                return  # Never repeat a protection POST with an unknown response.
            parent_operation = next(o for o in self.state['operations']
                if o.get('intent', {}).get('intent_id') == lot['parent_intent_id'])
            parent = OrderIntent(**parent_operation['intent'])
            stop = make_intent(self.state, lot['parent_id']+'-sl', quantity=lot['remaining'], side='sell',
                role=IntentRole.INITIAL_STOP, order_type='stop', stop=lot['stop'], parent=parent.intent_id)
            tp = (make_intent(self.state, lot['parent_id']+'-tp', quantity=lot['remaining'], side='sell',
                role=IntentRole.TAKE_PROFIT, order_type='limit', price=lot['tp'], parent=parent.intent_id)
                if lot['tp'] else None)
            operation = self.reserve('PROTECT', tp or stop, lot_index=i, stop_intent=asdict(stop))
            tp_order, stop_order = self.broker.protect(self.state, lot, parent, tp_intent=tp, stop_intent=stop)
            lot['stop_order_id'] = stop_order.broker_order_id
            lot['tp_order_id'] = tp_order.broker_order_id if tp_order else None
            operation.update(status='DONE', broker_id=(tp_order or stop_order).broker_order_id)
            self.save()
            self.metrics['winner_protections_submitted'] += 1

    def reconcile_lots(self):
        for lot in self.state['lots']:
            observations = []
            for key in ('stop_order_id', 'tp_order_id'):
                if lot.get(key):
                    raw = self.broker.get(lot[key])
                    journal = getattr(self.broker, 'journal_lot', None)
                    if callable(journal):
                        journal(self.state, lot, raw)
                    self.apply_lot_sale(lot, raw)
                    observations.append(raw)
            exit_pending = any(o['action'] == 'EXIT' and o['status'] in ('RESERVED', 'UNKNOWN', 'SUBMITTED')
                for o in self.state['operations'])
            if lot['remaining'] and not exit_pending and any(
                    raw.get('status') in ('canceled', 'cancelled', 'rejected', 'expired') for raw in observations):
                self.save()  # Preserve any confirmed fills before requiring repair.
                raise ValueError('A campaign protection is terminal while shares remain; repair required')
        self.save()

    def apply_lot_sale(self, lot, raw):
        cumulative = float(raw.get('filled_qty') or 0)
        if not cumulative.is_integer():
            raise ValueError('Fractional campaign exit unsupported')
        seen = lot['sell_seen'].get(raw['id'], 0)
        delta = int(cumulative)-seen
        if delta < 0 or delta > lot['remaining']:
            raise ValueError('Exit race exceeds qualified remaining lot; no further sell')
        if delta:
            price = float(raw.get('filled_avg_price') or 0)
            if not math.isfinite(price) or price <= 0:
                raise ValueError('Filled exit price missing')
            p = WinnerPyramidingConfig(**self.state['policy'])
            self.state['realized_losses'] += max(delta*(lot['entry']-price), 0)+delta*p.fee*(lot['entry']+price)
            lot['remaining'] -= delta
            lot['sell_seen'][raw['id']] = int(cumulative)

    def tighten(self, bars):
        p = WinnerPyramidingConfig(**self.state['policy'])
        if not p.trailing_stop_pct or self.pending():
            return
        for i, lot in enumerate(self.state['lots']):
            if not lot['remaining'] or not lot['stop_order_id']:
                continue
            next_lot = deepcopy(lot)
            for bar in sorted(bars, key=lambda b: aware(b['timestamp'])):
                start, end = aware(bar['timestamp']), aware(bar['timestamp'])+timedelta(minutes=5)
                if (start < aware(lot['filled_at']) or end > self.now or bar.get('session_tag') != 'regular'
                        or lot['last_bar_end'] and end <= aware(lot['last_bar_end'])):
                    continue
                observe_completed_bar(next_lot, float(bar['high']), p)
                next_lot['last_bar_end'] = end.isoformat()
            if next_lot['stop'] > lot['stop']:
                intent = make_intent(self.state, lot['parent_id']+'-trail-'+str(next_lot['stop']),
                    quantity=lot['remaining'], side='sell', role=IntentRole.INITIAL_STOP,
                    order_type='stop', stop=next_lot['stop'], parent=lot['parent_intent_id'])
                operation = self.reserve('TIGHTEN', intent, lot_index=i, old_stop=lot['stop'])
                order = self.broker.tighten(self.state, lot, intent)
                lot.update(stop_order_id=order.broker_order_id, stop=next_lot['stop'],
                    peak=next_lot['peak'], last_bar_end=next_lot['last_bar_end'])
                operation.update(status='DONE', broker_id=order.broker_order_id)
                self.metrics['winner_stops_tightened'] += 1
            else:
                lot.update(peak=next_lot['peak'], last_bar_end=next_lot['last_bar_end'])
            self.save()

    def deadline(self):
        if not self.state.get('due_open') or not any(l['remaining'] for l in self.state['lots']):
            return False
        from common.market_calendar import get_market_calendar
        cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
        due, ny = aware(self.state['due_open']), self.now.astimezone(ZoneInfo('America/New_York'))
        sessions = [s for s in cal.sessions(ny.date(), ny.date()) if s.is_open]
        if not sessions:
            return self.now >= due
        session = sessions[0]
        # Never remove standing stops for an entire night to prequeue MOO.
        moo = due.date() == self.now.date() and due-timedelta(minutes=10) <= self.now < due-timedelta(minutes=2)
        late = due <= self.now and session.open_at_utc <= self.now < session.close_at_utc
        if not (moo or late):
            return self.now >= due
        for operation in self.state['operations']:
            if operation['action'] == 'EXIT':
                return True  # One exit intent only; rejected/unknown state needs explicit review.
        # Cancel and observe every leg first, then account for fills during cancel.
        for lot in self.state['lots']:
            if not lot['remaining']:
                continue
            for key in ('stop_order_id', 'tp_order_id'):
                if lot.get(key):
                    raw = self.broker.cancel(lot[key])
                    self.apply_lot_sale(lot, raw)
                    self.save()
                    if raw.get('status') not in TERMINAL:
                        raise ValueError('Deadline cancel unconfirmed; selling forbidden')
        quantity = sum(l['remaining'] for l in self.state['lots'])
        if not quantity:
            return True
        positions = self.broker.positions()
        own = next((x for x in positions if x['symbol'] == self.state['symbol']), None)
        if own is None or str(own.get('side')) != 'long' or float(own['qty']) < quantity:
            raise ValueError('Broker quantity does not cover deadline sale; reconcile first')
        intent = make_intent(self.state, self.state['campaign_id']+'-deadline', quantity=quantity,
            side='sell', role=IntentRole.EXIT, order_type='market',
            price=float(self.state['lots'][0]['entry']), tif='opg' if moo else None)
        operation = self.reserve('EXIT', intent, booked_quantity=0, execution_timing='MOO' if moo else 'LATE_MARKET')
        try:
            order = self.broker.submit(self.state, intent)
        except Exception as exc:
            from service.alpaca.trading_client import BrokerApiError
            if (isinstance(exc, BrokerApiError) and 400 <= exc.status_code < 500
                    and exc.status_code != 429 and 'client_order_id' not in str(exc.body)):
                operation.update(status='DONE', definitive_rejection=str(exc)[:500])
                self.save()
                self.rearm_failed_exit()
            raise
        operation.update(status='SUBMITTED', broker_id=order.broker_order_id)
        self.save()
        self.metrics['winner_exits_submitted'] += 1
        return True

    def book_sell(self, operation, raw):
        cumulative = float(raw.get('filled_qty') or 0)
        delta = cumulative-operation['booked_quantity']
        if not delta.is_integer() or delta < 0 or delta > sum(l['remaining'] for l in self.state['lots']):
            raise ValueError('Invalid cumulative deadline quantity')
        for lot in self.state['lots']:
            used = min(int(delta), lot['remaining'])
            if used:
                self.apply_lot_sale(lot, dict(raw, filled_qty=lot['sell_seen'].get(raw['id'], 0)+used))
                delta -= used
        operation['booked_quantity'] = int(cumulative)
