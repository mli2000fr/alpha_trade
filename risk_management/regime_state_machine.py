"""risk_management/regime_state_machine.py — Machine d'états régime (Sprint Maître 9).

Formalise le contrat entre le régime marché et le moteur de risque.
La state machine est **pure** : pas d'I/O, pas de side effects.
Elle consomme un ``MarketRegimeSnapshot`` (depuis ``service.market``) et
produit des décisions de risque (actions de transition, contraintes).

États canoniques (alignés avec ``service.market.models.RegimeMode``) :
- ``NORMAL`` : comportement nominal, toutes les stratégies actives
- ``WARNING`` : signaux faibles, contraintes soft actives, entrées réduites
- ``CAPITAL_PRESERVATION`` : risque réduit, shorts hedging autorisés, longs bloqués
- ``RECOVERY`` : sortie progressive du mode défensif, ramp-up contrôlé

Usage ::

    from risk_management.regime_state_machine import (
        RegimeState, RegimeStateMachine, TransitionAction, RegimeTransition,
    )
    sm = RegimeStateMachine()
    transition = sm.evaluate_transition(previous_snapshot, current_snapshot)
    if transition.action == TransitionAction.LIQUIDATE:
        liquidate_all_positions()
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from service.market.models import MarketRegimeSnapshot


# ── RegimeState ─────────────────────────────────────────────────────────────


class RegimeState(StrEnum):
    """États canoniques de la state machine régime (Sprint Maître 9).

    Alignés avec ``service.market.models.RegimeMode`` mais enrichis
    de ``WARNING`` et ``RECOVERY`` pour granularité risque.
    """

    NORMAL = "normal"
    WARNING = "warning"
    CAPITAL_PRESERVATION = "capital_preservation"
    CLOSE_ONLY = "close_only"
    CASH_ONLY = "cash_only"
    RECOVERY = "recovery"

    # ── Classification ──────────────────────────────────────────────────

    @property
    def is_defensive(self) -> bool:
        """True si le régime est défensif (risque réduit, contraintes actives)."""
        return self in (
            RegimeState.WARNING,
            RegimeState.CAPITAL_PRESERVATION,
            RegimeState.CLOSE_ONLY,
            RegimeState.CASH_ONLY,
        )

    @property
    def is_blocking_entries(self) -> bool:
        """True si les nouvelles entrées sont bloquées."""
        return self in (RegimeState.CLOSE_ONLY, RegimeState.CASH_ONLY)

    @property
    def allows_long(self) -> bool:
        return self == RegimeState.NORMAL

    @property
    def allows_short(self) -> bool:
        return self in (
            RegimeState.NORMAL,
            RegimeState.WARNING,
            RegimeState.CAPITAL_PRESERVATION,
        )

    @property
    def requires_exit_management(self) -> bool:
        """True si les sorties doivent être gérées activement (stops, trailing)."""
        return self.is_defensive

    # ── Conversion depuis/vers service.market ───────────────────────────

    @classmethod
    def from_regime_mode(cls, mode: str) -> RegimeState:
        """Convertit un ``RegimeMode`` (service.market) en ``RegimeState``."""
        mapping: dict[str, RegimeState] = {
            "normal": cls.NORMAL,
            "capital_preservation": cls.CAPITAL_PRESERVATION,
            "close_only": cls.CLOSE_ONLY,
            "cash_only": cls.CASH_ONLY,
        }
        return mapping.get(mode, cls.NORMAL)

    def to_regime_mode(self) -> str:
        """Convertit en ``RegimeMode`` pour compatibilité service.market."""
        mapping: dict[RegimeState, str] = {
            RegimeState.NORMAL: "normal",
            RegimeState.WARNING: "normal",  # WARNING → normal pour service.market
            RegimeState.CAPITAL_PRESERVATION: "capital_preservation",
            RegimeState.CLOSE_ONLY: "close_only",
            RegimeState.CASH_ONLY: "cash_only",
            RegimeState.RECOVERY: "normal",  # RECOVERY → normal avec ramp-up
        }
        return mapping.get(self, "normal")


# ── TransitionAction ────────────────────────────────────────────────────────


class TransitionAction(StrEnum):
    """Action à entreprendre lors d'une transition de régime (Sprint Maître 9).

    Ordonnées par sévérité croissante.
    """

    NO_OP = "no_op"               # Aucun changement
    BLOCK_ENTRY = "block_entry"   # Bloquer nouvelles entrées (longs et/ou shorts)
    REDUCE = "reduce"             # Réduire positions existantes (partial close)
    HEDGE = "hedge"               # Ouvrir hedges (shorts contre longs existants)
    LIQUIDATE_LONGS = "liquidate_longs"   # Liquider tous les longs
    LIQUIDATE_SHORTS = "liquidate_shorts" # Liquider tous les shorts
    LIQUIDATE_ALL = "liquidate_all"       # Liquider toutes les positions
    CLOSE_ONLY = "close_only"     # Gérer sorties uniquement, pas d'entrées
    CASH_ONLY = "cash_only"       # Aucune activité de trading

    @property
    def is_destructive(self) -> bool:
        """True si l'action détruit des positions existantes."""
        return self in (
            TransitionAction.REDUCE,
            TransitionAction.LIQUIDATE_LONGS,
            TransitionAction.LIQUIDATE_SHORTS,
            TransitionAction.LIQUIDATE_ALL,
        )

    @property
    def blocks_new_entries(self) -> bool:
        """True si l'action bloque les nouvelles entrées."""
        return self in (
            TransitionAction.BLOCK_ENTRY,
            TransitionAction.CLOSE_ONLY,
            TransitionAction.CASH_ONLY,
            TransitionAction.LIQUIDATE_ALL,
        )


# ── RegimeTransition ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RegimeTransition:
    """Résultat d'une évaluation de transition de régime (Sprint Maître 9).

    Attributes
    ----------
    from_state : RegimeState
        État précédent.
    to_state : RegimeState
        Nouvel état.
    action : TransitionAction
        Action à exécuter.
    reason : str
        Raison lisible de la transition.
    hysteresis_applied : bool
        True si l'hystérésis a influencé la décision.
    min_hold_remaining : int | None
        Jours restants avant la prochaine transition autorisée (si applicable).
    risk_multiplier : float
        Multiplicateur de risque pour le sizing (1.0 = nominal).
    max_gross_exposure : float | None
        Exposition brute maximale autorisée.
    allow_new_entries : bool
        Nouvelles entrées autorisées.
    allow_long : bool
        Longs autorisés.
    allow_short : bool
        Shorts autorisés.
    """

    from_state: RegimeState
    to_state: RegimeState
    action: TransitionAction
    reason: str = ""
    hysteresis_applied: bool = False
    min_hold_remaining: int | None = None
    risk_multiplier: float = 1.0
    max_gross_exposure: float | None = None
    allow_new_entries: bool = True
    allow_long: bool = True
    allow_short: bool = False

    @property
    def is_transition(self) -> bool:
        """True si l'état a changé."""
        return self.from_state != self.to_state

    @property
    def is_escalation(self) -> bool:
        """True si la sévérité augmente (normal → défensif)."""
        severity = {
            RegimeState.NORMAL: 0,
            RegimeState.RECOVERY: 1,
            RegimeState.WARNING: 2,
            RegimeState.CAPITAL_PRESERVATION: 3,
            RegimeState.CLOSE_ONLY: 4,
            RegimeState.CASH_ONLY: 5,
        }
        return severity.get(self.to_state, 0) > severity.get(self.from_state, 0)

    @property
    def is_deescalation(self) -> bool:
        """True si la sévérité diminue (défensif → normal)."""
        return not self.is_escalation and self.is_transition

    def to_dict(self) -> dict[str, object]:
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "action": self.action.value,
            "reason": self.reason,
            "hysteresis_applied": self.hysteresis_applied,
            "min_hold_remaining": self.min_hold_remaining,
            "risk_multiplier": self.risk_multiplier,
            "max_gross_exposure": self.max_gross_exposure,
            "allow_new_entries": self.allow_new_entries,
            "allow_long": self.allow_long,
            "allow_short": self.allow_short,
            "is_transition": self.is_transition,
            "is_escalation": self.is_escalation,
        }


# ── RegimeStateMachine ──────────────────────────────────────────────────────


@dataclass
class RegimeStateMachine:
    """Machine d'états pure pour le régime marché (Sprint Maître 9).

    Évalue les transitions entre états et produit des ``RegimeTransition``.
    Implémente l'hystérésis et les durées minimales.

    Parameters
    ----------
    min_hold_days_defensive : int
        Durée minimale en mode défensif avant de pouvoir en sortir.
    enter_confirm_days : int
        Jours consécutifs de signaux soft pour entrer en défensif.
    exit_confirm_days : int
        Jours consécutifs de calme pour sortir du défensif.
    hard_exit_confirm_days : int
        Jours de calme requis après un hard trigger.
    """

    min_hold_days_defensive: int = 5
    enter_confirm_days: int = 2
    exit_confirm_days: int = 3
    hard_exit_confirm_days: int = 2

    def evaluate_transition(
        self,
        current_state: RegimeState,
        target_state: RegimeState,
        *,
        days_in_current_mode: int = 0,
        soft_entry_streak: int = 0,
        soft_exit_streak: int = 0,
        hard_calm_streak: int = 0,
        hard_triggered: bool = False,
        hard_trigger_immediate: bool = True,
    ) -> RegimeTransition:
        """Évalue la transition d'état selon les règles d'hystérésis.

        Parameters
        ----------
        current_state : RegimeState
            État actuel.
        target_state : RegimeState
            État cible proposé par le moteur de détection.
        days_in_current_mode : int
            Jours passés dans l'état actuel.
        soft_entry_streak : int
            Jours consécutifs avec signaux soft d'entrée en défensif.
        soft_exit_streak : int
            Jours consécutifs sans signaux (calme).
        hard_calm_streak : int
            Jours depuis le dernier hard trigger.
        hard_triggered : bool
            True si un hard trigger est actif aujourd'hui.
        hard_trigger_immediate : bool
            Si True, les hard triggers bypassent l'hystérésis.

        Returns
        -------
        RegimeTransition
        """
        # ── Pas de changement ──────────────────────────────────────────
        if target_state == current_state:
            return RegimeTransition(
                from_state=current_state,
                to_state=current_state,
                action=TransitionAction.NO_OP,
                reason=f"maintien en {current_state.value}",
            )

        # ── Escalade (normal → défensif) ───────────────────────────────
        if (
            current_state == RegimeState.NORMAL
            and target_state.is_defensive
        ):
            # Hard trigger → immédiat
            if hard_triggered and hard_trigger_immediate:
                return self._build_escalation(
                    current_state, target_state,
                    reason="hard_trigger_immediate",
                )

            # Soft entry → besoin de confirmation
            if soft_entry_streak < self.enter_confirm_days:
                return RegimeTransition(
                    from_state=current_state,
                    to_state=current_state,
                    action=TransitionAction.NO_OP,
                    reason=(
                        f"entrée défensive en attente "
                        f"(streak={soft_entry_streak}/{self.enter_confirm_days})"
                    ),
                    hysteresis_applied=True,
                )
            return self._build_escalation(
                current_state, target_state,
                reason=f"soft_entry_confirmed (streak={soft_entry_streak})",
                hysteresis_applied=True,
            )

        # ── Escalade intra-défensif ────────────────────────────────────
        if current_state.is_defensive and target_state.is_defensive:
            # Hard trigger immédiat vers état plus sévère
            if hard_triggered and hard_trigger_immediate:
                return self._build_escalation(
                    current_state, target_state,
                    reason="hard_trigger_escalation",
                )
            return self._build_escalation(
                current_state, target_state,
                reason="escalation_intra_defensive",
                hysteresis_applied=True,
            )

        # ── Désescalade (défensif → normal) ────────────────────────────
        if current_state.is_defensive and target_state == RegimeState.NORMAL:
            # Min hold non atteint
            if days_in_current_mode < self.min_hold_days_defensive:
                remaining = self.min_hold_days_defensive - days_in_current_mode
                return RegimeTransition(
                    from_state=current_state,
                    to_state=current_state,
                    action=TransitionAction.NO_OP,
                    reason=(
                        f"min_hold non atteint "
                        f"({days_in_current_mode}/{self.min_hold_days_defensive}j)"
                    ),
                    hysteresis_applied=True,
                    min_hold_remaining=remaining,
                )

            # Hard exit : besoin de calm streak
            required_calm = self.hard_exit_confirm_days if hard_calm_streak > 0 else 0
            calm_ok = (
                hard_calm_streak >= self.hard_exit_confirm_days
                if required_calm > 0
                else soft_exit_streak >= self.exit_confirm_days
            )

            if not calm_ok:
                return RegimeTransition(
                    from_state=current_state,
                    to_state=current_state,
                    action=TransitionAction.NO_OP,
                    reason=(
                        f"sortie défensive en attente "
                        f"(exit_streak={soft_exit_streak}/{self.exit_confirm_days}, "
                        f"calm={hard_calm_streak}/{self.hard_exit_confirm_days})"
                    ),
                    hysteresis_applied=True,
                )

            return self._build_deescalation(
                current_state,
                reason=f"sortie confirmée (exit={soft_exit_streak}, calm={hard_calm_streak})",
                hysteresis_applied=True,
            )

        # ── Fallback ───────────────────────────────────────────────────
        return RegimeTransition(
            from_state=current_state,
            to_state=target_state,
            action=TransitionAction.NO_OP,
            reason=f"transition non gérée: {current_state.value} → {target_state.value}",
        )

    def evaluate_from_snapshot(
        self,
        previous_state: RegimeState,
        snapshot: MarketRegimeSnapshot,
    ) -> RegimeTransition:
        """Évalue la transition à partir d'un ``MarketRegimeSnapshot``.

        C'est le point d'entrée principal pour la consommation côté risque.
        """
        target = RegimeState.from_regime_mode(snapshot.mode)

        # Si on est en WARNING et que le snapshot dit "normal" → on doit
        # vérifier si les contraintes soft sont encore actives
        if target == RegimeState.NORMAL and snapshot.soft_constraints_active:
            target = RegimeState.WARNING

        # Si on est en RECOVERY → on y reste tant que le ramp-up n'est pas fini
        # (géré par CircuitBreaker.allocation_scale)

        transition = self.evaluate_transition(
            current_state=previous_state,
            target_state=target,
            days_in_current_mode=snapshot.state_age_days or 0,
            soft_entry_streak=snapshot.soft_signal_count or 0,
            soft_exit_streak=0,  # Pas directement exposé par snapshot
            hard_calm_streak=0,  # Pas directement exposé
            hard_triggered=snapshot.hard_triggered,
        )
        if transition.to_state != target or transition.is_transition:
            return transition

        # Une transition NO_OP ne signifie pas que les permissions redeviennent
        # nominales. L'état déjà actif doit conserver ses plafonds et ses
        # autorisations tant qu'il est maintenu.
        return RegimeTransition(
            from_state=transition.from_state,
            to_state=transition.to_state,
            action=transition.action,
            reason=transition.reason,
            hysteresis_applied=transition.hysteresis_applied,
            min_hold_remaining=transition.min_hold_remaining,
            risk_multiplier=self._risk_multiplier_for_state(target),
            max_gross_exposure=self._max_gross_for_state(target),
            allow_new_entries=not target.is_blocking_entries,
            allow_long=target.allows_long,
            allow_short=target.allows_short,
        )

    # ── Helpers ─────────────────────────────────────────────────────────

    def _build_escalation(
        self,
        from_state: RegimeState,
        to_state: RegimeState,
        *,
        reason: str,
        hysteresis_applied: bool = False,
    ) -> RegimeTransition:
        """Construit une transition d'escalade avec les contraintes appropriées."""
        action = self._action_for_state(to_state)
        return RegimeTransition(
            from_state=from_state,
            to_state=to_state,
            action=action,
            reason=reason,
            hysteresis_applied=hysteresis_applied,
            risk_multiplier=self._risk_multiplier_for_state(to_state),
            max_gross_exposure=self._max_gross_for_state(to_state),
            allow_new_entries=not to_state.is_blocking_entries,
            allow_long=to_state.allows_long,
            allow_short=to_state.allows_short,
        )

    def _build_deescalation(
        self,
        from_state: RegimeState,
        *,
        reason: str,
        hysteresis_applied: bool = False,
    ) -> RegimeTransition:
        """Construit une transition de désescalade vers NORMAL."""
        return RegimeTransition(
            from_state=from_state,
            to_state=RegimeState.RECOVERY,
            action=TransitionAction.NO_OP,
            reason=reason,
            hysteresis_applied=hysteresis_applied,
            risk_multiplier=0.5,  # Ramp-up progressif
            max_gross_exposure=0.5,
            allow_new_entries=True,
            allow_long=True,
            allow_short=False,
        )

    @staticmethod
    def _action_for_state(state: RegimeState) -> TransitionAction:
        """Détermine l'action de transition pour un état cible."""
        mapping: dict[RegimeState, TransitionAction] = {
            RegimeState.NORMAL: TransitionAction.NO_OP,
            RegimeState.WARNING: TransitionAction.REDUCE,
            RegimeState.CAPITAL_PRESERVATION: TransitionAction.LIQUIDATE_LONGS,
            RegimeState.CLOSE_ONLY: TransitionAction.CLOSE_ONLY,
            RegimeState.CASH_ONLY: TransitionAction.CASH_ONLY,
            RegimeState.RECOVERY: TransitionAction.NO_OP,
        }
        return mapping.get(state, TransitionAction.NO_OP)

    @staticmethod
    def _risk_multiplier_for_state(state: RegimeState) -> float:
        mapping: dict[RegimeState, float] = {
            RegimeState.NORMAL: 1.0,
            RegimeState.WARNING: 0.7,
            RegimeState.CAPITAL_PRESERVATION: 0.3,
            RegimeState.CLOSE_ONLY: 0.0,
            RegimeState.CASH_ONLY: 0.0,
            RegimeState.RECOVERY: 0.5,
        }
        return mapping.get(state, 1.0)

    @staticmethod
    def _max_gross_for_state(state: RegimeState) -> float | None:
        mapping: dict[RegimeState, float | None] = {
            RegimeState.NORMAL: None,  # Pas de limite (utilise config)
            RegimeState.WARNING: 0.80,
            RegimeState.CAPITAL_PRESERVATION: 0.30,
            RegimeState.CLOSE_ONLY: 0.0,
            RegimeState.CASH_ONLY: 0.0,
            RegimeState.RECOVERY: 0.50,
        }
        return mapping.get(state)


# ── Helpers ─────────────────────────────────────────────────────────────────


def compute_regime_transition(
    previous_mode: str,
    current_snapshot: MarketRegimeSnapshot,
    *,
    min_hold_days: int = 5,
) -> RegimeTransition:
    """Fonction pure d'évaluation de transition (sans état persistant).

    Utile pour le backtesting et les tests unitaires.
    """
    sm = RegimeStateMachine(min_hold_days_defensive=min_hold_days)
    prev = RegimeState.from_regime_mode(previous_mode)
    return sm.evaluate_from_snapshot(prev, current_snapshot)
