"""Contrat léger des artefacts Oracle utilisable par le CLI et l'IHM."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _positive_horizon(value: Any) -> int | None:
    try:
        horizon = int(value)
    except (TypeError, ValueError):
        return None
    return horizon if horizon > 0 else None


def resolve_oracle_artifact_horizon(
    batch_id: str | None,
    artifacts_root: Path | str = Path("artifacts/models"),
) -> int | None:
    """Retourne l'horizon Oracle déclaré par les artefacts du batch.

    ``None`` signifie que le batch ne possède pas de contrat Oracle identifiable.
    Un ancien batch Oracle avec champions mais sans profil explicite conserve H20.
    """
    normalized = str(batch_id or "").strip()
    if not normalized:
        return None
    root = Path(artifacts_root)
    batch_root = root if root.name == normalized else root / normalized
    candidates = (
        batch_root / "oracle" / "feature_profile.json",
        root / "oracle" / "champions" / normalized / "feature_profile.json",
        Path("artifacts/models/oracle/champions") / normalized / "feature_profile.json",
    )
    for profile_path in candidates:
        if not profile_path.is_file():
            continue
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        horizon = _positive_horizon(profile.get("oracle_horizon"))
        if horizon is not None:
            return horizon

    manifest_path = batch_root / "cascade_manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            oracle = manifest.get("oracle") or {}
            result = oracle.get("result") or {}
            profile = result.get("feature_profile") or {}
            for value in (
                result.get("horizon"),
                profile.get("oracle_horizon"),
                oracle.get("horizon"),
            ):
                horizon = _positive_horizon(value)
                if horizon is not None:
                    return horizon
        except (OSError, ValueError, TypeError):
            pass

    legacy_champions = (
        root / "oracle" / "champions" / normalized / "oracle_champions.json",
        Path("artifacts/models/oracle/champions") / normalized / "oracle_champions.json",
    )
    if any(path.is_file() for path in legacy_champions):
        return 20
    return None


def oracle_horizon_badge(
    batch_id: str | None,
    artifacts_root: Path | str = Path("artifacts/models"),
) -> str:
    """Badge court destiné aux libellés IHM, vide pour un batch sans Oracle."""
    horizon = resolve_oracle_artifact_horizon(batch_id, artifacts_root)
    return f"H{horizon}" if horizon is not None else ""
