"""Sprint 12-A : règles CN_A datées et contrôles d'ordre sans fills fictifs.

Le contrat reste inerte pour le live. Les profils RESEARCH_PROXY exigent un
opt-in explicite ; une règle ou un coût absent/ambigu provoque un refus.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection

from service.market.cn_tradability_contract import assess_execution_data


class CNExecutionContractError(RuntimeError):
    """Aucune décision d'ordre ne peut être prise avec un contrat incertain."""


@dataclass(frozen=True)
class ExecutionRule:
    rule_id: int
    valid_from: date
    valid_to: date | None
    exchange_mic: str
    board_code: str
    buy_increment: int
    minimum_buy_shares: int
    minimum_sell_shares: int
    tick_size: Decimal
    same_day_sell_allowed: bool
    short_selling_allowed: bool
    settlement_cycle_days: int
    research_only: bool
    rule_version: str


@dataclass(frozen=True)
class CostProfile:
    profile_id: int
    profile_key: str
    valid_from: date
    valid_to: date | None
    source_type: Literal["RESEARCH_PROXY", "VERIFIED_BROKER"]
    commission_bps_buy: Decimal
    commission_bps_sell: Decimal
    commission_min_cny: Decimal
    transfer_fee_bps_buy: Decimal
    transfer_fee_bps_sell: Decimal
    stamp_duty_bps_sell: Decimal
    slippage_bps_buy: Decimal
    slippage_bps_sell: Decimal
    source_ref: str


@dataclass(frozen=True)
class InventoryLot:
    shares: int
    acquired_session: date


@dataclass(frozen=True)
class OrderDecision:
    state: Literal["ORDER_CANDIDATE", "PROXY_ELIGIBLE", "REJECTED", "DEFERRED_T1", "UNVERIFIABLE"]
    reason: str
    shares: int


@dataclass(frozen=True)
class CostBreakdown:
    commission_cny: Decimal
    transfer_fee_cny: Decimal
    stamp_duty_cny: Decimal
    slippage_cny: Decimal
    total_cny: Decimal


def _metadata(value: Any) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise CNExecutionContractError("Métadonnées de règle CN absentes ou invalides")
    return parsed


def _date_value(value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _exactly_one(rows: list[Any], kind: str) -> Any:
    if len(rows) != 1:
        raise CNExecutionContractError(f"{kind} CN attendu exactement une fois, trouvé={len(rows)}")
    return rows[0]


def resolve_rule(
    conn: Connection, *, exchange_mic: str, board_code: str, session_date: date,
    allow_research_rules: bool = False,
) -> ExecutionRule:
    if exchange_mic not in {"XSHG", "XSHE"} or board_code not in {
        "SH_MAIN", "SZ_MAIN", "CHINEXT", "STAR",
    }:
        raise CNExecutionContractError("MIC ou board CN_A non pris en charge")
    rows = conn.execute(text("""
        SELECT rule_id,market_code,exchange_mic,board_code,valid_from,valid_to,
               currency,settlement_cycle_days,buy_lot_size,sell_lot_size,
               tick_size,daily_price_limit_pct,short_selling_allowed,
               same_day_sell_allowed,metadata_json
        FROM market_execution_rules
        WHERE market_code='CN_A' AND exchange_mic=:mic AND board_code=:board
          AND valid_from<=:session_date
          AND (valid_to IS NULL OR valid_to>=:session_date)
    """), {"mic": exchange_mic, "board": board_code, "session_date": session_date}).mappings().all()
    row = _exactly_one(rows, "Règle d'exécution")
    meta = _metadata(row["metadata_json"])
    if (row["currency"] != "CNY" or row["market_code"] != "CN_A"
            or row["exchange_mic"] != exchange_mic or row["board_code"] != board_code
            or row["daily_price_limit_pct"] is not None):
        raise CNExecutionContractError("Règle CN incohérente ou limite générique dangereuse")
    research_only = meta.get("research_only") is True or meta.get("research_only") == 1
    verified = meta.get("source_type") == "OFFICIAL_VERIFIED" and bool(meta.get("source_ref"))
    if not research_only and not verified:
        raise CNExecutionContractError("Règle CN sans provenance officielle vérifiée")
    if research_only and not allow_research_rules:
        raise CNExecutionContractError("Règle CN recherche interdite sans opt-in explicite")
    minimum_buy = int(meta.get("minimum_buy_shares", 0))
    minimum_sell = int(meta.get("minimum_sell_shares", 0))
    buy_increment = int(row["buy_lot_size"])
    tick = Decimal(str(row["tick_size"]))
    if (minimum_buy < 1 or minimum_sell < 1 or buy_increment < 1
            or tick <= 0 or int(row["sell_lot_size"]) != 1
            or int(row["settlement_cycle_days"]) != 1
            or bool(row["same_day_sell_allowed"]) or bool(row["short_selling_allowed"])
            or not str(meta.get("rule_version") or "")):
        raise CNExecutionContractError("Règle CN incomplète ou non conforme au contrat T+1")
    return ExecutionRule(
        rule_id=int(row["rule_id"]), valid_from=_date_value(row["valid_from"]),
        valid_to=_date_value(row["valid_to"]),
        exchange_mic=exchange_mic, board_code=board_code, buy_increment=buy_increment,
        minimum_buy_shares=minimum_buy, minimum_sell_shares=minimum_sell,
        tick_size=tick, same_day_sell_allowed=False, short_selling_allowed=False,
        settlement_cycle_days=1, research_only=research_only, rule_version=str(meta["rule_version"]),
    )


def resolve_cost_profile(
    conn: Connection, *, profile_key: str, session_date: date,
    allow_research_proxy: bool = False,
) -> CostProfile:
    rows = conn.execute(text("""
        SELECT profile_id,market_code,profile_key,valid_from,valid_to,currency,source_type,
               commission_bps_buy,commission_bps_sell,commission_min_cny,
               transfer_fee_bps_buy,transfer_fee_bps_sell,stamp_duty_bps_sell,
               slippage_bps_buy,slippage_bps_sell,source_ref
        FROM cn_execution_cost_profiles
        WHERE market_code='CN_A' AND profile_key=:profile
          AND valid_from<=:session_date
          AND (valid_to IS NULL OR valid_to>=:session_date)
    """), {"profile": profile_key, "session_date": session_date}).mappings().all()
    row = _exactly_one(rows, "Profil de coûts")
    if row["currency"] != "CNY" or row["source_type"] not in {"RESEARCH_PROXY", "VERIFIED_BROKER"}:
        raise CNExecutionContractError("Profil de coûts CN non vérifiable")
    if row["source_type"] == "RESEARCH_PROXY" and not allow_research_proxy:
        raise CNExecutionContractError("Coûts de recherche interdits sans opt-in explicite")
    values = {
        field: Decimal(str(row[field])) for field in (
            "commission_bps_buy", "commission_bps_sell", "commission_min_cny",
            "transfer_fee_bps_buy", "transfer_fee_bps_sell", "stamp_duty_bps_sell",
            "slippage_bps_buy", "slippage_bps_sell",
        )
    }
    if any(value < 0 for value in values.values()) or not str(row["source_ref"] or ""):
        raise CNExecutionContractError("Profil de coûts CN négatif ou sans source")
    return CostProfile(
        profile_id=int(row["profile_id"]), profile_key=str(row["profile_key"]),
        valid_from=_date_value(row["valid_from"]), valid_to=_date_value(row["valid_to"]),
        source_type=row["source_type"], source_ref=str(row["source_ref"]), **values,
    )


def estimate_cost(*, profile: CostProfile, side: Literal["BUY", "SELL"],
                  notional_cny: Decimal) -> CostBreakdown:
    if side not in {"BUY", "SELL"} or notional_cny <= 0:
        raise CNExecutionContractError("Côté ou notionnel CN invalide")
    commission_bps = profile.commission_bps_buy if side == "BUY" else profile.commission_bps_sell
    transfer_bps = profile.transfer_fee_bps_buy if side == "BUY" else profile.transfer_fee_bps_sell
    slippage_bps = profile.slippage_bps_buy if side == "BUY" else profile.slippage_bps_sell
    basis = notional_cny / Decimal(10_000)
    commission = max(profile.commission_min_cny, basis * commission_bps)
    transfer = basis * transfer_bps
    stamp = basis * profile.stamp_duty_bps_sell if side == "SELL" else Decimal(0)
    slippage = basis * slippage_bps
    return CostBreakdown(
        commission_cny=commission, transfer_fee_cny=transfer,
        stamp_duty_cny=stamp, slippage_cny=slippage,
        total_cny=commission + transfer + stamp + slippage,
    )


def prepare_buy(
    *, rule: ExecutionRule, price_cny: Decimal, budget_cny: Decimal,
    profile: CostProfile,
) -> OrderDecision:
    if price_cny <= 0 or budget_cny <= 0:
        return OrderDecision("REJECTED", "INVALID_PRICE_OR_BUDGET", 0)
    increment = rule.buy_increment
    shares = int((budget_cny / price_cny / increment).to_integral_value(rounding=ROUND_FLOOR)) * increment
    while shares >= rule.minimum_buy_shares:
        notional = price_cny * shares
        if notional + estimate_cost(profile=profile, side="BUY", notional_cny=notional).total_cny <= budget_cny:
            return OrderDecision("ORDER_CANDIDATE", "LOT_AND_BUDGET_CHECKS_PASSED", shares)
        shares -= increment
    return OrderDecision("REJECTED", "LOT_OR_FEES_NOT_AFFORDABLE", 0)


def prepare_sell(
    *, rule: ExecutionRule, lots: tuple[InventoryLot, ...],
    session_date: date, requested_shares: int,
) -> OrderDecision:
    if requested_shares <= 0 or any(lot.shares <= 0 for lot in lots):
        return OrderDecision("REJECTED", "INVALID_SELL_QUANTITY_OR_INVENTORY", 0)
    held = sum(lot.shares for lot in lots)
    if requested_shares > held:
        return OrderDecision("REJECTED", "SELL_EXCEEDS_HELD", 0)
    sellable = sum(lot.shares for lot in lots if lot.acquired_session < session_date)
    if requested_shares > sellable:
        return OrderDecision("DEFERRED_T1", "SHARES_NOT_YET_SELLABLE", 0)
    if requested_shares < rule.minimum_sell_shares and requested_shares != held:
        return OrderDecision("REJECTED", "ODD_LOT_ONLY_AS_FULL_RESIDUAL", 0)
    return OrderDecision("ORDER_CANDIDATE", "INVENTORY_AND_T1_CHECKS_PASSED", requested_shares)


def assess_fill_proxy(
    *, side: Literal["BUY", "SELL"], bar_present: bool,
    trading_status: str | None, limit_policy: str | None,
    locked_up: bool | None, locked_down: bool | None,
) -> OrderDecision:
    if side not in {"BUY", "SELL"}:
        raise CNExecutionContractError("Côté d'ordre CN inconnu")
    if not bar_present:
        return OrderDecision("REJECTED", "NO_SESSION_BAR", 0)
    if trading_status not in {"TRADE", "TRADE|ST", "SUSPENDED", "SUSPENDED|ST"}:
        return OrderDecision("UNVERIFIABLE", "UNKNOWN_TRADING_STATUS", 0)
    if trading_status.startswith("SUSPENDED"):
        return OrderDecision("REJECTED", "SUSPENDED_SESSION", 0)
    if locked_up is None or locked_down is None:
        return OrderDecision("UNVERIFIABLE", "LIMIT_LOCK_STATE_UNKNOWN", 0)
    known_limits = {
        "CN_MAIN_10PCT_V1", "CN_ST_5PCT_V1", "CN_STAR_20PCT_V1",
        "CN_CHINEXT_20PCT_POST_20200824_V1",
        "CN_MAIN_ST_10PCT_POST_20260706_V1",
    }
    if limit_policy not in known_limits:
        return OrderDecision("UNVERIFIABLE", "LIMIT_POLICY_NOT_VERIFIED", 0)
    assessment = assess_execution_data(
        bar_present=bar_present, trading_status=trading_status,
        limit_policy=limit_policy, locked_up=locked_up, locked_down=locked_down,
    )
    if assessment.state == "DATA_CHECKS_PASSED":
        return OrderDecision("PROXY_ELIGIBLE", "DATA_CHECKS_PASSED_NO_ORDER_BOOK_FILL_PROOF", 0)
    state = "REJECTED" if assessment.state == "EXCLUDED" else "UNVERIFIABLE"
    return OrderDecision(state, assessment.reason, 0)
