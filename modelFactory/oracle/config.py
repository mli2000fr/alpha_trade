"""modelFactory/oracle/config.py — Configuration dédiée à la couche Oracle.

Ne touche **pas** ``TrainingConfig`` (B25 reste intouchable). Cette config pilote
uniquement la couche Oracle (labels, modèle Extreme, combinaison).

Le modèle Oracle Extreme (ex-« Oracle TOP ») apprend la **détection d'extrêmes** :
``oracle_extreme10 = oracle_top10 OR oracle_bottom10`` (gros mouvement H20),
PAS la direction (E0/D0/D1/D1d l'ont établi). L'ancien modèle Oracle BOTTOM
est supprimé (redondant avec TOP, cf. E0b).

Les valeurs par défaut reflètent les décisions actées (2026-08-18) :
- horizon canonique **H20** ;
- target **brut cross-sectionnel** (``raw_target=True``) ;
- ``top_pct`` 0.10 (~40 titres / ~399).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_HORIZON = 20
DEFAULT_TOP_PCT = 0.10
_CONFIG_PATH = Path("config.yaml")


@dataclass(frozen=True, slots=True)
class OracleConfig:
    """Paramètres de la couche Oracle (labels + modèles)."""

    horizon: int = DEFAULT_HORIZON
    top_pct: float = DEFAULT_TOP_PCT
    raw_target: bool = True           # brut d'abord ; False = target neutralisé (ablation)
    batch_id: str | None = None       # override ; sinon batch_diagnostics.backtest_batch_id
    available_date_offset_days: int = 1  # oracle_available_date = exit + N jours ouvrés


def load_oracle_config(path: Path | str = _CONFIG_PATH) -> OracleConfig:
    """Lit la section ``oracle:`` de config.yaml (absente → défauts)."""
    raw: dict = {}
    try:
        import yaml

        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except Exception:
        raw = {}
    section = raw.get("oracle") or {}

    def _int(key: str, default: int) -> int:
        try:
            return int(section.get(key, default))
        except (TypeError, ValueError):
            return default

    def _float(key: str, default: float) -> float:
        try:
            return float(section.get(key, default))
        except (TypeError, ValueError):
            return default

    def _bool(key: str, default: bool) -> bool:
        value = section.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    return OracleConfig(
        horizon=_int("horizon", DEFAULT_HORIZON),
        top_pct=_float("top_pct", DEFAULT_TOP_PCT),
        raw_target=_bool("raw_target", True),
        batch_id=str(section.get("batch_id") or "").strip() or None,
        available_date_offset_days=_int("available_date_offset_days", 1),
    )


def load_backtest_batch_id(path: Path | str = _CONFIG_PATH) -> str | None:
    """Lit ``batch_diagnostics.backtest_batch_id`` (batch B25 de référence)."""
    try:
        import yaml

        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        bid = str((raw.get("batch_diagnostics") or {}).get("backtest_batch_id") or "").strip()
        return bid or None
    except Exception:
        return None


def resolve_oracle_batch_id(path: Path | str = _CONFIG_PATH) -> str | None:
    """Batch_id du Global Model utilisé pour construire les labels Oracle.

    Priorité : ``oracle.batch_id`` (config.yaml) puis ``batch_diagnostics.backtest_batch_id``.
    """
    cfg = load_oracle_config(path)
    return cfg.batch_id or load_backtest_batch_id(path)
