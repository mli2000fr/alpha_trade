"""Modèles de données du module execution_engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Constantes d'état
# ---------------------------------------------------------------------------

class OrderStatus:
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    TERMINAL = frozenset({FILLED, CANCELED, REJECTED, FAILED, EXPIRED})


class EventType:
    RUN_STARTED = "RUN_STARTED"
    RUN_LOCKED = "RUN_LOCKED"
    PRECHECK_OK = "PRECHECK_OK"
    PRECHECK_FAILED = "PRECHECK_FAILED"
    ACCOUNT_CONSTRAINT_APPLIED = "ACCOUNT_CONSTRAINT_APPLIED"
    CIRCUIT_BREAKER_ACTIVE = "CIRCUIT_BREAKER_ACTIVE"
    INTENT_BUILT = "INTENT_BUILT"
    INTENT_SKIPPED_DUPLICATE = "INTENT_SKIPPED_DUPLICATE"
    INTENT_SKIPPED_ACCOUNT_CONSTRAINT = "INTENT_SKIPPED_ACCOUNT_CONSTRAINT"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELED = "ORDER_CANCELED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_TIMEOUT = "ORDER_TIMEOUT"
    CHILDREN_SUBMITTED = "CHILDREN_SUBMITTED"
    CHILDREN_DEFERRED_ACCOUNT_CONSTRAINT = "CHILDREN_DEFERRED_ACCOUNT_CONSTRAINT"
    PROTECTION_TRIGGER_HIT = "PROTECTION_TRIGGER_HIT"
    PROTECTION_TRANSITION_COMPLETED = "PROTECTION_TRANSITION_COMPLETED"
    PROTECTION_TRANSITION_FAILED = "PROTECTION_TRANSITION_FAILED"
    OCO_CANCEL_TRIGGERED = "OCO_CANCEL_TRIGGERED"
    SLIPPAGE_ALERT = "SLIPPAGE_ALERT"
    RECONCILE_OK = "RECONCILE_OK"
    RECONCILE_DIFF = "RECONCILE_DIFF"
    KILL_SWITCH_ACTIVATED = "KILL_SWITCH_ACTIVATED"
    THROTTLE_WAIT = "THROTTLE_WAIT"
    TCA_SUMMARY = "TCA_SUMMARY"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    DRY_RUN_SIMULATED = "DRY_RUN_SIMULATED"


class IntentRole:
    ENTRY = "entry"
    TAKE_PROFIT = "take_profit"
    INITIAL_STOP = "initial_stop"
    TRAILING_STOP = "trailing_stop"
    EXIT = "exit"                    # vente de liquidation / reconciliation
    REBALANCE_BUY = "rebalance_buy"  # achat de reequilibrage / reconciliation


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ExecutionTarget:
    """Cible d'exécution lue depuis portfolio_targets."""
    risk_run_id: str
    trade_date: date
    symbol: str
    target_shares: int
    entry_price: float
    target_weight: float
    sector: str | None
    conviction_score: float | None
    sizing_method: str | None
    kelly_fraction: float | None
    decision_rank: int | None = None
    side: str | None = None
    atr_20: float | None = None
    price_asof_date: date | None = None
    atr_asof_date: date | None = None
    stop_price_initial: float | None = None
    risk_per_share: float | None = None
    risk_budget_dollars: float | None = None
    initial_risk_dollars: float | None = None
    target_notional: float | None = None


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """Intention d'ordre avant soumission broker."""
    intent_id: str
    risk_run_id: str
    exec_run_id: str
    symbol: str
    side: str
    qty: float
    order_type: str
    limit_price: float | None
    trail_percent: float | None
    broker_mode: str
    parent_intent_id: str | None
    intent_role: str
    idempotency_key: str
    decision_price: float
    stop_price: float | None = None


@dataclass(frozen=True, slots=True)
class BrokerOrder:
    """Représentation locale d'un ordre soumis au broker."""
    broker_order_id: str
    client_order_id: str
    intent_id: str
    symbol: str
    side: str
    qty: float
    filled_qty: float
    avg_fill_price: float | None
    status: str
    order_type: str
    limit_price: float | None
    stop_price: float | None
    trail_percent: float | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class ExecutionFill:
    """Fill individuel reçu du broker."""
    fill_id: str
    broker_order_id: str
    intent_id: str
    symbol: str
    filled_qty: float
    avg_fill_price: float
    fill_timestamp: datetime
    decision_price: float
    slippage_bps: float
    implementation_shortfall: float


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """Événement auditable du lifecycle."""
    event_id: str
    exec_run_id: str
    symbol: str | None
    event_type: str
    message: str
    broker_order_id: str | None = None
    intent_id: str | None = None
    payload_json: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReconcileDiff:
    """Différence positions broker vs cibles."""
    symbol: str
    target_qty: int
    broker_qty: float
    delta: float
    action: str


@dataclass(frozen=True, slots=True)
class TcaSummary:
    """Résumé TCA pour un run complet."""
    total_orders: int
    total_filled: int
    total_notional: float
    avg_slippage_bps: float
    max_slippage_bps: float
    total_implementation_shortfall: float
    slippage_alerts: int


@dataclass(frozen=True, slots=True)
class ProtectionWatchItem:
    """Contexte minimal relu depuis la DB pour surveiller une transition post-run."""
    source_exec_run_id: str
    risk_run_id: str
    trade_date: date
    account_id: str | None
    broker_mode: str
    symbol: str
    parent_intent_id: str
    initial_stop_intent_id: str
    initial_stop_broker_order_id: str
    fill_qty: float
    fill_price: float
    stop_price_initial: float | None = None
    risk_per_share: float | None = None
    initial_risk_dollars: float | None = None
    target_notional: float | None = None


