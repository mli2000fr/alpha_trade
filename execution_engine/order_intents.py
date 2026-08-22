"""Construction d'OrderIntent — fonctions pures, testables."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import is_dataclass, replace
import hashlib
from typing import cast
import uuid

from backtesting.microstructure import should_skip_entry_for_gap
from common.quantity_utils import format_share_quantity, is_effectively_integer_quantity, normalize_share_quantity
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


def resolve_initial_stop_price(
    reference_price: float,
    target: ExecutionTarget | None = None,
    side: str = "buy",
) -> float | None:
    """Détermine un stop initial broker-side exploitable, direction-aware (Sprint 3).

    Long  : stop < reference_price
    Short : stop > reference_price
    """
    from core.direction import is_short_side
    short = is_short_side(side)

    if target is None or reference_price <= 0:
        return None

    if target.stop_price_initial is not None and target.stop_price_initial > 0:
        if not short and target.stop_price_initial < reference_price:
            return round(float(target.stop_price_initial), 2)
        if short and target.stop_price_initial > reference_price:
            return round(float(target.stop_price_initial), 2)

    if target.risk_per_share is not None and target.risk_per_share > 0:
        sign = -1 if short else 1
        derived_stop = reference_price - sign * float(target.risk_per_share)
        if not short and 0 < derived_stop < reference_price:
            return round(derived_stop, 2)
        if short and derived_stop > reference_price:
            return round(derived_stop, 2)
    return None


def resolve_trailing_activation_price(
    fill_price: float,
    config: ExecutionConfig,
    target: ExecutionTarget | None = None,
    side: str = "buy",
) -> tuple[float | None, str | None]:
    """Détermine le prix auquel le stop initial doit être promu en trailing dynamique, direction-aware (Sprint 3)."""
    from core.direction import is_short_side
    short = is_short_side(side)

    if fill_price <= 0:
        return None, None

    if config.trailing_activation_trigger == "multiple_r":
        if target is not None and target.risk_per_share is not None and target.risk_per_share > 0:
            sign = -1 if short else 1
            activation = fill_price + sign * (float(target.risk_per_share) * config.trailing_activation_r_multiple)
            return round(activation, 2), "multiple_r"
        sign = -1 if short else 1
        return round(fill_price * (1 + sign * config.trailing_activation_profit_pct), 2), "profit_pct_fallback"

    sign = -1 if short else 1
    return round(fill_price * (1 + sign * config.trailing_activation_profit_pct), 2), "profit_pct"


def build_entry_intents(
    targets: list[ExecutionTarget],
    config: ExecutionConfig,
    exec_run_id: str,
    *,
    decision_fingerprints: dict[str, str] | None = None,
) -> list[OrderIntent]:
    """Construit les OrderIntent d'entrée, direction-aware (Sprint 3).

    Parameters
    ----------
    decision_fingerprints:
        Mapping symbole → fingerprint de décision (Point 11).
        Injecté depuis le journal d'audit du CLI risque pour associer
        chaque ordre broker à la décision qui l'a produit.
    """
    from core.direction import is_short_side

    intents: list[OrderIntent] = []
    for t in targets:
        if t.target_shares <= 0:
            continue
        qty = normalize_share_quantity(float(t.target_shares))
        if qty <= 0:
            continue
        # Sprint 3 — side canonique depuis la target
        side = str(getattr(t, "side", None) or "buy").strip().lower()
        if side not in ("buy", "sell"):
            side = "buy"
        short = is_short_side(side)

        limit_price: float | None = None
        if config.entry_order_type == "limit":
            # Sprint 3 — buffer signé : négatif = favorable (sous signal pour long,
            # au-dessus pour short). Pour le short, on inverse le signe du buffer.
            bps = float(config.limit_price_buffer_bps)
            if short:
                bps = -bps  # short: on veut être au-dessus du signal
            limit_price = round(t.entry_price * (1 + bps / 10_000), 2)

        intent_id = _make_id()
        _dfp = (decision_fingerprints or {}).get(t.symbol.upper())
        intents.append(OrderIntent(
            intent_id=intent_id,
            risk_run_id=t.risk_run_id,
            exec_run_id=exec_run_id,
            symbol=t.symbol,
            side=side,
            qty=qty,
            order_type=config.entry_order_type,
            limit_price=limit_price,
            trail_percent=None,
            broker_mode=config.broker_mode,
            parent_intent_id=None,
            intent_role=IntentRole.ENTRY,
            idempotency_key=_idempotency_key(
                t.risk_run_id, t.symbol, IntentRole.ENTRY, side, qty, config.broker_mode,
            ),
            decision_price=t.entry_price,
            stop_price=None,
            submission_key=_submission_key(exec_run_id, t.symbol, IntentRole.ENTRY, side, qty, intent_id),
            decision_fingerprint=_dfp,
        ))
    return intents


def apply_live_leverage_to_targets(
    *,
    targets: list[ExecutionTarget],
    effective_leverage: float,
    active: bool,
    allow_fractional_shares: bool,
    exposure_multiplier: float = 1.0,
) -> tuple[list[ExecutionTarget], dict[str, float | int | bool]]:
    """Scale explicitement les cibles live pour consommer le buying power levier.

    Les targets issues de ``portfolio_targets`` sont généralement calibrées sur
    1.0x d'equity. Quand le levier live est actif, on doit multiplier les
    quantités / notionnels visés, sinon l'exécuteur ne fait qu'autoriser un
    budget supérieur sans jamais l'utiliser réellement.

    E46 (2026-08-22) : ``exposure_multiplier`` (config.yaml
    ``risk_management.exposure_multiplier``, défaut 1.0) scale le sizing des
    entrées LONG **et** SHORT (multiplicatif) SANS toucher CP-V2 / B4 /
    WORST_50 / 6L/2S. 1.0 = comportement PROD inchangé (les shorts restent
    non-scalés par le levier, comme avant).
    """
    normalized_leverage = max(float(effective_leverage or 1.0), 1.0)
    exp_mult = max(float(exposure_multiplier or 1.0), 0.0)
    buy_scale = normalized_leverage * exp_mult
    gross_before = round(
        sum(max(float(getattr(target, "target_weight", 0.0) or 0.0), 0.0) for target in targets),
        6,
    )
    notional_before = round(
        sum(float(target.target_notional or (target.target_shares * target.entry_price) or 0.0) for target in targets),
        2,
    )
    if not targets or ((not active or normalized_leverage <= 1.0 + 1e-12) and abs(exp_mult - 1.0) < 1e-12):
        return list(targets), {
            "leverage_active": bool(active),
            "effective_leverage": round(normalized_leverage, 6),
            "target_scale": 1.0,
            "scaled_targets": 0,
            "gross_exposure_before": gross_before,
            "gross_exposure_after": gross_before,
            "total_target_notional_before": notional_before,
            "total_target_notional_after": notional_before,
        }

    scaled_targets: list[ExecutionTarget] = []
    scaled_count = 0
    gross_after = 0.0
    notional_after = 0.0

    for target in targets:
        side = _normalized_target_side(target)
        is_buy = side not in {"sell", "short"} and float(target.target_shares) > 0.0
        scale = buy_scale if is_buy else exp_mult
        if abs(scale - 1.0) < 1e-12:
            scaled_targets.append(target)
            gross_after += max(float(getattr(target, "target_weight", 0.0) or 0.0), 0.0)
            notional_after += float(target.target_notional or (target.target_shares * target.entry_price) or 0.0)
            continue

        scaled_shares = normalize_share_quantity(float(target.target_shares) * scale)
        if not allow_fractional_shares and is_effectively_integer_quantity(target.target_shares):
            scaled_shares = float(int(scaled_shares))

        scaled_notional = scaled_shares * float(target.entry_price)
        scaled_weight = max(float(getattr(target, "target_weight", 0.0) or 0.0), 0.0) * scale
        scaled_risk_budget = (
            float(target.risk_budget_dollars) * scale
            if target.risk_budget_dollars is not None
            else None
        )
        scaled_initial_risk = (
            float(target.initial_risk_dollars) * scale
            if target.initial_risk_dollars is not None
            else None
        )
        if is_dataclass(target):
            scaled_target = replace(
                target,
                target_shares=scaled_shares,
                target_weight=scaled_weight,
                target_notional=scaled_notional,
                risk_budget_dollars=scaled_risk_budget,
                initial_risk_dollars=scaled_initial_risk,
            )
        else:
            scaled_target = ExecutionTarget(
                risk_run_id=str(getattr(target, "risk_run_id")),
                trade_date=getattr(target, "trade_date"),
                symbol=str(getattr(target, "symbol")),
                target_shares=scaled_shares,
                entry_price=float(getattr(target, "entry_price")),
                target_weight=scaled_weight,
                sector=getattr(target, "sector", None),
                conviction_score=getattr(target, "conviction_score", None),
                sizing_method=getattr(target, "sizing_method", None),
                kelly_fraction=getattr(target, "kelly_fraction", None),
                selection_rank=getattr(target, "selection_rank", None),
                decision_rank=getattr(target, "decision_rank", None),
                selector_signal_mode=getattr(target, "selector_signal_mode", None),
                selection_explanation=getattr(target, "selection_explanation", None),
                selector_earnings_blackout=getattr(target, "selector_earnings_blackout", None),
                side=getattr(target, "side", None),
                atr_20=getattr(target, "atr_20", None),
                price_asof_date=getattr(target, "price_asof_date", None),
                atr_asof_date=getattr(target, "atr_asof_date", None),
                stop_price_initial=getattr(target, "stop_price_initial", None),
                risk_per_share=getattr(target, "risk_per_share", None),
                risk_budget_dollars=scaled_risk_budget,
                initial_risk_dollars=scaled_initial_risk,
                target_notional=scaled_notional,
                previous_close=getattr(target, "previous_close", None),
            )
        scaled_targets.append(scaled_target)
        if (
            abs(float(scaled_target.target_shares) - float(target.target_shares)) > 1e-9
            or abs(float(scaled_target.target_weight) - float(target.target_weight)) > 1e-9
        ):
            scaled_count += 1
        gross_after += max(float(scaled_target.target_weight or 0.0), 0.0)
        notional_after += float(scaled_target.target_notional or 0.0)

    return scaled_targets, {
        "leverage_active": True,
        "effective_leverage": round(normalized_leverage, 6),
        "target_scale": round(buy_scale, 6),
        "scaled_targets": int(scaled_count),
        "gross_exposure_before": round(gross_before, 6),
        "gross_exposure_after": round(gross_after, 6),
        "total_target_notional_before": round(notional_before, 2),
        "total_target_notional_after": round(notional_after, 2),
    }


def _target_priority_key(target: ExecutionTarget) -> tuple[int, int, str]:
    decision_rank = getattr(target, "decision_rank", None)
    selection_rank = getattr(target, "selection_rank", None)
    return (
        int(cast(int, decision_rank)) if decision_rank is not None else 10**9,
        int(cast(int, selection_rank)) if selection_rank is not None else 10**9,
        str(target.symbol).strip().upper(),
    )


def _normalized_target_side(target: ExecutionTarget) -> str:
    return str(getattr(target, "side", "") or "buy").strip().lower() or "buy"


def filter_targets_by_live_regime_guards(
    *,
    targets: list[ExecutionTarget],
    config: ExecutionConfig,
    fractionable_by_symbol: dict[str, bool] | None = None,
) -> tuple[list[ExecutionTarget], list[dict[str, float | int | str | None]]]:
    """Applique des garde-fous live dérivés du snapshot régime marché.

    Ces garde-fous ne remplacent pas le sizing Risk (étape 11) ; ils servent de
    filet de sécurité en exécution live/paper si un run consomme des targets
    trop anciennes ou incompatibles avec le régime courant.
    """
    blocked: list[dict[str, float | int | str | None]] = []
    kept_targets = list(targets)

    if kept_targets:
        next_targets: list[ExecutionTarget] = []
        fractionable_lookup = {
            str(symbol).strip().upper(): bool(value)
            for symbol, value in (fractionable_by_symbol or {}).items()
        }
        for target in kept_targets:
            qty = normalize_share_quantity(getattr(target, "target_shares", 0.0))
            if is_effectively_integer_quantity(qty):
                next_targets.append(target)
                continue
            if not config.fractional_live_entries_enabled:
                blocked.append(
                    {
                        "symbol": target.symbol,
                        "sector": target.sector,
                        "target_weight": float(getattr(target, "target_weight", 0.0) or 0.0),
                        "target_shares": qty,
                        "reason": "fractional_shares_disabled",
                    }
                )
                continue
            if _normalized_target_side(target) in {"sell", "short"}:
                blocked.append(
                    {
                        "symbol": target.symbol,
                        "sector": target.sector,
                        "target_weight": float(getattr(target, "target_weight", 0.0) or 0.0),
                        "target_shares": qty,
                        "reason": "fractional_short_not_supported",
                    }
                )
                continue
            symbol = str(target.symbol).strip().upper()
            if fractionable_lookup.get(symbol) is True:
                next_targets.append(target)
                continue
            blocked.append(
                {
                    "symbol": target.symbol,
                    "sector": target.sector,
                    "target_weight": float(getattr(target, "target_weight", 0.0) or 0.0),
                    "target_shares": qty,
                    "reason": "asset_not_fractionable",
                }
            )
        kept_targets = next_targets

    max_position_weight = getattr(config, "regime_max_position_weight", None)
    if max_position_weight is not None:
        max_position_weight_limit = float(cast(float, max_position_weight))
        next_targets: list[ExecutionTarget] = []
        for target in kept_targets:
            target_weight = float(getattr(target, "target_weight", 0.0) or 0.0)
            if target_weight <= max_position_weight_limit + 1e-12:
                next_targets.append(target)
                continue
            blocked.append(
                {
                    "symbol": target.symbol,
                    "sector": target.sector,
                    "target_weight": target_weight,
                    "limit": max_position_weight_limit,
                    "reason": "regime_max_position_weight",
                }
            )
        kept_targets = next_targets

    max_sector_weight = getattr(config, "regime_max_sector_weight", None)
    if max_sector_weight is not None and kept_targets:
        max_sector_weight_limit = float(cast(float, max_sector_weight))
        allowed_ids: set[int] = set()
        sector_weights: dict[str, float] = defaultdict(float)
        for target in sorted(kept_targets, key=_target_priority_key):
            sector = str(target.sector or "UNKNOWN").strip() or "UNKNOWN"
            target_weight = max(float(getattr(target, "target_weight", 0.0) or 0.0), 0.0)
            projected_sector_weight = sector_weights[sector] + target_weight
            if projected_sector_weight <= max_sector_weight_limit + 1e-12:
                allowed_ids.add(id(target))
                sector_weights[sector] = projected_sector_weight
                continue
            blocked.append(
                {
                    "symbol": target.symbol,
                    "sector": target.sector,
                    "target_weight": target_weight,
                    "sector_weight_before": sector_weights[sector],
                    "sector_weight_after": projected_sector_weight,
                    "limit": max_sector_weight_limit,
                    "reason": "regime_max_sector_weight",
                }
            )
        kept_targets = [target for target in kept_targets if id(target) in allowed_ids]

    max_gross_exposure = getattr(config, "regime_max_gross_exposure", None)
    if max_gross_exposure is not None and kept_targets:
        max_gross_exposure_limit = float(cast(float, max_gross_exposure))
        allowed_ids = set()
        gross_exposure = 0.0
        for target in sorted(kept_targets, key=_target_priority_key):
            target_weight = max(float(getattr(target, "target_weight", 0.0) or 0.0), 0.0)
            projected_gross_exposure = gross_exposure + target_weight
            if projected_gross_exposure <= max_gross_exposure_limit + 1e-12:
                allowed_ids.add(id(target))
                gross_exposure = projected_gross_exposure
                continue
            blocked.append(
                {
                    "symbol": target.symbol,
                    "sector": target.sector,
                    "target_weight": target_weight,
                    "gross_exposure_before": gross_exposure,
                    "gross_exposure_after": projected_gross_exposure,
                    "limit": max_gross_exposure_limit,
                    "reason": "regime_max_gross_exposure",
                }
            )
        kept_targets = [target for target in kept_targets if id(target) in allowed_ids]

    max_positions = getattr(config, "regime_max_positions", None)
    if max_positions is not None:
        max_positions_limit = int(cast(int, max_positions))
    else:
        max_positions_limit = None
    if max_positions_limit is not None and len(kept_targets) > max_positions_limit:
        ranked_targets = sorted(kept_targets, key=_target_priority_key)
        allowed_ids = {id(target) for target in ranked_targets[:max_positions_limit]}
        for target in ranked_targets[max_positions_limit:]:
            blocked.append(
                {
                    "symbol": target.symbol,
                    "sector": target.sector,
                    "target_weight": float(getattr(target, "target_weight", 0.0) or 0.0),
                    "rank": int(getattr(target, "decision_rank", None) or getattr(target, "selection_rank", None) or 0),
                    "limit": max_positions_limit,
                    "reason": "regime_max_positions",
                }
            )
        kept_targets = [target for target in kept_targets if id(target) in allowed_ids]

    return kept_targets, blocked


def split_entry_intents_by_gap_filter(
    *,
    targets: list[ExecutionTarget],
    intents: list[OrderIntent],
    config: ExecutionConfig,
    latest_market_prices: dict[str, float] | None = None,
) -> tuple[list[OrderIntent], list[dict[str, float | str | None]]]:
    """Sépare les intents conservées des intents rejetées par le gap filter live."""
    if float(config.max_entry_gap_pct or 0.0) <= 0.0:
        return intents, []

    latest_market_prices = latest_market_prices or {}
    target_by_symbol = {str(target.symbol).strip().upper(): target for target in targets}
    kept: list[OrderIntent] = []
    blocked: list[dict[str, float | str | None]] = []

    for intent in intents:
        symbol = str(intent.symbol).strip().upper()
        target = target_by_symbol.get(symbol)
        previous_close = float(target.previous_close) if target is not None and target.previous_close is not None else None
        latest_price = latest_market_prices.get(symbol)
        if latest_price is None:
            latest_price = latest_market_prices.get(str(intent.symbol))
        decision_price = float(latest_price) if latest_price is not None else float(intent.decision_price)
        gap_pct = (
            abs(decision_price - previous_close) / previous_close
            if previous_close is not None and previous_close > 0
            else None
        )
        if should_skip_entry_for_gap(previous_close, decision_price, max_gap_pct=float(config.max_entry_gap_pct)):
            blocked.append(
                {
                    "symbol": intent.symbol,
                    "previous_close": previous_close,
                    "decision_price": decision_price,
                    "entry_gap_pct": gap_pct,
                    "max_entry_gap_pct": float(config.max_entry_gap_pct),
                }
            )
            continue
        kept.append(intent)
    return kept, blocked


def build_take_profit_intent(
    parent: OrderIntent,
    fill_qty: float,
    avg_fill_price: float,
    config: ExecutionConfig,
    target: ExecutionTarget | None = None,
) -> OrderIntent:
    # Sprint 3 — direction-aware TP
    from core.direction import compute_take_profit_price, is_short_side
    parent_side = str(getattr(parent, "side", "buy") or "buy").strip().lower()
    short = is_short_side(parent_side)
    exit_side = "buy" if short else "sell"

    # ── V1 Multi-Horizon TP (2026-08-09) ──
    # E21-B25 (P2) : ancrage du TP sur le prix d'entrée (fill) — fidélité recherche.
    _tp_anchor_entry = bool(getattr(config, "tp_anchor_entry", False))
    if (
        _tp_anchor_entry
        and target is not None and avg_fill_price > 0
        and target.tp_atr_multiple and target.tp_max_pct
        and target.atr_20 and target.atr_20 > 0
        and target.previous_close and target.previous_close > 0
    ):
        _atr_pct = float(target.atr_20) / float(target.previous_close)
        _dist_pct = min(_atr_pct * float(target.tp_atr_multiple), float(target.tp_max_pct))
        _sign = -1 if short else 1
        limit_price = round(avg_fill_price + _sign * (avg_fill_price * _dist_pct), 2)
    # Priorité 1 : take_profit_price pré-calculé par PortfolioBuilder
    elif target is not None and target.take_profit_price is not None and target.take_profit_price > 0:
        limit_price = round(float(target.take_profit_price), 2)
    else:
        # Priorité 2 : risk-based (2× risk_per_share)
        percent_target = compute_take_profit_price(parent_side, avg_fill_price, float(config.profit_taker_pct))
        risk_based_target = None
        if target is not None and target.risk_per_share is not None and target.risk_per_share > 0:
            sign = -1 if short else 1
            risk_based_target = avg_fill_price + sign * (2.0 * target.risk_per_share)
        if risk_based_target is not None:
            limit_price = round(max(percent_target, risk_based_target) if not short else min(percent_target, risk_based_target), 2)
        else:
            limit_price = round(percent_target, 2)

    intent_id = _make_id()
    return OrderIntent(
        intent_id=intent_id,
        risk_run_id=parent.risk_run_id,
        exec_run_id=parent.exec_run_id,
        symbol=parent.symbol,
        side=exit_side,
        qty=fill_qty,
        order_type="limit",
        limit_price=limit_price,
        trail_percent=None,
        broker_mode=parent.broker_mode,
        parent_intent_id=parent.intent_id,
        intent_role=IntentRole.TAKE_PROFIT,
        idempotency_key=_idempotency_key(
            parent.exec_run_id, parent.symbol, IntentRole.TAKE_PROFIT,
            exit_side, fill_qty, parent.broker_mode,
        ),
        decision_price=parent.decision_price,
        stop_price=None,
        submission_key=_submission_key(parent.exec_run_id, parent.symbol, IntentRole.TAKE_PROFIT, exit_side, fill_qty, intent_id),
        decision_fingerprint=parent.decision_fingerprint,
    )


def build_initial_stop_intent(
    parent: OrderIntent,
    fill_qty: float,
    avg_fill_price: float,
    config: ExecutionConfig,
    target: ExecutionTarget | None = None,
) -> OrderIntent | None:
    # Sprint 3 — direction-aware stop
    from core.direction import compute_initial_stop_price, is_short_side
    parent_side = str(getattr(parent, "side", "buy") or "buy").strip().lower()
    short = is_short_side(parent_side)
    exit_side = "buy" if short else "sell"

    reference_price = avg_fill_price or parent.decision_price
    # E21-B25 (P3) : ancrage du SL initial sur le prix d'entrée (fill) — fidélité recherche.
    if (
        bool(getattr(config, "sl_anchor_entry", False))
        and target is not None and avg_fill_price > 0
        and target.risk_per_share and target.risk_per_share > 0
        and target.previous_close and target.previous_close > 0
    ):
        _sign = -1 if short else 1
        _dist = avg_fill_price * float(target.risk_per_share) / float(target.previous_close)
        _derived = avg_fill_price - _sign * _dist
        if (not short and 0 < _derived < avg_fill_price) or (short and _derived > avg_fill_price):
            stop_price = round(_derived, 2)
        else:
            stop_price = resolve_initial_stop_price(reference_price, target, side=parent_side)
    else:
        stop_price = resolve_initial_stop_price(reference_price, target, side=parent_side)
    if stop_price is None:
        return None

    intent_id = _make_id()
    return OrderIntent(
        intent_id=intent_id,
        risk_run_id=parent.risk_run_id,
        exec_run_id=parent.exec_run_id,
        symbol=parent.symbol,
        side=exit_side,
        qty=fill_qty,
        order_type="stop",
        limit_price=None,
        trail_percent=None,
        broker_mode=parent.broker_mode,
        parent_intent_id=parent.intent_id,
        intent_role=IntentRole.INITIAL_STOP,
        idempotency_key=_idempotency_key(
            parent.exec_run_id, parent.symbol, IntentRole.INITIAL_STOP,
            exit_side, fill_qty, parent.broker_mode,
        ),
        decision_price=parent.decision_price,
        stop_price=stop_price,
        submission_key=_submission_key(parent.exec_run_id, parent.symbol, IntentRole.INITIAL_STOP, exit_side, fill_qty, intent_id),
        decision_fingerprint=parent.decision_fingerprint,
    )


def build_manual_buy_initial_stop_intent(
    parent: OrderIntent,
    fill_qty: float,
    avg_fill_price: float,
    config: ExecutionConfig,
    *,
    atr_value: float | None = None,
) -> OrderIntent | None:
    """Construit un STOP `sell` pour un achat manuel orphelin adopté.

    Contrairement à ``build_initial_stop_intent``, ce helper ne dépend pas
    d'un ``ExecutionTarget`` (pas d'ATR / risk_per_share disponible pour un
    achat passé hors Alpha Trade).

    Mode ``trailing_stop.mode == "dynamic_atr"`` (Axe F du plan ``prompt/parttern/plan.md``) :
    si ``atr_value`` est fourni et > 0, le stop = ``avg_fill_price - atr × multiplier``.
    Sinon fallback sur ``trailing_stop.fallback_fixed_pct`` si trailing_stop activé,
    ou sur ``config.manual_buy_stop_loss_pct`` (rétrocompat historique).
    """
    reference_price = avg_fill_price or parent.decision_price
    if reference_price <= 0 or fill_qty <= 0:
        return None

    ts = config.trailing_stop
    use_dynamic_atr = (
        ts.enabled
        and ts.mode == "dynamic_atr"
        and ts.apply_to_manual_orphan_buys
        and atr_value is not None
        and atr_value > 0
    )
    if use_dynamic_atr:
        stop_price = round(reference_price - float(atr_value) * float(ts.atr_multiplier), 2)
    elif ts.enabled and ts.apply_to_manual_orphan_buys:
        # fallback fixe configuré dans trailing_stop
        stop_price = round(reference_price * (1.0 - float(ts.fallback_fixed_pct) / 100.0), 2)
    else:
        # comportement historique inchangé
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
        decision_fingerprint=parent.decision_fingerprint,
    )


def build_trailing_stop_intent(
    parent: OrderIntent,
    fill_qty: float,
    avg_fill_price: float,
    config: ExecutionConfig,
    target: ExecutionTarget | None = None,
) -> OrderIntent:
    # Sprint 3 — direction-aware trailing stop
    from core.direction import is_short_side
    parent_side = str(getattr(parent, "side", "buy") or "buy").strip().lower()
    short = is_short_side(parent_side)
    exit_side = "buy" if short else "sell"

    reference_price = avg_fill_price or parent.decision_price
    # E21-v2 : trailing par-signal (régime SPY PIT) — priorité sur la config globale.
    _tgt_pct = (
        float(getattr(target, "trailing_stop_pct", None))
        if (target is not None and getattr(target, "trailing_stop_pct", None) is not None)
        else None
    )
    _tgt_risk = bool(getattr(target, "trailing_risk_based", False)) if target is not None else False
    # P13/P14 expérimental : override global, sinon override side-spécifique.
    trail_pct_override = getattr(config, "trailing_pct_override", None)
    if _tgt_risk:
        trail_pct_override = None  # force risk-based (2.5xATR)
    elif _tgt_pct is not None:
        trail_pct_override = _tgt_pct
    elif trail_pct_override is None:
        trail_pct_override = (
            getattr(config, "trailing_pct_short_override", None)
            if short
            else getattr(config, "trailing_pct_long_override", None)
        )
    if trail_pct_override is not None:
        # P13/P14 : trailing fixe (parité recherche) au lieu du risk-based.
        trail_pct = round(float(trail_pct_override) * 100, 2)
    else:
        risk_based_trail_pct = None
        if target is not None:
            if target.stop_price_initial is not None and reference_price > 0:
                risk_based_trail_pct = abs(reference_price - target.stop_price_initial) / reference_price
            elif target.risk_per_share is not None and target.risk_per_share > 0 and reference_price > 0:
                risk_based_trail_pct = target.risk_per_share / reference_price
        trail_pct = round((risk_based_trail_pct if risk_based_trail_pct is not None else config.trailing_stop_pct) * 100, 2)
    intent_id = _make_id()
    return OrderIntent(
        intent_id=intent_id,
        risk_run_id=parent.risk_run_id,
        exec_run_id=parent.exec_run_id,
        symbol=parent.symbol,
        side=exit_side,
        qty=fill_qty,
        order_type="trailing_stop",
        limit_price=None,
        trail_percent=trail_pct,
        broker_mode=parent.broker_mode,
        parent_intent_id=parent.intent_id,
        intent_role=IntentRole.TRAILING_STOP,
        idempotency_key=_idempotency_key(
            parent.exec_run_id, parent.symbol, IntentRole.TRAILING_STOP,
            exit_side, fill_qty, parent.broker_mode,
        ),
        decision_price=parent.decision_price,
        stop_price=None,
        submission_key=_submission_key(parent.exec_run_id, parent.symbol, IntentRole.TRAILING_STOP, exit_side, fill_qty, intent_id),
        decision_fingerprint=parent.decision_fingerprint,
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
    qty = normalize_share_quantity(qty)
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
    qty = normalize_share_quantity(qty)
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


def _resolve_alpaca_time_in_force(intent: OrderIntent, config: ExecutionConfig | None = None) -> str:
    if intent.intent_role in (IntentRole.ENTRY, IntentRole.EXIT, IntentRole.REBALANCE_BUY):
        return "day"
    if config is None:
        return "gtc"
    return config.resolve_fractional_protection_time_in_force(intent.qty)


def intent_to_alpaca_payload(intent: OrderIntent, config: ExecutionConfig | None = None) -> dict[str, str]:
    """Convertit un OrderIntent en payload dict pour l'API Alpaca Trading v2.
    Utilise _alpaca_client_order_id (base exec_run_id) et non idempotency_key
    pour garantir l'unicite cote Alpaca meme en cas de relance.
    """
    tif = _resolve_alpaca_time_in_force(intent, config)
    alpaca_client_id = intent.submission_key or _alpaca_client_order_id(
        intent.exec_run_id, intent.symbol, intent.intent_role, intent.side, intent.qty
    )
    payload: dict[str, str] = {
        "symbol": intent.symbol,
        "qty": format_share_quantity(intent.qty),
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
    config: ExecutionConfig | None = None,
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
    qty = normalize_share_quantity(qty)
    qty_str = format_share_quantity(qty)

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
        "time_in_force": config.resolve_fractional_protection_time_in_force(qty) if config is not None else "gtc",
        "order_class": "oco",
        "client_order_id": client_order_id,
        "limit_price": str(tp_intent.limit_price),
        "take_profit": take_profit,
        "stop_loss": stop_loss,
    }
    return payload


