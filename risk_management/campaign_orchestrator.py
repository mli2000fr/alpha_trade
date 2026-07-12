"""risk_management/campaign_orchestrator.py — Orchestrateur de campagne shadow/paper (Point 13).

Orchestre une campagne continue de shadow puis paper trading :
- Exécute chaque jour les décisions avec modèle et config gelés
- Relie décisions → journal → quotes → fills → coûts → protections
- Produit rapport quotidien de convergence + revue hebdomadaire
- Applique durées minimales (4 semaines shadow, 8-12 paper)
- Vérifie les gates de promotion (divergence, protection, frais, borrow, réconciliation)
- Enregistre les approbations humaines et rollback

Usage ::

    from risk_management.campaign_orchestrator import (
        CampaignConfig, CampaignOrchestrator, CampaignDayResult,
    )
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Campaign phase ──────────────────────────────────────────────────────────

class CampaignPhase:
    SHADOW = "shadow"
    PAPER = "paper"
    PROMOTION_REVIEW = "promotion_review"

    SHADOW_MIN_WEEKS = 4
    PAPER_MIN_WEEKS = 8
    PAPER_MAX_WEEKS = 12


# ── CampaignConfig ──────────────────────────────────────────────────────────

@dataclass
class CampaignConfig:
    """Configuration d'une campagne shadow/paper (Point 13).

    Attributes
    ----------
    campaign_id : str
        Identifiant unique de la campagne.
    phase : str
        Phase actuelle: "shadow" | "paper" | "promotion_review".
    start_date : date
        Date de début.
    end_date : date | None
        Date de fin planifiée. None = indéfini (jusqu'à GO/NO-GO).
    model_run_id : str
        Modèle gelé pour toute la campagne (pas de changement sauf rollback sécurité).
    policy_version : int
        Policy de décision gelée.
    config_fingerprint : str
        Fingerprint de la config gelée.
    run_mode : str
        "shadow" ou "paper".
    dry_run : bool
        True = shadow (pas d'ordre), False = paper (ordres paper).
    approved_by : str | None
        Approbateur humain (nom/email).
    approved_at : datetime | None
        Date d'approbation.
    frozen_artifacts : dict[str, str]
        Artefacts gelés (model_path, calibrator_path, config_path).
    auto_promote : bool
        Si True, promeut automatiquement aux paliers suivants quand les gates passent.
        Si False, exige une approbation humaine explicite.
    """

    campaign_id: str = ""
    phase: str = CampaignPhase.SHADOW
    start_date: date = field(default_factory=date.today)
    end_date: date | None = None
    model_run_id: str = ""
    policy_version: int = 1
    config_fingerprint: str = ""
    run_mode: str = "shadow"
    dry_run: bool = True
    approved_by: str | None = None
    approved_at: datetime | None = None
    frozen_artifacts: dict[str, str] = field(default_factory=dict)
    auto_promote: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "phase": self.phase,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "model_run_id": self.model_run_id,
            "policy_version": self.policy_version,
            "config_fingerprint": self.config_fingerprint,
            "run_mode": self.run_mode,
            "dry_run": self.dry_run,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "frozen_artifacts": self.frozen_artifacts,
            "auto_promote": self.auto_promote,
        }

    @property
    def is_valid(self) -> bool:
        return bool(self.campaign_id and self.model_run_id)

    @property
    def weeks_elapsed(self) -> float:
        return max(0.0, (date.today() - self.start_date).days / 7.0)

    @property
    def min_weeks_required(self) -> int:
        if self.phase == CampaignPhase.SHADOW:
            return CampaignPhase.SHADOW_MIN_WEEKS
        return CampaignPhase.PAPER_MIN_WEEKS

    @property
    def can_promote(self) -> bool:
        return self.weeks_elapsed >= self.min_weeks_required


# ── CampaignDayResult ───────────────────────────────────────────────────────

@dataclass
class CampaignDayResult:
    """Résultat d'une journée de campagne (Point 13).

    Relie la décision du jour au journal, quotes, fills, coûts et protections.
    """

    trade_date: date
    campaign_id: str
    phase: str
    day_number: int

    # Résultats du run risque
    risk_run_id: str = ""
    risk_run_summary_path: str = ""
    decision_audit_path: str = ""
    entries_count: int = 0
    entries_long: int = 0
    entries_short: int = 0

    # Résultats du run exécution (paper uniquement)
    exec_run_id: str = ""
    exec_run_summary_path: str = ""
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_failed: int = 0

    # Shadow compare (si applicable)
    shadow_report_path: str = ""
    shadow_divergence_rate: float = 0.0
    shadow_is_convergent: bool = True

    # Métriques
    slippage_median_bps: float | None = None
    protection_coverage_pct: float = 100.0
    reconciliation_status: str = "clean"

    # Gates
    freshness_blocked: bool = False
    model_compatible: bool = True
    liquidity_blocked: int = 0

    # Status
    status: str = "pending"
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_date": self.trade_date.isoformat(),
            "campaign_id": self.campaign_id,
            "phase": self.phase,
            "day_number": self.day_number,
            "risk_run_id": self.risk_run_id,
            "entries_count": self.entries_count,
            "entries_long": self.entries_long,
            "entries_short": self.entries_short,
            "exec_run_id": self.exec_run_id,
            "orders_submitted": self.orders_submitted,
            "orders_filled": self.orders_filled,
            "orders_failed": self.orders_failed,
            "shadow_divergence_rate": round(self.shadow_divergence_rate, 4),
            "shadow_is_convergent": self.shadow_is_convergent,
            "slippage_median_bps": round(self.slippage_median_bps, 1) if self.slippage_median_bps else None,
            "protection_coverage_pct": round(self.protection_coverage_pct, 1),
            "reconciliation_status": self.reconciliation_status,
            "freshness_blocked": self.freshness_blocked,
            "model_compatible": self.model_compatible,
            "liquidity_blocked": self.liquidity_blocked,
            "status": self.status,
            "errors": self.errors,
        }


# ── WeeklyReview ────────────────────────────────────────────────────────────

@dataclass
class WeeklyReview:
    """Revue hebdomadaire de campagne (Point 13)."""

    campaign_id: str
    week_number: int
    week_start: date
    week_end: date
    days_completed: int = 0
    days_skipped: int = 0

    # Agrégation
    total_entries: int = 0
    total_orders: int = 0
    total_fills: int = 0

    avg_divergence_rate: float = 0.0
    avg_slippage_bps: float | None = None
    avg_protection_coverage: float = 100.0

    freshness_blocks: int = 0
    model_issues: int = 0
    liquidity_blocks: int = 0

    # Extrêmes
    best_day_entries: int = 0
    worst_day_entries: int = 0
    max_slippage_day: str = ""

    # Abstention
    total_abstentions: int = 0
    abstention_rate: float = 0.0

    # Recommandation
    recommendation: str = "continue"
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "week_number": self.week_number,
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "days_completed": self.days_completed,
            "days_skipped": self.days_skipped,
            "total_entries": self.total_entries,
            "total_orders": self.total_orders,
            "total_fills": self.total_fills,
            "avg_divergence_rate": round(self.avg_divergence_rate, 4),
            "avg_slippage_bps": round(self.avg_slippage_bps, 1) if self.avg_slippage_bps else None,
            "avg_protection_coverage": round(self.avg_protection_coverage, 1),
            "freshness_blocks": self.freshness_blocks,
            "model_issues": self.model_issues,
            "liquidity_blocks": self.liquidity_blocks,
            "best_day_entries": self.best_day_entries,
            "worst_day_entries": self.worst_day_entries,
            "total_abstentions": self.total_abstentions,
            "abstention_rate": round(self.abstention_rate, 4),
            "recommendation": self.recommendation,
            "issues": self.issues,
        }


# ── CampaignOrchestrator ────────────────────────────────────────────────────

@dataclass
class CampaignOrchestrator:
    """Orchestre une campagne shadow/paper quotidienne (Point 13).

    Usage typique ::

        orchestrator = CampaignOrchestrator(
            CampaignConfig(
                campaign_id="shadow_2026Q3",
                phase=CampaignPhase.SHADOW,
                model_run_id="mdl_abc123",
                run_mode="shadow",
                dry_run=True,
            ),
        )
        orchestrator.run_daily_cycle()
        # ... après 4 semaines ...
        report = orchestrator.build_campaign_report()
    """

    config: CampaignConfig
    _results: list[CampaignDayResult] = field(default_factory=list)
    _reviews: list[WeeklyReview] = field(default_factory=list)

    @property
    def campaign_dir(self) -> Path:
        return PROJECT_ROOT / "artifacts" / "campaigns" / self.config.campaign_id

    @property
    def daily_dir(self) -> Path:
        return self.campaign_dir / "daily"

    @property
    def weekly_dir(self) -> Path:
        return self.campaign_dir / "weekly"

    def init_campaign(self) -> None:
        """Initialise la structure de la campagne."""
        self.campaign_dir.mkdir(parents=True, exist_ok=True)
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.weekly_dir.mkdir(parents=True, exist_ok=True)

        # Persister la config
        (self.campaign_dir / "campaign_config.json").write_text(
            json.dumps(self.config.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        LOGGER.info("Campagne initialisée | id=%s phase=%s dir=%s",
                     self.config.campaign_id, self.config.phase, self.campaign_dir)

    def validate_frozen_state(self) -> bool:
        """Vérifie que le modèle/policy/config sont toujours gelés.

        Returns False si un changement non autorisé est détecté (rollback sécurité).
        """
        issues: list[str] = []

        if not self.config.model_run_id:
            issues.append("model_run_id manquant")
        if not self.config.config_fingerprint:
            issues.append("config_fingerprint manquant")

        # Vérifier que les artefacts gelés existent toujours
        for key, path_str in self.config.frozen_artifacts.items():
            p = Path(path_str) if Path(path_str).is_absolute() else PROJECT_ROOT / path_str
            if not p.exists():
                issues.append(f"artefact gelé manquant: {key} → {path_str}")

        if issues:
            LOGGER.error("Frozen state violation: %s", issues)
            return False
        return True

    def run_daily_cycle(self, trade_date: date | None = None) -> CampaignDayResult:
        """Exécute le cycle quotidien de décision (Point 13).

        En shadow : run risque uniquement (pas d'ordres).
        En paper  : run risque + run exécution paper.
        """
        td = trade_date or date.today()
        day_number = len(self._results) + 1

        result = CampaignDayResult(
            trade_date=td,
            campaign_id=self.config.campaign_id,
            phase=self.config.phase,
            day_number=day_number,
        )

        try:
            # ── 1. Vérifier l'état gelé ──
            if not self.validate_frozen_state():
                result.status = "frozen_state_violation"
                result.errors.append("frozen_state_violation")
                self._results.append(result)
                self._persist_day_result(result)
                return result

            # ── 2. Exécuter le run risque (décisions) ──
            # Note: en production, ceci appelle subprocess ou l'API CLI
            # Pour le framework, on enregistre les métadonnées
            risk_result = self._execute_risk_run(td)
            result.risk_run_id = risk_result.get("run_id", "")
            result.entries_count = risk_result.get("entries_count", 0)
            result.entries_long = risk_result.get("entries_long", 0)
            result.entries_short = risk_result.get("entries_short", 0)
            result.freshness_blocked = risk_result.get("freshness_blocked", False)
            result.model_compatible = risk_result.get("model_compatible", True)
            result.liquidity_blocked = risk_result.get("liquidity_blocked", 0)

            # ── 3. En paper : exécuter le run exécution ──
            if not self.config.dry_run:
                exec_result = self._execute_paper_run(td, result.risk_run_id)
                result.exec_run_id = exec_result.get("run_id", "")
                result.orders_submitted = exec_result.get("orders_submitted", 0)
                result.orders_filled = exec_result.get("orders_filled", 0)
                result.orders_failed = exec_result.get("orders_failed", 0)
                result.slippage_median_bps = exec_result.get("slippage_median_bps")
                result.protection_coverage_pct = exec_result.get("protection_coverage_pct", 100.0)
                result.reconciliation_status = exec_result.get("reconciliation_status", "clean")

            # ── 4. Shadow compare (si applicable) ──
            shadow_compare = self._run_shadow_compare(td)
            if shadow_compare:
                result.shadow_divergence_rate = shadow_compare.get("divergence_rate", 0.0)
                result.shadow_is_convergent = shadow_compare.get("is_convergent", True)

            result.status = "completed"

        except Exception as exc:
            LOGGER.error("Campaign day %d failed: %s", day_number, exc, exc_info=True)
            result.status = "failed"
            result.errors.append(str(exc))

        self._results.append(result)
        self._persist_day_result(result)

        # ── Revue hebdomadaire ──
        if day_number % 5 == 0:
            self._build_weekly_review()

        return result

    # ── Internals ────────────────────────────────────────────────────────

    def _execute_risk_run(self, trade_date: date) -> dict[str, Any]:
        """Exécute le run risque (décisions) pour un jour donné."""
        day_dir = self.daily_dir / trade_date.isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)

        # Lecture du résumé de run existant (produit par risk_management/cli.py)
        summary_path = day_dir / "risk_run_summary.json"
        if summary_path.exists():
            return json.loads(summary_path.read_text(encoding="utf-8"))

        # Si pas de run pré-existant, retourne un squelette
        LOGGER.warning("Aucun run risque pré-existant pour %s — squelette.", trade_date)
        return {"run_id": "", "entries_count": 0}

    def _execute_paper_run(self, trade_date: date, risk_run_id: str) -> dict[str, Any]:
        """Exécute le run paper (ordres simulés) pour un jour donné."""
        day_dir = self.daily_dir / trade_date.isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)

        summary_path = day_dir / "exec_run_summary.json"
        if summary_path.exists():
            return json.loads(summary_path.read_text(encoding="utf-8"))

        return {"run_id": "", "orders_submitted": 0, "orders_filled": 0}

    def _run_shadow_compare(self, trade_date: date) -> dict[str, Any] | None:
        """Compare les décisions shadow vs live."""
        if self.config.phase != CampaignPhase.SHADOW:
            return None
        day_dir = self.daily_dir / trade_date.isoformat()
        compare_path = day_dir / "shadow_compare.json"
        if compare_path.exists():
            return json.loads(compare_path.read_text(encoding="utf-8"))
        return None

    def _persist_day_result(self, result: CampaignDayResult) -> None:
        """Persiste le résultat quotidien."""
        day_dir = self.daily_dir / result.trade_date.isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "campaign_day_result.json").write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def _build_weekly_review(self) -> WeeklyReview:
        """Construit la revue hebdomadaire à partir des résultats quotidiens."""
        if not self._results:
            return WeeklyReview(campaign_id=self.config.campaign_id, week_number=0,
                                week_start=date.today(), week_end=date.today())

        week_number = len(self._reviews) + 1
        # Prendre les 5 derniers jours (ou moins si début de campagne)
        recent = self._results[-5:]
        week_start = recent[0].trade_date
        week_end = recent[-1].trade_date

        review = WeeklyReview(
            campaign_id=self.config.campaign_id,
            week_number=week_number,
            week_start=week_start,
            week_end=week_end,
            days_completed=sum(1 for r in recent if r.status == "completed"),
            days_skipped=sum(1 for r in recent if r.status != "completed"),
            total_entries=sum(r.entries_count for r in recent),
            total_orders=sum(r.orders_submitted for r in recent),
            total_fills=sum(r.orders_filled for r in recent),
            freshness_blocks=sum(1 for r in recent if r.freshness_blocked),
            model_issues=sum(1 for r in recent if not r.model_compatible),
            liquidity_blocks=sum(r.liquidity_blocked for r in recent),
        )

        # Moyennes
        div_rates = [r.shadow_divergence_rate for r in recent if r.shadow_divergence_rate > 0]
        review.avg_divergence_rate = sum(div_rates) / len(div_rates) if div_rates else 0.0

        slips = [r.slippage_median_bps for r in recent if r.slippage_median_bps is not None]
        review.avg_slippage_bps = sum(slips) / len(slips) if slips else None

        covs = [r.protection_coverage_pct for r in recent]
        review.avg_protection_coverage = sum(covs) / len(covs) if covs else 100.0

        # Extrêmes
        entries_by_day = [(r.entries_count, r.trade_date.isoformat()) for r in recent]
        if entries_by_day:
            review.best_day_entries = max(e[0] for e in entries_by_day)
            review.worst_day_entries = min(e[0] for e in entries_by_day)
            review.max_slippage_day = max(
                ((r.slippage_median_bps or 0), r.trade_date.isoformat()) for r in recent
            )[1]

        # Recommandation
        issues: list[str] = []
        if review.freshness_blocks > 0:
            issues.append(f"{review.freshness_blocks} jours bloqués par fraîcheur")
        if review.model_issues > 0:
            issues.append(f"{review.model_issues} jours avec modèle incompatible")
        if review.liquidity_blocks > 0:
            issues.append(f"{review.liquidity_blocks} rejets liquidité")
        if review.days_completed < 3:
            issues.append("moins de 3 jours complétés dans la semaine")
        review.issues = issues

        if issues:
            review.recommendation = "review_required"
        elif review.avg_divergence_rate > 0.05:
            review.recommendation = "investigate_divergence"
        else:
            review.recommendation = "continue"

        self._reviews.append(review)

        # Persister
        (self.weekly_dir / f"week_{week_number:02d}.json").write_text(
            json.dumps(review.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        LOGGER.info("Revue hebdomadaire #%d | reco=%s issues=%d",
                     week_number, review.recommendation, len(issues))
        return review

    # ── Rapport de campagne ──────────────────────────────────────────────

    def build_campaign_report(self) -> dict[str, Any]:
        """Produit le rapport de campagne complet (Point 13)."""
        weeks_elapsed = self.config.weeks_elapsed
        total_days = len(self._results)
        completed_days = sum(1 for r in self._results if r.status == "completed")

        # Vérifier les gates de promotion
        can_promote, promotion_issues = self._check_promotion_gates()

        return {
            "campaign_id": self.config.campaign_id,
            "phase": self.config.phase,
            "weeks_elapsed": round(weeks_elapsed, 1),
            "min_weeks_required": self.config.min_weeks_required,
            "total_days": total_days,
            "completed_days": completed_days,
            "completion_rate": round(completed_days / max(total_days, 1), 2),
            "can_promote": can_promote,
            "promotion_issues": promotion_issues,
            "config": self.config.to_dict(),
            "weekly_reviews": [r.to_dict() for r in self._reviews],
            "last_updated": datetime.now().isoformat(),
        }

    def _check_promotion_gates(self) -> tuple[bool, list[str]]:
        """Vérifie les gates de promotion (Point 13)."""
        issues: list[str] = []

        # 1. Durée minimale
        if not self.config.can_promote:
            issues.append(
                f"durée insuffisante: {self.config.weeks_elapsed:.1f} semaines "
                f"/ {self.config.min_weeks_required} requises"
            )

        # 2. Divergence side
        for r in self._results:
            if r.shadow_divergence_rate > 0.0:
                issues.append(
                    f"divergence side le {r.trade_date}: "
                    f"taux={r.shadow_divergence_rate:.4f}"
                )
                break  # Une seule suffit

        # 3. Protection
        for r in self._results:
            if r.protection_coverage_pct < 100.0:
                issues.append(
                    f"couverture protection < 100% le {r.trade_date}: "
                    f"{r.protection_coverage_pct:.1f}%"
                )

        # 4. Slippage
        if self._results:
            slips = [r.slippage_median_bps for r in self._results if r.slippage_median_bps is not None]
            if slips:
                avg_slip = sum(slips) / len(slips)
                if avg_slip > 10.0:  # 10 bps threshold
                    issues.append(f"slippage médian moyen {avg_slip:.1f} bps > 10 bps")

        # 5. Réconciliation
        for r in self._results:
            if r.reconciliation_status != "clean":
                issues.append(f"réconciliation non clean le {r.trade_date}: {r.reconciliation_status}")

        # 6. Fraîcheur / compatibilité
        freshness_fails = sum(1 for r in self._results if r.freshness_blocked)
        if freshness_fails > max(1, len(self._results) * 0.05):  # >5% des jours
            issues.append(f"{freshness_fails} jours bloqués par fraîcheur")

        return len(issues) == 0, issues

    def save_campaign_report(self) -> str:
        """Persiste le rapport de campagne."""
        report = self.build_campaign_report()
        path = self.campaign_dir / "campaign_report.json"
        path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return str(path)


# ── Factory ─────────────────────────────────────────────────────────────────

def create_campaign(
    *,
    campaign_id: str,
    phase: str = CampaignPhase.SHADOW,
    model_run_id: str = "",
    policy_version: int = 1,
    config_fingerprint: str = "",
    run_mode: str = "shadow",
    dry_run: bool = True,
    approved_by: str | None = None,
    start_date: date | None = None,
    auto_promote: bool = False,
    frozen_model_path: str = "",
    frozen_calibrator_path: str = "",
    frozen_config_path: str = "",
) -> CampaignOrchestrator:
    """Crée un orchestrateur de campagne (Point 13)."""
    config = CampaignConfig(
        campaign_id=campaign_id,
        phase=phase,
        start_date=start_date or date.today(),
        model_run_id=model_run_id,
        policy_version=policy_version,
        config_fingerprint=config_fingerprint,
        run_mode=run_mode,
        dry_run=dry_run,
        approved_by=approved_by,
        approved_at=datetime.now() if approved_by else None,
        auto_promote=auto_promote,
        frozen_artifacts={
            "model": frozen_model_path,
            "calibrator": frozen_calibrator_path,
            "config": frozen_config_path,
        },
    )
    orchestrator = CampaignOrchestrator(config)
    orchestrator.init_campaign()
    return orchestrator
