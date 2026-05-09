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


def _submission_key(exec_run_id: str, symbol: str, role: str, side: str, qty: float, unique_id: str | None = None) -> str:
    """
    client_order_id unique par execution run envoyé à Alpaca.
    Inclut exec_run_id pour éviter le 403 'client_order_id already in use'.
    Ajoute un composant unique (intent_id) pour garantir l'unicité même si on repose un stop identique après annulation.
    Si unique_id n'est pas fourni, le hash reste identique à l'ancien comportement.
    """
    if unique_id is not None:
        raw = f"{exec_run_id}|{symbol}|{role}|{side}|{qty}|{unique_id}"
    else:
        raw = f"{exec_run_id}|{symbol}|{role}|{side}|{qty}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _alpaca_client_order_id(exec_run_id: str, symbol: str, role: str, side: str, qty: float) -> str:
    return _submission_key(exec_run_id, symbol, role, side, qty)


def resolve_initial_stop_price(reference_price: float, target: ExecutionTarget | None = None) -> float | None:
    """Détermine un stop initial broker-side exploitable à partir des champs risque."""
    if target is None or reference_price <= 0:
        return None

    if target.stop_price_initial is not None and 0 < target.stop_price_initial < reference_price:
        return round(float(target.stop_price_initial), 2)

    if target.risk_per_share is not None and target.risk_per_share > 0:
        derived_stop = reference_price - float(target.risk_per_share)
        if 0 < derived_stop < reference_price:
            return round(derived_stop, 2)
    return None


def resolve_trailing_activation_price(
    fill_price: float,
    config: ExecutionConfig,
    target: ExecutionTarget | None = None,
) -> tuple[float | None, str | None]:
    """Détermine le prix auquel le stop initial doit être promu en trailing dynamique."""
    if fill_price <= 0:
        return None, None

    if config.trailing_activation_trigger == "multiple_r":
        if target is not None and target.risk_per_share is not None and target.risk_per_share > 0:
            return round(fill_price + (float(target.risk_per_share) * config.trailing_activation_r_multiple), 2), "multiple_r"
        return round(fill_price * (1 + config.trailing_activation_profit_pct), 2), "profit_pct_fallback"

    return round(fill_price * (1 + config.trailing_activation_profit_pct), 2), "profit_pct"


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

        intent_id = _make_id()
        intents.append(OrderIntent(
            intent_id=intent_id,
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
            stop_price=None,
            submission_key=_submission_key(exec_run_id, t.symbol, IntentRole.ENTRY, "buy", qty, intent_id),
        ))
    return intents


def build_take_profit_intent(
    parent: OrderIntent,
    fill_qty: float,
    avg_fill_price: float,
    config: ExecutionConfig,
    target: ExecutionTarget | None = None,
) -> OrderIntent:
    percent_target = avg_fill_price * (1 + config.profit_taker_pct)
    risk_based_target = None
    if target is not None and target.risk_per_share is not None and target.risk_per_share > 0:
        risk_based_target = avg_fill_price + (2.0 * target.risk_per_share)
    limit_price = round(max(percent_target, risk_based_target or percent_target), 2)
    intent_id = _make_id()
    return OrderIntent(
        intent_id=intent_id,
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
        stop_price=None,
        submission_key=_submission_key(parent.exec_run_id, parent.symbol, IntentRole.TAKE_PROFIT, "sell", fill_qty, intent_id),
    )


def build_initial_stop_intent(
    parent: OrderIntent,
    fill_qty: float,
    avg_fill_price: float,
    config: ExecutionConfig,
    target: ExecutionTarget | None = None,
) -> OrderIntent | None:
    reference_price = avg_fill_price or parent.decision_price
    stop_price = resolve_initial_stop_price(reference_price, target)
    if stop_price is None:
        return None

    intent_id = _make_id()
    return OrderIntent(
        intent_id=intent_id,
        risk_run_id=parent.risk_run_id,
        exec_run_id=parent.exec_run_id,
        symbol=parent.symbol,
        side="sell",
        qty=fill_qty,
        order_type="stop",
        limit_price=None,
        trail_percent=None,
        broker_mode=parent.broker_mode,
        parent_intent_id=parent.intent_id,
        intent_role=IntentRole.INITIAL_STOP,
        idempotency_key=_idempotency_key(
            parent.exec_run_id, parent.symbol, IntentRole.INITIAL_STOP,
            "sell", fill_qty, parent.broker_mode,
        ),
        decision_price=parent.decision_price,
        stop_price=stop_price,
        submission_key=_submission_key(parent.exec_run_id, parent.symbol, IntentRole.INITIAL_STOP, "sell", fill_qty, intent_id),
    )


def build_manual_buy_initial_stop_intent(
    parent: OrderIntent,
    fill_qty: float,
    avg_fill_price: float,
    config: ExecutionConfig,
) -> OrderIntent | None:
    """Construit un STOP `sell` pour un achat manuel orphelin adopté.

    Contrairement à ``build_initial_stop_intent``, ce helper ne dépend pas
    d'un ``ExecutionTarget`` (pas d'ATR / risk_per_share disponible pour un
    achat passé hors Alpha Trade). Il applique simplement le pourcentage
    ``config.manual_buy_stop_loss_pct`` sous le prix d'entrée moyen.
    """
    reference_price = avg_fill_price or parent.decision_price
    if reference_price <= 0 or fill_qty <= 0:
        return None
    stop_price = round(reference_price * (1.0 - float(config.manual_buy_stop_loss_pct)), 2)
    if stop_price <= 0 or stop_price >= reference_price:
        return None

    intent_id = _make_id()
    return OrderIntent(
        intent_id=intent_id,
        risk_run_id=parent.risk_run_id,
        exec_run_id=parent.exec_run_id,
        symbol=parent.symbol,
        side="sell",
        qty=fill_qty,
        order_type="stop",
        limit_price=None,
        trail_percent=None,
        broker_mode=parent.broker_mode,
        parent_intent_id=parent.intent_id,
        intent_role=IntentRole.INITIAL_STOP,
        idempotency_key=_idempotency_key(
            parent.exec_run_id, parent.symbol, IntentRole.INITIAL_STOP,
            "sell", fill_qty, parent.broker_mode,
        ),
        decision_price=parent.decision_price,
        stop_price=stop_price,
        submission_key=_submission_key(parent.exec_run_id, parent.symbol, IntentRole.INITIAL_STOP, "sell", fill_qty, intent_id),
    )


def build_trailing_stop_intent(
    parent: OrderIntent,
    fill_qty: float,
    avg_fill_price: float,
    config: ExecutionConfig,
    target: ExecutionTarget | None = None,
) -> OrderIntent:
    reference_price = avg_fill_price or parent.decision_price
    risk_based_trail_pct = None
    if target is not None:
        if target.stop_price_initial is not None and reference_price > 0 and target.stop_price_initial < reference_price:
            risk_based_trail_pct = (reference_price - target.stop_price_initial) / reference_price
        elif target.risk_per_share is not None and target.risk_per_share > 0 and reference_price > 0:
            risk_based_trail_pct = target.risk_per_share / reference_price
    trail_pct = round((risk_based_trail_pct if risk_based_trail_pct is not None else config.trailing_stop_pct) * 100, 2)
    intent_id = _make_id()
    return OrderIntent(
        intent_id=intent_id,
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
        stop_price=None,
        submission_key=_submission_key(parent.exec_run_id, parent.symbol, IntentRole.TRAILING_STOP, "sell", fill_qty, intent_id),
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
    intent_id = _make_id()
    return OrderIntent(
        intent_id=intent_id,
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
        stop_price=None,
        submission_key=_submission_key(exec_run_id, symbol, IntentRole.EXIT, "sell", qty, intent_id),
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
    intent_id = _make_id()
    return OrderIntent(
        intent_id=intent_id,
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
        stop_price=None,
        submission_key=_submission_key(exec_run_id, symbol, IntentRole.REBALANCE_BUY, "buy", qty, intent_id),
    )


def intent_to_alpaca_payload(intent: OrderIntent) -> dict[str, str]:
    """Convertit un OrderIntent en payload dict pour l'API Alpaca Trading v2.
    Utilise _alpaca_client_order_id (base exec_run_id) et non idempotency_key
    pour garantir l'unicite cote Alpaca meme en cas de relance.
    """
    tif = "day" if intent.intent_role in (IntentRole.ENTRY, IntentRole.EXIT, IntentRole.REBALANCE_BUY) else "gtc"
    alpaca_client_id = intent.submission_key or _alpaca_client_order_id(
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
    if intent.order_type == "stop" and intent.stop_price is not None:
        payload["stop_price"] = str(intent.stop_price)
    if intent.order_type == "trailing_stop" and intent.trail_percent is not None:
        payload["trail_percent"] = str(intent.trail_percent)
    return payload


def build_oco_protection_payload(
    parent: OrderIntent,
    tp_intent: OrderIntent,
    stop_intent: OrderIntent,
    oco_id: str | None = None,
) -> dict[str, str | dict[str, str]]:
    """Construit un payload Alpaca OCO (TP limit + SL stop) lié à une position.

    Pose les deux protections de manière atomique côté broker : si l'une est
    exécutée, l'autre est annulée automatiquement. Évite l'erreur 403
    "insufficient qty" obtenue lors d'une soumission séquentielle de TP puis
    SL sur la même position (les deux essayaient de réserver la même qty).
    """
    if tp_intent.limit_price is None:
        raise ValueError("OCO take_profit requires limit_price on tp_intent")
    if stop_intent.stop_price is None:
        raise ValueError("OCO stop_loss requires stop_price on stop_intent")

    qty = tp_intent.qty if tp_intent.qty == stop_intent.qty else min(tp_intent.qty, stop_intent.qty)
    qty_str = str(int(qty)) if qty == int(qty) else str(qty)

    # Génération ou utilisation d'un identifiant unique pour l'OCO
    if oco_id is None:
        oco_id = _make_id()
    # client_order_id stable et unique par exec_run_id + symbol + oco_id pour idempotence et traçabilité
    client_order_id = f"oco-{_alpaca_client_order_id(parent.exec_run_id, parent.symbol, 'oco_protection', 'sell', qty)}-{oco_id}"

    take_profit: dict[str, str] = {"limit_price": str(tp_intent.limit_price)}
    stop_loss: dict[str, str] = {"stop_price": str(stop_intent.stop_price)}
    if stop_intent.limit_price is not None:
        stop_loss["limit_price"] = str(stop_intent.limit_price)

    payload: dict[str, str | dict[str, str]] = {
        "symbol": parent.symbol,
        "qty": qty_str,
        "side": "sell",
        "type": "limit",
        "time_in_force": "gtc",
        "order_class": "oco",
        "client_order_id": client_order_id,
        "limit_price": str(tp_intent.limit_price),
        "take_profit": take_profit,
        "stop_loss": stop_loss,
    }
    return payload


