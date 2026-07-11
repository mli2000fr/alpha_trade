"""risk_management/protection_contract.py — Contrat de protection directionnelle (Sprint Maître 12).

Formalise le contrat de protection pour garantir qu'aucune position
n'est laissée sans protection (stop, TP, trailing, OCO).

Usage ::

    from risk_management.protection_contract import (
        ProtectionContract, ProtectionStatus, ProtectionSLA, OCOGroup,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


# ── ProtectionStatus ────────────────────────────────────────────────────────


class ProtectionStatus(StrEnum):
    """Statut de protection d'une position (Sprint Maître 12)."""

    PROTECTED = "protected"               # Stop + TP en place
    PARTIALLY_PROTECTED = "partially"     # Stop seul, pas de TP
    UNPROTECTED = "unprotected"           # Aucune protection
    PENDING_ARM = "pending_arm"           # En attente d'armement
    REPAIRING = "repairing"               # Réparation automatique en cours
    FORCE_CLOSING = "force_closing"       # Liquidation forcée
    CLOSED = "closed"                     # Position fermée

    @property
    def is_safe(self) -> bool:
        """True si la position est protégée ou partiellement protégée."""
        return self in (ProtectionStatus.PROTECTED, ProtectionStatus.PARTIALLY_PROTECTED)

    @property
    def requires_action(self) -> bool:
        """True si une action est nécessaire (arming, repair, force close)."""
        return self in (
            ProtectionStatus.UNPROTECTED,
            ProtectionStatus.PENDING_ARM,
            ProtectionStatus.REPAIRING,
        )


# ── ProtectionSLA ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ProtectionSLA:
    """Service Level Agreement pour la protection (Sprint Maître 12).

    Définit les délais maximum pour chaque action de protection.
    """

    arm_timeout_seconds: float = 30.0        # Max pour armer un stop après fill
    repair_timeout_seconds: float = 60.0     # Max pour réparer une protection manquante
    force_close_timeout_seconds: float = 120.0  # Max pour liquider une position non protégée
    reconciliation_interval_seconds: float = 300.0  # Intervalle de réconciliation (5 min)

    def is_breached(
        self,
        status: ProtectionStatus,
        time_since_last_action: float,
    ) -> bool:
        """True si le SLA est violé pour ce statut."""
        thresholds = {
            ProtectionStatus.PENDING_ARM: self.arm_timeout_seconds,
            ProtectionStatus.UNPROTECTED: self.repair_timeout_seconds,
            ProtectionStatus.REPAIRING: self.repair_timeout_seconds,
        }
        threshold = thresholds.get(status)
        if threshold is None:
            return False
        return time_since_last_action > threshold


# ── OCOGroup ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OCOGroup:
    """Groupe OCO (One-Cancels-Other) pour une position (Sprint Maître 12).

    Garantit que :
    - Les quantités protégées = quantités filled
    - Si un ordre est exécuté, l'autre est annulé
    - Les ordres enfants sont liés au parent
    """

    oco_id: str
    symbol: str
    side: str
    parent_intent_id: str
    entry_order_id: str | None = None
    stop_order_id: str | None = None
    tp_order_id: str | None = None
    trailing_order_id: str | None = None
    protected_quantity: float = 0.0
    filled_quantity: float = 0.0
    status: str = "pending"  # pending, active, filled, cancelled, rejected

    @property
    def is_complete(self) -> bool:
        """True si toutes les jambes sont en place."""
        return (
            self.stop_order_id is not None
            and self.protected_quantity == self.filled_quantity
        )

    @property
    def is_orphan(self) -> bool:
        """True si le stop existe mais pas le parent."""
        return (
            self.stop_order_id is not None
            and self.entry_order_id is None
        )

    @property
    def quantity_match(self) -> bool:
        """True si les quantités protégées égalent les quantités fill."""
        return abs(self.protected_quantity - self.filled_quantity) < 0.01

    def to_dict(self) -> dict[str, object]:
        return {
            "oco_id": self.oco_id,
            "symbol": self.symbol,
            "side": self.side,
            "parent_intent_id": self.parent_intent_id,
            "entry_order_id": self.entry_order_id,
            "stop_order_id": self.stop_order_id,
            "tp_order_id": self.tp_order_id,
            "trailing_order_id": self.trailing_order_id,
            "protected_quantity": self.protected_quantity,
            "filled_quantity": self.filled_quantity,
            "status": self.status,
            "is_complete": self.is_complete,
            "is_orphan": self.is_orphan,
            "quantity_match": self.quantity_match,
        }


# ── ProtectionContract ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ProtectionState:
    """État de protection d'une position (Sprint Maître 12)."""

    symbol: str
    side: str
    entry_price: float
    fill_quantity: float
    fill_price: float | None = None
    stop_price: float | None = None
    tp_price: float | None = None
    status: ProtectionStatus = ProtectionStatus.PENDING_ARM
    oco_group: OCOGroup | None = None
    last_action_at: datetime | None = None
    force_close_reason: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    mae_pct: float | None = None  # Maximum Adverse Excursion
    mfe_pct: float | None = None  # Maximum Favorable Excursion
    r_multiple: float | None = None  # R-multiple réalisé

    @property
    def is_protected(self) -> bool:
        return self.status.is_safe

    @property
    def needs_repair(self) -> bool:
        return self.status.requires_action

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "fill_quantity": self.fill_quantity,
            "fill_price": self.fill_price,
            "stop_price": self.stop_price,
            "tp_price": self.tp_price,
            "status": self.status.value,
            "oco_group": self.oco_group.to_dict() if self.oco_group else None,
            "last_action_at": self.last_action_at.isoformat() if self.last_action_at else None,
            "force_close_reason": self.force_close_reason,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "mae_pct": round(self.mae_pct, 4) if self.mae_pct is not None else None,
            "mfe_pct": round(self.mfe_pct, 4) if self.mfe_pct is not None else None,
            "r_multiple": round(self.r_multiple, 4) if self.r_multiple is not None else None,
            "is_protected": self.is_protected,
            "needs_repair": self.needs_repair,
        }


@dataclass
class ProtectionContract:
    """Contrat de protection directionnelle (Sprint Maître 12).

    Vérifie et garantit :
    1. Stop du bon côté (long sous entrée, short au-dessus)
    2. Quantités protégées = quantités filled
    3. OCO logique (stop + TP liés)
    4. SLA respecté (délai max pour armer/réparer)
    5. Force-close si protection impossible

    Le contrat est PUR : il vérifie, ne soumet pas d'ordres.
    """

    sla: ProtectionSLA = field(default_factory=ProtectionSLA)

    def check_state(self, state: ProtectionState) -> tuple[bool, list[str]]:
        """Vérifie l'état de protection d'une position.

        Returns
        -------
        (is_valid, violations)
        """
        violations: list[str] = []

        # ── 1. Stop du bon côté ────────────────────────────────────────
        if state.stop_price is not None and state.entry_price > 0:
            if state.side == "long" and state.stop_price >= state.entry_price:
                violations.append(
                    f"stop_long_mal_place: stop={state.stop_price} >= entry={state.entry_price}"
                )
            elif state.side == "short" and state.stop_price <= state.entry_price:
                violations.append(
                    f"stop_short_mal_place: stop={state.stop_price} <= entry={state.entry_price}"
                )

        # ── 2. Position non protégée ───────────────────────────────────
        if state.status in (ProtectionStatus.UNPROTECTED,):
            violations.append(f"position_non_protegee: {state.symbol} ({state.side})")

        # ── 3. Quantités OCO ───────────────────────────────────────────
        if state.oco_group is not None and not state.oco_group.quantity_match:
            violations.append(
                f"oco_quantity_mismatch: protected={state.oco_group.protected_quantity} "
                f"filled={state.oco_group.filled_quantity}"
            )

        # ── 4. SLA ─────────────────────────────────────────────────────
        if state.last_action_at is not None and state.status.requires_action:
            elapsed = (datetime.now() - state.last_action_at).total_seconds()
            if self.sla.is_breached(state.status, elapsed):
                violations.append(
                    f"sla_breached: status={state.status.value} elapsed={elapsed:.0f}s"
                )

        # ── 5. Orphan stop ─────────────────────────────────────────────
        if state.oco_group is not None and state.oco_group.is_orphan:
            violations.append(f"orphan_stop: {state.symbol}")

        return len(violations) == 0, violations

    def should_force_close(
        self,
        state: ProtectionState,
        time_since_last_action: float,
    ) -> tuple[bool, str | None]:
        """Détermine si une position doit être liquidée pour non-protection.

        Une position doit être force-close si :
        - Elle est UNPROTECTED depuis > force_close_timeout
        - Le stop est du mauvais côté et ne peut pas être réparé

        Returns
        -------
        (should_close, reason)
        """
        if state.status == ProtectionStatus.UNPROTECTED:
            if time_since_last_action > self.sla.force_close_timeout_seconds:
                return True, f"non protegee depuis {time_since_last_action:.0f}s > {self.sla.force_close_timeout_seconds}s"

        if state.stop_price is not None and state.entry_price > 0:
            if state.side == "long" and state.stop_price >= state.entry_price:
                return True, "stop long au-dessus de l'entree (invalide)"
            if state.side == "short" and state.stop_price <= state.entry_price:
                return True, "stop short en-dessous de l'entree (invalide)"

        return False, None

    def resolve_conflicts(
        self,
        open_orders: list[dict[str, object]],
        force_close_symbol: str,
    ) -> list[str]:
        """Identifie les ordres conflictuels à annuler avant force-close.

        Returns
        -------
        list[str]
            IDs des ordres à annuler.
        """
        to_cancel: list[str] = []
        for order in open_orders:
            if str(order.get("symbol", "")) == force_close_symbol:
                to_cancel.append(str(order.get("order_id", "")))
        return to_cancel


# ── Helpers ─────────────────────────────────────────────────────────────────


def check_protection_state(state: ProtectionState) -> tuple[bool, list[str]]:
    """Vérifie l'état de protection (fonction pure)."""
    contract = ProtectionContract()
    return contract.check_state(state)


def build_oco_group(
    oco_id: str,
    symbol: str,
    side: str,
    parent_intent_id: str,
    filled_quantity: float,
    *,
    stop_order_id: str | None = None,
    tp_order_id: str | None = None,
) -> OCOGroup:
    """Construit un groupe OCO."""
    return OCOGroup(
        oco_id=oco_id,
        symbol=symbol,
        side=side,
        parent_intent_id=parent_intent_id,
        stop_order_id=stop_order_id,
        tp_order_id=tp_order_id,
        protected_quantity=filled_quantity,
        filled_quantity=filled_quantity,
        status="active" if stop_order_id else "pending",
    )
