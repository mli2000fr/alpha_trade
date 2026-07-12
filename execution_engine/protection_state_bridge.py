"""execution_engine/protection_state_bridge.py — Pont fills → ProtectionState (Point 11).

Convertit les fills broker en états de protection vérifiables et persistables.
Point de jonction entre risk_management/protection_contract.py et le watcher.

Usage ::

    from execution_engine.protection_state_bridge import (
        build_protection_state_from_fill,
        verify_fill_protection_consistency,
    )
    state = build_protection_state_from_fill(
        symbol="AAPL", side="long", fill_qty=100, fill_price=150.0,
        decision_price=149.5, atr=2.5,
    )
    ok, issues = verify_fill_protection_consistency(state)
"""

from __future__ import annotations

import logging
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


def build_protection_state_from_fill(
    symbol: str,
    side: str,
    fill_qty: float,
    fill_price: float,
    *,
    decision_price: float | None = None,
    atr: float | None = None,
    parent_intent_id: str | None = None,
    stop_price_initial: float | None = None,
    risk_per_share: float | None = None,
    decision_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Convertit un fill broker en ``ProtectionState`` vérifiable.

    Utilise ``StopCalculator.recalculate_after_fill()`` pour recentrer
    les niveaux de stop/TP sur le prix de fill réel.

    Returns un dict sérialisable avec les champs de ``ProtectionState``.
    """
    from risk_management.stop_calculator import StopCalculator, StopLevels

    calc = StopCalculator()
    entry_price = fill_price  # Le fill EST le prix d'entrée réel

    # Construire les niveaux de stop initiaux avant recalcul
    initial_levels = calc.compute(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        atr=atr,
    )

    # Recalculer sur le fill réel (si le prix de décision diffère)
    recalc_levels = initial_levels.recalculate_after_fill(
        fill_price=fill_price,
        fill_quantity=fill_qty,
    )

    return {
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "fill_quantity": fill_qty,
        "fill_price": fill_price,
        "decision_price": decision_price,
        "stop_price": recalc_levels.stop_price,
        "stop_distance_pct": recalc_levels.stop_distance_pct,
        "tp_price": recalc_levels.take_profit_price,
        "risk_per_share": recalc_levels.risk_per_share,
        "risk_total": recalc_levels.risk_total,
        "trailing_activation_price": recalc_levels.trailing_activation_price,
        "time_stop_sessions": recalc_levels.time_stop_sessions,
        "status": "protected",
        "last_action_at": datetime.now(timezone.utc).isoformat(),
        "parent_intent_id": parent_intent_id,
        "decision_fingerprint": decision_fingerprint,
    }


def persist_protection_state(
    state_dict: dict[str, Any],
    *,
    exec_run_id: str,
    root_dir: Path | None = None,
) -> Path:
    """Persiste atomiquement l'état de protection d'un fill, idempotent par intent."""
    base_dir = root_dir or Path("artifacts") / "protection_states"
    target = base_dir / f"{exec_run_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"exec_run_id": exec_run_id, "states": []}
    if target.exists():
        loaded = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = loaded
    states = [entry for entry in payload.get("states", []) if isinstance(entry, dict)]
    identity = str(state_dict.get("parent_intent_id") or state_dict.get("symbol") or "")
    states = [entry for entry in states if str(entry.get("parent_intent_id") or entry.get("symbol") or "") != identity]
    states.append(dict(state_dict))
    payload["states"] = states
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    os.replace(temporary, target)
    return target


def verify_fill_protection_consistency(
    state_dict: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Vérifie qu'un fill est correctement protégé via ``ProtectionContract``.

    Returns (is_safe, list_of_issues). Si is_safe=False, les issues
    décrivent ce qui doit être corrigé.
    """
    from risk_management.protection_contract import (
        ProtectionContract,
        ProtectionState,
        ProtectionStatus,
    )

    try:
        state = ProtectionState(
            symbol=str(state_dict.get("symbol", "")),
            side=str(state_dict.get("side", "long")),
            entry_price=float(state_dict.get("entry_price", 0.0)),
            fill_quantity=float(state_dict.get("fill_quantity", 0.0)),
            fill_price=float(state_dict.get("fill_price", 0.0)),
            stop_price=float(state_dict.get("stop_price", 0.0)) if state_dict.get("stop_price") else None,
            tp_price=float(state_dict.get("tp_price", 0.0)) if state_dict.get("tp_price") else None,
            status=ProtectionStatus.PROTECTED,
        )
    except Exception:
        return False, [f"ProtectionState construction failed for {state_dict.get('symbol', '?')}"]

    contract = ProtectionContract()
    is_safe, issues = contract.check_state(state)

    if not is_safe:
        force_close, reason = contract.should_force_close(state, 0.0)
        if force_close:
            issues.append(f"FORCE_CLOSE required: {reason}")

    return is_safe, issues
