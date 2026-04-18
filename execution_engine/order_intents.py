"""Construction d'OrderIntent — fonctions pures, testables."""
from __future__ import annotations

import hashlib
import uuid

from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionTarget, IntentRole, OrderIntent


def _make_id() -> str:
    return uuid.uuid4().hex[:16]


def _idempotency_key(run_id: str, symbol: str, role: str, side: str, qty: float, broker_mode: str) -> str:
    """Cle stable basee sur risk_run_id — utilise pour la deduplication en base."""
    raw = f"{run_id}|{symbol}|{role}|{side}|{qty}|{broker_mode}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _alpaca_client_order_id(exec_run_id: str, symbol: str, role: str, side: str, qty: float) -> str:
    """
    client_order_id unique par execution run envoye a Alpaca.
    Inclut exec_run_id pour eviter le 403 'client_order_id already in use'
    lors d'une re-soumission apres echec ou relance manuelle.
    NOTE: different de idempotency_key (base sur risk_run_id) pour permettre
    plusieurs execution runs sur le meme portefeuille cible.
    """
    raw = f"{exec_run_id}|{symbol}|{role}|{side}|{qty}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def build_entry_intents(
    targets: list[ExecutionTarget],
    config: ExecutionConfig,
    exec_run_id: str,
) -> list[OrderIntent]:
    intents: list[OrderIntent] = []
    for t in targets:
        if t.target_shares <= 0:
            continue
        qty = float(t.target_shares)
        limit_price: float | None = None
        if config.entry_order_type == "limit":
            limit_price = round(t.entry_price * (1 + config.limit_price_buffer_bps / 10_000), 2)

        intents.append(OrderIntent(
            intent_id=_make_id(),
            risk_run_id=t.risk_run_id,
            exec_run_id=exec_run_id,
            symbol=t.symbol,
            side="buy",
            qty=qty,
            order_type=config.entry_order_type,
            limit_price=limit_price,
            trail_percent=None,
            broker_mode=config.broker_mode,
            parent_intent_id=None,
            intent_role=IntentRole.ENTRY,
            idempotency_key=_idempotency_key(
                t.risk_run_id, t.symbol, IntentRole.ENTRY, "buy", qty, config.broker_mode,
            ),
            decision_price=t.entry_price,
        ))
    return intents


def build_take_profit_intent(
    parent: OrderIntent,
    fill_qty: float,
    avg_fill_price: float,
    config: ExecutionConfig,
) -> OrderIntent:
    limit_price = round(avg_fill_price * (1 + config.profit_taker_pct), 2)
    return OrderIntent(
        intent_id=_make_id(),
        risk_run_id=parent.risk_run_id,
        exec_run_id=parent.exec_run_id,
        symbol=parent.symbol,
        side="sell",
        qty=fill_qty,
        order_type="limit",
        limit_price=limit_price,
        trail_percent=None,
        broker_mode=parent.broker_mode,
        parent_intent_id=parent.intent_id,
        intent_role=IntentRole.TAKE_PROFIT,
        idempotency_key=_idempotency_key(
            parent.exec_run_id, parent.symbol, IntentRole.TAKE_PROFIT,
            "sell", fill_qty, parent.broker_mode,
        ),
        decision_price=parent.decision_price,
    )


def build_trailing_stop_intent(
    parent: OrderIntent,
    fill_qty: float,
    config: ExecutionConfig,
) -> OrderIntent:
    trail_pct = round(config.trailing_stop_pct * 100, 2)
    return OrderIntent(
        intent_id=_make_id(),
        risk_run_id=parent.risk_run_id,
        exec_run_id=parent.exec_run_id,
        symbol=parent.symbol,
        side="sell",
        qty=fill_qty,
        order_type="trailing_stop",
        limit_price=None,
        trail_percent=trail_pct,
        broker_mode=parent.broker_mode,
        parent_intent_id=parent.intent_id,
        intent_role=IntentRole.TRAILING_STOP,
        idempotency_key=_idempotency_key(
            parent.exec_run_id, parent.symbol, IntentRole.TRAILING_STOP,
            "sell", fill_qty, parent.broker_mode,
        ),
        decision_price=parent.decision_price,
    )


def build_rebalance_sell_intent(
    exec_run_id: str,
    risk_run_id: str,
    symbol: str,
    qty: float,
    broker_mode: str,
    current_price: float = 0.0,
) -> OrderIntent:
    """Ordre de vente marche pour liquider un excedent detecte en reconciliation."""
    qty = float(int(qty)) if qty == int(qty) else qty
    return OrderIntent(
        intent_id=_make_id(),
        risk_run_id=risk_run_id,
        exec_run_id=exec_run_id,
        symbol=symbol,
        side="sell",
        qty=qty,
        order_type="market",
        limit_price=None,
        trail_percent=None,
        broker_mode=broker_mode,
        parent_intent_id=None,
        intent_role=IntentRole.EXIT,
        idempotency_key=_idempotency_key(exec_run_id, symbol, IntentRole.EXIT, "sell", qty, broker_mode),
        decision_price=current_price,
    )


def build_rebalance_buy_intent(
    exec_run_id: str,
    risk_run_id: str,
    symbol: str,
    qty: float,
    broker_mode: str,
    current_price: float = 0.0,
) -> OrderIntent:
    """Ordre d'achat marche pour completer une position insuffisante detectee en reconciliation."""
    qty = float(int(qty)) if qty == int(qty) else qty
    return OrderIntent(
        intent_id=_make_id(),
        risk_run_id=risk_run_id,
        exec_run_id=exec_run_id,
        symbol=symbol,
        side="buy",
        qty=qty,
        order_type="market",
        limit_price=None,
        trail_percent=None,
        broker_mode=broker_mode,
        parent_intent_id=None,
        intent_role=IntentRole.REBALANCE_BUY,
        idempotency_key=_idempotency_key(exec_run_id, symbol, IntentRole.REBALANCE_BUY, "buy", qty, broker_mode),
        decision_price=current_price,
    )


def intent_to_alpaca_payload(intent: OrderIntent) -> dict[str, str]:
    """Convertit un OrderIntent en payload dict pour l'API Alpaca Trading v2.
    Utilise _alpaca_client_order_id (base exec_run_id) et non idempotency_key
    pour garantir l'unicite cote Alpaca meme en cas de relance.
    """
    tif = "day" if intent.intent_role in (IntentRole.ENTRY, IntentRole.EXIT, IntentRole.REBALANCE_BUY) else "gtc"
    alpaca_client_id = _alpaca_client_order_id(
        intent.exec_run_id, intent.symbol, intent.intent_role, intent.side, intent.qty
    )
    payload: dict[str, str] = {
        "symbol": intent.symbol,
        "qty": str(int(intent.qty)) if intent.qty == int(intent.qty) else str(intent.qty),
        "side": intent.side,
        "type": intent.order_type,
        "time_in_force": tif,
        "client_order_id": alpaca_client_id,
    }
    if intent.order_type == "limit" and intent.limit_price is not None:
        payload["limit_price"] = str(intent.limit_price)
    if intent.order_type == "trailing_stop" and intent.trail_percent is not None:
        payload["trail_percent"] = str(intent.trail_percent)
    return payload

