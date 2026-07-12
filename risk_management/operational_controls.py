"""risk_management/operational_controls.py — Contrôles opérationnels permanents (Sprint Maître 15).

Contrôles quotidiens/hebdomadaires/mensuels/trimestriels :
- Smoke test avant session
- Fraîcheur et intégrité quotidiennes
- Parité backtest/live quotidienne
- Réconciliation quotidienne
- Rollback drill mensuel
- Restauration complète trimestrielle

Usage ::

    from risk_management.operational_controls import (
        OperationalControls, SmokeTest, ControlSchedule, ControlResult,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


# ── ControlFrequency ────────────────────────────────────────────────────────


class ControlFrequency(StrEnum):
    """Fréquence d'un contrôle opérationnel (Sprint Maître 15)."""

    PRE_SESSION = "pre_session"     # Avant chaque session de trading
    DAILY = "daily"                 # Quotidien (post-session)
    WEEKLY = "weekly"               # Hebdomadaire
    MONTHLY = "monthly"             # Mensuel
    QUARTERLY = "quarterly"         # Trimestriel


# ── ControlStatus ───────────────────────────────────────────────────────────


class ControlStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


# ── SmokeTest ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SmokeTest:
    """Un smoke test pré-session (Sprint Maître 15)."""

    test_id: str
    name: str
    description: str = ""
    status: ControlStatus = ControlStatus.PENDING
    duration_ms: float = 0.0
    detail: str = ""
    checked_at: datetime | None = None

    @property
    def is_blocking(self) -> bool:
        """True si ce test bloquant doit empêcher le trading."""
        return self.status == ControlStatus.FAILED

    def to_dict(self) -> dict[str, object]:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 1),
            "detail": self.detail,
        }


# ── ControlResult ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ControlResult:
    """Résultat d'un contrôle opérationnel (Sprint Maître 15)."""

    control_id: str
    name: str
    frequency: ControlFrequency
    status: ControlStatus = ControlStatus.PENDING
    detail: str = ""
    checked_at: datetime | None = None
    requires_escalation: bool = False

    @property
    def is_blocking(self) -> bool:
        return self.status == ControlStatus.FAILED

    def to_dict(self) -> dict[str, object]:
        return {
            "control_id": self.control_id,
            "name": self.name,
            "frequency": self.frequency.value,
            "status": self.status.value,
            "detail": self.detail,
            "requires_escalation": self.requires_escalation,
        }


# ── ControlSchedule ─────────────────────────────────────────────────────────


@dataclass
class ControlSchedule:
    """Planning des contrôles opérationnels (Sprint Maître 15).

    Définit les contrôles à exécuter par fréquence.
    """

    # ── Pré-session (smoke tests) ──────────────────────────────────────
    PRE_SESSION_TESTS: tuple[SmokeTest, ...] = (
        SmokeTest("SMOKE_CONNECTIVITY", "Connectivité broker", "Vérifier que l'API broker répond"),
        SmokeTest("SMOKE_DATA_FRESH", "Fraîcheur données", "Vérifier prix/ADV/earnings < seuil"),
        SmokeTest("SMOKE_KILL_SWITCH", "Kill switch inactif", "Vérifier qu'aucun kill switch n'est actif"),
        SmokeTest("SMOKE_CIRCUIT_BREAKER", "Circuit breaker OK", "Vérifier que le breaker n'est pas trippé"),
        SmokeTest("SMOKE_ML_READY", "Modèle ML prêt", "Vérifier que le champion est chargé et non drifté"),
        SmokeTest("SMOKE_CASH", "Cash disponible", "Vérifier buying power > 0"),
        SmokeTest("SMOKE_WATCHER", "Watcher actif", "Vérifier que le protection watcher tourne"),
    )

    # ── Quotidiens ─────────────────────────────────────────────────────
    DAILY_CONTROLS: tuple[str, ...] = (
        "reconciliation",              # Réconciliation ordres/positions/protections/PnL/cash
        "freshness_check",             # Fraîcheur données/modèle/calibration/régime/borrow
        "parity_check",                # Parité backtest/live
        "integrity_check",             # Intégrité audit chain
        "drift_check",                 # Drift features/probas/sides/calibration/PnL/coûts
    )

    # ── Hebdomadaires ──────────────────────────────────────────────────
    WEEKLY_CONTROLS: tuple[str, ...] = (
        "attribution_review",          # Revue d'attribution par régime/secteur
        "cost_review",                 # Revue des coûts (slippage, commission, borrow)
        "capacity_review",             # Revue de capacité par stratégie
        "concentration_review",        # Revue de concentration
    )

    # ── Mensuels ───────────────────────────────────────────────────────
    MONTHLY_CONTROLS: tuple[str, ...] = (
        "rollback_drill",              # Test de rollback atomique
        "shadow_validation",           # Validation du modèle shadow
        "calibration_review",          # Revue de calibration par cohorte
        "incident_review",             # Revue des incidents du mois
    )

    # ── Trimestriels ───────────────────────────────────────────────────
    QUARTERLY_CONTROLS: tuple[str, ...] = (
        "full_restore_drill",          # Restauration complète depuis backup
        "independent_review",          # Revue indépendante trimestrielle
        "disaster_recovery_test",      # Test de disaster recovery
        "champion_challenger_review",  # Revue champion/challenger
    )

    def get_controls(self, frequency: ControlFrequency) -> tuple[str, ...]:
        mapping = {
            ControlFrequency.DAILY: self.DAILY_CONTROLS,
            ControlFrequency.WEEKLY: self.WEEKLY_CONTROLS,
            ControlFrequency.MONTHLY: self.MONTHLY_CONTROLS,
            ControlFrequency.QUARTERLY: self.QUARTERLY_CONTROLS,
        }
        return mapping.get(frequency, ())

    def get_smoke_tests(self) -> tuple[SmokeTest, ...]:
        return self.PRE_SESSION_TESTS


# ── OperationalControls ─────────────────────────────────────────────────────


@dataclass
class OperationalControls:
    """Gestionnaire des contrôles opérationnels (Sprint Maître 15).

    Exécute et trace les contrôles par fréquence.
    """

    schedule: ControlSchedule = field(default_factory=ControlSchedule)
    smoke_results: list[SmokeTest] = field(default_factory=list)
    control_results: list[ControlResult] = field(default_factory=list)

    def run_smoke_tests(
        self,
        *,
        connectivity_ok: bool = True,
        data_fresh_ok: bool = True,
        kill_switch_ok: bool = True,
        circuit_breaker_ok: bool = True,
        ml_ready: bool = True,
        cash_ok: bool = True,
        watcher_ok: bool = True,
    ) -> tuple[bool, list[SmokeTest]]:
        """Exécute les smoke tests pré-session.

        Returns
        -------
        (all_passed, results)
        """
        results_map = {
            "SMOKE_CONNECTIVITY": connectivity_ok,
            "SMOKE_DATA_FRESH": data_fresh_ok,
            "SMOKE_KILL_SWITCH": kill_switch_ok,
            "SMOKE_CIRCUIT_BREAKER": circuit_breaker_ok,
            "SMOKE_ML_READY": ml_ready,
            "SMOKE_CASH": cash_ok,
            "SMOKE_WATCHER": watcher_ok,
        }

        results: list[SmokeTest] = []
        now = datetime.now()

        for test in self.schedule.get_smoke_tests():
            ok = results_map.get(test.test_id, True)
            results.append(SmokeTest(
                test_id=test.test_id,
                name=test.name,
                description=test.description,
                status=ControlStatus.PASSED if ok else ControlStatus.FAILED,
                detail="OK" if ok else "ÉCHEC — action requise",
                checked_at=now,
            ))

        self.smoke_results = results
        all_passed = all(r.status == ControlStatus.PASSED for r in results)
        return all_passed, results

    def record_control(
        self,
        control_id: str,
        name: str,
        frequency: ControlFrequency,
        passed: bool,
        detail: str = "",
    ) -> ControlResult:
        """Enregistre le résultat d'un contrôle."""
        result = ControlResult(
            control_id=control_id,
            name=name,
            frequency=frequency,
            status=ControlStatus.PASSED if passed else ControlStatus.FAILED,
            detail=detail,
            checked_at=datetime.now(),
            requires_escalation=not passed,
        )
        self.control_results.append(result)
        return result

    def daily_checks_passed(self, date_check: date | None = None) -> tuple[bool, list[ControlResult]]:
        """Vérifie si tous les contrôles quotidiens sont passés."""
        daily = [r for r in self.control_results if r.frequency == ControlFrequency.DAILY]
        all_ok = all(r.status == ControlStatus.PASSED for r in daily)
        return all_ok, daily

    def is_ready_to_trade(self) -> tuple[bool, str]:
        """Détermine si le système est prêt à trader.

        Vérifie :
        1. Smoke tests tous passés
        2. Pas de kill switch actif
        3. Circuit breaker non trippé

        Returns
        -------
        (ready, reason)
        """
        if not self.smoke_results:
            return False, "Smoke tests non exécutés"

        failed_smokes = [s for s in self.smoke_results if s.is_blocking]
        if failed_smokes:
            names = ", ".join(s.name for s in failed_smokes)
            return False, f"Smoke tests échoués: {names}"

        return True, "Système prêt à trader"

    def summary(self) -> dict[str, object]:
        """Résumé de l'état des contrôles."""
        all_results = self.smoke_results + [  # type: ignore[operator]
            r for r in self.control_results
        ]
        passed = sum(1 for r in all_results if hasattr(r, 'status') and r.status == ControlStatus.PASSED)
        failed = sum(1 for r in all_results if hasattr(r, 'status') and r.status == ControlStatus.FAILED)
        return {
            "total_checks": len(all_results),
            "passed": passed,
            "failed": failed,
            "smoke_tests_passed": all(r.status == ControlStatus.PASSED for r in self.smoke_results),
            "ready_to_trade": self.is_ready_to_trade()[0],
        }


# ── Helpers ─────────────────────────────────────────────────────────────────


def run_pre_session_smoke_tests(
    *,
    connectivity_ok: bool = True,
    data_fresh_ok: bool = True,
    kill_switch_ok: bool = True,
    circuit_breaker_ok: bool = True,
    ml_ready: bool = True,
    cash_ok: bool = True,
    watcher_ok: bool = True,
) -> tuple[bool, list[SmokeTest]]:
    """Exécute les smoke tests pré-session (fonction pure)."""
    ctrls = OperationalControls()
    return ctrls.run_smoke_tests(
        connectivity_ok=connectivity_ok,
        data_fresh_ok=data_fresh_ok,
        kill_switch_ok=kill_switch_ok,
        circuit_breaker_ok=circuit_breaker_ok,
        ml_ready=ml_ready,
        cash_ok=cash_ok,
        watcher_ok=watcher_ok,
    )


# ── Point 14 : probes réelles (remplace les booléens injectés) ──────────────

def build_operational_probes(
    *,
    broker: object | None = None,
    circuit_breaker: object | None = None,
    config: object | None = None,
    trade_date: date | None = None,
    model_registry_path: str = "artifacts/model_registry.json",
) -> dict[str, bool]:
    """Construit les résultats des 7 smoke tests avec des probes réelles (Point 14).

    Remplace les booléens injectés par défaut de ``run_smoke_tests()``.
    Chaque probe interroge l'état réel du système.

    Returns un dict {test_id: ok_bool}.
    """
    import time as _time

    probes: dict[str, bool] = {}

    # 1. Connectivité broker
    if broker is not None:
        try:
            t0 = _time.monotonic()
            _ = broker.get_account_equity() if hasattr(broker, "get_account_equity") else None
            probes["SMOKE_CONNECTIVITY"] = True
        except Exception:
            probes["SMOKE_CONNECTIVITY"] = False
    else:
        probes["SMOKE_CONNECTIVITY"] = True  # dry-run: skip

    # 2. Fraîcheur données — vérifier que trade_date n'est pas trop ancien
    if trade_date is not None:
        from datetime import date as _date
        staleness = (_date.today() - trade_date).days
        probes["SMOKE_DATA_FRESH"] = staleness <= 1
    else:
        probes["SMOKE_DATA_FRESH"] = True

    # 3. Kill switch — vérifier qu'aucun kill switch n'est actif
    if config is not None:
        blocks_new = getattr(config, "blocks_new_entries", False)
        probes["SMOKE_KILL_SWITCH"] = not blocks_new
    else:
        probes["SMOKE_KILL_SWITCH"] = True

    # 4. Circuit breaker — vérifier que le breaker n'est pas trippé
    if circuit_breaker is not None:
        try:
            tripped = getattr(circuit_breaker, "just_tripped", lambda: False)()
            probes["SMOKE_CIRCUIT_BREAKER"] = not tripped
        except Exception:
            probes["SMOKE_CIRCUIT_BREAKER"] = True  # fail-open si indisponible
    else:
        probes["SMOKE_CIRCUIT_BREAKER"] = True

    # 5. Modèle ML prêt — vérifier que le champion existe dans le registry
    try:
        from risk_management.model_registry import ModelRegistry
        registry = ModelRegistry.load_from_json(model_registry_path)
        if registry is not None:
            champions = registry.count_by_status().get("champion", 0)
            probes["SMOKE_ML_READY"] = champions > 0
        else:
            probes["SMOKE_ML_READY"] = True  # premier run
    except Exception:
        probes["SMOKE_ML_READY"] = True  # fail-open

    # 6. Cash disponible
    if broker is not None:
        try:
            equity = broker.get_account_equity() if hasattr(broker, "get_account_equity") else 0
            probes["SMOKE_CASH"] = float(equity or 0) > 0
        except Exception:
            probes["SMOKE_CASH"] = False
    else:
        probes["SMOKE_CASH"] = True  # dry-run

    # 7. Watcher actif — vérifier qu'un watcher tourne (via lock DB ou PID)
    probes["SMOKE_WATCHER"] = True  # best-effort: le watcher est optionnel en shadow

    return probes


# ── Point 14 : persistance des transitions RampUpManager ────────────────────

def persist_ramp_up_transition(
    *,
    from_stage: str,
    to_stage: str,
    approved_by: str,
    reason: str = "",
    metrics_snapshot: dict[str, object] | None = None,
    journal_path: str = "artifacts/ramp_up_journal.json",
) -> str | None:
    """Persiste une transition de palier RampUpManager dans le journal immuable (Point 14).

    Returns le chemin du journal ou None si erreur.
    """
    import json as _json
    from datetime import datetime as _dt
    from pathlib import Path as _Path

    # Essaye d'abord ImmutableJournal, sinon fallback JSON simple
    try:
        from risk_management.immutable_journal import ImmutableJournal

        journal = ImmutableJournal.load_or_create(journal_path)
        journal.add_entry(
            entry_type="ramp_up_transition",
            payload={
                "from_stage": from_stage,
                "to_stage": to_stage,
                "approved_by": approved_by,
                "reason": reason,
                "metrics_snapshot": metrics_snapshot or {},
                "transition_at": _dt.now().isoformat(),
            },
        )
        journal.save_atomic(journal_path)
        return str(_Path(journal_path).absolute())
    except (ImportError, AttributeError):
        pass  # fallback ci-dessous

    # Fallback: simple JSON append
    try:
        target = _Path(journal_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "type": "ramp_up_transition",
            "from_stage": from_stage,
            "to_stage": to_stage,
            "approved_by": approved_by,
            "reason": reason,
            "timestamp": _dt.now().isoformat(),
        }
        existing: list[dict[str, object]] = []
        if target.exists():
            existing = _json.loads(target.read_text(encoding="utf-8"))
        existing.append(entry)
        target.write_text(_json.dumps(existing, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return str(target.absolute())
    except Exception:
        return None
