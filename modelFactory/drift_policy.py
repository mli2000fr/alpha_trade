"""Sprint S4 (A-021) — Policy gate ML adossé au drift monitor.

Décide, à partir d'un :class:`modelFactory.drift_monitor.DriftReport`, si le
flux de prédictions ML doit être **désactivé automatiquement** (kill switch)
avant consommation par ``risk_management``.

Convention :

- ``DriftReport.status == "ALERT"``   →  gate ``disabled`` / action
  ``kill_switch_ml`` (par défaut).
- ``DriftReport.status == "WARN"``    →  gate ``enabled`` (grâce
  configurable) ; logger ``WARNING``.
- ``DriftReport.status == "OK"``      →  gate ``enabled``.

Le résultat est exposé :

- dans ``run_summary`` ML (champs ``ml_kill_switch_active``,
  ``ml_drift_status``, ``ml_drift_ks_pvalue``, ``ml_drift_psi``,
  ``ml_kill_switch_reason``) ;
- dans ``ml_drift_runs.payload.gate_action`` (rétro-compat : aucune nouvelle
  table — on enrichit le JSON existant).

La propagation effective côté ``risk_management`` est assurée via
:mod:`risk_management.ml_gate` (Sprint S8 livré) : si la dernière décision
``drift_policy_decision`` porte ``gate=disabled`` ou
``gate_action=kill_switch_ml``, :func:`risk_management.db_io.RiskRepository.load_predictions_asof`
retourne ``{}`` et le scoring retombe sur le quant pur.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from modelFactory.drift_monitor import DriftReport

LOGGER = logging.getLogger(__name__)

DEFAULT_KILL_STATUSES: tuple[str, ...] = ("ALERT",)


@dataclass(frozen=True, slots=True)
class MLPolicyDecision:
    """Décision de gate ML produite après évaluation drift."""

    model_id: str
    drift_status: str  # OK | WARN | ALERT | n/a
    gate: str          # enabled | disabled
    action: str        # allow | kill_switch_ml
    reason: str
    ks_pvalue: float | None
    psi: float | None
    n_samples: int
    n_baseline: int
    computed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_drift_gate(
    report: DriftReport | None,
    *,
    kill_on: tuple[str, ...] = DEFAULT_KILL_STATUSES,
    warn_grace: bool = True,
) -> MLPolicyDecision:
    """Décide gate/kill switch ML à partir d'un :class:`DriftReport`.

    Parameters
    ----------
    report:
        Sortie de :func:`modelFactory.drift_monitor.compute_drift`. ``None``
        ou rapport sans données suffisantes → gate ``enabled`` (échantillon
        trop faible n'est pas une dérive).
    kill_on:
        Statuts qui déclenchent le kill switch. Par défaut ``("ALERT",)``.
        Ajouter ``"WARN"`` pour durcir.
    warn_grace:
        Si ``True``, ``WARN`` ne déclenche pas le kill switch (juste log).
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if report is None:
        return MLPolicyDecision(
            model_id="n/a",
            drift_status="n/a",
            gate="enabled",
            action="allow",
            reason="no_drift_report_available",
            ks_pvalue=None,
            psi=None,
            n_samples=0,
            n_baseline=0,
            computed_at=now,
        )

    status = report.status
    if "sample_size_too_small" in (report.notes or []):
        return MLPolicyDecision(
            model_id=report.model_id,
            drift_status=status,
            gate="enabled",
            action="allow",
            reason="sample_size_too_small",
            ks_pvalue=report.ks_pvalue,
            psi=report.psi,
            n_samples=report.n_samples,
            n_baseline=report.n_baseline,
            computed_at=now,
        )

    if status in kill_on and not (status == "WARN" and warn_grace):
        decision = MLPolicyDecision(
            model_id=report.model_id,
            drift_status=status,
            gate="disabled",
            action="kill_switch_ml",
            reason=f"drift_status={status} ks_p={report.ks_pvalue} psi={report.psi}",
            ks_pvalue=report.ks_pvalue,
            psi=report.psi,
            n_samples=report.n_samples,
            n_baseline=report.n_baseline,
            computed_at=now,
        )
        LOGGER.warning(
            "ML kill switch ACTIVATED model_id=%s status=%s ks_pvalue=%s psi=%s",
            report.model_id, status, report.ks_pvalue, report.psi,
        )
        # Métrique Prometheus
        try:
            from service.prometheus_metrics import set_model_drift_active
            set_model_drift_active(True)
        except Exception:
            pass
        # Alerte système multi-canal
        try:
            from service.alerting import send_system_alert
            send_system_alert(
                event="ML_MODEL_DRIFT_KILL_SWITCH",
                payload={
                    "model_id": report.model_id,
                    "drift_status": status,
                    "ks_pvalue": report.ks_pvalue,
                    "psi": report.psi,
                    "n_samples": report.n_samples,
                    "n_baseline": report.n_baseline,
                    "reason": decision.reason,
                },
                severity="critical",
            )
        except Exception:
            LOGGER.debug("Alerte ML drift indisponible.", exc_info=True)
        return decision

    if status == "WARN":
        LOGGER.warning(
            "ML drift WARN (grace) model_id=%s ks_pvalue=%s psi=%s",
            report.model_id, report.ks_pvalue, report.psi,
        )
        # Alerte précoce : drift en warning
        try:
            from service.alerting import send_system_alert
            send_system_alert(
                event="ML_MODEL_DRIFT_WARNING",
                payload={
                    "model_id": report.model_id,
                    "drift_status": status,
                    "ks_pvalue": report.ks_pvalue,
                    "psi": report.psi,
                    "n_samples": report.n_samples,
                    "n_baseline": report.n_baseline,
                },
                severity="warning",
            )
        except Exception:
            LOGGER.debug("Alerte ML drift warning indisponible.", exc_info=True)

    return MLPolicyDecision(
        model_id=report.model_id,
        drift_status=status,
        gate="enabled",
        action="allow",
        reason=f"drift_status={status}",
        ks_pvalue=report.ks_pvalue,
        psi=report.psi,
        n_samples=report.n_samples,
        n_baseline=report.n_baseline,
        computed_at=now,
    )


def apply_kill_switch(
    decision: MLPolicyDecision,
    predictions_df: pd.DataFrame,
    *,
    proba_columns: tuple[str, ...] = ("predicted_proba", "raw_proba"),
) -> pd.DataFrame:
    """Annote / neutralise un DataFrame de prédictions selon ``decision``.

    Si ``decision.action == "kill_switch_ml"`` :
    - ajoute la colonne ``ml_disabled = True``
    - met à ``None`` les colonnes ``proba_columns`` présentes
    - logge un ``WARNING`` structuré

    Sinon, ajoute simplement ``ml_disabled = False``.
    """
    df = predictions_df.copy()
    if decision.action == "kill_switch_ml":
        df["ml_disabled"] = True
        for col in proba_columns:
            if col in df.columns:
                df[col] = None
        LOGGER.warning(
            "kill_switch_ml applied rows=%s reason=%s", len(df), decision.reason,
        )
    else:
        df["ml_disabled"] = False
    return df


def persist_kill_switch_event(decision: MLPolicyDecision, *, engine: Any) -> None:
    """Enrichit le dernier ``ml_drift_runs`` avec la décision (best-effort).

    Mécanisme : on insère un nouvel enregistrement ``ml_drift_runs`` *audit*
    avec ``status = decision.drift_status`` et ``payload`` contenant
    ``gate_action``. Reste rétro-compatible (pas de nouvelle table).
    """
    from sqlalchemy import text

    payload = {
        "schema_version": 1,
        "kind": "drift_policy_decision",
        "decision": decision.to_dict(),
        "gate_action": decision.action,
    }
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO ml_drift_runs
                        (run_id, computed_at, model_id, ks_stat, ks_pvalue, psi,
                         n_samples, n_baseline, status, payload, schema_version)
                    VALUES
                        (:run_id, :computed_at, :model_id, NULL, :ks_pvalue, :psi,
                         :n_samples, :n_baseline, :status, :payload, 1)
                    """
                ),
                {
                    "run_id": f"mdr-policy-{int(datetime.now(timezone.utc).timestamp())}",
                    "computed_at": datetime.now(timezone.utc),
                    "model_id": decision.model_id,
                    "ks_pvalue": decision.ks_pvalue,
                    "psi": decision.psi,
                    "n_samples": decision.n_samples,
                    "n_baseline": decision.n_baseline,
                    "status": decision.drift_status,
                    "payload": json.dumps(payload),
                },
            )
    except Exception as exc:  # pragma: no cover - best effort
        LOGGER.warning("persist_kill_switch_event failed: %s", exc)


def summary_fields(decision: MLPolicyDecision | None) -> dict[str, Any]:
    """Retourne les 5 champs à injecter dans ``run_summary`` ML."""
    if decision is None:
        return {
            "ml_drift_status": "n/a",
            "ml_kill_switch_active": False,
            "ml_kill_switch_reason": None,
            "ml_drift_ks_pvalue": None,
            "ml_drift_psi": None,
        }
    return {
        "ml_drift_status": decision.drift_status,
        "ml_kill_switch_active": decision.action == "kill_switch_ml",
        "ml_kill_switch_reason": decision.reason if decision.action == "kill_switch_ml" else None,
        "ml_drift_ks_pvalue": decision.ks_pvalue,
        "ml_drift_psi": decision.psi,
    }


__all__ = [
    "MLPolicyDecision",
    "evaluate_drift_gate",
    "apply_kill_switch",
    "persist_kill_switch_event",
    "summary_fields",
    "DEFAULT_KILL_STATUSES",
]

