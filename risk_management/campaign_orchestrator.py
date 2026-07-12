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
import os
import subprocess
import hmac
from hashlib import sha256
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
    base_risk_budget: float = 0.0
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
    risk_command: list[str] = field(default_factory=list)
    execution_command: list[str] = field(default_factory=list)
    signing_key_env: str = "ALPHA_TRADE_CAMPAIGN_SIGNING_KEY"

    def to_dict(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "phase": self.phase,
            "start_date": self.start_date.isoformat(),
            "base_risk_budget": self.base_risk_budget,
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
            "risk_command": self.risk_command,
            "execution_command": self.execution_command,
            "signing_key_env": self.signing_key_env,
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
    effective_risk_budget: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_date": self.trade_date.isoformat(),
            "campaign_id": self.campaign_id,
            "phase": self.phase,
            "effective_risk_budget": self.effective_risk_budget,
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
    _ramp_up: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._reload_history()
        self._ramp_up = self._load_ramp_up_state()

    @property
    def campaign_dir(self) -> Path:
        return PROJECT_ROOT / "artifacts" / "campaigns" / self.config.campaign_id

    @property
    def daily_dir(self) -> Path:
        return self.campaign_dir / "daily"

    @property
    def weekly_dir(self) -> Path:
        return self.campaign_dir / "weekly"

    @property
    def ramp_up_state_path(self) -> Path:
        return self.campaign_dir / "ramp_up_state.json"

    @property
    def effective_risk_budget(self) -> float:
        return float(self._ramp_up.effective_risk_budget(self.config.base_risk_budget))

    def init_campaign(self) -> None:
        """Initialise la structure de la campagne."""
        self.campaign_dir.mkdir(parents=True, exist_ok=True)
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.weekly_dir.mkdir(parents=True, exist_ok=True)

        # Persister la config
        self._write_json_atomic(self.campaign_dir / "campaign_config.json", self.config.to_dict())
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
        self._reload_history()
        day_number = len(self._results) + 1

        result = CampaignDayResult(
            trade_date=td,
            campaign_id=self.config.campaign_id,
            phase=self.config.phase,
            day_number=day_number,
            effective_risk_budget=self.effective_risk_budget,
        )

        try:
            # ── 1. Vérifier l'état gelé ──
            if not self.validate_frozen_state():
                result.status = "frozen_state_violation"
                result.errors.append("frozen_state_violation")
                self._results.append(result)
                self._persist_day_result(result)
                return result
            if self.config.phase != CampaignPhase.SHADOW and not os.environ.get(self.config.signing_key_env):
                raise RuntimeError(f"clé de signature campagne absente: {self.config.signing_key_env}")

            # ── 2. Exécuter le run risque (décisions) ──
            # Note: en production, ceci appelle subprocess ou l'API CLI
            # Pour le framework, on enregistre les métadonnées
            risk_result = self._execute_risk_run(td)
            result.risk_run_id = risk_result.get("run_id", "")
            if not result.risk_run_id:
                raise RuntimeError("résumé risque sans run_id")
            result.entries_count = risk_result.get("entries_count", risk_result.get("target_positions", 0))
            result.entries_long = risk_result.get("entries_long", 0)
            result.entries_short = risk_result.get("entries_short", 0)
            result.freshness_blocked = risk_result.get("freshness_blocked", False)
            result.model_compatible = risk_result.get("model_compatible", True)
            result.liquidity_blocked = risk_result.get("liquidity_blocked", 0)

            # ── 3. En paper : exécuter le run exécution ──
            if not self.config.dry_run:
                exec_result = self._execute_paper_run(td, result.risk_run_id)
                result.exec_run_id = exec_result.get("run_id", "")
                if not result.exec_run_id:
                    raise RuntimeError("résumé paper sans run_id")
                result.orders_submitted = exec_result.get("orders_submitted", exec_result.get("submitted", 0))
                result.orders_filled = exec_result.get("orders_filled", exec_result.get("filled", 0))
                result.orders_failed = exec_result.get("orders_failed", exec_result.get("failed", 0))
                result.slippage_median_bps = exec_result.get("slippage_median_bps")
                result.protection_coverage_pct = exec_result.get("protection_coverage_pct", 100.0)
                result.reconciliation_status = exec_result.get("reconciliation_status", "clean")

            # ── 4. Shadow compare (si applicable) ──
            shadow_compare = self._run_shadow_compare(td)
            if self.config.phase == CampaignPhase.SHADOW and shadow_compare is None:
                raise RuntimeError("rapport shadow_compare manquant")
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
        self._persist_runtime_parameters(day_dir)
        self._run_configured_entrypoint(
            kind="risk",
            command=self.config.risk_command,
            trade_date=trade_date,
            day_dir=day_dir,
            risk_run_id=None,
        )

        # Lecture du résumé de run existant (produit par risk_management/cli.py)
        summary_path = day_dir / "risk_run_summary.json"
        if summary_path.exists():
            return json.loads(summary_path.read_text(encoding="utf-8"))

        raise FileNotFoundError(
            f"Résumé risque requis absent pour {trade_date}: {summary_path}"
        )

    def _execute_paper_run(self, trade_date: date, risk_run_id: str) -> dict[str, Any]:
        """Exécute le run paper (ordres simulés) pour un jour donné."""
        day_dir = self.daily_dir / trade_date.isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)
        self._run_configured_entrypoint(
            kind="execution",
            command=self.config.execution_command,
            trade_date=trade_date,
            day_dir=day_dir,
            risk_run_id=risk_run_id,
        )

        summary_path = day_dir / "exec_run_summary.json"
        if summary_path.exists():
            return json.loads(summary_path.read_text(encoding="utf-8"))

        raise FileNotFoundError(
            f"Résumé paper requis absent pour {trade_date}: {summary_path}"
        )

    def _run_shadow_compare(self, trade_date: date) -> dict[str, Any] | None:
        """Compare les décisions shadow vs live."""
        if self.config.phase != CampaignPhase.SHADOW:
            return None
        day_dir = self.daily_dir / trade_date.isoformat()
        compare_path = day_dir / "shadow_compare.json"
        if compare_path.exists():
            return json.loads(compare_path.read_text(encoding="utf-8"))
        return None

    def _run_configured_entrypoint(
        self,
        *,
        kind: str,
        command: list[str],
        trade_date: date,
        day_dir: Path,
        risk_run_id: str | None,
    ) -> None:
        """Exécute une commande configurée sans shell et conserve un reçu haché."""
        if not command:
            return
        values = {
            "trade_date": trade_date.isoformat(),
            "day_dir": str(day_dir),
            "risk_run_id": risk_run_id or "",
            "effective_risk_budget": f"{self.effective_risk_budget:.8f}",
        }
        rendered = [str(part).format_map(values) for part in command]
        if kind == "risk":
            rendered.extend([
                "--trade-date", trade_date.isoformat(), "--run-mode", self.config.run_mode,
                "--summary-path", str(day_dir / "risk_run_summary.json"),
            ])
            if self.effective_risk_budget > 0.0:
                rendered.extend(["--risk-budget-dollars", f"{self.effective_risk_budget:.8f}"])
        elif risk_run_id:
            rendered.extend([
                "--run-id", risk_run_id, "--date", trade_date.isoformat(),
                "--summary-path", str(day_dir / "exec_run_summary.json"),
            ])
        completed = subprocess.run(
            rendered,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        self._write_json_atomic(day_dir / f"{kind}_entrypoint_receipt.json", {
            "kind": kind,
            "command": rendered,
            "returncode": completed.returncode,
            "stdout_sha256": sha256(completed.stdout.encode("utf-8", errors="replace")).hexdigest(),
            "stderr_sha256": sha256(completed.stderr.encode("utf-8", errors="replace")).hexdigest(),
        })
        if completed.returncode != 0:
            raise RuntimeError(f"entrypoint {kind} failed with exit code {completed.returncode}")

    def _persist_day_result(self, result: CampaignDayResult) -> None:
        """Persiste le résultat quotidien."""
        day_dir = self.daily_dir / result.trade_date.isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(day_dir / "campaign_day_result.json", result.to_dict())
        summaries = {}
        for name in ("risk_run_summary.json", "exec_run_summary.json", "shadow_compare.json"):
            path = day_dir / name
            if path.exists():
                summaries[name] = sha256(path.read_bytes()).hexdigest()
        manifest = {
            "campaign_id": self.config.campaign_id,
            "trade_date": result.trade_date.isoformat(),
            "status": result.status,
            "summary_sha256": summaries,
        }
        signing_key = os.environ.get(self.config.signing_key_env, "")
        canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        manifest["signature_hmac_sha256"] = (
            hmac.new(signing_key.encode("utf-8"), canonical.encode("utf-8"), "sha256").hexdigest()
            if signing_key else None
        )
        manifest["signature_key_env"] = self.config.signing_key_env
        self._write_json_atomic(day_dir / "evidence_manifest.json", manifest)

    def _reload_history(self) -> None:
        """Recharge les journées persistées avant tout rapport ou promotion."""
        if not self.daily_dir.exists():
            return
        loaded: list[CampaignDayResult] = []
        for path in sorted(self.daily_dir.glob("*/campaign_day_result.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["trade_date"] = date.fromisoformat(str(data["trade_date"]))
                allowed = {field_name: data[field_name] for field_name in CampaignDayResult.__dataclass_fields__ if field_name in data}
                loaded.append(CampaignDayResult(**allowed))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                LOGGER.error("Historique campagne invalide: %s", path, exc_info=True)
        self._results = loaded

    def _load_ramp_up_state(self) -> Any:
        from risk_management.gradual_ramp_up import RampUpManager, RampUpStage

        if self.ramp_up_state_path.exists():
            try:
                data = json.loads(self.ramp_up_state_path.read_text(encoding="utf-8"))
                return RampUpManager(
                    current_stage=RampUpStage(str(data["current_stage"])),
                    stage_started_at=date.fromisoformat(str(data["stage_started_at"])),
                    drawdown_current=float(data.get("drawdown_current", 0.0)),
                    open_incidents=int(data.get("open_incidents", 0)),
                )
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                LOGGER.error("État ramp-up invalide: %s", self.ramp_up_state_path, exc_info=True)
                raise RuntimeError("Etat ramp-up persiste invalide")
        try:
            stage = RampUpStage(self.config.phase)
        except ValueError:
            stage = RampUpStage.SHADOW
        return RampUpManager(current_stage=stage, stage_started_at=self.config.start_date)

    def _persist_ramp_up_state(self) -> None:
        self._write_json_atomic(self.ramp_up_state_path, {
            "current_stage": self._ramp_up.current_stage.value,
            "stage_started_at": self._ramp_up.stage_started_at.isoformat(),
            "drawdown_current": self._ramp_up.drawdown_current,
            "open_incidents": self._ramp_up.open_incidents,
            "effective_risk_budget": self.effective_risk_budget,
        })

    def _persist_runtime_parameters(self, day_dir: Path) -> None:
        self._write_json_atomic(day_dir / "runtime_parameters.json", {
            "campaign_id": self.config.campaign_id,
            "ramp_up_stage": self._ramp_up.current_stage.value,
            "base_risk_budget": self.config.base_risk_budget,
            "effective_risk_budget": self.effective_risk_budget,
        })

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(temporary, path)

    def transition_ramp_up(self, *, reviewer: str, reason: str = "") -> tuple[bool, str]:
        """Applique une promotion gouvernée et journalise chaque transition."""
        can_promote, gate_reason = self._ramp_up.can_promote(
            checklist_passed=self._check_promotion_gates()[0],
            shadow_convergent=all(result.shadow_is_convergent for result in self._results),
            human_reviewer=reviewer,
        )
        if not can_promote:
            return False, gate_reason
        transition = self._ramp_up.promote(
            checklist_passed=True,
            shadow_convergent=True,
            human_reviewer=reviewer,
        )
        from risk_management.operational_controls import persist_ramp_up_transition
        persist_ramp_up_transition(
            from_stage=transition.from_stage.value,
            to_stage=transition.to_stage.value if transition.to_stage else "",
            approved_by=reviewer,
            reason=reason or transition.reason,
            metrics_snapshot={"campaign_id": self.config.campaign_id, "completed_days": len(self._results)},
            journal_path=str(self.campaign_dir / "ramp_up_journal.json"),
        )
        self.config.phase = self._ramp_up.current_stage.value
        self.config.run_mode = (
            "shadow" if self._ramp_up.current_stage.value == CampaignPhase.SHADOW
            else "paper" if self._ramp_up.current_stage.value == CampaignPhase.PAPER
            else "live"
        )
        self.config.dry_run = self._ramp_up.current_stage.value == CampaignPhase.SHADOW
        self._persist_ramp_up_state()
        self._write_json_atomic(self.campaign_dir / "campaign_config.json", self.config.to_dict())
        return True, transition.reason

    def _maybe_auto_rollback(self, result: CampaignDayResult) -> None:
        incidents = int(result.orders_failed > 0 or result.reconciliation_status != "clean")
        self._ramp_up.open_incidents = incidents
        transition = self._ramp_up.check_drawdown_breach(0.0)
        if transition is not None:
            from risk_management.operational_controls import persist_ramp_up_transition
            persist_ramp_up_transition(
                from_stage=transition.from_stage.value,
                to_stage=transition.to_stage.value if transition.to_stage else "",
                approved_by="system",
                reason=transition.reason,
                metrics_snapshot={"campaign_id": self.config.campaign_id, "incidents": incidents},
                journal_path=str(self.campaign_dir / "ramp_up_journal.json"),
            )
        self._persist_ramp_up_state()

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
        self._write_json_atomic(self.weekly_dir / f"week_{week_number:02d}.json", review.to_dict())

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
        self._write_json_atomic(path, report)
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
    base_risk_budget: float = 0.0,
    risk_command: list[str] | None = None,
    execution_command: list[str] | None = None,
    signing_key_env: str = "ALPHA_TRADE_CAMPAIGN_SIGNING_KEY",
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
        base_risk_budget=base_risk_budget,
        risk_command=list(risk_command or []),
        execution_command=list(execution_command or []),
        signing_key_env=signing_key_env,
        frozen_artifacts={
            "model": frozen_model_path,
            "calibrator": frozen_calibrator_path,
            "config": frozen_config_path,
        },
    )
    orchestrator = CampaignOrchestrator(config)
    orchestrator.init_campaign()
    return orchestrator
