"""Research-only stock exchange. Unknown fractional proceeds are NOT cash.

STRICT rejects a fractional entitlement with no qualified cash/payment record.
UNVALUED_RECEIVABLE is an explicitly incomplete-wealth scenario, not broker
parity: only whole delivered shares trade; the unpriced claim is unavailable.
Native TP/SL replacement is simulated atomically, not an observed broker fill.
"""
from copy import deepcopy
from dataclasses import fields, replace
from decimal import Decimal, ROUND_FLOOR
import math

import pandas as pd

from scripts.research.us_oracle_barrier_comparison import FixedBarrierLedger


EVENTS = (
    dict(source='AVB', target='VMRK', day='2026-08-17', ratio='2.793', cash_fraction=True,
         trading_symbol='EQR'),
    dict(source='EQR', target='VMRK', day='2026-08-18', ratio='1', cash_fraction=False,
         trading_symbol='VMRK'),
)
PRICE_FIELDS = {'entry_price', 'fill_price', 'expected_price', 'stop_price', 'limit_price',
    'price', 'trigger_price', 'risk_per_share', 'replay_take_profit_price',
    'replay_initial_stop_price', 'replay_trailing_activation_price', 'avg_fill_price'}
QUANTITY_FIELDS = {'qty', 'quantity', 'filled_qty', 'order_qty', 'cumulative_qty', 'remaining_qty'}


def exchange_quantities(quantity, ratio, *, cash_fraction):
    total = Decimal(str(quantity))*Decimal(str(ratio))
    if not total.is_finite() or total <= 0:
        raise ValueError('Invalid share exchange')
    whole = total.to_integral_value(rounding=ROUND_FLOOR) if cash_fraction else total
    return float(whole), float(total-whole), float(total)


def rebase_protection(protection, *, source, target, ratio, quantity, day):
    """New simulated group, preserving original entry/expiry chronology."""
    values = {}
    for descriptor in fields(protection):
        value = getattr(protection, descriptor.name)
        if isinstance(value, pd.DataFrame):
            frame = value.copy(deep=True)
            if 'symbol' in frame:
                frame.loc[frame.symbol.eq(source), 'symbol'] = target
            for column in PRICE_FIELDS & set(frame.columns):
                frame[column] = pd.to_numeric(frame[column], errors='raise')/ratio
            for column in QUANTITY_FIELDS & set(frame.columns):
                frame[column] = quantity
            for column in ('order_id', 'intent_id', 'oco_group_id', 'parent_order_id'):
                if column in frame:
                    frame[column] = frame[column].map(
                        lambda x: f'ca-{pd.Timestamp(day).date()}-{x}' if pd.notna(x) else x)
            values[descriptor.name] = frame
    values['diagnostics'] = dict(protection.diagnostics,
        ca_protection_replacement='SIMULATED_ATOMIC_AT_OPEN_NOT_BROKER_OBSERVED',
        original_symbol=source, new_symbol=target, ratio=ratio)
    return replace(protection, **values)


class MergerLedger(FixedBarrierLedger):
    def __init__(self, *args, events=EVENTS, cash_policy='STRICT', **kwargs):
        if cash_policy not in {'STRICT', 'UNVALUED_RECEIVABLE'}:
            raise ValueError('Unknown cash-in-lieu policy')
        super().__init__(*args, **kwargs)
        self.ca_events, self.cash_policy = tuple(events), cash_policy
        self.corporate_action_audits, self.unvalued_claims = [], []
        self.ca_done, self.today_conversions = set(), []

    def begin_day(self, day):
        day = pd.Timestamp(day).normalize()
        if self.current_day is not None or self.failed:
            raise ValueError('Cannot mutate an active/failed ledger')
        self.today_conversions = []
        for e in self.ca_events:
            if day != pd.Timestamp(e['day']):
                continue
            key = (e['source'], e['day'])
            if key in self.ca_done:
                raise ValueError('Duplicate corporate action')
            self._convert(e, day)
            self.ca_done.add(key)
        super().begin_day(day)

    def _convert(self, event, day):
        source, target, ratio = event['source'], event['target'], float(event['ratio'])
        if not math.isfinite(ratio) or ratio <= 0 or source == target:
            raise ValueError('Invalid corporate-action identity/ratio')
        position = self.state.positions.get(source)
        if position is None:
            self.corporate_action_audits.append(dict(event, status='NO_POSITION', cash_credit=0.))
            return
        if target in self.state.positions:
            raise ValueError('Co-held merger lots require aggregate-identity qualification')
        # AVB and EQR cannot both be silently collapsed into one position.
        competing = [e['source'] for e in self.ca_events if e['target'] == target
                     and e['source'] != source and e['source'] in self.state.positions]
        if competing:
            raise ValueError(f'Co-held merger lots require qualification: {source}/{competing}')
        quantity, fraction, entitlement = exchange_quantities(position.quantity, event['ratio'],
            cash_fraction=event['cash_fraction'])
        if fraction > 1e-12 and self.cash_policy == 'STRICT':
            raise ValueError(f'Unqualified cash-in-lieu {source}: {fraction:.9f} successor shares')
        for frame in (self.opens, self.high, self.low, self.close, self.volume):
            if target not in frame or day not in frame.index or not pd.notna(frame.at[day, target]) \
                    or not math.isfinite(float(frame.at[day, target])) or frame.at[day, target] <= 0:
                raise ValueError(f'Unqualified successor bar {target}/{day.date()}')
        protection = self.protections.get(source)
        if protection is None:
            raise ValueError('Missing old protections')
        share = quantity/entitlement
        # Preserve the separate cost basis of the fractional receivable. It is
        # neither written off as a realised loss nor credited into buying power.
        claim = dict(source=source, target=target, effective_date=str(day.date()),
            successor_share_units=fraction, value=None, payment_date=None,
            original_entry_date=str(position.entry_date.date()),
            entry_cash_flow=position.entry_cash_flow*(1-share),
            allocated_entry_cost=position.entry_cost*(1-share), usable_cash=0.)
        changes = dict(symbol=target, quantity=quantity,
            entry_cost=position.entry_cost*share, entry_cash_flow=position.entry_cash_flow*share,
            signal_context=dict(position.signal_context, original_symbol=source,
                original_quantity=position.quantity, original_entry_price=position.entry_price,
                merger_ratio=ratio, entry_symbol=source, execution_symbol=target))
        for name in ('entry_price', 'peak_high', 'trough_low', 'initial_stop_price',
                     'risk_per_share', 'replay_take_profit_price', 'replay_initial_stop_price',
                     'replay_trailing_activation_price'):
            value = getattr(position, name)
            if value is not None:
                changes[name] = value/ratio
        migrated = replace(position, **changes)
        for name in PRICE_FIELDS & set(migrated.signal_context):
            value = migrated.signal_context[name]
            if value is not None and pd.notna(value):
                migrated.signal_context[name] = float(value)/ratio
        for name in QUANTITY_FIELDS & set(migrated.signal_context):
            migrated.signal_context[name] = quantity
        if abs(position.quantity*position.entry_price-entitlement*migrated.entry_price) > 1e-7:
            raise AssertionError('Share exchange changed total historical gross cost')
        replacement = rebase_protection(protection, source=source, target=target,
            ratio=ratio, quantity=quantity, day=day)
        # A protection follows this lot's AVB observations until conversion,
        # not the unrelated pre-merger EQR price path. This is a labelled
        # lineage series in memory, never bars inserted under AVB in SQL.
        history = (self.days >= position.entry_date) & (self.days < day)
        for frame in (self.opens, self.close, self.high, self.low):
            frame.loc[history, target] = frame.loc[history, source]/ratio
        self.volume.loc[history, target] = self.volume.loc[history, source]*ratio
        self.adv[target] = (self.close[target]*self.volume[target]).rolling(20, min_periods=20).mean().shift(1)
        self.state.positions.pop(source)
        self.protections.pop(source)
        if quantity > 0:
            self.state.positions[target] = migrated
            self.protections[target] = replacement
        if fraction > 1e-12:
            self.unvalued_claims.append(claim)
        audit = dict(event, status='CONVERTED', old_quantity=position.quantity,
            delivered_quantity=quantity, total_entitlement=entitlement, fraction=fraction,
            cash_credit=0., cash_policy=self.cash_policy, receivable=claim if fraction > 1e-12 else None,
            old_entry_price=position.entry_price, new_entry_price=migrated.entry_price,
            old_stop=position.replay_initial_stop_price, new_stop=migrated.replay_initial_stop_price,
            old_tp=position.replay_take_profit_price, new_tp=migrated.replay_take_profit_price,
            preserved_entry_date=str(position.entry_date.date()), entry_idx=position.entry_idx,
            protection_replacement='SIMULATED_ATOMIC_AT_OPEN', source_orders_cancelled=True,
            quantity_basis='RAW_PREDECESSOR_TO_SUCCESSOR_ONCE', historical_prefix='OWN_LOT_LINEAGE')
        self.corporate_action_audits.append(audit)
        self.today_conversions.append((source, target, quantity/position.quantity))

    def corporate_action_open(self, session, pending, steps, day):
        retired = {e['source'] for e in self.ca_events if pd.Timestamp(e['day']) <= day}
        cancelled = [p for p in pending if p.symbol in retired]
        pending = [p for p in pending if p.symbol not in retired]
        if cancelled:
            self.corporate_action_audits.append(dict(day=str(day.date()),
                status='UNEXECUTED_ENTRY_CANCELLED', symbols=[p.symbol for p in cancelled]))
        # Destructive orders keep the same proportion, converted once. No new
        # approval/order on a retired symbol may leak into the next-open engine.
        for source, target, ratio in self.today_conversions:
            steps = [replace(s, symbol=target, quantity=s.quantity*ratio)
                     if s.symbol == source else s for s in steps]
            key_old, key_new = f'long:{source}', f'long:{target}'
            history = session.trades._history.pop(key_old, [])
            session.trades._history[key_new] = sorted(session.trades._history.get(key_new, [])+history)
        return pending, steps

    def reconciliation_error(self):
        # The cash ledger is exactly reconciled while the receivable's VALUE
        # remains unknown. This does not assert complete economic reconciliation.
        return super().reconciliation_error()-sum(c['entry_cash_flow'] for c in self.unvalued_claims)

    def corporate_action_report(self):
        return dict(corporate_action_cash_policy=self.cash_policy,
            corporate_action_events=sum(a.get('status') == 'CONVERTED' for a in self.corporate_action_audits),
            unvalued_fractional_claims=deepcopy(self.unvalued_claims),
            account_wealth_complete=not bool(self.unvalued_claims),
            full_broker_corporate_action_parity=False,
            equity_scope='CASH_AND_WHOLE_TRADEABLE_POSITIONS_EXCLUDING_UNVALUED_RECEIVABLES',
            simulated_atomic_ca_protection_replacement=True,
            cash_in_lieu_pnl=None if self.unvalued_claims else 0.)
