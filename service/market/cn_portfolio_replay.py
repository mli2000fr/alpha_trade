"""Replay de portefeuille CN_A, isolé du moteur US (Sprint 12-B).

Les fills sont des hypothèses de scénario sur des barres quotidiennes, jamais
des exécutions constatées. Les données/règles manquantes arrêtent le replay ou
laissent la position explicitement non résolue.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy.engine import Connection

from service.market.cn_execution_contract import (
    CNExecutionContractError,
    InventoryLot,
    assess_fill_proxy,
    estimate_cost,
    prepare_buy,
    prepare_sell,
    resolve_cost_profile,
    resolve_rule,
)

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class CNInstrument:
    instrument_id: int
    exchange_mic: str
    board_code: str
    listing_date: date | None = None
    delisting_date: date | None = None


@dataclass(frozen=True)
class CNBar:
    session_date: date
    instrument_id: int
    open_cny: Decimal | None
    close_cny: Decimal | None
    trading_status: str | None
    limit_policy: str | None
    locked_up: bool | None
    locked_down: bool | None
    volume_shares: Decimal | None = None
    factor_event_unresolved: bool = False


@dataclass(frozen=True)
class CNIntent:
    intent_id: str
    signal_date: date
    instrument_id: int
    side: Side
    budget_cny: Decimal | None = None
    shares: int | None = None
    reason: str = "SIGNAL"
    priority: Decimal = Decimal(0)


@dataclass(frozen=True)
class CNAction:
    action_id: str
    instrument_id: int
    ex_date: date
    kind: Literal["SPLIT", "CASH_DIVIDEND", "UNRESOLVED"]
    share_multiplier: Decimal | None = None
    cash_per_share_cny: Decimal | None = None
    payment_date: date | None = None


@dataclass(frozen=True)
class ReplayConfig:
    initial_cash_cny: Decimal
    cost_profile_key: str = "cn_a_research"
    scenario: Literal["permissive", "base", "conservative"] = "base"
    pending_policy: Literal["carry", "cancel_day"] = "carry"
    max_wait_sessions: int = 3
    max_positions: int = 8
    allow_pyramiding: bool = False
    allow_research_rules: bool = False
    allow_research_proxy: bool = False

    def __post_init__(self) -> None:
        if (self.initial_cash_cny <= 0 or self.max_wait_sessions < 1
                or self.max_positions < 1 or self.scenario not in {"permissive", "base", "conservative"}
                or self.pending_policy not in {"carry", "cancel_day"}):
            raise ValueError("Configuration de replay CN invalide")


@dataclass
class _Lot:
    shares: int
    acquired_session: date


@dataclass
class _Pending:
    intent: CNIntent
    wait_sessions: int = 0


@dataclass
class ReplayResult:
    journal: list[dict[str, Any]]
    daily: list[dict[str, Any]]
    cash_cny: Decimal
    lots: dict[int, list[InventoryLot]]
    unresolved: dict[int, str]
    pending_intents: list[str]
    economic_result_valid: bool


def _event(day: date, kind: str, **fields: Any) -> dict[str, Any]:
    return {"session_date": day.isoformat(), "event": kind, **fields}


def _positive_price(value: Decimal | None) -> bool:
    return value is not None and value.is_finite() and value > 0


class CNPortfolioReplay:
    """État déterministe du portefeuille ; connexion CN et opt-ins explicites."""

    def __init__(self, conn: Connection, config: ReplayConfig) -> None:
        self.conn = conn
        self.config = config
        self.cash = config.initial_cash_cny
        self.withdrawable_cash = config.initial_cash_cny
        self.unsettled: list[tuple[date, Decimal]] = []
        self.dividends_due: list[tuple[date, Decimal, int, str]] = []
        self.lots: dict[int, list[_Lot]] = defaultdict(list)
        self.last_close: dict[int, Decimal] = {}
        self.unresolved: dict[int, str] = {}
        self.pending: list[_Pending] = []
        self.journal: list[dict[str, Any]] = []
        self.daily: list[dict[str, Any]] = []
        self.commission_total = Decimal(0)
        self.other_cost_total = Decimal(0)
        self._used = False

    def _rule(self, instrument: CNInstrument, day: date):
        return resolve_rule(
            self.conn, exchange_mic=instrument.exchange_mic,
            board_code=instrument.board_code, session_date=day,
            allow_research_rules=self.config.allow_research_rules,
        )

    def _cost(self, day: date):
        return resolve_cost_profile(
            self.conn, profile_key=self.config.cost_profile_key,
            session_date=day, allow_research_proxy=self.config.allow_research_proxy,
        )

    def _settle(self, day: date) -> None:
        remaining = []
        for due, value in self.unsettled:
            if due <= day:
                self.withdrawable_cash += value
            else:
                remaining.append((due, value))
        self.unsettled = remaining
        remaining_dividends = []
        for due, value, instrument_id, action_id in self.dividends_due:
            if due <= day:
                self.cash += value
                self.withdrawable_cash += value
                self.journal.append(_event(day, "DIVIDEND_PAID", instrument_id=instrument_id,
                                           action_id=action_id, cash_cny=str(value)))
            else:
                remaining_dividends.append((due, value, instrument_id, action_id))
        self.dividends_due = remaining_dividends

    def _spend_cash(self, amount: Decimal) -> None:
        """L'argent d'une vente peut être réinvesti, pas retiré avant règlement."""
        if amount > self.cash:
            raise CNExecutionContractError("Dépense CN supérieure au cash")
        remaining = amount
        new_unsettled = []
        for due, value in self.unsettled:
            used = min(remaining, value)
            remaining -= used
            if value > used:
                new_unsettled.append((due, value - used))
        if remaining > self.withdrawable_cash:
            raise CNExecutionContractError("Cash CN non réconcilié")
        self.unsettled = new_unsettled
        self.withdrawable_cash -= remaining
        self.cash -= amount

    def _actions(self, day: date, actions: list[CNAction]) -> None:
        # Le droit au dividende est figé avant tout split de la même ex-date ;
        # il ne dépend pas de l'ordre des lignes d'entrée.
        entitled = {instrument_id: sum(lot.shares for lot in lots)
                    for instrument_id, lots in self.lots.items()}
        for action in actions:
            if action.ex_date != day:
                continue
            held = sum(lot.shares for lot in self.lots[action.instrument_id])
            if held == 0:
                continue
            if action.kind == "SPLIT" and action.share_multiplier and action.share_multiplier > 0:
                multiplied = [Decimal(lot.shares) * action.share_multiplier for lot in self.lots[action.instrument_id]]
                if any(value != value.to_integral_value() for value in multiplied):
                    self.unresolved[action.instrument_id] = "FRACTIONAL_CORPORATE_ACTION"
                else:
                    for lot, new_shares in zip(self.lots[action.instrument_id], multiplied, strict=True):
                        lot.shares = int(new_shares)
                    self.journal.append(_event(day, "SPLIT_APPLIED", instrument_id=action.instrument_id,
                                               action_id=action.action_id, shares_after=sum(int(x) for x in multiplied)))
                    continue
            elif (action.kind == "CASH_DIVIDEND" and action.cash_per_share_cny is not None
                  and action.cash_per_share_cny >= 0 and action.payment_date is not None
                  and action.payment_date >= day):
                amount = Decimal(entitled.get(action.instrument_id, 0)) * action.cash_per_share_cny
                self.dividends_due.append((action.payment_date, amount, action.instrument_id, action.action_id))
                self.journal.append(_event(day, "DIVIDEND_RECEIVABLE", instrument_id=action.instrument_id,
                                           action_id=action.action_id, cash_cny=str(amount),
                                           payment_date=action.payment_date.isoformat()))
                continue
            else:
                self.unresolved[action.instrument_id] = "UNRESOLVED_CORPORATE_ACTION"
            self.journal.append(_event(day, "CORPORATE_ACTION_UNRESOLVED", instrument_id=action.instrument_id,
                                       action_id=action.action_id, reason=self.unresolved[action.instrument_id]))

    def _attempt(self, day: date, pending: _Pending, instrument: CNInstrument,
                 bar: CNBar | None) -> Literal["DONE", "KEEP"]:
        intent = pending.intent
        if instrument.listing_date is None or day < instrument.listing_date:
            self.journal.append(_event(day, "ORDER_CANCELLED", intent_id=intent.intent_id,
                                       reason="NOT_YET_LISTED_OR_UNKNOWN_LISTING"))
            return "DONE"
        if instrument.delisting_date is not None and day > instrument.delisting_date:
            if self.lots[instrument.instrument_id]:
                self.unresolved[instrument.instrument_id] = "DELISTING_WITHOUT_VERIFIED_CASH_RECOVERY"
            self.journal.append(_event(day, "ORDER_CANCELLED", intent_id=intent.intent_id,
                                       reason="AFTER_DELISTING_DATE"))
            return "DONE"
        if instrument.instrument_id in self.unresolved:
            self.journal.append(_event(day, "ORDER_CANCELLED", intent_id=intent.intent_id,
                                       reason=self.unresolved[instrument.instrument_id]))
            return "DONE"
        rule = self._rule(instrument, day)
        profile = self._cost(day)
        if bar is not None and bar.factor_event_unresolved:
            self.unresolved[instrument.instrument_id] = "FACTOR_EVENT_UNRESOLVED"
            self.journal.append(_event(day, "ORDER_CANCELLED", intent_id=intent.intent_id,
                                       reason="FACTOR_EVENT_UNRESOLVED"))
            return "DONE"
        assessment = assess_fill_proxy(
            side=intent.side, bar_present=bar is not None,
            trading_status=bar.trading_status if bar else None,
            limit_policy=bar.limit_policy if bar else None,
            locked_up=bar.locked_up if bar else None,
            locked_down=bar.locked_down if bar else None,
        )
        if assessment.state != "PROXY_ELIGIBLE" or bar is None or not _positive_price(bar.open_cny):
            reason = assessment.reason if assessment.state != "PROXY_ELIGIBLE" else "OPEN_PRICE_UNKNOWN"
            self.journal.append(_event(day, "ORDER_NOT_FILLED", intent_id=intent.intent_id,
                                       reason=reason, scenario=self.config.scenario))
            return "KEEP"
        if (bar.volume_shares is None or not bar.volume_shares.is_finite()
                or bar.volume_shares <= 0):
            self.journal.append(_event(day, "ORDER_NOT_FILLED", intent_id=intent.intent_id,
                                       reason="VOLUME_UNKNOWN_OR_ZERO"))
            return "KEEP"
        price = bar.open_cny
        if price % rule.tick_size != 0:
            self.journal.append(_event(day, "ORDER_NOT_FILLED", intent_id=intent.intent_id,
                                       reason="OPEN_PRICE_OFF_TICK"))
            return "KEEP"
        if intent.side == "BUY":
            if self.lots[intent.instrument_id] and not self.config.allow_pyramiding:
                self.journal.append(_event(day, "ORDER_REJECTED", intent_id=intent.intent_id,
                                           reason="PYRAMIDING_DISABLED"))
                return "DONE"
            if self.lots[intent.instrument_id] == [] and sum(bool(value) for value in self.lots.values()) >= self.config.max_positions:
                self.journal.append(_event(day, "ORDER_NOT_FILLED", intent_id=intent.intent_id,
                                           reason="MAX_POSITIONS"))
                return "KEEP"
            budget = min(self.cash, intent.budget_cny or Decimal(0))
            decision = prepare_buy(rule=rule, price_cny=price, budget_cny=budget, profile=profile)
            quantity = decision.shares
        else:
            if intent.shares is None:
                quantity = sum(lot.shares for lot in self.lots[intent.instrument_id])
            else:
                quantity = intent.shares
            decision = prepare_sell(
                rule=rule, lots=tuple(InventoryLot(lot.shares, lot.acquired_session)
                                      for lot in self.lots[intent.instrument_id]),
                session_date=day, requested_shares=quantity,
            )
        if decision.state != "ORDER_CANDIDATE":
            kind = "ORDER_DEFERRED" if decision.state == "DEFERRED_T1" else "ORDER_REJECTED"
            self.journal.append(_event(day, kind, intent_id=intent.intent_id, reason=decision.reason))
            return "KEEP" if decision.state == "DEFERRED_T1" else "DONE"
        quantity = decision.shares if intent.side == "BUY" else quantity
        share_cap = {"permissive": Decimal("0.10"), "base": Decimal("0.05"),
                     "conservative": Decimal("0.01")}[self.config.scenario]
        if Decimal(quantity) > bar.volume_shares * share_cap:
            self.journal.append(_event(day, "ORDER_NOT_FILLED", intent_id=intent.intent_id,
                                       reason="PARTICIPATION_CAP", requested_shares=quantity))
            return "KEEP"
        notional = price * quantity
        cost = estimate_cost(profile=profile, side=intent.side, notional_cny=notional)
        if intent.side == "BUY":
            if notional + cost.total_cny > self.cash:
                raise CNExecutionContractError("Budget achat calculé sans frais")
            self._spend_cash(notional + cost.total_cny)
            self.lots[intent.instrument_id].append(_Lot(quantity, day))
        else:
            proceeds = notional - cost.total_cny
            if proceeds < 0:
                self.journal.append(_event(day, "ORDER_REJECTED", intent_id=intent.intent_id,
                                           reason="SELL_COST_EXCEEDS_NOTIONAL"))
                return "DONE"
            remaining = quantity
            for lot in self.lots[intent.instrument_id]:
                take = min(remaining, lot.shares) if lot.acquired_session < day else 0
                lot.shares -= take
                remaining -= take
            if remaining:
                raise CNExecutionContractError("Vente dépassant l'inventaire T+1")
            self.lots[intent.instrument_id] = [lot for lot in self.lots[intent.instrument_id] if lot.shares]
            self.cash += proceeds
            self.unsettled.append((day, proceeds))  # passage à withdrawable à la séance suivante
        self.commission_total += cost.commission_cny
        self.other_cost_total += cost.total_cny - cost.commission_cny
        self.journal.append(_event(day, "HYPOTHETICAL_FILL", intent_id=intent.intent_id,
                                   instrument_id=intent.instrument_id, side=intent.side,
                                   scenario=self.config.scenario, shares=quantity,
                                   price_cny=str(price), notional_cny=str(notional),
                                   cost_cny=str(cost.total_cny), cost_breakdown={
                                       key: str(value) for key, value in asdict(cost).items()},
                                   evidence="DAILY_BAR_PROXY_NOT_OBSERVED_EXECUTION"))
        return "DONE"

    def run(self, *, sessions: list[date], instruments: list[CNInstrument],
            bars: list[CNBar], intents: list[CNIntent],
            actions: list[CNAction] | None = None) -> ReplayResult:
        if self._used:
            raise RuntimeError("Une instance de replay CN ne peut être exécutée qu'une fois")
        self._used = True
        days = sorted(set(sessions))
        if not days or len(days) != len(sessions):
            raise ValueError("Calendrier CN vide ou dupliqué")
        by_instrument = {item.instrument_id: item for item in instruments}
        if len(by_instrument) != len(instruments):
            raise ValueError("Instruments CN dupliqués")
        if any(item.exchange_mic not in {"XSHG", "XSHE"} for item in instruments):
            raise ValueError("Instrument non CN_A dans le replay")
        # Une absence de règle/coût en fin de période ne doit pas passer
        # inaperçue lorsque aucun ordre n'y est tenté (notamment en 2026).
        cost = self._cost(days[0])
        if cost.valid_to is not None and cost.valid_to < days[-1]:
            raise CNExecutionContractError("Profil de coûts non valide sur toute la fenêtre")
        for instrument in instruments:
            active_days = [day for day in days if instrument.listing_date is not None
                           and day >= instrument.listing_date
                           and (instrument.delisting_date is None or day <= instrument.delisting_date)]
            if active_days:
                rule = self._rule(instrument, active_days[0])
                if rule.valid_to is not None and rule.valid_to < active_days[-1]:
                    raise CNExecutionContractError("Règle CN non valide sur toute la fenêtre active")
        by_bar = {(item.session_date, item.instrument_id): item for item in bars}
        if len(by_bar) != len(bars) or any(key[0] not in days or key[1] not in by_instrument for key in by_bar):
            raise ValueError("Barres CN dupliquées ou hors univers/calendrier")
        signals: dict[date, list[CNIntent]] = defaultdict(list)
        identifiers = set()
        for intent in intents:
            if (intent.intent_id in identifiers or intent.signal_date not in days
                    or intent.instrument_id not in by_instrument or intent.side not in {"BUY", "SELL"}
                    or (intent.side == "BUY" and (
                        intent.budget_cny is None or not intent.budget_cny.is_finite()
                        or intent.budget_cny <= 0 or intent.shares is not None))
                    or (intent.side == "SELL" and intent.budget_cny is not None)
                    or (intent.side == "SELL" and intent.shares is not None and intent.shares <= 0)
                    or not intent.priority.is_finite()):
                raise ValueError("Signal CN invalide ou dupliqué")
            identifiers.add(intent.intent_id)
            signals[intent.signal_date].append(intent)
        events = actions or []
        if len({item.action_id for item in events}) != len(events) or any(
            item.instrument_id not in by_instrument or item.ex_date not in days for item in events
        ):
            raise ValueError("Corporate actions CN invalides ou dupliquées")
        for index, day in enumerate(days):
            self._settle(day)
            self._actions(day, events)
            # Un ordre décidé après clôture J ne peut jamais prendre l'open J.
            ready = [item for item in self.pending if item.intent.signal_date < day]
            self.pending = [item for item in self.pending if item.intent.signal_date >= day]
            ready.sort(key=lambda item: (item.intent.side != "SELL", -item.intent.priority,
                                         item.intent.intent_id))
            for item in ready:
                item.wait_sessions += 1
                instrument = by_instrument[item.intent.instrument_id]
                state = self._attempt(day, item, instrument, by_bar.get((day, instrument.instrument_id)))
                if state == "KEEP":
                    if (self.config.pending_policy == "cancel_day"
                            or item.wait_sessions >= self.config.max_wait_sessions):
                        self.journal.append(_event(day, "ORDER_CANCELLED", intent_id=item.intent.intent_id,
                                                   reason="END_OF_DAY" if self.config.pending_policy == "cancel_day"
                                                   else "MAX_WAIT_SESSIONS"))
                    else:
                        self.pending.append(item)
            for intent in sorted(signals[day], key=lambda value: value.intent_id):
                self.pending.append(_Pending(intent))
                self.journal.append(_event(day, "ORDER_QUEUED_NEXT_SESSION", intent_id=intent.intent_id,
                                           instrument_id=intent.instrument_id, side=intent.side,
                                           reason=intent.reason))
            for instrument_id, instrument in by_instrument.items():
                bar = by_bar.get((day, instrument_id))
                if bar is not None and bar.factor_event_unresolved and self.lots[instrument_id]:
                    self.unresolved[instrument_id] = "FACTOR_EVENT_UNRESOLVED"
                if instrument.delisting_date is not None and day > instrument.delisting_date and self.lots[instrument_id]:
                    self.unresolved[instrument_id] = "DELISTING_WITHOUT_VERIFIED_CASH_RECOVERY"
                if bar is not None and _positive_price(bar.close_cny):
                    self.last_close[instrument_id] = bar.close_cny
            receivables = sum((value for _, value, _, _ in self.dividends_due), Decimal(0))
            holdings = sum((Decimal(sum(lot.shares for lot in lots)) * self.last_close.get(instrument_id, Decimal(0))
                            for instrument_id, lots in self.lots.items()), Decimal(0))
            unpriced = sorted(instrument_id for instrument_id, lots in self.lots.items()
                              if lots and instrument_id not in self.last_close)
            stale = sorted(instrument_id for instrument_id, lots in self.lots.items()
                           if lots and (by_bar.get((day, instrument_id)) is None
                                        or not _positive_price(by_bar[(day, instrument_id)].close_cny)))
            self.daily.append({
                "session_date": day.isoformat(), "cash_spendable_cny": str(self.cash),
                "cash_withdrawable_cny": str(self.withdrawable_cash),
                "dividend_receivable_cny": str(receivables),
                "holdings_mark_cny": str(holdings),
                "equity_mark_cny": str(self.cash + receivables + holdings),
                "mark_valid": not self.unresolved and not unpriced and not stale,
                "unresolved_instruments": sorted(self.unresolved), "unpriced_instruments": unpriced,
                "stale_marks": stale,
                "open_positions": sum(bool(value) for value in self.lots.values()),
                "pending_orders": len(self.pending), "commission_cny": str(self.commission_total),
                "other_costs_cny": str(self.other_cost_total), "session_index": index,
            })
        for item in self.pending:
            self.journal.append(_event(days[-1], "ORDER_UNEXECUTED_END_OF_REPLAY",
                                       intent_id=item.intent.intent_id, reason="NO_FUTURE_SESSION"))
        return ReplayResult(
            journal=self.journal, daily=self.daily, cash_cny=self.cash,
            lots={key: [InventoryLot(lot.shares, lot.acquired_session) for lot in value]
                  for key, value in self.lots.items() if value},
            unresolved=dict(self.unresolved),
            pending_intents=[item.intent.intent_id for item in self.pending],
            economic_result_valid=not self.unresolved and all(item["mark_valid"] for item in self.daily),
        )
