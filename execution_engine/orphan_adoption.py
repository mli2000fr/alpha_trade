"""Adoption d'ordres / positions orphelins dans le journal canonique.

Un *ordre orphelin* est un ordre / fill broker qui n'a aucun ``OrderIntent``
parent en base ``execution_order_requests`` — typiquement :

* une vente déclenchée depuis le site / app Alpaca (ou le bouton "Vendre tout"
  de la page Compte Alpaca),
* un achat manuel passé hors Alpha Trade.

Sans adoption, ces actions cassent l'audit trail canonique (Q5 / Q6 / Q8 du
FAQ opérateur). Ce module crée à la volée des ``OrderIntent`` synthétiques
marqués ``intent_role`` ``adopted_entry`` / ``adopted_exit`` et émet un
événement ``ORPHAN_ADOPTED`` afin que la généalogie reste auditable.

Idempotence : la clé ``business_key`` (``idempotency_key``) est dérivée de
``account_id + broker_order_id`` (ou ``symbol`` pour une position pure), de
sorte qu'une seconde adoption ne crée pas de doublon (les UPSERT
``execution_order_requests`` / ``execution_broker_orders`` détectent l'unicité
via ``request_id`` / ``broker_order_id``).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from execution_engine.audit import event_to_db_dict, make_event
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import (
    BrokerOrder,
    EventType,
    ExecutionFill,
    IntentRole,
    OrderIntent,
    OrderStatus,
)
from execution_engine.tca import compute_implementation_shortfall, compute_slippage_bps

LOGGER = logging.getLogger(__name__)

# Préfixe stable pour repérer un exec_run_id "synthétique" créé pour une
# adoption (pas de run d'exécution réel à rattacher).
ADOPTION_RUN_PREFIX = "adopt"


@dataclass(frozen=True, slots=True)
class AdoptionResult:
    """Résultat d'une adoption d'ordre orphelin."""
    intent: OrderIntent
    broker_order: BrokerOrder
    fill: ExecutionFill | None
    trigger: str  # "manual_sell" | "manual_buy" | "watcher_orphan_buy"


def _stable_id(seed: str, length: int = 16) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:length]


def _ensure_adoption_run(
    repo: ExecutionRepository,
    *,
    account_id: str,
    broker_mode: str,
    trade_date,
) -> str:
    """Garantit qu'un ``execution_runs`` existe pour rattacher l'adoption.

    Best-effort : si la table est indisponible ou l'insert échoue, on retourne
    quand même un identifiant synthétique. Les FK ``execution_order_requests
    -> execution_runs`` ne sont pas strictes côté SQLite (les tests s'y
    appuient), et côté MySQL l'insertion réussit dans la pratique.
    """
    if isinstance(trade_date, datetime):
        trade_date = trade_date.date()
    seed = f"{ADOPTION_RUN_PREFIX}|{account_id}|{trade_date.isoformat()}"
    exec_run_id = f"{ADOPTION_RUN_PREFIX}-{_stable_id(seed, 12)}"
    try:
        repo.insert_execution_run(
            exec_run_id=exec_run_id,
            risk_run_id=exec_run_id,
            trade_date=trade_date,
            broker_mode=broker_mode,
            dry_run=False,
            total_targets=0,
            account_id=account_id,
            execution_profile="custom",
            submission_window=None,
        )
    except Exception:
        # déjà créé OU table absente — non bloquant pour l'adoption.
        LOGGER.debug("insert_execution_run adoption ignoré pour %s", exec_run_id, exc_info=True)
    return exec_run_id


def _build_synthetic_intent(
    *,
    exec_run_id: str,
    symbol: str,
    side: str,
    qty: float,
    order_type: str,
    broker_mode: str,
    decision_price: float,
    role: str,
    business_key: str,
    submission_key: str | None,
    limit_price: float | None = None,
    stop_price: float | None = None,
) -> OrderIntent:
    return OrderIntent(
        intent_id=_stable_id(business_key, 16),
        risk_run_id=exec_run_id,
        exec_run_id=exec_run_id,
        symbol=symbol,
        side=side,
        qty=qty,
        order_type=order_type,
        limit_price=limit_price,
        trail_percent=None,
        broker_mode=broker_mode,
        parent_intent_id=None,
        intent_role=role,
        idempotency_key=business_key,
        decision_price=decision_price,
        stop_price=stop_price,
        submission_key=submission_key,
    )


def _build_broker_order_from_payload(
    *,
    intent: OrderIntent,
    broker_order_id: str,
    client_order_id: str | None,
    raw_order: dict[str, Any] | None,
    qty: float,
    filled_qty: float,
    avg_fill_price: float | None,
    status: str,
) -> BrokerOrder:
    def _ts(val: Any) -> datetime | None:
        if not val:
            return None
        if isinstance(val, datetime):
            return val
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except Exception:
            return None

    created_at = updated_at = datetime.now(timezone.utc)
    if raw_order:
        created_at = _ts(raw_order.get("submitted_at") or raw_order.get("created_at")) or created_at
        updated_at = _ts(raw_order.get("updated_at") or raw_order.get("filled_at")) or updated_at

    return BrokerOrder(
        broker_order_id=broker_order_id,
        client_order_id=client_order_id or intent.submission_key or intent.idempotency_key,
        intent_id=intent.intent_id,
        symbol=intent.symbol,
        side=intent.side,
        qty=qty,
        filled_qty=filled_qty,
        avg_fill_price=avg_fill_price,
        status=status,
        order_type=intent.order_type,
        limit_price=intent.limit_price,
        stop_price=intent.stop_price,
        trail_percent=None,
        created_at=created_at,
        updated_at=updated_at,
    )


def _persist_event(repo: ExecutionRepository, event) -> None:
    try:
        repo.insert_execution_event(event_to_db_dict(event))
    except Exception:
        LOGGER.debug("Persistance event ORPHAN_ADOPTED impossible", exc_info=True)


def _normalize_status(raw_status: str | None) -> str:
    if not raw_status:
        return OrderStatus.FILLED
    raw = str(raw_status).strip().lower()
    mapping = {
        "filled": OrderStatus.FILLED,
        "partially_filled": OrderStatus.PARTIALLY_FILLED,
        "canceled": OrderStatus.CANCELED,
        "cancelled": OrderStatus.CANCELED,
        "rejected": OrderStatus.REJECTED,
        "expired": OrderStatus.EXPIRED,
        "new": OrderStatus.NEW,
        "accepted": OrderStatus.SUBMITTED,
        "pending_new": OrderStatus.SUBMITTED,
    }
    return mapping.get(raw, OrderStatus.FILLED)


def adopt_orphan_sell(
    repo: ExecutionRepository,
    *,
    broker_mode: str,
    account_id: str,
    raw_order: dict[str, Any],
    trade_date=None,
) -> AdoptionResult | None:
    """Adopte un ordre de vente passé hors Alpha Trade.

    ``raw_order`` est le payload broker tel que renvoyé par Alpaca
    (clés ``id``, ``client_order_id``, ``symbol``, ``qty``, ``filled_qty``,
    ``filled_avg_price``, ``status``, ``submitted_at``, ...).
    """
    broker_order_id = str(raw_order.get("id") or "").strip()
    symbol = str(raw_order.get("symbol") or "").strip().upper()
    if not broker_order_id or not symbol:
        LOGGER.warning("adopt_orphan_sell: payload sans broker_order_id ou symbol")
        return None

    qty = float(raw_order.get("qty") or raw_order.get("filled_qty") or 0.0)
    filled_qty = float(raw_order.get("filled_qty") or qty)
    if filled_qty <= 0:
        LOGGER.debug("adopt_orphan_sell: filled_qty <= 0 pour %s, on saute", symbol)
        return None
    avg_fill_price_raw = raw_order.get("filled_avg_price") or raw_order.get("avg_fill_price")
    avg_fill_price = float(avg_fill_price_raw) if avg_fill_price_raw not in (None, "", 0) else 0.0
    decision_price = avg_fill_price or float(raw_order.get("limit_price") or 0.0)
    status = _normalize_status(raw_order.get("status"))
    client_order_id = str(raw_order.get("client_order_id") or "").strip() or None

    if trade_date is None:
        ts = raw_order.get("filled_at") or raw_order.get("submitted_at") or raw_order.get("created_at")
        try:
            trade_date = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date() if ts else datetime.now(timezone.utc).date()
        except Exception:
            trade_date = datetime.now(timezone.utc).date()

    exec_run_id = _ensure_adoption_run(
        repo, account_id=account_id, broker_mode=broker_mode, trade_date=trade_date,
    )
    business_key = f"adopt-sell|{account_id}|{broker_order_id}"
    intent = _build_synthetic_intent(
        exec_run_id=exec_run_id,
        symbol=symbol,
        side="sell",
        qty=qty or filled_qty,
        order_type=str(raw_order.get("type") or "market"),
        broker_mode=broker_mode,
        decision_price=decision_price,
        role=IntentRole.ADOPTED_EXIT,
        business_key=business_key,
        submission_key=client_order_id or _stable_id(business_key, 32),
    )

    broker_order = _build_broker_order_from_payload(
        intent=intent,
        broker_order_id=broker_order_id,
        client_order_id=client_order_id,
        raw_order=raw_order,
        qty=intent.qty,
        filled_qty=filled_qty,
        avg_fill_price=avg_fill_price or None,
        status=status,
    )

    repo.upsert_execution_order_request_from_intent(intent, account_id=account_id, status=status)
    repo.upsert_execution_broker_order(intent, broker_order, account_id=account_id, raw_response=raw_order)

    fill: ExecutionFill | None = None
    if filled_qty > 0 and avg_fill_price > 0:
        fill_seed = f"adopt-sell-fill|{broker_order_id}|{filled_qty:.8f}|{avg_fill_price:.6f}"
        fill = ExecutionFill(
            fill_id=_stable_id(fill_seed, 32),
            broker_order_id=broker_order_id,
            intent_id=intent.intent_id,
            symbol=symbol,
            filled_qty=filled_qty,
            avg_fill_price=avg_fill_price,
            fill_timestamp=broker_order.updated_at or datetime.now(timezone.utc),
            decision_price=decision_price or avg_fill_price,
            slippage_bps=compute_slippage_bps(avg_fill_price, decision_price or avg_fill_price),
            implementation_shortfall=compute_implementation_shortfall(
                avg_fill_price, decision_price or avg_fill_price, filled_qty,
            ),
        )
        try:
            repo.insert_execution_broker_fill(fill, account_id=account_id, raw_fill=raw_order)
        except Exception:
            LOGGER.debug("insert_execution_broker_fill orphan sell ignoré pour %s", symbol, exc_info=True)

    _persist_event(repo, make_event(
        exec_run_id,
        EventType.ORPHAN_ADOPTED,
        f"Vente manuelle adoptée pour {symbol} (qty={filled_qty})",
        symbol=symbol,
        broker_order_id=broker_order_id,
        intent_id=intent.intent_id,
        payload={
            "trigger": "manual_sell",
            "source": "adopted_orphan",
            "client_order_id": client_order_id,
            "filled_qty": filled_qty,
            "avg_fill_price": avg_fill_price,
            "raw_status": raw_order.get("status"),
        },
    ))
    return AdoptionResult(intent=intent, broker_order=broker_order, fill=fill, trigger="manual_sell")


def adopt_orphan_buy(
    repo: ExecutionRepository,
    *,
    broker_mode: str,
    account_id: str,
    raw_order: dict[str, Any] | None = None,
    broker_position: dict[str, Any] | None = None,
    trade_date=None,
) -> AdoptionResult | None:
    """Adopte un achat manuel orphelin (depuis ``raw_order`` ou ``broker_position``).

    - Si ``raw_order`` est fourni : crée un parent ``adopted_entry`` rattaché
      au broker_order_id réel + insère le fill.
    - Si seulement ``broker_position`` est fourni (cas watcher) : crée un
      parent ``adopted_entry`` rattaché à un broker_order_id synthétique
      ``adopt-pos-<sha>`` + insère un fill agrégé reflétant la position.

    Retourne l'``AdoptionResult`` ; l'``OrderIntent`` parent peut servir de
    base à la fabrication des enfants TP / SL par le watcher.
    """
    if raw_order is None and broker_position is None:
        return None

    if raw_order is not None:
        broker_order_id = str(raw_order.get("id") or "").strip()
        symbol = str(raw_order.get("symbol") or "").strip().upper()
        qty = float(raw_order.get("qty") or raw_order.get("filled_qty") or 0.0)
        filled_qty = float(raw_order.get("filled_qty") or qty)
        avg_fill_price_raw = raw_order.get("filled_avg_price") or raw_order.get("avg_fill_price")
        avg_fill_price = float(avg_fill_price_raw) if avg_fill_price_raw not in (None, "", 0) else 0.0
        status = _normalize_status(raw_order.get("status"))
        client_order_id = str(raw_order.get("client_order_id") or "").strip() or None
        order_type = str(raw_order.get("type") or "market")
    else:
        assert broker_position is not None  # for type checker
        symbol = str(broker_position.get("symbol") or "").strip().upper()
        filled_qty = float(broker_position.get("qty") or 0.0)
        qty = filled_qty
        avg_fill_price = float(broker_position.get("avg_entry_price") or broker_position.get("avg_price") or 0.0)
        status = OrderStatus.FILLED
        client_order_id = None
        order_type = "market"
        # broker_order_id synthétique stable par symbol/account
        broker_order_id = f"adopt-pos-{_stable_id(f'{account_id}|{symbol}', 24)}"

    if not symbol or filled_qty <= 0 or avg_fill_price <= 0:
        LOGGER.debug("adopt_orphan_buy: payload incomplet (symbol=%s, qty=%s, price=%s)",
                     symbol, filled_qty, avg_fill_price)
        return None

    if trade_date is None:
        trade_date = datetime.now(timezone.utc).date()

    exec_run_id = _ensure_adoption_run(
        repo, account_id=account_id, broker_mode=broker_mode, trade_date=trade_date,
    )
    business_key = f"adopt-buy|{account_id}|{broker_order_id}"
    intent = _build_synthetic_intent(
        exec_run_id=exec_run_id,
        symbol=symbol,
        side="buy",
        qty=qty or filled_qty,
        order_type=order_type,
        broker_mode=broker_mode,
        decision_price=avg_fill_price,
        role=IntentRole.ADOPTED_ENTRY,
        business_key=business_key,
        submission_key=client_order_id or _stable_id(business_key, 32),
    )

    broker_order = _build_broker_order_from_payload(
        intent=intent,
        broker_order_id=broker_order_id,
        client_order_id=client_order_id,
        raw_order=raw_order,
        qty=intent.qty,
        filled_qty=filled_qty,
        avg_fill_price=avg_fill_price,
        status=status,
    )

    repo.upsert_execution_order_request_from_intent(intent, account_id=account_id, status=status)
    repo.upsert_execution_broker_order(intent, broker_order, account_id=account_id, raw_response=raw_order)

    fill_seed = f"adopt-buy-fill|{broker_order_id}|{filled_qty:.8f}|{avg_fill_price:.6f}"
    fill = ExecutionFill(
        fill_id=_stable_id(fill_seed, 32),
        broker_order_id=broker_order_id,
        intent_id=intent.intent_id,
        symbol=symbol,
        filled_qty=filled_qty,
        avg_fill_price=avg_fill_price,
        fill_timestamp=broker_order.updated_at or datetime.now(timezone.utc),
        decision_price=avg_fill_price,
        slippage_bps=0.0,
        implementation_shortfall=0.0,
    )
    try:
        repo.insert_execution_broker_fill(fill, account_id=account_id, raw_fill=raw_order)
    except Exception:
        LOGGER.debug("insert_execution_broker_fill orphan buy ignoré pour %s", symbol, exc_info=True)

    trigger = "manual_buy" if raw_order is not None else "watcher_orphan_buy"
    _persist_event(repo, make_event(
        exec_run_id,
        EventType.ORPHAN_ADOPTED,
        f"Achat manuel adopté pour {symbol} (qty={filled_qty}, prix={avg_fill_price:.2f})",
        symbol=symbol,
        broker_order_id=broker_order_id,
        intent_id=intent.intent_id,
        payload={
            "trigger": trigger,
            "source": "adopted_orphan",
            "client_order_id": client_order_id,
            "filled_qty": filled_qty,
            "avg_fill_price": avg_fill_price,
        },
    ))
    return AdoptionResult(intent=intent, broker_order=broker_order, fill=fill, trigger=trigger)


__all__ = [
    "AdoptionResult",
    "adopt_orphan_sell",
    "adopt_orphan_buy",
]


