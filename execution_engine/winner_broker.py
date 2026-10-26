"""US campaign broker bridge: canonical OMS journal, no blind POST retries.

The coordinator persists the operation before entering these methods. A lost
response is reconciled by its stable client ID; a404 is not permission to POST
again. This bridge does not qualify market signals or approve portfolio risk.
"""
from decimal import Decimal, ROUND_CEILING
import hashlib

from common.winner_pyramiding import aware
from execution_engine.models import ExecutionFill, IntentRole, OrderIntent
from execution_engine.order_intents import intent_to_alpaca_payload
from service.alpaca.trading_client import BrokerApiError


def client_key(value):
    return 'wp-'+hashlib.sha256(value.encode()).hexdigest()[:36]


def make_intent(state, key, *, quantity, side='buy', role=IntentRole.ENTRY,
        order_type='limit', price=None, stop=None, parent=None, tif=None, entry_mode=None):
    return OrderIntent(intent_id=client_key(key), risk_run_id=state['risk_run_id'],
        exec_run_id=state['exec_run_id'], symbol=state['symbol'], side=side,
        qty=quantity, order_type=order_type, limit_price=price if order_type == 'limit' else None,
        trail_percent=None, broker_mode=state['broker_mode'], parent_intent_id=parent,
        intent_role=role, idempotency_key=client_key(key), decision_price=float(price or stop or 0),
        stop_price=stop, submission_key=client_key(key), time_in_force=tif,
        winner_campaign_id=state['campaign_id'], winner_entry_mode=entry_mode)


class NativeWinnerBroker:
    def __init__(self, repo, broker, config):
        self.repo, self.broker, self.config = repo, broker, config
        # The generic legacy port deliberately has no unsafe fallback here.
        self.client = broker._client

    def lookup(self, intent):
        try:
            return self.client._request('GET', '/v2/orders:by_client_order_id',
                params={'client_order_id': intent.submission_key, 'nested': 'true'})
        except BrokerApiError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get(self, broker_id):
        return self.client._request('GET', f'/v2/orders/{broker_id}', params={'nested': 'true'})

    def submit(self, state, intent):
        self.repo.upsert_execution_order_request_from_intent(intent,
            account_id=state['account_id'], status='NEW')
        try:
            order = self.broker.submit_intent(intent)
        except BrokerApiError as exc:
            if 400 <= exc.status_code < 500 and exc.status_code != 429 and 'client_order_id' not in str(exc.body):
                self.repo.upsert_execution_order_request_from_intent(intent,
                    account_id=state['account_id'], status='REJECTED', failure_reason=str(exc)[:500])
            raise
        self.persist_order(state, intent, order)
        return order

    def persist_order(self, state, intent, order):
        self.repo.upsert_execution_order_request_from_intent(intent,
            account_id=state['account_id'], status=order.status)
        self.repo.upsert_execution_broker_order(intent, order, account_id=state['account_id'],
            raw_payload=intent_to_alpaca_payload(intent, config=self.config))

    def persist(self, state, intent, raw):
        order = self.broker.broker_order_from_api(raw, intent_id=intent.intent_id)
        self.persist_order(state, intent, order)
        if float(raw.get('filled_qty') or 0) > 0:
            self.journal_fill(state, intent, raw)
        return order

    def journal_fill(self, state, intent, raw):
        try:
            stamp = self.actual_fill_time(raw, state)
        except ValueError:
            return  # The coordinator protects known buys and flags the missing receipt.
        cumulative = float(raw['filled_qty'])
        existing = self.repo.load_cumulative_filled_qty(request_id=intent.intent_id)
        if existing > cumulative+1e-8:
            raise ValueError('Canonical fill quantity exceeds broker cumulative quantity')
        delta = cumulative-existing
        if delta <= 1e-8:
            return
        previous_price = self.repo.load_entry_fill_price(intent.intent_id) if existing else 0.
        if existing and previous_price is None:
            raise ValueError('Prior canonical fill price missing')
        price = (cumulative*float(raw['filled_avg_price'])-existing*previous_price)/delta
        fill_id = hashlib.sha256(f'{raw["id"]}|{intent.intent_id}|{cumulative:.8f}'.encode()).hexdigest()[:32]
        fill = ExecutionFill(fill_id, raw['id'], intent.intent_id, intent.symbol, delta, price, stamp,
            intent.decision_price, 10000*(price/intent.decision_price-1) if intent.decision_price > 0 else 0.,
            delta*(price-intent.decision_price))
        self.repo.insert_execution_broker_fill(fill, account_id=state['account_id'], raw_fill=raw)

    def journal_lot(self, state, lot, raw):
        for operation in reversed(state['operations']):
            if operation.get('broker_id') == raw['id'] and operation.get('intent'):
                return self.persist(state, OrderIntent(**operation['intent']), raw)
            if operation['action'] == 'PROTECT' and operation.get('lot_index') == state['lots'].index(lot):
                if raw['id'] == lot['stop_order_id']:
                    return self.persist(state, OrderIntent(**operation['stop_intent']), raw)
        raise ValueError('Campaign child order lineage missing')

    def protect(self, state, lot, parent, *, tp_intent, stop_intent):
        for intent in (tp_intent, stop_intent):
            if intent:
                self.repo.upsert_execution_order_request_from_intent(intent,
                    account_id=state['account_id'], status='NEW')
        if tp_intent is None:
            order = self.broker.submit_intent(stop_intent)
            self.persist_order(state, stop_intent, order)
            return None, order
        tp_order, stop_order = self.broker.submit_oco_protection(parent, tp_intent, stop_intent)
        self.persist_order(state, tp_intent, tp_order)
        self.persist_order(state, stop_intent, stop_order)
        return tp_order, stop_order

    def tighten(self, state, lot, intent):
        """PATCH a standing stop; never cancel it to create its replacement."""
        current = self.get(lot['stop_order_id'])
        if str(current.get('status')) not in ('new', 'accepted', 'pending_new', 'partially_filled', 'held'):
            raise ValueError('Standing stop must be reconciled before amend')
        if intent.stop_price < float(current['stop_price']):
            raise ValueError('Campaign stop cannot loosen')
        self.repo.upsert_execution_order_request_from_intent(intent,
            account_id=state['account_id'], status='NEW')
        raw = self.client.replace_order(lot['stop_order_id'],
            {'stop_price': str(intent.stop_price), 'client_order_id': intent.submission_key})
        order = self.persist(state, intent, raw)
        if order.stop_price is None or order.stop_price+1e-8 < float(current['stop_price']):
            raise ValueError('Broker did not confirm a non-loosening stop')
        return order

    def positions(self):
        # Unlike get_position(), this method does not mask a transport failure
        # as a flat account. A missing response is never evidence of a closure.
        return self.broker.get_all_positions()

    def cancel(self, broker_id):
        terminal = {'filled', 'canceled', 'cancelled', 'rejected', 'expired'}
        current = self.get(broker_id)
        if current.get('status') in terminal:
            return current
        try:
            self.broker.cancel_broker_order(broker_id)
        except BrokerApiError as exc:
            if exc.status_code not in (404, 422):
                raise
            # Fill/cancel can win the race after the first GET. Only a second
            # terminal observation confirms that no live leg remains.
            current = self.get(broker_id)
            if current.get('status') in terminal:
                return current
            raise
        return self.get(broker_id)  # A cancel request is not a cancel confirmation.

    def actual_fill_time(self, raw, state):
        if raw.get('filled_at'):
            return aware(raw['filled_at'])
        # Partial fills can have no filled_at. Fetch real activities, strictly
        # paginated, without the legacy helper's partial-success-on-error mode.
        params = {'activity_types': 'FILL', 'direction': 'asc', 'page_size': '100',
            'after': state['created_at']}
        found, tokens = [], set()
        for _ in range(200):
            page = self.client._request('GET', '/v2/account/activities', params=params)
            if not isinstance(page, list):
                raise ValueError('Invalid account fills response')
            found.extend(x for x in page if x.get('order_id') == raw['id'])
            if len(page) < 100:
                if not found:
                    raise ValueError('Actual fill timestamp unavailable; protect then reconcile')
                return max(aware(x['transaction_time']) for x in found)
            token = str(page[-1].get('id') or '')
            if not token or token in tokens:
                raise ValueError('Incomplete account fill pagination')
            tokens.add(token)
            params['page_token'] = token
        raise ValueError('Account fill pagination truncated')


def entry_limit(ask):
    return float(Decimal(str(ask)).quantize(Decimal('.01'), rounding=ROUND_CEILING))
