"""Sprint 18-B : journal d'exécution CN_A hypothétique, sans broker ni DB.

Deux temps stricts : planification avec seules données PIT au signal, puis
qualification ex post d'une barre observée. Aucun état « filled » broker.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from service.market.cn_execution_contract import (
    CNExecutionContractError, CostBreakdown, CostProfile, ExecutionRule, InventoryLot,
    assess_fill_proxy, estimate_cost, prepare_buy, prepare_sell,
)
from service.market.cn_tradability_contract import assess_pretrade

SHANGHAI = ZoneInfo("Asia/Shanghai")
PARTICIPATION = {"permissive": Decimal("0.10"), "base": Decimal("0.05"),
                 "conservative": Decimal("0.01")}


@dataclass(frozen=True)
class ShadowIntent:
    intent_id: str
    instrument_id: int
    symbol: str
    market_code: str
    exchange_mic: str
    board_code: str
    signal_at: datetime
    execution_session: date
    side: Literal["BUY", "SELL"]
    budget_cny: Decimal | None = None
    requested_shares: int | None = None
    source_ref: str = ""


@dataclass(frozen=True)
class ShadowPlan:
    intent: ShadowIntent
    state: Literal["QUEUED", "REJECTED"]
    reason: str
    decision_fingerprint: str


@dataclass(frozen=True)
class ShadowBar:
    session_date: date
    instrument_id: int
    market_code: str
    observed_at: datetime
    open_cny: Decimal | None
    close_cny: Decimal | None
    volume_shares: Decimal | None
    trading_status: str | None
    limit_policy: str | None
    locked_up: bool | None
    locked_down: bool | None
    source_ref: str
    factor_event_unresolved: bool = False


@dataclass(frozen=True)
class ShadowAttempt:
    intent_id: str
    instrument_id: int
    market_code: str
    side: Literal["BUY", "SELL"]
    session_date: date
    observed_at: datetime | None
    state: Literal["REJECTED", "DEFERRED_T1", "UNVERIFIABLE", "NOT_FILLED",
                   "HYPOTHETICAL_FILL"]
    reason: str
    shares: int
    hypothetical_price_cny: Decimal | None
    hypothetical_notional_cny: Decimal | None
    hypothetical_cost_cny: Decimal | None
    hypothetical_cost_breakdown: CostBreakdown | None
    decision_fingerprint: str
    observation_fingerprint: str
    observed_bar: ShadowBar | None
    rule_id: int | None
    rule_version: str
    cost_profile_id: int | None
    cost_profile_key: str
    cost_source_type: str
    scenario: str
    evidence: str = "DAILY_BAR_PROXY_NOT_OBSERVED_EXECUTION"


@dataclass(frozen=True)
class ShadowMark:
    intent_id: str
    instrument_id: int
    mark_session: date
    observed_at: datetime
    mark_close_cny: Decimal
    directional_move_pct: Decimal
    observed_bar: ShadowBar
    note: str = "PRICE_COMPARISON_ONLY_NOT_REALIZED_PNL"


def _fingerprint(value: object) -> str:
    payload = json.dumps(asdict(value), sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _shanghai_date(value: datetime) -> date:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CNExecutionContractError("Horodatage shadow sans fuseau horaire")
    return value.astimezone(SHANGHAI).date()


def plan_shadow_intent(
    intent: ShadowIntent, *, listing_date: date | None,
    delisting_date: date | None, known_trading_status: str | None = None,
    status_available_at: datetime | None = None,
    known_limit_policy: str | None = None,
    limit_available_at: datetime | None = None,
    delisting_available_at: datetime | None = None,
) -> ShadowPlan:
    """Décide sans barre future ; un signal J ne tente jamais un fill J."""
    signal_day = _shanghai_date(intent.signal_at)
    if not intent.intent_id or not intent.symbol or not intent.source_ref or intent.instrument_id <= 0:
        raise CNExecutionContractError("Identité ou provenance de l'intention absente")
    if intent.market_code != "CN_A" or intent.exchange_mic not in {"XSHG", "XSHE"}:
        raise CNExecutionContractError("Shadow réservé aux actions CN_A XSHG/XSHE")
    if intent.board_code not in {"SH_MAIN", "SZ_MAIN", "CHINEXT", "STAR"}:
        raise CNExecutionContractError("Board CN inconnu")
    if intent.execution_session <= signal_day:
        raise CNExecutionContractError("Séance de tentative non postérieure au signal")
    if intent.side == "BUY":
        if (intent.budget_cny is None or not intent.budget_cny.is_finite()
                or intent.budget_cny <= 0 or intent.requested_shares is not None):
            raise CNExecutionContractError("Budget achat CN invalide")
    elif intent.side == "SELL":
        if intent.budget_cny is not None or (intent.requested_shares is not None
                                             and intent.requested_shares <= 0):
            raise CNExecutionContractError("Quantité vente CN invalide")
    else:
        raise CNExecutionContractError("Côté CN inconnu")
    for available_at in (status_available_at, limit_available_at, delisting_available_at):
        if available_at is not None:
            _shanghai_date(available_at)
    if delisting_date is not None and delisting_date >= signal_day and delisting_available_at is None:
        raise CNExecutionContractError("Radiation future sans horodatage de disponibilité PIT")
    effective_delisting = (
        delisting_date if delisting_available_at is not None
        and delisting_available_at <= intent.signal_at else None
    )
    if delisting_date is not None and delisting_date < signal_day:
        effective_delisting = delisting_date
    pretrade = assess_pretrade(
        session_date=intent.execution_session, decision_at=intent.signal_at,
        listing_date=listing_date, delisting_date=effective_delisting,
        trading_status=known_trading_status, status_available_at=status_available_at,
        limit_policy=known_limit_policy, limit_available_at=limit_available_at,
    )
    return ShadowPlan(intent, "QUEUED" if pretrade.state == "CANDIDATE" else "REJECTED",
                      pretrade.reason, _fingerprint(intent))


def assess_shadow_attempt(
    plan: ShadowPlan, *, bar: ShadowBar | None, rule: ExecutionRule,
    profile: CostProfile, lots: tuple[InventoryLot, ...] = (),
    cash_available_cny: Decimal = Decimal(0), scenario: str = "base",
    allow_research_rules: bool = False, allow_research_proxy: bool = False,
) -> ShadowAttempt:
    """Qualifie ex post une tentative ; un fill n'est qu'une hypothèse de barre."""
    intent = plan.intent
    if scenario not in PARTICIPATION:
        raise CNExecutionContractError("Scénario de participation inconnu")
    if plan.decision_fingerprint != _fingerprint(intent):
        raise CNExecutionContractError("Plan shadow altéré après décision")
    day = intent.execution_session
    if (rule.exchange_mic != intent.exchange_mic or rule.board_code != intent.board_code
            or rule.valid_from > day or (rule.valid_to is not None and rule.valid_to < day)
            or profile.valid_from > day or (profile.valid_to is not None and profile.valid_to < day)):
        raise CNExecutionContractError("Règle/coût CN non valide pour la séance et l'instrument")
    if rule.research_only and not allow_research_rules:
        raise CNExecutionContractError("Règle de recherche sans opt-in shadow")
    if profile.source_type == "RESEARCH_PROXY" and not allow_research_proxy:
        raise CNExecutionContractError("Coûts proxy sans opt-in shadow")
    if cash_available_cny < 0 or not cash_available_cny.is_finite():
        raise CNExecutionContractError("Cash shadow invalide")
    if bar is not None:
        if (bar.market_code != "CN_A" or bar.instrument_id != intent.instrument_id
                or bar.session_date != day or _shanghai_date(bar.observed_at) < day):
            raise CNExecutionContractError("Barre observée hors séance ou avant séance")
        if not bar.source_ref:
            raise CNExecutionContractError("Barre shadow sans provenance")
        earliest = datetime.combine(day, time(15, 0), tzinfo=SHANGHAI)
        if bar.observed_at.astimezone(SHANGHAI) < earliest:
            raise CNExecutionContractError("Barre quotidienne observée avant la clôture CN")

    def result(state: str, reason: str, shares: int = 0,
               price: Decimal | None = None,
               cost: CostBreakdown | None = None) -> ShadowAttempt:
        return ShadowAttempt(
            intent.intent_id, intent.instrument_id, intent.market_code, intent.side,
            day, bar.observed_at if bar else None,
            state, reason, shares, price, price * shares if price is not None else None,
            cost.total_cny if cost else None, cost, plan.decision_fingerprint,
            _fingerprint(bar) if bar is not None else "NO_BAR", bar, rule.rule_id,
            rule.rule_version, profile.profile_id, profile.profile_key,
            profile.source_type, scenario,
        )

    if plan.state != "QUEUED":
        return result("REJECTED", plan.reason)
    if bar is not None and bar.factor_event_unresolved:
        return result("UNVERIFIABLE", "FACTOR_EVENT_UNRESOLVED")
    assessment = assess_fill_proxy(
        side=intent.side, bar_present=bar is not None,
        trading_status=bar.trading_status if bar else None,
        limit_policy=bar.limit_policy if bar else None,
        locked_up=bar.locked_up if bar else None,
        locked_down=bar.locked_down if bar else None,
    )
    if assessment.state != "PROXY_ELIGIBLE":
        state = "UNVERIFIABLE" if assessment.state == "UNVERIFIABLE" else "NOT_FILLED"
        return result(state, assessment.reason)
    assert bar is not None
    price, volume = bar.open_cny, bar.volume_shares
    if price is None or not price.is_finite() or price <= 0:
        return result("UNVERIFIABLE", "OPEN_PRICE_UNKNOWN")
    if rule.tick_size <= 0 or price % rule.tick_size != 0:
        return result("UNVERIFIABLE", "OPEN_PRICE_OFF_TICK")
    if volume is None or not volume.is_finite() or volume <= 0:
        return result("UNVERIFIABLE", "VOLUME_UNKNOWN_OR_ZERO")
    if intent.side == "BUY":
        budget = min(cash_available_cny, intent.budget_cny or Decimal(0))
        decision = prepare_buy(rule=rule, price_cny=price, budget_cny=budget, profile=profile)
    else:
        quantity = intent.requested_shares or sum(lot.shares for lot in lots)
        decision = prepare_sell(rule=rule, lots=lots, session_date=day,
                                requested_shares=quantity)
    if decision.state != "ORDER_CANDIDATE":
        state = "DEFERRED_T1" if decision.state == "DEFERRED_T1" else "REJECTED"
        return result(state, decision.reason)
    if Decimal(decision.shares) > volume * PARTICIPATION[scenario]:
        return result("NOT_FILLED", "PARTICIPATION_CAP", decision.shares)
    notional = price * decision.shares
    cost = estimate_cost(profile=profile, side=intent.side, notional_cny=notional)
    if intent.side == "SELL" and cost.total_cny > notional:
        return result("REJECTED", "SELL_COST_EXCEEDS_NOTIONAL")
    return result("HYPOTHETICAL_FILL", "DAILY_BAR_PROXY_ONLY", decision.shares,
                  price, cost)


def mark_shadow_attempt(attempt: ShadowAttempt, *, next_bar: ShadowBar) -> ShadowMark:
    """Rapprochement ex post du prix suivant, jamais un PnL réalisé."""
    if attempt.state != "HYPOTHETICAL_FILL" or attempt.hypothetical_price_cny is None:
        raise CNExecutionContractError("Aucun prix hypothétique à rapprocher")
    if (next_bar.market_code != "CN_A" or next_bar.instrument_id != attempt.instrument_id
            or next_bar.session_date <= attempt.session_date
            or _shanghai_date(next_bar.observed_at) < next_bar.session_date):
        raise CNExecutionContractError("La marque doit provenir d'une séance ultérieure observée")
    if not next_bar.source_ref:
        raise CNExecutionContractError("Marque shadow sans provenance")
    earliest = datetime.combine(next_bar.session_date, time(15, 0), tzinfo=SHANGHAI)
    if next_bar.observed_at.astimezone(SHANGHAI) < earliest:
        raise CNExecutionContractError("Marque observée avant clôture")
    close = next_bar.close_cny
    if (close is None or not close.is_finite() or close <= 0
            or next_bar.factor_event_unresolved
            or next_bar.trading_status not in {"TRADE", "TRADE|ST"}):
        raise CNExecutionContractError("Close ultérieur ou facteur non vérifiable")
    # Le sens d'un SELL représente uniquement le mouvement évité après sortie.
    raw_move = close / attempt.hypothetical_price_cny - Decimal(1)
    signed_move = raw_move if attempt.side == "BUY" else -raw_move
    return ShadowMark(attempt.intent_id, attempt.instrument_id,
                      next_bar.session_date, next_bar.observed_at,
                      close, signed_move, next_bar)


def write_shadow_audit(
    path: Path, *, plan: ShadowPlan, attempt: ShadowAttempt,
    mark: ShadowMark | None = None,
) -> None:
    """Archive une preuve immuable ; refuse d'écraser un ancien résultat."""
    if (attempt.intent_id != plan.intent.intent_id
            or attempt.instrument_id != plan.intent.instrument_id
            or attempt.market_code != plan.intent.market_code
            or attempt.side != plan.intent.side
            or attempt.session_date != plan.intent.execution_session
            or attempt.decision_fingerprint != plan.decision_fingerprint
            or plan.decision_fingerprint != _fingerprint(plan.intent)
            or attempt.observation_fingerprint != (
                _fingerprint(attempt.observed_bar)
                if attempt.observed_bar is not None else "NO_BAR")
            or (mark is not None and (
                mark.intent_id != attempt.intent_id
                or mark.instrument_id != attempt.instrument_id
                or mark.mark_session <= attempt.session_date
                or mark.observed_bar.instrument_id != attempt.instrument_id
                or mark.observed_bar.session_date != mark.mark_session
                or mark.observed_bar.observed_at != mark.observed_at
                or mark.observed_bar.close_cny != mark.mark_close_cny))):
        raise CNExecutionContractError("Chaîne de preuves shadow incohérente")
    if mark is not None and mark != mark_shadow_attempt(attempt, next_bar=mark.observed_bar):
        raise CNExecutionContractError("Marque shadow altérée")
    payload = {
        "schema_version": "cn_shadow_18b_v1", "mode": "SHADOW_RESEARCH_ONLY",
        "not_broker_execution": True, "plan": asdict(plan),
        "attempt": asdict(attempt), "mark": asdict(mark) if mark else None,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, default=str, indent=2)
        stream.write("\n")
