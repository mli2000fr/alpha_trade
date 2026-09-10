"""Contrat léger de résolution automatique des bundles de cascade ML."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DIRECTIONAL_BUNDLE_TYPE = "oracle_extreme_plus_per_symbol_directional"


def load_serving_directional_bundle_manifest(
    artifacts_dir: Path | str,
    batch_id: str | None,
) -> dict[str, Any] | None:
    """Charge un manifeste directionnel terminé et explicitement servable."""
    normalized = str(batch_id or "").strip()
    if not normalized or Path(normalized).name != normalized:
        return None
    root = Path(artifacts_dir)
    candidates = [root / normalized, root]
    for candidate in candidates:
        path = candidate / "cascade_manifest.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        oracle = payload.get("oracle") or {}
        coverage = payload.get("coverage") or {}
        if (
            payload.get("cascade_type") == DIRECTIONAL_BUNDLE_TYPE
            and payload.get("status") == "completed"
            and payload.get("serving_ready") is True
            and oracle.get("status") == "completed"
            and int(coverage.get("paired_symbols") or 0) > 0
        ):
            return payload
    return None


def infer_oracle_only_cascade_mode(
    artifacts_dir: Path | str,
    batch_id: str | None,
    *,
    oracle_rows: int,
    global_rank_rows: int,
) -> str | None:
    """Résout le mode implicite d'un batch sans rang global.

    Un bundle directionnel servable doit utiliser les deux branches Per-Symbol.
    Un ancien batch Oracle sans manifeste conserve le mode LONG-only historique.
    """
    if oracle_rows <= 0 or global_rank_rows > 0:
        return None
    if load_serving_directional_bundle_manifest(artifacts_dir, batch_id):
        return "extreme_gate_directional"
    return "extreme_gate"
