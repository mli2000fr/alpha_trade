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


def safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def estimate_intent_notional(intent: OrderIntent) -> float:
    price = intent.limit_price if intent.limit_price is not None else intent.decision_price
    return max(float(intent.qty) * max(float(price), 0.0), 0.0)


def build_account_constraint_state(
    cfg: "ExecutionConfig", broker: "BrokerAdapter"
) -> _AccountConstraintState:
    if cfg.dry_run:
        equity = float(cfg.simulated_account_equity)
        settled_cash = equity
        buying_power = (
            equity * cfg.simulated_margin_buying_power_multiplier
            if cfg.account_type == "margin"
            else settled_cash
        )
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
        buying_power = safe_float(
            snapshot.get("buying_power")
            if cfg.account_type == "margin"
            else snapshot.get("non_marginable_buying_power"),
            default=settled_cash if cfg.account_type == "cash" else equity,
        )
        if cfg.account_type == "cash":
            buying_power = settled_cash
        daytrade_count = int(safe_float(snapshot.get("daytrade_count"), default=0.0))

    return _AccountConstraintState(
        account_type=cfg.account_type,
        swing_only=cfg.swing_only,
        equity=equity,
        buying_power_available=max(buying_power, 0.0),
        settled_cash_available=max(settled_cash, 0.0),
        daytrade_count=max(daytrade_count, 0),
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

