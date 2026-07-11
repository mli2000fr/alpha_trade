"""risk_management/pre_live_checklist.py — Checklist pré-live et go-live progressif (Sprint Maître 14).

Agrège toutes les gates des sprints 0-13 en une checklist GO/NO-GO formelle.
Chaque gate doit être vérifiée avant de passer au palier suivant.

Usage ::

    from risk_management.pre_live_checklist import (
        PreLiveChecklist, ChecklistGate, GateStatus, GoLiveGate,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


# ── GateStatus ──────────────────────────────────────────────────────────────


class GateStatus(StrEnum):
    """Statut d'une gate de la checklist (Sprint Maître 14)."""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"


# ── ChecklistGate ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ChecklistGate:
    """Une gate de la checklist pré-live (Sprint Maître 14).

    Attributes
    ----------
    gate_id : str
        Identifiant unique de la gate.
    name : str
        Nom lisible.
    category : str
        Catégorie (parity, data, risk, execution, protection, mlops, operations).
    sprint : int
        Sprint maître d'origine.
    status : GateStatus
    detail : str
        Détail du résultat.
    checked_at : datetime | None
    checked_by : str
    """

    gate_id: str
    name: str = ""
    category: str = "general"
    sprint: int = 0
    status: GateStatus = GateStatus.PENDING
    detail: str = ""
    checked_at: datetime | None = None
    checked_by: str = ""

    @property
    def is_blocking(self) -> bool:
        """True si cette gate est bloquante (FAILED → NO-GO)."""
        return self.status == GateStatus.FAILED

    def to_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "category": self.category,
            "sprint": self.sprint,
            "status": self.status.value,
            "detail": self.detail,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "checked_by": self.checked_by,
        }


# ── GoLiveGate ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class GoLiveGate:
    """Gate de go-live pour un palier de capital (Sprint Maître 14).

    Agrège toutes les checklist gates et détermine si le palier peut être franchi.
    """

    stage: str  # "shadow", "paper", "live_5pct", "live_10pct", ...
    gates: tuple[ChecklistGate, ...] = ()
    all_passed: bool = True
    blocking_gates: tuple[str, ...] = ()
    warning_gates: tuple[str, ...] = ()
    recommended_action: str = ""
    reviewed_by: str = ""
    reviewed_at: datetime | None = None

    @property
    def go(self) -> bool:
        return self.all_passed and len(self.blocking_gates) == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "go": self.go,
            "all_passed": self.all_passed,
            "blocking_gates": list(self.blocking_gates),
            "warning_gates": list(self.warning_gates),
            "recommended_action": self.recommended_action,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "gates": [g.to_dict() for g in self.gates],
        }


# ── PreLiveChecklist ────────────────────────────────────────────────────────


@dataclass
class PreLiveChecklist:
    """Checklist pré-live formelle (Sprint Maître 14).

    Définit les gates canoniques à vérifier avant chaque palier.
    Les gates sont organisées par catégorie et sprint d'origine.

    Palier 1 — SHADOW (4 semaines min) :
    - Le modèle tourne en parallèle, pas d'ordres
    - Vérifier : disponibilité features, latence, couverture, staleness

    Palier 2 — PAPER (8-12 semaines min) :
    - Ordres envoyés au broker paper
    - Vérifier : fills, partial fills, slippage, rejets, borrow, protections

    Palier 3 — LIVE 5% → 10% → 25% → 50% → 100% :
    - Capital réel progressif
    - Vérifier : PnL, drawdown, coûts, calibration par cohorte
    """

    # ── Gates canoniques (tous les sprints 0-13) ───────────────────────

    CANONICAL_GATES: tuple[ChecklistGate, ...] = (
        # Sprint 0 — Baseline et décision ternaire
        ChecklistGate("S00_PARITY", "Parité side décision", "parity", 0),
        ChecklistGate("S00_RESEARCH", "Blocage research_only", "parity", 0),

        # Sprint 1 — Métriques et calibration
        ChecklistGate("S01_METRICS", "Métriques valides (AUC, Brier, NLL)", "mlops", 1),
        ChecklistGate("S01_COLLAPSE", "Anti-collapse actif", "mlops", 1),

        # Sprint 2 — Données PIT
        ChecklistGate("S02_FUTURE", "Zéro donnée future", "data", 2),
        ChecklistGate("S02_SURVIVORSHIP", "Univers sans survivorship bias", "data", 2),

        # Sprint 3 — Labels swing
        ChecklistGate("S03_LABELS", "Triple-barrier labels valides", "data", 3),

        # Sprint 4 — Benchmark
        ChecklistGate("S04_BENCHMARK", "Modèle > baselines", "mlops", 4),

        # Sprint 5 — Contrat ML→Risque
        ChecklistGate("S05_CONTRACT", "MLRankedCandidate contrat respecté", "parity", 5),
        ChecklistGate("S05_NO_RESCORING", "Aucun rescoring selector", "parity", 5),

        # Sprint 6 — Contraintes directionnelles
        ChecklistGate("S06_CAPS", "Caps long/short respectés", "risk", 6),
        ChecklistGate("S06_ADV", "ADV fail-closed", "risk", 6),
        ChecklistGate("S06_FINGERPRINT", "Config fingerprint stable", "risk", 6),

        # Sprint 7 — Walk-forward
        ChecklistGate("S07_SHARPE", "Sharpe OOS > seuil", "risk", 7),
        ChecklistGate("S07_HOLDOUT", "Holdout externe intact", "risk", 7),

        # Sprint 8 — Edge net
        ChecklistGate("S08_EDGE", "Edge net positif obligatoire", "risk", 8),
        ChecklistGate("S08_ABSTENTION", "Abstention policy active", "risk", 8),

        # Sprint 9 — Régime
        ChecklistGate("S09_HYSTERESIS", "Hystérésis régime active", "risk", 9),
        ChecklistGate("S09_FAIL_CLOSED", "Fail-closed sur données critiques", "risk", 9),

        # Sprint 10 — Liquidité
        ChecklistGate("S10_BORROW", "100% shorts avec borrow validé", "risk", 10),
        ChecklistGate("S10_ADV_FRESH", "ADV frais pour toutes les entrées", "risk", 10),

        # Sprint 11 — Optimisation portefeuille
        ChecklistGate("S11_CONSTRAINTS", "Toutes contraintes signées satisfaites", "risk", 11),
        ChecklistGate("S11_TURNOVER", "Turnover sous budget", "risk", 11),

        # Sprint 12 — Parité et protections
        ChecklistGate("S12_PARITY", "Parité replay/live 100%", "parity", 12),
        ChecklistGate("S12_PROTECTION", "100% positions protégées dans SLA", "protection", 12),
        ChecklistGate("S12_STOP_SIDE", "Stops du bon côté (long bas, short haut)", "protection", 12),
        ChecklistGate("S12_OCO", "OCO quantités = fills", "protection", 12),

        # Sprint 13 — MLOps
        ChecklistGate("S13_REGISTRY", "Modèle enregistré avec statut valide", "mlops", 13),
        ChecklistGate("S13_FRESHNESS", "Fraîcheur données/modèle/calibration OK", "mlops", 13),
        ChecklistGate("S13_DRIFT", "Pas de drift sévère (ALERT)", "mlops", 13),
        ChecklistGate("S13_ROLLBACK", "Rollback testé et fonctionnel", "mlops", 13),

        # Opérations
        ChecklistGate("OPS_KILL_SWITCH", "Kill switch testé", "operations", 0),
        ChecklistGate("OPS_BACKUP", "Backup DB valide < 24h", "operations", 0),
        ChecklistGate("OPS_ALERTS", "Alertes configurées et testées", "operations", 0),
        ChecklistGate("OPS_WATCHER", "Protection watcher actif", "operations", 0),
        ChecklistGate("OPS_PREFLIGHT", "Pre-flight checks tous verts", "operations", 0),
    )

    def build_checklist(self, stage: str) -> GoLiveGate:
        """Construit la checklist pour un palier donné.

        Parameters
        ----------
        stage : str
            "shadow", "paper", "live_5pct", "live_10pct", "live_25pct",
            "live_50pct", "live_100pct"

        Returns
        -------
        GoLiveGate
        """
        # Toutes les gates sont requises pour tous les paliers
        return GoLiveGate(
            stage=stage,
            gates=self.CANONICAL_GATES,
            all_passed=True,  # Sera mis à jour après vérification
            recommended_action=f"Vérifier les {len(self.CANONICAL_GATES)} gates avant le palier {stage}",
        )

    def evaluate(self, gate_results: dict[str, GateStatus], stage: str = "live_5pct") -> GoLiveGate:
        """Évalue la checklist avec des résultats de gates.

        Parameters
        ----------
        gate_results : dict[str, GateStatus]
            Mapping gate_id → statut.
        stage : str

        Returns
        -------
        GoLiveGate
        """
        updated_gates: list[ChecklistGate] = []
        blocking: list[str] = []
        warnings: list[str] = []

        for gate in self.CANONICAL_GATES:
            status = gate_results.get(gate.gate_id, GateStatus.PENDING)
            new_gate = ChecklistGate(
                gate_id=gate.gate_id,
                name=gate.name,
                category=gate.category,
                sprint=gate.sprint,
                status=status,
                detail=f"Statut: {status.value}",
                checked_at=datetime.now(),
            )
            updated_gates.append(new_gate)
            if status == GateStatus.FAILED:
                blocking.append(gate.gate_id)
            elif status == GateStatus.PENDING:
                warnings.append(gate.gate_id)

        all_passed = len(blocking) == 0 and len(warnings) == 0

        action = "GO — toutes les gates sont vertes"
        if blocking:
            action = f"NO-GO — {len(blocking)} gates bloquantes: {', '.join(blocking)}"
        elif warnings:
            action = f"ATTENTION — {len(warnings)} gates en attente: {', '.join(warnings)}"

        return GoLiveGate(
            stage=stage,
            gates=tuple(updated_gates),
            all_passed=all_passed,
            blocking_gates=tuple(blocking),
            warning_gates=tuple(warnings),
            recommended_action=action,
        )

    def gates_by_category(self) -> dict[str, list[ChecklistGate]]:
        """Regroupe les gates par catégorie."""
        cats: dict[str, list[ChecklistGate]] = {}
        for gate in self.CANONICAL_GATES:
            cats.setdefault(gate.category, []).append(gate)
        return cats

    def gates_by_sprint(self) -> dict[int, list[ChecklistGate]]:
        """Regroupe les gates par sprint."""
        sprints: dict[int, list[ChecklistGate]] = {}
        for gate in self.CANONICAL_GATES:
            sprints.setdefault(gate.sprint, []).append(gate)
        return sprints


# ── Helpers ─────────────────────────────────────────────────────────────────


def build_pre_live_checklist(stage: str = "shadow") -> GoLiveGate:
    """Construit la checklist pré-live pour un palier."""
    checklist = PreLiveChecklist()
    return checklist.build_checklist(stage)


def evaluate_pre_live_gates(
    gate_results: dict[str, GateStatus],
    stage: str = "live_5pct",
) -> GoLiveGate:
    """Évalue les résultats des gates."""
    checklist = PreLiveChecklist()
    return checklist.evaluate(gate_results, stage)
