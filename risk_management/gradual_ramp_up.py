"""risk_management/gradual_ramp_up.py — Go-live progressif par paliers (Sprint Maître 14).

Gère la montée en charge progressive du capital :
5% → 10% → 25% → 50% → 100%

Chaque palier exige :
- Une fenêtre minimale d'observation
- Une revue humaine documentée
- Toutes les gates de la checklist pré-live vertes
- Aucun incident critique ouvert

Usage ::

    from risk_management.gradual_ramp_up import (
        RampUpStage, RampUpManager, RampUpConfig,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum


# ── RampUpStage ─────────────────────────────────────────────────────────────


class RampUpStage(StrEnum):
    """Palier de go-live progressif (Sprint Maître 14)."""

    SHADOW = "shadow"            # Shadow trading (pas d'ordres)
    PAPER = "paper"              # Paper trading (ordres simulés)
    LIVE_5PCT = "live_5pct"      # 5% du budget risque
    LIVE_10PCT = "live_10pct"    # 10%
    LIVE_25PCT = "live_25pct"    # 25%
    LIVE_50PCT = "live_50pct"    # 50%
    LIVE_100PCT = "live_100pct"  # 100% — pleine capacité

    @property
    def allocation_pct(self) -> float:
        """Fraction du budget risque allouée."""
        mapping: dict[RampUpStage, float] = {
            RampUpStage.SHADOW: 0.0,
            RampUpStage.PAPER: 0.0,
            RampUpStage.LIVE_5PCT: 0.05,
            RampUpStage.LIVE_10PCT: 0.10,
            RampUpStage.LIVE_25PCT: 0.25,
            RampUpStage.LIVE_50PCT: 0.50,
            RampUpStage.LIVE_100PCT: 1.00,
        }
        return mapping.get(self, 0.0)

    @property
    def is_live(self) -> bool:
        """True si le capital réel est engagé."""
        return self.allocation_pct > 0.0

    @property
    def requires_human_review(self) -> bool:
        """True si une revue humaine est obligatoire pour ce palier."""
        return self.is_live

    def next_stage(self) -> RampUpStage | None:
        """Palier suivant, ou None si déjà au maximum."""
        order = list(RampUpStage)
        idx = order.index(self)
        if idx + 1 < len(order):
            return order[idx + 1]
        return None

    def previous_stage(self) -> RampUpStage | None:
        """Palier précédent, ou None si premier."""
        order = list(RampUpStage)
        idx = order.index(self)
        if idx > 0:
            return order[idx - 1]
        return None


# ── RampUpConfig ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RampUpConfig:
    """Configuration du go-live progressif (Sprint Maître 14).

    Attributes
    ----------
    min_days_per_stage : dict[RampUpStage, int]
        Jours minimum par palier avant de pouvoir passer au suivant.
    require_checklist_pass : bool
        Si True, la checklist pré-live doit être 100% verte.
    require_shadow_convergence : bool
        Si True, le shadow doit être convergent avant le paper.
    require_no_critical_incidents : bool
        Si True, aucun incident critique ouvert n'est toléré.
    max_drawdown_per_stage : dict[RampUpStage, float]
        Drawdown max autorisé par palier (fraction).
    auto_rollback_on_breach : bool
        Si True, rollback automatique au palier précédent si drawdown dépassé.
    """

    min_days_per_stage: dict[RampUpStage, int] = field(default_factory=lambda: {
        RampUpStage.SHADOW: 28,
        RampUpStage.PAPER: 56,
        RampUpStage.LIVE_5PCT: 14,
        RampUpStage.LIVE_10PCT: 21,
        RampUpStage.LIVE_25PCT: 30,
        RampUpStage.LIVE_50PCT: 45,
        RampUpStage.LIVE_100PCT: 0,
    })

    require_checklist_pass: bool = True
    require_shadow_convergence: bool = True
    require_no_critical_incidents: bool = True
    auto_rollback_on_breach: bool = True

    max_drawdown_per_stage: dict[RampUpStage, float] = field(default_factory=lambda: {
        RampUpStage.SHADOW: 1.0,
        RampUpStage.PAPER: 1.0,
        RampUpStage.LIVE_5PCT: 0.05,
        RampUpStage.LIVE_10PCT: 0.05,
        RampUpStage.LIVE_25PCT: 0.10,
        RampUpStage.LIVE_50PCT: 0.10,
        RampUpStage.LIVE_100PCT: 0.15,
    })

    def get_min_days(self, stage: RampUpStage) -> int:
        return self.min_days_per_stage.get(stage, 0)

    def get_max_drawdown(self, stage: RampUpStage) -> float:
        return self.max_drawdown_per_stage.get(stage, 1.0)


# ── StageTransition ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class StageTransition:
    """Transition entre deux paliers (Sprint Maître 14)."""

    from_stage: RampUpStage
    to_stage: RampUpStage | None
    is_promotion: bool = False
    is_rollback: bool = False
    reason: str = ""
    days_in_stage: int = 0
    checklist_passed: bool = False
    human_reviewed: bool = False
    reviewer: str = ""
    transition_date: date | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "from_stage": self.from_stage.value,
            "to_stage": self.to_stage.value if self.to_stage else None,
            "is_promotion": self.is_promotion,
            "is_rollback": self.is_rollback,
            "reason": self.reason,
            "days_in_stage": self.days_in_stage,
            "checklist_passed": self.checklist_passed,
            "human_reviewed": self.human_reviewed,
            "reviewer": self.reviewer,
            "transition_date": self.transition_date.isoformat() if self.transition_date else None,
        }


# ── RampUpManager ───────────────────────────────────────────────────────────


@dataclass
class RampUpManager:
    """Gère la montée en charge progressive du capital (Sprint Maître 14).

    Règles :
    - Chaque palier a une durée minimale
    - Une revue humaine est obligatoire avant chaque promotion
    - Si le drawdown dépasse le seuil du palier → rollback automatique
    - La checklist pré-live doit être verte
    """

    config: RampUpConfig = field(default_factory=RampUpConfig)
    current_stage: RampUpStage = RampUpStage.SHADOW
    stage_started_at: date = field(default_factory=date.today)
    transitions: list[StageTransition] = field(default_factory=list)
    drawdown_current: float = 0.0
    open_incidents: int = 0

    @property
    def days_in_current_stage(self) -> int:
        return (date.today() - self.stage_started_at).days

    @property
    def current_allocation(self) -> float:
        return self.current_stage.allocation_pct

    def can_promote(
        self,
        *,
        checklist_passed: bool = True,
        shadow_convergent: bool = True,
        human_reviewer: str = "",
    ) -> tuple[bool, str]:
        """Vérifie si on peut passer au palier suivant.

        Returns
        -------
        (can_promote, reason)
        """
        next_stage = self.current_stage.next_stage()
        if next_stage is None:
            return False, "Déjà au palier maximum (LIVE_100PCT)"

        min_days = self.config.get_min_days(self.current_stage)
        if self.days_in_current_stage < min_days:
            remaining = min_days - self.days_in_current_stage
            return False, f"Fenêtre minimale non atteinte: {self.days_in_current_stage}/{min_days}j (reste {remaining}j)"

        if self.config.require_checklist_pass and not checklist_passed:
            return False, "Checklist pré-live non verte"

        if self.config.require_shadow_convergence and self.current_stage == RampUpStage.SHADOW and not shadow_convergent:
            return False, "Shadow non convergent — impossible de passer au paper"

        if self.config.require_no_critical_incidents and self.open_incidents > 0:
            return False, f"{self.open_incidents} incident(s) critique(s) ouvert(s)"

        if next_stage.requires_human_review and not human_reviewer:
            return False, "Revue humaine obligatoire pour ce palier"

        return True, f"Prêt pour {next_stage.value}"

    def promote(
        self,
        *,
        checklist_passed: bool = True,
        shadow_convergent: bool = True,
        human_reviewer: str = "",
    ) -> StageTransition:
        """Tente de promouvoir au palier suivant.

        Returns
        -------
        StageTransition
        """
        next_stage = self.current_stage.next_stage()
        can, reason = self.can_promote(
            checklist_passed=checklist_passed,
            shadow_convergent=shadow_convergent,
            human_reviewer=human_reviewer,
        )

        if not can:
            return StageTransition(
                from_stage=self.current_stage,
                to_stage=None,
                reason=reason,
                days_in_stage=self.days_in_current_stage,
                checklist_passed=checklist_passed,
                human_reviewed=bool(human_reviewer),
                reviewer=human_reviewer,
            )

        transition = StageTransition(
            from_stage=self.current_stage,
            to_stage=next_stage,
            is_promotion=True,
            reason=reason,
            days_in_stage=self.days_in_current_stage,
            checklist_passed=checklist_passed,
            human_reviewed=bool(human_reviewer),
            reviewer=human_reviewer,
            transition_date=date.today(),
        )

        self.transitions.append(transition)
        self.current_stage = next_stage  # type: ignore[assignment]
        self.stage_started_at = date.today()
        return transition

    def check_drawdown_breach(self, current_drawdown: float) -> StageTransition | None:
        """Vérifie si le drawdown actuel dépasse le seuil du palier.

        Si oui et si auto_rollback_on_breach → rollback automatique.
        """
        self.drawdown_current = current_drawdown
        max_dd = self.config.get_max_drawdown(self.current_stage)

        if current_drawdown <= max_dd:
            return None

        # Breach détecté
        if not self.config.auto_rollback_on_breach:
            return StageTransition(
                from_stage=self.current_stage,
                to_stage=None,
                reason=f"Drawdown {current_drawdown:.2%} > seuil {max_dd:.2%} — rollback auto désactivé",
                days_in_stage=self.days_in_current_stage,
            )

        return self.rollback(f"Drawdown {current_drawdown:.2%} > seuil palier {max_dd:.2%}")

    def rollback(self, reason: str) -> StageTransition | None:
        """Rollback au palier précédent."""
        prev = self.current_stage.previous_stage()
        if prev is None:
            return None

        transition = StageTransition(
            from_stage=self.current_stage,
            to_stage=prev,
            is_rollback=True,
            reason=reason,
            days_in_stage=self.days_in_current_stage,
            transition_date=date.today(),
        )

        self.transitions.append(transition)
        self.current_stage = prev
        self.stage_started_at = date.today()
        return transition

    def effective_risk_budget(self, base_budget: float) -> float:
        """Calcule le budget de risque effectif pour le palier actuel."""
        return base_budget * self.current_allocation

    def allocation_summary(self, account_equity: float) -> dict[str, object]:
        """Résumé de l'allocation actuelle."""
        return {
            "stage": self.current_stage.value,
            "allocation_pct": self.current_allocation,
            "effective_capital": round(account_equity * self.current_allocation, 2),
            "days_in_stage": self.days_in_current_stage,
            "min_days_required": self.config.get_min_days(self.current_stage),
            "drawdown_current": round(self.drawdown_current, 4),
            "drawdown_max": self.config.get_max_drawdown(self.current_stage),
            "open_incidents": self.open_incidents,
            "can_promote": self.can_promote()[0],
        }


# ── Helpers ─────────────────────────────────────────────────────────────────


def create_ramp_up_manager(
    start_stage: RampUpStage = RampUpStage.SHADOW,
    start_date: date | None = None,
) -> RampUpManager:
    """Crée un gestionnaire de ramp-up."""
    return RampUpManager(
        current_stage=start_stage,
        stage_started_at=start_date or date.today(),
    )
