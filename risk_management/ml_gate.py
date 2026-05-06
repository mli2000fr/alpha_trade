"""Sprint S8 (A-021 finalisation) — Propagation kill-switch ML côté risk.

Le module :mod:`modelFactory.drift_policy` calcule une :class:`MLPolicyDecision`
et la persiste dans la table ``ml_drift_runs`` (champ ``payload`` au format
JSON, ``payload.kind == "drift_policy_decision"``). Ce module fournit la
**lecture** côté risk : on charge la dernière décision et on en déduit si la
consommation de ``model_predictions`` doit être ignorée.

Combinaison avec :mod:`core.feature_flags` :
    Si ``FeatureFlags.disable_ml`` est ``True`` (CLI ``--disable-ml``),
    le ML est ignoré sans même interroger ``ml_drift_runs``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from core.feature_flags import is_ml_disabled

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MlGateState:
    """État du gate ML résultant de la dernière décision drift."""

    enabled: bool
    reason: str
    decision_id: Optional[str] = None
    drift_status: Optional[str] = None
    action: Optional[str] = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "ml_gate_enabled": bool(self.enabled),
            "ml_gate_reason": self.reason,
            "ml_gate_decision_id": self.decision_id,
            "ml_gate_drift_status": self.drift_status,
            "ml_gate_action": self.action,
        }


def load_latest_ml_gate_decision(engine: Any) -> Optional[dict]:
    """Charge le dernier ``payload`` ``drift_policy_decision`` (ou None)."""
    if engine is None:
        return None
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT run_id, status, payload
                    FROM ml_drift_runs
                    ORDER BY computed_at DESC
                    LIMIT 50
                    """
                )
            ).mappings().all()
    except Exception as exc:  # pragma: no cover - best effort
        LOGGER.warning("[ml_gate] lecture ml_drift_runs impossible: %s", exc)
        return None

    for r in row:
        raw = r.get("payload")
        if raw is None:
            continue
        try:
            payload = json.loads(raw) if isinstance(raw, (str, bytes)) else dict(raw)
        except (TypeError, ValueError):
            continue
        if str(payload.get("kind")) == "drift_policy_decision":
            payload.setdefault("run_id", r.get("run_id"))
            payload.setdefault("status", r.get("status"))
            return payload
    return None


def resolve_ml_gate_state(engine: Any) -> MlGateState:
    """Combine feature flag CLI + dernière décision drift en un état effectif.

    Ordre de priorité :

    1. ``FeatureFlags.disable_ml`` (kill manuel CLI/env).
    2. ``payload.gate_action == "kill_switch_ml"`` ou
       ``payload.decision.gate == "disabled"`` (kill drift automatique).
    3. Aucune décision en base → gate par défaut **enabled**
       (rétro-compatibilité).
    """
    if is_ml_disabled():
        return MlGateState(
            enabled=False,
            reason="feature_flag_disable_ml",
        )

    payload = load_latest_ml_gate_decision(engine)
    if payload is None:
        return MlGateState(enabled=True, reason="no_decision_default_enabled")

    decision = payload.get("decision") or {}
    gate = str(decision.get("gate") or "enabled").lower()
    action = str(payload.get("gate_action") or decision.get("action") or "allow")
    drift_status = decision.get("drift_status")
    decision_id = payload.get("run_id")

    if gate == "disabled" or action == "kill_switch_ml":
        return MlGateState(
            enabled=False,
            reason="drift_policy_kill_switch",
            decision_id=decision_id,
            drift_status=drift_status,
            action=action,
        )
    return MlGateState(
        enabled=True,
        reason="drift_policy_enabled",
        decision_id=decision_id,
        drift_status=drift_status,
        action=action,
    )


__all__ = [
    "MlGateState",
    "load_latest_ml_gate_decision",
    "resolve_ml_gate_state",
]

