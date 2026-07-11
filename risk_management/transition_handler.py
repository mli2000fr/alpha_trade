"""risk_management/transition_handler.py — Gestion des positions/ordres lors des transitions de régime (Sprint Maître 9).

Définit le contrat pour traiter les positions existantes, ordres ouverts
et partial fills lors des changements d'état du régime marché.

Principes :
- Aucune position n'est abandonnée sans ordre explicite.
- Les ordres ouverts sont annulés AVANT les liquidations.
- Les partial fills sont consolidés avant décision.
- Chaque action de transition est auditée (quoi, pourquoi, quand).

Usage ::

    from risk_management.transition_handler import TransitionHandler, PositionTransitionPlan
    handler = TransitionHandler()
    plan = handler.build_plan(transition, open_positions, open_orders)
    for step in plan.steps:
        execute(step)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from risk_management.regime_state_machine import RegimeTransition, TransitionAction


# ── OrderAction ─────────────────────────────────────────────────────────────


class OrderAction(StrEnum):
    """Action sur un ordre ou une position."""

    CANCEL = "cancel"           # Annuler l'ordre ouvert
    HOLD = "hold"               # Garder la position (ne rien faire)
    REDUCE = "reduce"           # Réduire la position (partial close)
    LIQUIDATE = "liquidate"     # Liquider complètement la position
    HEDGE = "hedge"             # Ouvrir un hedge


# ── TransitionStep ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TransitionStep:
    """Une étape atomique du plan de transition.

    Attributes
    ----------
    symbol : str
        Symbole concerné.
    action : OrderAction
        Action à exécuter.
    side : str
        ``"long"`` ou ``"short"``.
    quantity : float | None
        Quantité à traiter (None si action==CANCEL ou HOLD).
    reason : str
        Raison de l'action (auditable).
    priority : int
        Priorité d'exécution (1 = plus haute).
    order_id : str | None
        ID de l'ordre si action == CANCEL.
    """

    symbol: str
    action: OrderAction
    side: str = "long"
    quantity: float | None = None
    reason: str = ""
    priority: int = 5
    order_id: str | None = None

    def __post_init__(self) -> None:
        if self.side not in ("long", "short"):
            raise ValueError(f"side invalide: {self.side!r}")

    @property
    def is_destructive(self) -> bool:
        return self.action in (OrderAction.REDUCE, OrderAction.LIQUIDATE)


# ── PositionTransitionPlan ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PositionTransitionPlan:
    """Plan complet de transition pour les positions et ordres.

    Attributes
    ----------
    transition : RegimeTransition
        La transition de régime qui a déclenché ce plan.
    steps : tuple[TransitionStep, ...]
        Étapes ordonnées par priorité.
    total_positions_affected : int
        Nombre de positions impactées.
    total_orders_cancelled : int
        Nombre d'ordres annulés.
    audit_log : tuple[str, ...]
        Logs d'audit pour chaque décision.
    """

    transition: RegimeTransition
    steps: tuple[TransitionStep, ...] = ()
    total_positions_affected: int = 0
    total_orders_cancelled: int = 0
    audit_log: tuple[str, ...] = ()

    @property
    def has_actions(self) -> bool:
        return len(self.steps) > 0

    @property
    def is_empty(self) -> bool:
        return not self.has_actions


# ── OpenPosition (contrat simplifié) ────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OpenPosition:
    """Représentation simplifiée d'une position ouverte.

    Ce type est un CONTRAT — les vrais objets position du broker
    doivent être adaptés vers ce contrat avant d'être passés au handler.
    """

    symbol: str
    side: str  # "long" ou "short"
    quantity: float
    avg_entry_price: float
    current_price: float | None = None
    unrealized_pnl_pct: float | None = None
    has_partial_fill: bool = False
    filled_quantity: float | None = None

    def __post_init__(self) -> None:
        if self.side not in ("long", "short"):
            raise ValueError(f"side invalide: {self.side!r}")
        if self.quantity <= 0:
            raise ValueError(f"quantity doit être > 0: {self.quantity}")


@dataclass(frozen=True, slots=True)
class OpenOrder:
    """Représentation simplifiée d'un ordre ouvert."""

    order_id: str
    symbol: str
    side: str  # "buy" ou "sell"
    order_type: str  # "limit", "market", "stop", "stop_limit"
    quantity: float
    filled_quantity: float = 0.0
    status: str = "open"  # "open", "partially_filled", "pending"

    def __post_init__(self) -> None:
        if self.side not in ("buy", "sell"):
            raise ValueError(f"side invalide: {self.side!r}")

    @property
    def has_partial_fill(self) -> bool:
        return self.filled_quantity > 0 and self.filled_quantity < self.quantity


# ── TransitionHandler ───────────────────────────────────────────────────────


@dataclass
class TransitionHandler:
    """Construit un plan de transition pour positions et ordres.

    Le handler est **pur** : il produit un plan, n'exécute rien.
    L'exécution est déléguée à l'executor.

    Règles (Sprint Maître 9) :
    1. Annuler TOUS les ordres ouverts AVANT toute liquidation.
    2. Consolider les partial fills avant de décider.
    3. Liquider dans l'ordre : shorts d'abord, puis longs (ou inverse selon régime).
    4. Ne jamais abandonner une position sans ordre explicite.
    5. Auditer chaque action (quoi, pourquoi, quand).
    """

    def build_plan(
        self,
        transition: RegimeTransition,
        positions: list[OpenPosition],
        orders: list[OpenOrder],
    ) -> PositionTransitionPlan:
        """Construit le plan de transition.

        Parameters
        ----------
        transition : RegimeTransition
            La transition évaluée par la state machine.
        positions : list[OpenPosition]
            Positions ouvertes actuelles.
        orders : list[OpenOrder]
            Ordres ouverts actuels.

        Returns
        -------
        PositionTransitionPlan
        """
        steps: list[TransitionStep] = []
        audit_log: list[str] = []
        priority = 1

        # ── 1. Annuler TOUS les ordres ouverts ─────────────────────────
        for order in orders:
            steps.append(TransitionStep(
                symbol=order.symbol,
                action=OrderAction.CANCEL,
                side="long" if order.side == "buy" else "short",
                reason=f"annulation ordre {order.order_id} — transition régime: {transition.reason}",
                priority=priority,
                order_id=order.order_id,
            ))
            if order.has_partial_fill:
                audit_log.append(
                    f"PARTIAL_FILL: {order.symbol} {order.order_id} "
                    f"filled={order.filled_quantity}/{order.quantity} — annulé"
                )
            priority += 1

        orders_cancelled = len(steps)

        # ── 2. Actions selon le type de transition ─────────────────────
        action = transition.action

        if action == TransitionAction.NO_OP:
            # Rien à faire
            pass

        elif action == TransitionAction.REDUCE:
            # Réduire toutes les positions de 50%
            for pos in positions:
                reduce_qty = pos.quantity * 0.5
                steps.append(TransitionStep(
                    symbol=pos.symbol,
                    action=OrderAction.REDUCE,
                    side=pos.side,
                    quantity=reduce_qty,
                    reason=f"réduction 50% — transition régime: {transition.reason}",
                    priority=priority,
                ))
                priority += 1

        elif action == TransitionAction.LIQUIDATE_LONGS:
            for pos in positions:
                if pos.side == "long":
                    steps.append(TransitionStep(
                        symbol=pos.symbol,
                        action=OrderAction.LIQUIDATE,
                        side="long",
                        quantity=pos.quantity,
                        reason=f"liquidation long — transition régime: {transition.reason}",
                        priority=priority,
                    ))
                    priority += 1
            # Shorts restent en place (hedge)

        elif action == TransitionAction.LIQUIDATE_SHORTS:
            for pos in positions:
                if pos.side == "short":
                    steps.append(TransitionStep(
                        symbol=pos.symbol,
                        action=OrderAction.LIQUIDATE,
                        side="short",
                        quantity=pos.quantity,
                        reason=f"liquidation short — transition régime: {transition.reason}",
                        priority=priority,
                    ))
                    priority += 1

        elif action == TransitionAction.LIQUIDATE_ALL:
            # Liquider shorts d'abord, puis longs
            for pos in sorted(positions, key=lambda p: 0 if p.side == "short" else 1):
                steps.append(TransitionStep(
                    symbol=pos.symbol,
                    action=OrderAction.LIQUIDATE,
                    side=pos.side,
                    quantity=pos.quantity,
                    reason=f"liquidation totale — transition régime: {transition.reason}",
                    priority=priority,
                ))
                priority += 1

        elif action == TransitionAction.HEDGE:
            # Garder les longs, ouvrir des shorts de couverture
            # (la sélection des hedges est déléguée au PortfolioBuilder)
            pass

        elif action in (TransitionAction.CLOSE_ONLY, TransitionAction.CASH_ONLY):
            # Pas de nouvelles entrées, mais on garde les positions existantes
            # avec gestion de sortie active
            pass

        # ── Audit ──────────────────────────────────────────────────────
        positions_affected = sum(
            1 for s in steps if s.is_destructive
        )

        audit_log.append(
            f"TRANSITION: {transition.from_state.value} → {transition.to_state.value} "
            f"action={transition.action.value} "
            f"positions_affected={positions_affected} "
            f"orders_cancelled={orders_cancelled} "
            f"reason={transition.reason}"
        )

        return PositionTransitionPlan(
            transition=transition,
            steps=tuple(steps),
            total_positions_affected=positions_affected,
            total_orders_cancelled=orders_cancelled,
            audit_log=tuple(audit_log),
        )

    @staticmethod
    def no_op_plan(transition: RegimeTransition) -> PositionTransitionPlan:
        """Plan vide pour une transition NO_OP."""
        return PositionTransitionPlan(
            transition=transition,
            audit_log=(f"NO_OP: {transition.reason}",),
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def build_transition_plan(
    transition: RegimeTransition,
    positions: list[OpenPosition] | None = None,
    orders: list[OpenOrder] | None = None,
) -> PositionTransitionPlan:
    """Fonction pure de construction de plan de transition."""
    handler = TransitionHandler()
    return handler.build_plan(
        transition,
        positions or [],
        orders or [],
    )
