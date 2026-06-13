"""Sprint S7 - ``_AccountConstraintState`` + capacity helpers.

Extracted from :mod:`execution_engine.executor` to slim the orchestrator.
The helpers stay private (``_``-prefixed for state, free functions for
behaviours) and are re-exported by :mod:`execution_engine.executor` for
backwards compatibility (tests/test_execution_engine_executor.py).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from execution_engine.audit import make_event
from execution_engine.models import EventType, ExecutionEvent, OrderIntent

if TYPE_CHECKING:  # pragma: no cover
    from execution_engine.broker_adapter import BrokerAdapter
    from execution_engine.config import ExecutionConfig

LOGGER = logging.getLogger(__name__)


class InvalidBrokerSnapshotError(RuntimeError):
    """Hardening live — levée lorsqu'un snapshot broker ne contient pas d'equity exploitable.

    Un snapshot avec ``equity <= 0`` (ou champ manquant) signale soit une erreur
    transitoire de l'API broker, soit un compte non provisionné. Dans tous les
    cas il est dangereux de :
      * dimensionner les ordres sur cette base ;
      * persister ce snapshot et polluer les analyses risque downstream.
    """


@dataclass(slots=True)
class _AccountConstraintState:
    account_type: str
    swing_only: bool
    equity: float
    buying_power_available: float
    settled_cash_available: float
    daytrade_count: int
    leverage_feature_enabled: bool = False
    leverage_active: bool = False
    leverage_configured_max: float = 1.0
    effective_leverage: float = 1.0
    leverage_target_budget: float = 0.0
    leverage_broker_buying_power: float | None = None
    leverage_buying_power_field: str | None = None
    leverage_reason: str | None = None


@dataclass(frozen=True, slots=True)
class _ResolvedLeverageBudget:
    budget: float
    active: bool
    feature_enabled: bool
    configured_max: float
    effective_leverage: float
    target_budget: float
    broker_buying_power: float | None = None
    buying_power_field: str | None = None
    reason: str | None = None


def safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def estimate_intent_notional(intent: OrderIntent) -> float:
    price = intent.limit_price if intent.limit_price is not None else intent.decision_price
    return max(float(intent.qty) * max(float(price), 0.0), 0.0)


def _resolve_leverage_activation(
    cfg: "ExecutionConfig",
    *,
    equity: float,
) -> tuple[bool, str | None]:
    leverage_cfg = cfg.leverage
    if not leverage_cfg.enabled or leverage_cfg.mode == "disabled" or leverage_cfg.max_leverage <= 1.0:
        return False, "feature_disabled"
    if cfg.account_type != "margin":
        return False, "cash_account"
    if leverage_cfg.require_margin_account and cfg.account_type != "margin":
        return False, "margin_account_required"
    if equity < leverage_cfg.min_equity_usd:
        return False, "equity_below_minimum"
    if leverage_cfg.only_in_entry_mode == "normal" and cfg.entry_mode != "normal":
        return False, "entry_mode_not_normal"
    if leverage_cfg.disable_in_capital_preservation and cfg.entry_mode == "capital_preservation":
        return False, "capital_preservation"
    return True, None


def _resolve_snapshot_buying_power(
    snapshot: dict[str, object],
    cfg: "ExecutionConfig",
) -> tuple[float | None, str | None]:
    for field_name in cfg.leverage.buying_power_field_priority:
        raw_value = snapshot.get(field_name)
        if raw_value not in (None, ""):
            return max(safe_float(raw_value, default=0.0), 0.0), field_name
    raw_buying_power = snapshot.get("buying_power")
    if raw_buying_power not in (None, ""):
        return max(safe_float(raw_buying_power, default=0.0), 0.0), "buying_power"
    return None, None


def _log_leverage_decision(
    cfg: "ExecutionConfig",
    state: _ResolvedLeverageBudget,
    *,
    equity: float,
) -> None:
    if not cfg.leverage.audit_log:
        return
    LOGGER.info(
        "Leverage %s | account=%s mode=%s entry_mode=%s equity=%.2f broker_buying_power=%s field=%s "
        "max_leverage=%.2f effective_budget=%.2f effective_leverage=%.2fx reason=%s",
        "applied" if state.active else "disabled",
        getattr(cfg, "resolved_account_id", "?"),
        getattr(cfg, "broker_mode", "?"),
        cfg.entry_mode,
        equity,
        f"{state.broker_buying_power:.2f}" if state.broker_buying_power is not None else "None",
        state.buying_power_field,
        state.configured_max,
        state.budget,
        state.effective_leverage,
        state.reason,
    )


def _resolve_margin_buying_power(
    cfg: "ExecutionConfig",
    *,
    equity: float,
    snapshot: dict[str, object] | None = None,
) -> _ResolvedLeverageBudget:
    leverage_active, reason = _resolve_leverage_activation(cfg, equity=equity)
    feature_enabled = bool(cfg.leverage.enabled and cfg.leverage.mode != "disabled")
    configured_max = cfg.leverage.capped_live_max_leverage
    if cfg.dry_run:
        multiplier = float(cfg.simulated_margin_buying_power_multiplier)
        if leverage_active:
            multiplier = min(
                multiplier,
                float(cfg.leverage.dry_run_simulated_leverage),
                cfg.leverage.capped_live_max_leverage,
            )
        effective_budget = max(equity * max(multiplier, 1.0), 0.0)
        state = _ResolvedLeverageBudget(
            budget=effective_budget,
            active=leverage_active,
            feature_enabled=feature_enabled,
            configured_max=configured_max,
            effective_leverage=(effective_budget / equity) if equity > 0 else 1.0,
            target_budget=max(equity * configured_max, 0.0),
            broker_buying_power=effective_budget,
            buying_power_field="dry_run_simulated_multiplier",
            reason=reason,
        )
        _log_leverage_decision(cfg, state, equity=equity)
        return state

    if snapshot is None:
        state = _ResolvedLeverageBudget(
            budget=max(equity, 0.0),
            active=False,
            feature_enabled=feature_enabled,
            configured_max=configured_max,
            effective_leverage=1.0 if equity > 0 else 0.0,
            target_budget=max(equity * configured_max, 0.0),
            reason="missing_snapshot",
        )
        _log_leverage_decision(cfg, state, equity=equity)
        return state

    broker_buying_power, field_used = _resolve_snapshot_buying_power(snapshot, cfg)
    base_budget = min(max(equity, 0.0), broker_buying_power) if broker_buying_power is not None else max(equity, 0.0)
    if not leverage_active:
        effective_budget = (
            max(broker_buying_power, 0.0)
            if reason == "feature_disabled" and broker_buying_power is not None
            else base_budget
        )
        state = _ResolvedLeverageBudget(
            budget=effective_budget,
            active=False,
            feature_enabled=feature_enabled,
            configured_max=configured_max,
            effective_leverage=(effective_budget / equity) if equity > 0 else 0.0,
            target_budget=max(equity * configured_max, 0.0),
            broker_buying_power=broker_buying_power,
            buying_power_field=field_used,
            reason=reason,
        )
        _log_leverage_decision(cfg, state, equity=equity)
        return state

    if broker_buying_power is None:
        fallback_reason = "missing_buying_power_field"
        state = _ResolvedLeverageBudget(
            budget=base_budget,
            active=False,
            feature_enabled=feature_enabled,
            configured_max=configured_max,
            effective_leverage=(base_budget / equity) if equity > 0 else 0.0,
            target_budget=max(equity * configured_max, 0.0),
            broker_buying_power=None,
            buying_power_field=None,
            reason=fallback_reason,
        )
        _log_leverage_decision(cfg, state, equity=equity)
        return state

    target_budget = max(equity * cfg.leverage.capped_live_max_leverage, 0.0)
    effective_budget = min(target_budget, broker_buying_power)
    state = _ResolvedLeverageBudget(
        budget=max(effective_budget, 0.0),
        active=True,
        feature_enabled=feature_enabled,
        configured_max=configured_max,
        effective_leverage=(effective_budget / equity) if equity > 0 else 0.0,
        target_budget=target_budget,
        broker_buying_power=broker_buying_power,
        buying_power_field=field_used,
        reason=None,
    )
    _log_leverage_decision(cfg, state, equity=equity)
    return state


def build_account_constraint_state(
    cfg: "ExecutionConfig", broker: "BrokerAdapter"
) -> _AccountConstraintState:
    if cfg.dry_run:
        equity = float(cfg.simulated_account_equity)
        settled_cash = equity
        leverage_state = (
            _resolve_margin_buying_power(cfg, equity=equity)
            if cfg.account_type == "margin"
            else _ResolvedLeverageBudget(
                budget=settled_cash,
                active=False,
                feature_enabled=bool(cfg.leverage.enabled and cfg.leverage.mode != "disabled"),
                configured_max=cfg.leverage.capped_live_max_leverage,
                effective_leverage=(settled_cash / equity) if equity > 0 else 0.0,
                target_budget=max(equity * cfg.leverage.capped_live_max_leverage, 0.0),
                broker_buying_power=settled_cash,
                buying_power_field="settled_cash",
                reason="cash_account" if cfg.account_type == "cash" else None,
            )
        )
        buying_power = leverage_state.budget
        daytrade_count = 0
    else:
        snapshot = broker.get_account_snapshot()
        raw_equity = snapshot.get("equity") or snapshot.get("portfolio_value")
        equity = safe_float(raw_equity, default=0.0)
        if equity <= 0.0:
            LOGGER.error(
                "Snapshot broker rejeté — equity invalide | account=%s broker_mode=%s "
                "raw_equity=%r snapshot_keys=%s",
                getattr(cfg, "resolved_account_id", "?"),
                getattr(cfg, "broker_mode", "?"),
                raw_equity,
                sorted(snapshot.keys()) if isinstance(snapshot, dict) else type(snapshot).__name__,
            )
            raise InvalidBrokerSnapshotError(
                f"Broker snapshot equity invalide ({raw_equity!r}) — refus de poursuivre l'exécution"
            )
        settled_cash = safe_float(
            snapshot.get("non_marginable_buying_power")
            if cfg.account_type == "cash"
            else snapshot.get("cash"),
            default=0.0,
        )
        if settled_cash <= 0:
            settled_cash = safe_float(snapshot.get("cash"), default=0.0)
        leverage_state = (
            _resolve_margin_buying_power(cfg, equity=equity, snapshot=snapshot)
            if cfg.account_type == "margin"
            else _ResolvedLeverageBudget(
                budget=safe_float(
                    snapshot.get("non_marginable_buying_power"),
                    default=settled_cash,
                ),
                active=False,
                feature_enabled=bool(cfg.leverage.enabled and cfg.leverage.mode != "disabled"),
                configured_max=cfg.leverage.capped_live_max_leverage,
                effective_leverage=1.0 if equity > 0 else 0.0,
                target_budget=max(equity * cfg.leverage.capped_live_max_leverage, 0.0),
                broker_buying_power=safe_float(snapshot.get("non_marginable_buying_power"), default=settled_cash),
                buying_power_field="non_marginable_buying_power",
                reason="cash_account",
            )
        )
        buying_power = leverage_state.budget
        if cfg.account_type == "cash":
            buying_power = settled_cash
            leverage_state = _ResolvedLeverageBudget(
                budget=settled_cash,
                active=False,
                feature_enabled=leverage_state.feature_enabled,
                configured_max=leverage_state.configured_max,
                effective_leverage=(settled_cash / equity) if equity > 0 else 0.0,
                target_budget=leverage_state.target_budget,
                broker_buying_power=settled_cash,
                buying_power_field="non_marginable_buying_power",
                reason="cash_account",
            )
        daytrade_count = int(safe_float(snapshot.get("daytrade_count"), default=0.0))

    return _AccountConstraintState(
        account_type=cfg.account_type,
        swing_only=cfg.swing_only,
        equity=equity,
        buying_power_available=max(buying_power, 0.0),
        settled_cash_available=max(settled_cash, 0.0),
        daytrade_count=max(daytrade_count, 0),
        leverage_feature_enabled=leverage_state.feature_enabled,
        leverage_active=leverage_state.active,
        leverage_configured_max=leverage_state.configured_max,
        effective_leverage=leverage_state.effective_leverage,
        leverage_target_budget=max(leverage_state.target_budget, 0.0),
        leverage_broker_buying_power=leverage_state.broker_buying_power,
        leverage_buying_power_field=leverage_state.buying_power_field,
        leverage_reason=leverage_state.reason,
    )


def reserve_account_capacity_for_intent(
    intent: OrderIntent,
    account_state: _AccountConstraintState,
    exec_run_id: str,
    events: list[ExecutionEvent],
    metrics: dict[str, int],
) -> bool:
    if intent.side != "buy":
        return True

    estimated_notional = estimate_intent_notional(intent)
    available_budget = (
        account_state.settled_cash_available
        if account_state.account_type == "cash"
        else account_state.buying_power_available
    )
    if estimated_notional <= available_budget + 1e-9:
        if account_state.account_type == "cash":
            account_state.settled_cash_available = max(
                account_state.settled_cash_available - estimated_notional, 0.0
            )
        account_state.buying_power_available = max(
            account_state.buying_power_available - estimated_notional, 0.0
        )
        return True

    metrics["skipped"] += 1
    metrics["constraint_blocked"] += 1
    events.append(
        make_event(
            exec_run_id,
            EventType.INTENT_SKIPPED_ACCOUNT_CONSTRAINT,
            (
                f"Blocked by account constraints: {intent.symbol} requires ~{estimated_notional:.2f}, "
                f"available={available_budget:.2f} ({account_state.account_type})"
            ),
            symbol=intent.symbol,
            intent_id=intent.intent_id,
            payload={
                "account_type": account_state.account_type,
                "estimated_notional": estimated_notional,
                "available_budget": available_budget,
                "swing_only": account_state.swing_only,
                "daytrade_count": account_state.daytrade_count,
            },
        )
    )
    return False


def should_defer_children(
    account_state: _AccountConstraintState,
) -> tuple[bool, str | None]:
    if account_state.swing_only:
        return True, "swing_only"
    return False, None


__all__ = [
    "_AccountConstraintState",
    "InvalidBrokerSnapshotError",
    "safe_float",
    "estimate_intent_notional",
    "build_account_constraint_state",
    "reserve_account_capacity_for_intent",
    "should_defer_children",
]

