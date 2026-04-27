"""Modèles de données du module execution_engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Constantes d'état
# ---------------------------------------------------------------------------

class OrderStatus:
    NEW = "NEW"
    SIMULATED = "SIMULATED"
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
    # Phase 5.2.c — kill switch global déclenché par opérateur (sous-commande
    # ``python -m execution_engine cancel-all``). Distinct du kill switch
    # interne ``KILL_SWITCH_ACTIVATED`` qui se déclenche sur échecs consécutifs.
    KILL_SWITCH_TRIGGERED = "KILL_SWITCH_TRIGGERED"
    THROTTLE_WAIT = "THROTTLE_WAIT"
    TCA_SUMMARY = "TCA_SUMMARY"
    BROKER_SYNC_COMPLETED = "BROKER_SYNC_COMPLETED"
    BROKER_SYNC_FAILED = "BROKER_SYNC_FAILED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    DRY_RUN_SIMULATED = "DRY_RUN_SIMULATED"


class ReconciliationStatus:
    SAFE_AUTO = "SAFE_AUTO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCKED = "BLOCKED"


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
    submission_key: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionOrderRequest:
    """Décision d'ordre interne historisée côté OMS."""
    request_id: str
    exec_run_id: str
    account_id: str
    risk_run_id: str
    symbol: str
    side: str
    target_qty: float
    order_type: str
    business_key: str
    submission_key: str | None
    attempt_no: int
    intent_role: str
    decision_price: float
    parent_request_id: str | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    trail_percent: float | None = None
    status: str = OrderStatus.NEW
    failure_reason: str | None = None


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
class BrokerOrderObservation:
    """Observation persistée d'un ordre broker pour une request OMS."""
    request_id: str
    exec_run_id: str
    account_id: str
    broker_order_id: str | None
    client_order_id: str | None
    symbol: str
    side: str
    qty: float
    filled_qty: float
    avg_fill_price: float | None
    raw_status: str
    normalized_status: str
    order_type: str
    limit_price: float | None = None
    stop_price: float | None = None
    trail_percent: float | None = None
    raw_payload_json: str | None = None
    raw_response_json: str | None = None
    submitted_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class BrokerAccountSnapshot:
    """Snapshot broker de compte pour audit capacité et cash."""
    exec_run_id: str
    account_id: str
    broker_mode: str
    snapshot_kind: str
    equity: float
    cash: float
    settled_cash: float
    buying_power: float
    daytrade_count: int
    raw_payload_json: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExecutionPosition:
    """Projection courante de la position nette broker par compte / symbole."""
    account_id: str
    symbol: str
    net_qty: float
    avg_entry_price: float | None = None
    market_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    broker_mode: str | None = None
    source_exec_run_id: str | None = None
    position_status: str = "OPEN"
    last_broker_snapshot_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExecutionPositionLot:
    """Lot ouvert/fermé reconstruit depuis les fills observés."""
    lot_id: str
    account_id: str
    symbol: str
    opened_qty: float
    remaining_qty: float
    entry_price: float
    opened_at: datetime
    open_exec_run_id: str | None = None
    open_request_id: str | None = None
    open_fill_id: str | None = None
    lot_status: str = "OPEN"
    close_exec_run_id: str | None = None
    close_request_id: str | None = None
    close_fill_id: str | None = None
    closed_at: datetime | None = None
    exit_price: float | None = None
    source_kind: str = "execution_broker_fill"


@dataclass(frozen=True, slots=True)
class ExecutionReconciliationResult:
    """Résultat analytique et actionnable de réconciliation par symbole."""
    exec_run_id: str
    account_id: str
    symbol: str
    target_qty: float
    internal_position_qty: float
    broker_position_qty: float
    position_delta: float
    open_request_buy_qty: float = 0.0
    open_request_sell_qty: float = 0.0
    open_broker_buy_qty: float = 0.0
    open_broker_sell_qty: float = 0.0
    has_open_protection: bool = False
    protection_qty: float = 0.0
    action: str = "none"
    reconciliation_status: str = ReconciliationStatus.SAFE_AUTO
    reason_code: str | None = None
    created_at: datetime | None = None


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


