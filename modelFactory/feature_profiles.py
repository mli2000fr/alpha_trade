"""Profils de features directionnels LONG/SHORT.

Les profils sont des contrats versionnés et immuables pendant un batch. Ils
remplacent les cases de features manuelles uniquement pour les branches
Per-Symbol ; l'Oracle Extreme conserve son propre contrat.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal

from modelFactory.config import TrainingConfig

Direction = Literal["oracle", "long", "short"]
PROFILE_ROOT = Path("config/features")


def profile_directory(direction: Direction, root: Path = PROFILE_ROOT) -> Path:
    return root / direction


def discover_feature_profiles(direction: Direction, root: Path = PROFILE_ROOT) -> list[str]:
    """Retourne les noms JSON disponibles, triés, sans accepter de sous-chemin."""
    directory = profile_directory(direction, root)
    if not directory.is_dir():
        return []
    return sorted(path.name for path in directory.glob("*.json") if path.is_file())


def resolve_profile_path(direction: Direction, name: str, root: Path = PROFILE_ROOT) -> Path:
    """Résout un nom de profil dans son répertoire et bloque la traversée."""
    clean_name = Path(str(name).strip()).name
    if not clean_name or clean_name != str(name).strip() or not clean_name.lower().endswith(".json"):
        raise ValueError(f"Nom de profil {direction} invalide: {name!r}")
    directory = profile_directory(direction, root).resolve()
    path = (directory / clean_name).resolve()
    if path.parent != directory or not path.is_file():
        raise FileNotFoundError(f"Profil {direction} introuvable: {path}")
    return path


def load_feature_profile(direction: Direction, name: str, root: Path = PROFILE_ROOT) -> dict[str, Any]:
    path = resolve_profile_path(direction, name, root)
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Profil {path} invalide: objet JSON attendu.")
    if int(data.get("schema_version", 0)) != 1:
        raise ValueError(f"Profil {path} invalide: schema_version=1 attendu.")
    if str(data.get("direction", "")).lower() != direction:
        raise ValueError(f"Profil {path} invalide: direction={direction!r} attendue.")
    columns = data.get("feature_columns")
    if not isinstance(columns, list) or not columns or any(not isinstance(v, str) or not v.strip() for v in columns):
        raise ValueError(f"Profil {path} invalide: feature_columns non vide attendue.")
    if len(columns) != len(set(columns)):
        raise ValueError(f"Profil {path} invalide: feature_columns contient des doublons.")
    options = data.get("generator_options", {})
    if not isinstance(options, dict):
        raise ValueError(f"Profil {path} invalide: generator_options doit être un objet.")
    return {**data, "profile_file": path.name, "profile_path": str(path), "sha256": sha256(raw).hexdigest()}


def apply_feature_profile(cfg: TrainingConfig, profile: dict[str, Any], direction: Direction) -> TrainingConfig:
    """Produit la configuration effective d'une branche directionnelle."""
    options = profile.get("generator_options", {})
    columns = tuple(str(v) for v in profile["feature_columns"])
    data = replace(
        cfg.data,
        feature_set=str(profile.get("feature_set", "expert")),
        feature_whitelist_enabled=True,
        feature_whitelist=columns,
        force_v1_lstm=False,
        include_sentiment_features=bool(options.get("include_sentiment", False)),
        include_screener_scores=bool(options.get("include_screener_scores", False)),
        include_short_score_features=bool(options.get("include_short_score", False)),
        include_macro_vix_features=bool(options.get("include_macro_vix", False)),
        include_macro_vxn_features=bool(options.get("include_macro_vxn", False)),
        include_macro_vix3m_features=bool(options.get("include_macro_vix3m", False)),
        include_macro_move_features=bool(options.get("include_macro_move", False)),
        include_fundamentals_features=bool(options.get("include_fundamentals", False)),
        include_factors_features=bool(options.get("include_factors", False)),
        include_macro_regime_features=bool(options.get("include_macro_regime", False)),
        include_score_components=False,
        include_volume_features=bool(options.get("include_volume_features", False)),
        enable_cross_sectional_features=bool(options.get("enable_cross_sectional", False)),
        include_directional_features=bool(options.get("include_directional_features", False)),
    )
    role = f"direction_{direction}"
    branch_root = Path(cfg.artifacts_dir) / "directions" / direction
    return replace(
        cfg,
        data=data,
        global_model=replace(
            cfg.global_model,
            stacking_enabled=bool(options.get("include_global_stacking", False)),
        ),
        artifacts_dir=branch_root,
        catboost_artifacts_dir=Path(cfg.catboost_artifacts_dir) / "directions" / direction,
        model_role=role,
    )
