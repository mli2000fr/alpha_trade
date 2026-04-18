"""
Réconciliation corporate actions : broker vs état interne.

Après un split ou un dividende, les positions chez le broker (Alpaca)
sont déjà ajustées automatiquement. Ce module compare l'état interne
(après application des corporate actions) avec le broker pour détecter
les incohérences.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CaReconcileDiff:
    """Différence détectée entre position interne et position broker."""
    symbol: str
    internal_qty: float
    broker_qty: float
    delta: float
    action: str  # "ok" | "investigate" | "qty_mismatch"


def reconcile_after_corporate_actions(
    internal_positions: dict[str, float],
    broker_positions: list[dict],
    tolerance: float = 0.01,
) -> list[CaReconcileDiff]:
    """
    Compare les positions internes (après application CA) avec le broker.

    Paramètres :
        internal_positions — {symbol: qty} après traitement CA
        broker_positions   — Liste de dicts broker (symbol, qty)
        tolerance          — Tolérance en nombre de parts

    Retourne une liste de différences.
    """
    broker_map: dict[str, float] = {
        str(p.get("symbol", "")).upper(): float(p.get("qty", 0))
        for p in broker_positions
    }
    all_symbols = sorted(set(internal_positions) | set(broker_map))
    diffs: list[CaReconcileDiff] = []

    for sym in all_symbols:
        internal = internal_positions.get(sym, 0.0)
        broker = broker_map.get(sym, 0.0)
        delta = broker - internal

        if abs(delta) <= tolerance:
            action = "ok"
        elif sym not in internal_positions:
            action = "investigate"
        else:
            action = "qty_mismatch"

        if action != "ok":
            LOGGER.warning(
                "CA reconciliation diff | symbol=%s internal=%.2f broker=%.2f delta=%.2f action=%s",
                sym, internal, broker, delta, action,
            )

        diffs.append(CaReconcileDiff(
            symbol=sym, internal_qty=internal, broker_qty=broker,
            delta=delta, action=action,
        ))

    return diffs

